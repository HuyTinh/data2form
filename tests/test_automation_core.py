import unittest
import os
import tempfile
from unittest.mock import Mock, patch

import pandas as pd
import automation_runtime
import main
import single_form_runner
from main import AutomationStatus, run_automation_core


class _FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector
        self.first = self
        self.value = ""

    def wait_for(self, state, timeout):
        if state == "visible" and self.selector in {"#missing", "#hidden-file"}:
            raise TimeoutError("mapped field is not visible")

    def evaluate(self, _script):
        if "matches('input[type=file]')" in _script:
            return self.selector == "#hidden-file"
        if "files ? node.files.length" in _script:
            return 1 if self.value else 0
        return "text"

    def scroll_into_view_if_needed(self):
        return None

    def fill(self, value):
        self.value = value

    def input_value(self):
        return self.value

    def set_input_files(self, path):
        self.value = path

    def click(self, **kwargs):
        self.page.clicked.append(self.selector)


class _FakePage:
    def __init__(self, goto_error=None):
        self.clicked = []
        self.selectors = []
        self.locators_created = []
        self.goto_error = goto_error

    def goto(self, *args, **kwargs):
        if self.goto_error:
            raise self.goto_error
        return None

    def wait_for_timeout(self, *_args):
        return None

    def locator(self, selector):
        self.selectors.append(selector)
        locator = _FakeLocator(self, selector)
        self.locators_created.append(locator)
        return locator


class AutomationCoreTests(unittest.TestCase):
    @patch("automation_runtime.sync_playwright")
    @patch("single_form_runner.pd.read_excel")
    def test_click_action_is_skipped_when_a_field_failed(self, read_excel, playwright_factory):
        read_excel.return_value = pd.DataFrame([{"Name": "Ada"}])
        page = _FakePage()
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.new_context.return_value = context
        playwright = Mock()
        playwright.chromium.launch.return_value = browser
        playwright_factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)

        status = AutomationStatus()
        mappings = {
            "Name": {"selector": "#missing", "type": "text"},
            "__click__": {"selector": "#save", "type": "click"},
        }
        run_automation_core("unused.xlsx", "http://example.test/form", mappings, "", status)

        self.assertEqual(status.row_results[0]["status"], "failed")
        self.assertEqual(status.row_results[0]["errors"][0]["message"], "Field is not visible")
        self.assertNotIn("#save", page.selectors)
        self.assertNotIn("#save", page.clicked)

    @patch("automation_runtime.sync_playwright")
    @patch("single_form_runner.pd.read_excel")
    def test_numeric_zero_is_filled_instead_of_skipped(self, read_excel, playwright_factory):
        read_excel.return_value = pd.DataFrame([{"Quantity": 0}])
        page = _FakePage()
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.new_context.return_value = context
        playwright = Mock()
        playwright.chromium.launch.return_value = browser
        playwright_factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)

        status = AutomationStatus()
        mappings = {"Quantity": {"selector": "#quantity", "type": "number"}}
        run_automation_core("unused.xlsx", "http://example.test/form", mappings, "", status)

        self.assertEqual(status.row_results[0]["status"], "completed")
        quantity_locator = next(locator for locator in page.locators_created if locator.selector == "#quantity")
        self.assertEqual(quantity_locator.value, "0")
        context.close.assert_not_called()
        browser.close.assert_not_called()

    @patch("automation_runtime.sync_playwright")
    @patch("single_form_runner.pd.read_excel")
    def test_hidden_file_input_is_uploaded_without_visibility_requirement(self, read_excel, playwright_factory):
        scratch = os.environ.get("TMPDIR") or os.getcwd()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", dir=scratch, delete=False) as file:
            file.write("fixture")
            upload_path = file.name
        self.addCleanup(os.unlink, upload_path)
        read_excel.return_value = pd.DataFrame([{"Attachment": upload_path}])
        page = _FakePage()
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.new_context.return_value = context
        playwright = Mock()
        playwright.chromium.launch.return_value = browser
        playwright_factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)

        status = AutomationStatus()
        mappings = {"Attachment": {"selector": "#hidden-file", "type": "upload"}}
        run_automation_core("unused.xlsx", "http://example.test/form", mappings, "", status)

        self.assertEqual(status.row_results[0]["status"], "completed")
        upload_locator = next(locator for locator in page.locators_created if locator.selector == "#hidden-file")
        self.assertEqual(upload_locator.value, upload_path)

    @patch("automation_runtime.sync_playwright")
    @patch("single_form_runner.pd.read_excel")
    def test_browser_is_left_open_when_navigation_fails(self, read_excel, playwright_factory):
        read_excel.return_value = pd.DataFrame([{"Name": "Ada"}])
        page = _FakePage(goto_error=RuntimeError("navigation failed"))
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.new_context.return_value = context
        playwright = Mock()
        playwright.chromium.launch.return_value = browser
        playwright_factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)

        with self.assertRaisesRegex(RuntimeError, "navigation failed"):
            run_automation_core(
                "unused.xlsx",
                "http://example.test/form",
                {"Name": {"selector": "#name", "type": "text"}},
                "",
                AutomationStatus(),
            )

        context.close.assert_not_called()
        browser.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
