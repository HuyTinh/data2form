import ast
from pathlib import Path
import unittest
from unittest.mock import patch

import app
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]


class WebOnlyContractTests(unittest.TestCase):
    def test_direct_server_entrypoint_binds_only_to_loopback(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        hosts = [
            keyword.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "uvicorn"
            for keyword in node.keywords
            if keyword.arg == "host" and isinstance(keyword.value, ast.Constant)
        ]

        self.assertEqual(hosts, ["127.0.0.1"])

    def test_browser_contexts_keep_tls_certificate_validation_enabled(self):
        modules = (
            "automation_runtime.py",
            "single_form_runner.py",
            "mapping_plan_runner.py",
            "selector_picker.py",
        )
        overrides = []
        for module in modules:
            tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr not in {
                    "new_context",
                    "launch_persistent_context",
                }:
                    continue
                if any(keyword.arg == "ignore_https_errors" for keyword in node.keywords):
                    overrides.append(module)

        self.assertEqual(overrides, [])

    def test_web_automation_endpoints_remain_without_desktop_endpoints(self):
        routes = set()
        for route in app.app.routes:
            path = getattr(route, "path", None)
            if path:
                routes.add(path)

        self.assertIn("/api/run", routes)
        self.assertIn("/api/pick-selector", routes)
        self.assertFalse(
            {path for path in routes if path.startswith("/api/desktop/")}
        )

    def test_frontend_has_no_desktop_mode_or_window_picker(self):
        frontend_files = (
            ROOT / "frontend" / "src" / "App.tsx",
            ROOT / "frontend" / "src" / "pages" / "SetupPage.tsx",
            ROOT / "frontend" / "src" / "pages" / "MonitoringPage.tsx",
            ROOT / "frontend" / "src" / "pages" / "HistoryPage.tsx",
        )
        desktop_markers = (
            "/api/desktop/",
            "mode-desktop",
            "mode-switcher",
            "window-dropdown",
            "fetchWindows",
            "filterWindows",
        )

        for path in frontend_files:
            source = path.read_text(encoding="utf-8").lower()
            for marker in desktop_markers:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(
                        marker.lower(), source, f"{path.name} still contains {marker}"
                    )

    def test_legacy_static_frontend_files_are_removed(self):
        for filename in ("index.html", "script.js", "style.css"):
            with self.subTest(filename=filename):
                self.assertFalse((ROOT / "static" / filename).exists())

    def test_root_requires_the_react_build_instead_of_serving_legacy_static_html(self):
        with patch.object(app, "DIST_DIR", str(ROOT / "missing-frontend-build")):
            with self.assertRaises(HTTPException) as error:
                app.read_root()

        self.assertEqual(error.exception.status_code, 503)

    def test_windows_automation_module_and_dependencies_are_removed(self):
        self.assertFalse((ROOT / "main_desktop.py").exists())

        requirements = (ROOT / "requirements.txt").read_text(
            encoding="utf-8-sig"
        ).lower()
        for package in ("pywinauto", "pywin32", "comtypes"):
            with self.subTest(package=package):
                self.assertNotIn(
                    package, requirements, f"requirements.txt still includes {package}"
                )


if __name__ == "__main__":
    unittest.main()
