import os
import tempfile
import unittest

import pandas as pd

from mapping_plan import load_mapping_plan_workbook


class MappingPlanWorkbookTests(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get("TMPDIR") or os.getcwd()
        handle, self.workbook_path = tempfile.mkstemp(suffix=".xlsx", dir=scratch)
        os.close(handle)
        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame(
                [
                    {"OrderID": "A-1", "Customer": "Acme"},
                    {"OrderID": "A-2", "Customer": "Globex"},
                ]
            ).to_excel(writer, sheet_name="Orders", index=False)
            pd.DataFrame(
                [
                    {"OrderID": "A-1", "SKU": "P-01", "Qty": "2"},
                    {"OrderID": "A-1", "SKU": "P-02", "Qty": "1"},
                    {"OrderID": "A-2", "SKU": "P-03", "Qty": "4"},
                ]
            ).to_excel(writer, sheet_name="Materials", index=False)
            pd.DataFrame(
                [{"OrderID": "A-1", "Service": "Install", "Hours": "3"}]
            ).to_excel(writer, sheet_name="Services", index=False)

    def tearDown(self):
        if os.path.exists(self.workbook_path):
            os.unlink(self.workbook_path)

    def make_plan(self):
        return {
            "version": 1,
            "parent": {
                "sheet_name": "Orders",
                "key_column": "OrderID",
                "mappings": {"Customer": {"selector": "#customer", "type": "text"}},
            },
            "open_form_trigger": "",
            "submit_selector": "#submit",
            "detail_tables": [
                {
                    "id": "materials",
                    "name": "Materials",
                    "sheet_name": "Materials",
                    "parent_key_column": "OrderID",
                    "mappings": {
                        "SKU": {"selector": "tr:nth-of-type({row}) .sku", "type": "text"},
                        "Qty": {"selector": "tr:nth-of-type({row}) .qty", "type": "number"},
                    },
                    "add_row_selector": "#add-material",
                    "row_save_selector": "",
                },
                {
                    "id": "services",
                    "name": "Services",
                    "sheet_name": "Services",
                    "parent_key_column": "OrderID",
                    "mappings": {
                        "Service": {"selector": "tr:nth-of-type({row}) .service", "type": "text"},
                        "Hours": {"selector": "tr:nth-of-type({row}) .hours", "type": "number"},
                    },
                    "add_row_selector": "",
                    "row_save_selector": "#save-service-{row}",
                },
            ],
        }

    def test_loads_multiple_detail_sheets_grouped_by_parent_key(self):
        loaded = load_mapping_plan_workbook(self.workbook_path, self.make_plan())

        self.assertEqual([row["OrderID"] for row in loaded["parent_rows"]], ["A-1", "A-2"])
        self.assertEqual(
            [row["SKU"] for row in loaded["detail_rows"]["materials"]["A-1"]],
            ["P-01", "P-02"],
        )
        self.assertEqual(loaded["detail_rows"]["materials"]["A-2"][0]["Qty"], "4")
        self.assertEqual(loaded["detail_rows"]["services"]["A-1"][0]["Service"], "Install")
        self.assertEqual(loaded["detail_rows"]["services"]["A-2"], [])

    def test_rejects_duplicate_parent_keys(self):
        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame(
                [{"OrderID": "A-1", "Customer": "Acme"}, {"OrderID": "A-1", "Customer": "Other"}]
            ).to_excel(writer, sheet_name="Orders", index=False)
            pd.DataFrame([{"OrderID": "A-1", "SKU": "P-01", "Qty": "2"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "Service": "Install", "Hours": "3"}]).to_excel(
                writer, sheet_name="Services", index=False
            )

        with self.assertRaisesRegex(ValueError, "duplicate parent key"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

    def test_rejects_orphan_detail_rows_before_execution(self):
        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame([{"OrderID": "A-1", "Customer": "Acme"}]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame([{"OrderID": "UNKNOWN", "SKU": "P-01", "Qty": "2"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame(columns=["OrderID", "Service", "Hours"]).to_excel(
                writer, sheet_name="Services", index=False
            )

        with self.assertRaisesRegex(ValueError, "no matching parent"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

    def test_rejects_blank_detail_keys_and_empty_parent_workbooks(self):
        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame([{"OrderID": "A-1", "Customer": "Acme"}]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame([{"OrderID": "", "SKU": "P-01", "Qty": "2"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame(columns=["OrderID", "Service", "Hours"]).to_excel(
                writer, sheet_name="Services", index=False
            )
        with self.assertRaisesRegex(ValueError, "blank parent key"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame(columns=["OrderID", "Customer"]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame(columns=["OrderID", "SKU", "Qty"]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame(columns=["OrderID", "Service", "Hours"]).to_excel(
                writer, sheet_name="Services", index=False
            )
        with self.assertRaisesRegex(ValueError, "no parent records"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

    def test_rejects_duplicate_or_blank_raw_headers(self):
        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame([["A-1", "Acme", "Other"]], columns=["OrderID", "Customer", "Customer"]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "SKU": "P-01", "Qty": "2"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "Service": "Install", "Hours": "3"}]).to_excel(
                writer, sheet_name="Services", index=False
            )
        with self.assertRaisesRegex(ValueError, "duplicate header"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

        with pd.ExcelWriter(self.workbook_path, engine="openpyxl") as writer:
            pd.DataFrame([["A-1", "Acme"]], columns=["OrderID", ""]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "SKU": "P-01", "Qty": "2"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "Service": "Install", "Hours": "3"}]).to_excel(
                writer, sheet_name="Services", index=False
            )
        with self.assertRaisesRegex(ValueError, "blank header"):
            load_mapping_plan_workbook(self.workbook_path, self.make_plan())

    def test_rejects_unknown_sheets_and_invalid_source_columns(self):
        plan = self.make_plan()
        plan["detail_tables"][1]["sheet_name"] = "Missing"
        with self.assertRaisesRegex(ValueError, "unknown sheet"):
            load_mapping_plan_workbook(self.workbook_path, plan)

        plan = self.make_plan()
        plan["parent"]["mappings"] = {"UnknownColumn": {"selector": "#customer", "type": "text"}}
        with self.assertRaisesRegex(ValueError, "UnknownColumn"):
            load_mapping_plan_workbook(self.workbook_path, plan)

    def test_rejects_unsupported_plan_version_and_missing_selector(self):
        plan = self.make_plan()
        plan["version"] = 2
        with self.assertRaisesRegex(ValueError, "version"):
            load_mapping_plan_workbook(self.workbook_path, plan)

        plan = self.make_plan()
        plan["detail_tables"][0]["mappings"]["SKU"]["selector"] = ""
        with self.assertRaisesRegex(ValueError, "selector"):
            load_mapping_plan_workbook(self.workbook_path, plan)

        plan = self.make_plan()
        plan["detail_tables"][0]["row_save_timeout"] = 0
        with self.assertRaisesRegex(ValueError, "row_save_timeout"):
            load_mapping_plan_workbook(self.workbook_path, plan)


if __name__ == "__main__":
    unittest.main()
