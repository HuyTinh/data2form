"""Shared browser lifecycle and automation run status."""

from contextlib import AbstractContextManager
import logging
import os
import sys

from playwright.sync_api import sync_playwright

from selector_utils import resolve_row_selector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_playwright_instance = None
_persistent_browser_contexts = {}


class _PersistentPlaywrightSession(AbstractContextManager):
    def __enter__(self):
        global _playwright_instance
        if _playwright_instance is None:
            _playwright_instance = sync_playwright().start()
        self.playwright = _playwright_instance
        return self.playwright

    def __exit__(self, exc_type, exc_value, traceback):
        # Intentionally do not stop Playwright; stopping it closes its browser.
        return False


def _get_persistent_browser_context(playwright, user_data_dir):
    key = os.path.abspath(user_data_dir)
    context = _persistent_browser_contexts.get(key)
    if context is None or context.is_closed():
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=key,
            headless=False,
            no_viewport=True,
        )
        _persistent_browser_contexts[key] = context
    return context


def setup_encoding():
    """Ensure stdout supports UTF-8 for Vietnamese characters."""
    try:
        reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
        if reconfigure_stdout is not None:
            reconfigure_stdout(encoding="utf-8")
    except Exception:
        pass


def _click_after_action(page, selector, table_mode, row_index):
    resolved_selector = resolve_row_selector(selector, row_index, table_mode)
    after_el = page.locator(resolved_selector).first
    after_el.wait_for(state="visible", timeout=10000)
    after_el.scroll_into_view_if_needed()
    after_el.click(force=True, timeout=5000)


class AutomationStatus:
    def __init__(self):
        self.is_running = False
        self.current_row = 0
        self.total_rows = 0
        self.logs = []
        self.screenshots = []
        self.has_errors = False
        self.row_results = []
        self.detail_results = []

    def log(self, message, level="info"):
        if level in ("error", "warning"):
            self.has_errors = True
        import datetime

        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append({
            "time": now_time,
            "message": message,
            "msg": message,
            "level": level,
        })
        logger.info(message)
