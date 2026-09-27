import importlib
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

_database_dir = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or os.getcwd())
_original_connect = sqlite3.connect


def _connect_to_scratch(database, *args, **kwargs):
    if database == "automation.db":
        database = os.path.join(_database_dir.name, "automation.db")
    return _original_connect(database, *args, **kwargs)


sqlite3.connect = _connect_to_scratch
try:
    app_module = importlib.import_module("app")
finally:
    sqlite3.connect = _original_connect


class FakePage:
    def __init__(self, selectors):
        self.selectors = selectors
        self.script = None

    def goto(self, _url, **_kwargs):
        pass

    def evaluate(self, script):
        self.script = script
        return self.selectors


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.closed = False

    def new_context(self, **_kwargs):
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, **_kwargs):
        return self.browser


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


class MultiSelectorPickerTests(unittest.TestCase):
    def test_batch_picker_returns_all_selectors_from_one_browser_session(self):
        page = FakePage(["#warehouse", "input[name='barcode']"])
        context = FakeContext(page)
        browser = FakeBrowser(context)
        playwright = FakePlaywright(FakeChromium(browser))

        with patch("selector_picker.sync_playwright", return_value=playwright) as launcher:
            result = app_module.pick_selectors(
                app_module.PickSelectorsRequest(
                    url="https://example.test/form",
                    use_session=False,
                    target_count=2,
                    target_labels=["Location", "Barcode"],
                )
            )

        self.assertEqual(result, {"selectors": ["#warehouse", "input[name='barcode']"]})
        self.assertIsNotNone(page.script)
        self.assertIn('"label": "Location"', page.script or "")
        self.assertIn('"label": "Barcode"', page.script or "")
        self.assertIn("window.innerWidth <= 520", page.script or "")
        self.assertIn("pickerTitle.textContent = 'D2F Picker:'", page.script or "")
        self.assertNotIn("innerHTML", page.script or "")
        launcher.assert_called_once()
        self.assertTrue(context.closed)
        self.assertTrue(browser.closed)

    def test_batch_picker_requires_at_least_one_target(self):
        with self.assertRaises(ValueError):
            app_module.PickSelectorsRequest(
                url="https://example.test/form",
                target_count=0,
            )

    def test_batch_picker_returns_target_ids_when_fields_are_selected_out_of_order(self):
        selections = [
            {"target_id": "barcode", "label": "Barcode", "selector": "input[name='barcode']"},
            {"target_id": "location", "label": "Location", "selector": "#warehouse"},
        ]
        page = FakePage(selections)
        context = FakeContext(page)
        browser = FakeBrowser(context)
        playwright = FakePlaywright(FakeChromium(browser))

        with patch("selector_picker.sync_playwright", return_value=playwright):
            result = app_module.pick_selectors(
                app_module.PickSelectorsRequest(
                    url="https://example.test/form",
                    use_session=False,
                    target_count=2,
                    target_labels=["Location", "Barcode"],
                    targets=[
                        {"id": "location", "label": "Location"},
                        {"id": "barcode", "label": "Barcode"},
                    ],
                )
            )

        self.assertEqual(result["selections"], selections)
        self.assertEqual(result["selectors"], [selection["selector"] for selection in selections])
        self.assertIn('"id": "location"', page.script or "")
        self.assertIn('"id": "barcode"', page.script or "")


if __name__ == "__main__":
    unittest.main()
