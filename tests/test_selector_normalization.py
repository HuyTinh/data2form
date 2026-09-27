import unittest
from unittest.mock import Mock
from unittest.mock import patch
import os
import main
import automation_runtime

from main import _PersistentPlaywrightSession, _click_after_action, _get_persistent_browser_context, _persistent_browser_contexts
from selector_utils import resolve_row_selector


class TestSelectorNormalization(unittest.TestCase):
    def test_generic_row_placeholder_resolves_to_one_based_row(self):
        self.assertEqual(
            resolve_row_selector("#orders tr:nth-of-type({row}) input", 2, True),
            "#orders tr:nth-of-type(2) input",
        )

    def test_single_form_keeps_row_placeholder_literal(self):
        self.assertEqual(
            resolve_row_selector("#orders tr:nth-of-type({row}) input", 2, False),
            "#orders tr:nth-of-type({row}) input",
        )

    def test_generic_helper_does_not_rewrite_selector_ids(self):
        self.assertEqual(resolve_row_selector("#item-473", 2, True), "#item-473")

    def test_placeholder_requires_positive_row_index(self):
        with self.assertRaisesRegex(ValueError, "positive one-based index"):
            resolve_row_selector("#orders tr:nth-of-type({row}) input", 0, True)

    def test_after_action_uses_user_selector_and_current_row(self):
        page = Mock()
        locator = Mock()
        locator.first = locator
        page.locator.return_value = locator

        _click_after_action(page, "#orders tr:nth-of-type({row}) button.save", True, 2)

        page.locator.assert_called_once_with("#orders tr:nth-of-type(2) button.save")
        locator.wait_for.assert_called_once_with(state="visible", timeout=10000)
        locator.click.assert_called_once_with(force=True, timeout=5000)

    @patch("automation_runtime.sync_playwright")
    def test_persistent_playwright_session_does_not_stop_browser_driver(self, playwright_factory):
        playwright = Mock()
        playwright_factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)
        with _PersistentPlaywrightSession() as active:
            self.assertIs(active, playwright)

        playwright.stop.assert_not_called()
        self.assertIs(automation_runtime._playwright_instance, playwright)

    def test_persistent_browser_context_is_reused_for_subsequent_runs(self):
        playwright = Mock()
        context = Mock()
        context.is_closed.return_value = False
        playwright.chromium.launch_persistent_context.return_value = context
        user_data_dir = os.path.abspath(".browser_session_test")
        _persistent_browser_contexts.pop(user_data_dir, None)
        self.addCleanup(_persistent_browser_contexts.pop, user_data_dir, None)

        first = _get_persistent_browser_context(playwright, user_data_dir)
        second = _get_persistent_browser_context(playwright, user_data_dir)

        self.assertIs(first, context)
        self.assertIs(second, context)
        playwright.chromium.launch_persistent_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
