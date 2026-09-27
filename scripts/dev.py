"""Cross-platform local backend/frontend process manager."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICE_DEFINITIONS = {
    "backend": {"port_env": "DATA2FORM_BACKEND_PORT", "default_port": 8000, "path": "/api/status"},
    "frontend": {"port_env": "DATA2FORM_FRONTEND_PORT", "default_port": 5173, "path": "/"},
}
READY_TIMEOUT = 30


def validate_host(host: str) -> str:
    """Only accept loopback addresses; this app has no remote-access auth."""
    normalized = host.strip().lower()
    if normalized == "localhost":
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError("DATA2FORM_HOST must be a loopback address") from exc
    if not address.is_loopback:
        raise ValueError("DATA2FORM_HOST must be a loopback address")
    return normalized


def _port_from_env(env: dict[str, str], service: str) -> int:
    definition = SERVICE_DEFINITIONS[service]
    value = env.get(definition["port_env"], str(definition["default_port"]))
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"{definition['port_env']} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{definition['port_env']} must be between 1 and 65535")
    return port


def state_directory(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get("DATA2FORM_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Data2Form" / "state"
    base = Path(env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "data2form"


def _state_file(env: Mapping[str, str] | None = None) -> Path:
    return state_directory(env) / "services.json"


def _read_state(env: dict[str, str] | None = None) -> dict[str, dict]:
    path = _state_file(env)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read Data2Form process state at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid Data2Form process state at {path}")
    return data


def _write_state(state: dict[str, dict], env: dict[str, str] | None = None) -> None:
    path = _state_file(env)
    if not state:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(state, stream, indent=2)
        stream.write("\n")
        temporary_path = Path(stream.name)
    os.replace(temporary_path, path)


def _python_executable() -> str:
    candidates = (
        ROOT_DIR / "venv" / "Scripts" / "python.exe",
        ROOT_DIR / "venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _service_url(host: str, port: int, path: str) -> str:
    url_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{url_host}:{port}{path}"


def _http_ready(url: str) -> bool:
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(url, timeout=1) as response:
            return 200 <= response.status < 400
    except (OSError, URLError, TimeoutError):
        return False


def _wait_ready(url: str, process: subprocess.Popen | None = None, timeout: int = READY_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _http_ready(url):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(1)
    return False


def _command_for(service: str, host: str, port: int) -> tuple[list[str], Path]:
    if service == "backend":
        return (
            [
                _python_executable(),
                "-m",
                "uvicorn",
                "app:app",
                "--app-dir",
                str(ROOT_DIR),
                "--host",
                host,
                "--port",
                str(port),
            ],
            ROOT_DIR,
        )

    frontend_dir = ROOT_DIR / "frontend"
    if not (frontend_dir / "node_modules").is_dir():
        raise RuntimeError("Frontend dependencies are missing. Run npm install in frontend/ first.")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise RuntimeError("npm was not found. Install Node.js/npm before starting the frontend.")
    command = [npm, "--prefix", str(frontend_dir), "run", "dev", "--", "--host", host, "--port", str(port)]
    if os.name == "nt" and Path(npm).suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline(command)
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]
    return command, frontend_dir


def _launch(service: str, command: list[str], working_dir: Path, host: str, port: int, env: dict[str, str]):
    run_dir = state_directory(env)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"{service}.log"
    creation_flags = 0
    popen_options = {}
    if os.name == "nt":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True

    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            command,
            cwd=working_dir,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=creation_flags,
            **popen_options,
        )
    record = {
        "pid": process.pid,
        "host": host,
        "port": port,
        "command": command,
        "cwd": str(working_dir),
        "started_at": time.time(),
        "log": str(log_path),
    }
    return process, record


def _process_command_line(pid: int) -> str | None:
    if os.name == "nt":
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            return None
        script = f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; if ($p) {{ [Console]::Write($p.CommandLine) }}"
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() or None

    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if proc_cmdline.is_file():
        try:
            return proc_cmdline.read_bytes().replace(b"\0", b" ").decode(errors="replace").strip() or None
        except OSError:
            return None
    try:
        result = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def _matches_service_process(service: str, record: dict, command_line: str | None = None) -> bool:
    if service not in SERVICE_DEFINITIONS:
        return False
    try:
        pid = int(record["pid"])
        port = int(record["port"])
        command = record["command"]
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(command, list) or not command:
        return False
    if not command_line:
        return False
    lowered = command_line.lower()
    port_arg = f"--port {port}"
    working_dir = str(record.get("cwd", "")).replace("\\", "/").rstrip("/").lower()
    if not working_dir or working_dir not in lowered.replace("\\", "/"):
        return False
    if service == "backend":
        executable = str(command[0]).lower()
        return executable in lowered and "uvicorn" in lowered and "app:app" in lowered and port_arg in lowered
    return ("npm" in lowered or "vite" in lowered) and "dev" in lowered and port_arg in lowered


def _record_match_status(service: str, record: dict) -> bool | None:
    """Return True/False for a verified match, or None when ownership is unverifiable."""
    try:
        pid = int(record["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    if not _process_running(pid):
        return False
    command_line = _process_command_line(pid)
    if command_line is None:
        return None
    return _matches_service_process(service, record, command_line)


def _process_running(pid: int) -> bool:
    if os.name == "nt":
        tasklist = shutil.which("tasklist.exe") or shutil.which("tasklist")
        if not tasklist:
            return True
        try:
            result = subprocess.run(
                [tasklist, "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return True
        return f'"{pid}"' in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _terminate_process_tree(pid: int) -> bool:
    if os.name == "nt":
        taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
        if not taskkill:
            return False
        subprocess.run([taskkill, "/F", "/T", "/PID", str(pid)], capture_output=True, text=True, timeout=10, check=False)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not _process_running(pid):
                return True
            time.sleep(0.2)
        return not _process_running(pid)

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not _process_running(pid):
            return True
        time.sleep(0.2)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if not _process_running(pid):
            return True
        time.sleep(0.2)
    return not _process_running(pid)


def _validate_configuration(env: dict[str, str]) -> tuple[str, dict[str, int]]:
    host = validate_host(env.get("DATA2FORM_HOST", "127.0.0.1"))
    ports = {name: _port_from_env(env, name) for name in SERVICE_DEFINITIONS}
    return host, ports


def start_services(env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    host, ports = _validate_configuration(env)
    state = _read_state(env)
    specifications = {
        name: {
            "url": _service_url(host, ports[name], definition["path"]),
            "port": ports[name],
        }
        for name, definition in SERVICE_DEFINITIONS.items()
    }

    for service, specification in specifications.items():
        url = specification["url"]
        if _http_ready(url):
            old_record = state.get(service)
            match = _record_match_status(service, old_record) if old_record else False
            if match is True and old_record is not None:
                print(f"{service.capitalize()} already responds at {url} (managed pid {old_record['pid']})")
            elif match is None:
                print(f"{service.capitalize()} responds at {url}; could not verify the recorded process owner, keeping its record.", file=sys.stderr)
            else:
                if old_record:
                    state.pop(service, None)
                    _write_state(state, env)
                print(f"{service.capitalize()} already responds at {url} (not managed by this script)")
            continue

        old_record = state.get(service)
        if old_record:
            match = _record_match_status(service, old_record)
            if match is True:
                if _wait_ready(url, timeout=READY_TIMEOUT):
                    print(f"{service.capitalize()} is ready at {url} (managed pid {old_record['pid']})")
                    continue
                print(f"{service.capitalize()} is recorded but not ready; see {old_record.get('log', 'its log file')}", file=sys.stderr)
                return 1
            if match is None:
                print(f"Cannot verify ownership of the recorded {service} PID; refusing to start a duplicate.", file=sys.stderr)
                return 1
        if old_record:
            state.pop(service, None)
            _write_state(state, env)

        command, working_dir = _command_for(service, host, specification["port"])
        process, record = _launch(service, command, working_dir, host, specification["port"], env)
        if not _wait_ready(url, process):
            _terminate_process_tree(process.pid)
            print(f"{service.capitalize()} did not become ready at {url}. Log: {record['log']}", file=sys.stderr)
            return 1
        state[service] = record
        _write_state(state, env)
        print(f"{service.capitalize()} started at {url} (pid {process.pid})")

    print(f"Local service state and logs: {state_directory(env)}")
    return 0


def stop_services(env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    state = _read_state(env)
    if not state:
        print("No Data2Form-managed services are recorded.")
        return 0

    remaining = dict(state)
    failures = []
    for service, record in state.items():
        if service not in SERVICE_DEFINITIONS:
            remaining.pop(service, None)
            print(f"Ignoring unknown service record '{service}'.", file=sys.stderr)
            continue
        try:
            pid = int(record["pid"])
        except (KeyError, TypeError, ValueError):
            remaining.pop(service, None)
            print(f"Ignoring invalid {service} process record.", file=sys.stderr)
            continue
        match = _record_match_status(service, record)
        if match is None:
            failures.append(service)
            print(f"Cannot inspect {service} PID {pid}; leaving its process record and not stopping it.", file=sys.stderr)
            continue
        if not match:
            remaining.pop(service, None)
            print(f"Not stopping stale/unmatched {service} PID {pid}; it is not verified as Data2Form-owned.", file=sys.stderr)
            continue
        if _terminate_process_tree(pid):
            remaining.pop(service, None)
            print(f"Stopped {service.capitalize()} (pid {pid})")
        else:
            failures.append(service)
            print(f"Could not verify that {service} PID {pid} stopped; process record retained.", file=sys.stderr)

    _write_state(remaining, env)
    return 1 if failures else 0


def show_status(env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    state = _read_state(env)
    if not state:
        print("No Data2Form-managed services are recorded.")
        return 0
    for service, record in state.items():
        match = _record_match_status(service, record)
        if match is None:
            print(f"{service.capitalize()}: process exists but ownership cannot be verified")
            continue
        if not match:
            print(f"{service.capitalize()}: stale or not verified as Data2Form-owned")
            continue
        host = record.get("host", "127.0.0.1")
        port = int(record["port"])
        path = SERVICE_DEFINITIONS.get(service, {}).get("path", "/")
        url = _service_url(host, port, path)
        state_text = "ready" if _http_ready(url) else "process running, endpoint not ready"
        print(f"{service.capitalize()}: {state_text} at {url} (pid {record['pid']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Data2Form's local development services.")
    parser.add_argument("command", choices=("start", "stop", "status"))
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            return start_services()
        if args.command == "stop":
            return stop_services()
        return show_status()
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
