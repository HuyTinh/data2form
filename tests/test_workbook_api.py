import asyncio
import importlib
import io
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException
from starlette.datastructures import UploadFile
import workbook_service

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


class WorkbookApiTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or os.getcwd())
        self.old_data_dir = app_module.DATA_DIR
        self.old_service_data_dir = workbook_service.DATA_DIR
        self.old_db_path = app_module.DB_PATH
        app_module.DATA_DIR = self.scratch.name
        workbook_service.DATA_DIR = self.scratch.name
        app_module.DB_PATH = os.path.join(self.scratch.name, "test.db")
        app_module.DATA_CACHE.clear()
        if hasattr(app_module, "WORKBOOK_CACHE"):
            app_module.WORKBOOK_CACHE.clear()
        if hasattr(app_module, "SHEET_CACHE"):
            app_module.SHEET_CACHE.clear()
        app_module.init_db()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame([{"OrderID": "A-1", "Customer": "Acme"}]).to_excel(
                writer, sheet_name="Orders", index=False
            )
            pd.DataFrame([{"OrderID": "A-1", "SKU": "P-01"}]).to_excel(
                writer, sheet_name="Materials", index=False
            )
        self.workbook_bytes = buffer.getvalue()

    def tearDown(self):
        app_module.DATA_DIR = self.old_data_dir
        workbook_service.DATA_DIR = self.old_service_data_dir
        app_module.DB_PATH = self.old_db_path
        app_module.DATA_CACHE.clear()
        if hasattr(app_module, "WORKBOOK_CACHE"):
            app_module.WORKBOOK_CACHE.clear()
        if hasattr(app_module, "SHEET_CACHE"):
            app_module.SHEET_CACHE.clear()
        self.scratch.cleanup()

    def test_upload_exposes_sheet_metadata_without_removing_legacy_fields(self):
        request_file = UploadFile(filename="orders.xlsx", file=io.BytesIO(self.workbook_bytes))
        response = asyncio.run(app_module.upload_file(request_file))

        self.assertEqual(response["columns"], ["OrderID", "Customer"])
        self.assertEqual(response["total_rows"], 1)
        self.assertEqual(
            response["sheets"],
            [
                {"name": "Orders", "columns": ["OrderID", "Customer"], "total_rows": 1},
                {"name": "Materials", "columns": ["OrderID", "SKU"], "total_rows": 1},
            ],
        )
        self.assertNotIn((response["filename"], "Materials"), app_module.SHEET_CACHE)
        preview = app_module.get_preview(response["filename"], sheet_name="Materials")
        self.assertEqual(preview["data"], [{"OrderID": "A-1", "SKU": "P-01"}])
        self.assertIn((response["filename"], "Materials"), app_module.SHEET_CACHE)

    def test_preset_round_trip_keeps_legacy_mappings_and_new_plan(self):
        plan = {
            "version": 1,
            "parent": {"sheet_name": "Orders", "key_column": "OrderID", "mappings": {}},
            "submit_selector": "#submit",
            "detail_tables": [],
        }
        app_module.save_preset(
            {
                "url": "http://example.test/form",
                "submit_selector": "#submit",
                "use_session": False,
                "mappings": {"Customer": {"selector": "#customer", "type": "text"}},
                "mapping_plan": plan,
                "saved_at": "2026-09-26T00:00:00Z",
            }
        )

        loaded = app_module.get_preset("http://example.test/form")
        self.assertEqual(loaded["mappings"]["Customer"]["selector"], "#customer")
        self.assertEqual(loaded["mapping_plan"], plan)

    def test_init_db_adds_mapping_plan_to_legacy_preset_table(self):
        legacy_db = os.path.join(self.scratch.name, "legacy.db")
        connection = sqlite3.connect(legacy_db)
        connection.execute(
            "CREATE TABLE presets (url TEXT PRIMARY KEY, submit_selector TEXT, use_session INTEGER, mappings TEXT, open_form_trigger TEXT DEFAULT '', saved_at TEXT)"
        )
        connection.commit()
        connection.close()
        old_db_path = app_module.DB_PATH
        try:
            app_module.DB_PATH = legacy_db
            app_module.init_db()
            connection = sqlite3.connect(legacy_db)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(presets)").fetchall()}
            connection.close()
        finally:
            app_module.DB_PATH = old_db_path

        self.assertIn("mapping_plan", columns)

    def test_legacy_preset_without_mapping_plan_still_loads(self):
        app_module.save_preset(
            {
                "url": "http://legacy.test/form",
                "submit_selector": "#submit",
                "use_session": False,
                "mappings": {"Customer": "#customer"},
                "saved_at": "2026-09-26T00:00:00Z",
            }
        )
        loaded = app_module.get_preset("http://legacy.test/form")
        self.assertEqual(loaded["mappings"], {"Customer": "#customer"})
        self.assertIsNone(loaded["mapping_plan"])

    def test_run_request_accepts_plan_without_changing_legacy_defaults(self):
        request = app_module.RunRequest(
            filename="orders.xlsx",
            url="http://example.test/form",
            mapping_plan={"version": 1},
        )

        self.assertEqual(request.mappings, {})
        self.assertEqual(request.mapping_plan, {"version": 1})
        self.assertEqual(request.table_mode, False)

    def test_invalid_plan_is_rejected_before_background_run_starts(self):
        workbook_path = os.path.join(self.scratch.name, "orders.xlsx")
        with open(workbook_path, "wb") as workbook_file:
            workbook_file.write(self.workbook_bytes)
        invalid_plan = {
            "version": 1,
            "parent": {
                "sheet_name": "MissingParent",
                "key_column": "OrderID",
                "mappings": {"Customer": {"selector": "#customer", "type": "text"}},
            },
            "submit_selector": "#submit",
            "detail_tables": [
                {
                    "id": "items",
                    "name": "Items",
                    "sheet_name": "Materials",
                    "parent_key_column": "OrderID",
                    "mappings": {"SKU": {"selector": "#sku", "type": "text"}},
                }
            ],
        }
        request = app_module.RunRequest(
            filename="orders.xlsx",
            url="http://example.test/form",
            mapping_plan=invalid_plan,
        )

        with patch.object(app_module.threading, "Thread") as thread:
            with self.assertRaises(HTTPException) as caught:
                app_module.run_automation(request)

        self.assertEqual(caught.exception.status_code, 422)
        thread.assert_not_called()

    def test_valid_mapping_plan_dispatches_to_new_core(self):
        workbook_path = os.path.join(self.scratch.name, "orders.xlsx")
        with open(workbook_path, "wb") as workbook_file:
            workbook_file.write(self.workbook_bytes)
        plan = {
            "version": 1,
            "parent": {
                "sheet_name": "Orders",
                "key_column": "OrderID",
                "mappings": {"Customer": {"selector": "#customer", "type": "text"}},
            },
            "submit_selector": "#submit",
            "detail_tables": [
                {
                    "id": "materials",
                    "name": "Materials",
                    "sheet_name": "Materials",
                    "parent_key_column": "OrderID",
                    "mappings": {"SKU": {"selector": "#sku", "type": "text"}},
                }
            ],
        }
        request = app_module.RunRequest(
            filename="orders.xlsx",
            url="http://example.test/form",
            mapping_plan=plan,
        )

        class ImmediateThread:
            def __init__(self, target):
                self.target = target

            def start(self):
                self.target()

        with patch.object(app_module.threading, "Thread", ImmediateThread), \
             patch.object(app_module, "run_mapping_plan_core") as plan_core, \
             patch.object(app_module, "run_automation_core") as legacy_core:
            response = app_module.run_automation(request)

        self.assertEqual(response, {"status": "started"})
        plan_core.assert_called_once()
        legacy_core.assert_not_called()

    def test_history_and_log_helpers_preserve_persisted_records(self):
        app_module.persistence.save_run_history(
            filename="orders.xlsx",
            rel_path="2026-01-02/orders.xlsx",
            start_time="12:00:00 02/01/2026",
            total_rows=3,
            status="Success",
            logs=[{"time": "12:00:01", "message": "run completed", "level": "success"}],
            db_path=app_module.DB_PATH,
        )

        [record] = app_module.get_history()
        self.assertEqual(record["filename"], "orders.xlsx")
        self.assertEqual(record["rel_path"], "2026-01-02/orders.xlsx")
        self.assertEqual(record["status"], "Success")
        self.assertEqual(
            app_module.get_history_logs(record["id"]),
            [{"time": "12:00:01", "message": "run completed", "msg": "run completed", "level": "success"}],
        )


if __name__ == "__main__":
    unittest.main()
