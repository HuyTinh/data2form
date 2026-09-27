import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import automation_runtime
import main
from main import AutomationStatus


class PlanFakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector
        self.first = self
        self.value = ""

    def evaluate(self, _script):
        return "text"

    def wait_for(self, state, timeout):
        if state == "visible" and self.selector == "#bad":
            raise TimeoutError("field unavailable")

    def scroll_into_view_if_needed(self):
        pass

    def fill(self, value):
        self.value = value
        self.page.fills.append((self.selector, value))
        self.page.events.append(("fill", self.selector, value))

    def input_value(self):
        return self.value

    def click(self, **_kwargs):
        self.page.clicks.append(self.selector)
        self.page.events.append(("click", self.selector))


class PlanFakePage:
    def __init__(self):
        self.fills = []
        self.clicks = []
        self.navigations = []
        self.events = []
        self.created_locators = []

    def goto(self, url, **_kwargs):
        self.navigations.append(url)
        self.events.append(("goto", url))

    def wait_for_timeout(self, *_args):
        pass

    def locator(self, selector):
        locator = PlanFakeLocator(self, selector)
        self.created_locators.append(locator)
        return locator


class MappingPlanExecutionTests(unittest.TestCase):
    def make_workbook(self, materials=None, services=None):
        scratch = os.environ.get("TMPDIR") or os.getcwd()
        handle, path = tempfile.mkstemp(suffix=".xlsx", dir=scratch)
        os.close(handle)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame(
                [{"OrderID": "A-1", "Customer": "Acme"}, {"OrderID": "A-2", "Customer": "Globex"}]
            ).to_excel(writer, sheet_name="Orders", index=False)
            pd.DataFrame(
                materials or [
                    {"OrderID": "A-1", "SKU": "P-01"},
                    {"OrderID": "A-1", "SKU": "P-02"},
                    {"OrderID": "A-2", "SKU": "P-03"},
                ]
            ).to_excel(writer, sheet_name="Materials", index=False)
            pd.DataFrame(
                services or [{"OrderID": "A-1", "Service": "Install"}]
            ).to_excel(writer, sheet_name="Services", index=False)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    def make_plan(self):
        return {
            "version": 1,
            "parent": {
                "sheet_name": "Orders",
                "key_column": "OrderID",
                "mappings": {"Customer": {"selector": "#customer", "type": "text"}},
            },
            "open_form_trigger": "#open",
            "submit_selector": "#submit",
            "detail_tables": [
                {
                    "id": "materials",
                    "name": "Materials",
                    "sheet_name": "Materials",
                    "parent_key_column": "OrderID",
                    "mappings": {"SKU": {"selector": "#material-{row}", "type": "text"}},
                    "add_row_selector": "#add-material",
                    "row_save_selector": "#save-material-{row}",
                },
                {
                    "id": "services",
                    "name": "Services",
                    "sheet_name": "Services",
                    "parent_key_column": "OrderID",
                    "mappings": {"Service": {"selector": "#service-{row}", "type": "text"}},
                    "add_row_selector": "",
                    "row_save_selector": "",
                },
            ],
        }

    def run_with_page(self, workbook_path, plan):
        page = PlanFakePage()
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.new_context.return_value = context
        playwright = Mock()
        playwright.chromium.launch.return_value = browser
        factory = Mock()
        factory.return_value.start.return_value = playwright
        previous_instance = automation_runtime._playwright_instance
        automation_runtime._playwright_instance = None
        self.addCleanup(setattr, automation_runtime, "_playwright_instance", previous_instance)
        status = AutomationStatus()
        with patch("automation_runtime.sync_playwright", factory):
            main.run_mapping_plan_core(workbook_path, "http://example.test/form", plan, status)
        return page, context, browser, status

    def test_fills_parent_once_and_runs_two_detail_tables_in_order(self):
        workbook_path = self.make_workbook()
        page, _context, _browser, status = self.run_with_page(workbook_path, self.make_plan())

        self.assertEqual(page.fills.count(("#customer", "Acme")), 1)
        self.assertEqual(page.fills.count(("#customer", "Globex")), 1)
        self.assertEqual(page.fills.count(("#material-1", "P-01")), 1)
        self.assertEqual(page.fills.count(("#material-2", "P-02")), 1)
        self.assertEqual(page.fills.count(("#service-1", "Install")), 1)
        self.assertEqual(page.clicks.count("#open"), 2)
        self.assertEqual(page.clicks.count("#add-material"), 3)
        self.assertEqual(page.clicks.count("#save-material-1"), 2)
        self.assertEqual(page.clicks.count("#submit"), 2)
        first_parent_events = page.events[:page.events.index(("goto", "http://example.test/form")) + 16]
        self.assertLess(first_parent_events.index(("fill", "#customer", "Acme")), first_parent_events.index(("click", "#add-material")))
        self.assertLess(first_parent_events.index(("fill", "#material-2", "P-02")), first_parent_events.index(("fill", "#service-1", "Install")))
        self.assertLess(first_parent_events.index(("fill", "#service-1", "Install")), first_parent_events.index(("click", "#submit")))
        self.assertEqual([table["table_id"] for table in status.detail_results[0]["tables"]], ["materials", "services"])
        self.assertEqual(status.detail_results[0]["status"], "completed")

    def test_field_error_prevents_row_save_and_parent_submit(self):
        workbook_path = self.make_workbook(
            materials=[{"OrderID": "A-1", "SKU": "P-01"}],
            services=[],
        )
        plan = self.make_plan()
        plan["detail_tables"] = plan["detail_tables"][:1]
        plan["detail_tables"][0]["mappings"]["SKU"]["selector"] = "#bad"
        page, _context, _browser, status = self.run_with_page(workbook_path, plan)

        self.assertNotIn("#save-material-1", page.clicks)
        self.assertNotIn("#submit", page.clicks)
        self.assertEqual(status.detail_results[0]["status"], "failed")
        self.assertEqual(status.detail_results[0]["tables"][0]["rows"][0]["status"], "failed")
        self.assertEqual(status.detail_results[0]["applied_fields"], ["Customer"])
        self.assertTrue(status.detail_results[0]["partial_state"])
        self.assertTrue(status.detail_results[0]["tables"][0]["rows"][0]["partial_state"])
        self.assertTrue(status.has_errors)


if __name__ == "__main__":
    unittest.main()
