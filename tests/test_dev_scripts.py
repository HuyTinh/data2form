import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import dev


ROOT = Path(__file__).resolve().parents[1]
DEV_SCRIPT = ROOT / "scripts" / "dev.py"


class LocalDevScriptTests(unittest.TestCase):
    def run_dev(self, command, state_dir, extra_env=None):
        env = os.environ.copy()
        env["DATA2FORM_STATE_DIR"] = str(state_dir)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(DEV_SCRIPT), command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_status_with_no_state_is_successful_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_dev("status", temp_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No Data2Form-managed services are recorded", result.stdout)
            self.assertFalse((Path(temp_dir) / "services.json").exists())

    def test_start_rejects_non_loopback_host_before_starting_services(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_dev("start", temp_dir, {"DATA2FORM_HOST": "0.0.0.0"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("DATA2FORM_HOST must be a loopback address", result.stderr)
            self.assertFalse((Path(temp_dir) / "services.json").exists())

    def test_stop_does_not_kill_a_pid_with_an_unrelated_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {"DATA2FORM_STATE_DIR": temp_dir}
            dev._write_state({
                "backend": {
                    "pid": os.getpid(),
                    "host": "127.0.0.1",
                    "port": 8000,
                    "command": ["python", "-m", "uvicorn", "app:app"],
                    "cwd": str(ROOT),
                    "started_at": 0,
                    "log": str(Path(temp_dir) / "backend.log"),
                }
            }, env)

            with patch.object(dev, "_process_command_line", return_value="python unrelated.py"), \
                 patch.object(dev, "_terminate_process_tree") as terminate:
                result = dev.stop_services(env)

            self.assertEqual(result, 0)
            terminate.assert_not_called()
            self.assertFalse((Path(temp_dir) / "services.json").exists())

    def test_stop_preserves_record_when_process_identity_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {"DATA2FORM_STATE_DIR": temp_dir}
            dev._write_state({
                "backend": {
                    "pid": os.getpid(),
                    "host": "127.0.0.1",
                    "port": 8000,
                    "command": ["python", "-m", "uvicorn", "app:app"],
                    "cwd": str(ROOT),
                    "started_at": 0,
                    "log": str(Path(temp_dir) / "backend.log"),
                }
            }, env)

            with patch.object(dev, "_process_command_line", return_value=None), \
                 patch.object(dev, "_terminate_process_tree") as terminate:
                result = dev.stop_services(env)

            self.assertEqual(result, 1)
            terminate.assert_not_called()
            self.assertTrue((Path(temp_dir) / "services.json").exists())

    def test_backend_command_binds_only_to_configured_loopback_and_project(self):
        command, working_dir = dev._command_for("backend", "127.0.0.1", 8123)

        self.assertEqual(working_dir, ROOT)
        self.assertIn("app:app", command)
        self.assertEqual(command[command.index("--app-dir") + 1], str(ROOT))
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--port") + 1], "8123")

    def test_python_resolution_uses_the_single_canonical_venv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canonical = root / "venv" / "Scripts" / "python.exe"
            duplicate = root / ".venv" / "Scripts" / "python.exe"
            canonical.parent.mkdir(parents=True)
            duplicate.parent.mkdir(parents=True)
            canonical.touch()
            duplicate.touch()

            with patch.object(dev, "ROOT_DIR", root):
                self.assertEqual(dev._python_executable(), str(canonical))

    def test_port_override_must_be_valid(self):
        self.assertEqual(dev._port_from_env({"DATA2FORM_BACKEND_PORT": "8123"}, "backend"), 8123)
        with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
            dev._port_from_env({"DATA2FORM_BACKEND_PORT": "70000"}, "backend")


if __name__ == "__main__":
    unittest.main()
