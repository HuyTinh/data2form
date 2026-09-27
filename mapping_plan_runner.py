"""Parent/detail mapping-plan automation runner."""

import logging
import os

from automation_runtime import (
    AutomationStatus,
    _PersistentPlaywrightSession,
    _get_persistent_browser_context,
    _click_after_action,
    setup_encoding,
)
from form_fields import (
    apply_field_value,
    infer_field_type,
    is_populated_cell_value,
    normalize_field_type,
    validate_target_url,
)
from mapping_plan import load_mapping_plan_workbook
from selector_utils import resolve_row_selector

logger = logging.getLogger(__name__)


def _apply_mapping_plan_fields(page, mappings, source_row, row_index, status, scope, table_mode=False, applied_fields=None):
    """Apply one parent or detail-row mapping group; never defer clicks after a field error."""
    errors = []
    pending_clicks = []
    pending_after_actions = []

    for source_column, mapping in mappings.items():
        action_type = normalize_field_type(mapping.get("type", "text"))
        selector = str(mapping.get("selector", "")).strip()
        selector = resolve_row_selector(selector, row_index, table_mode)
        is_click = action_type == "click"
        value = "click" if is_click else source_row.get(source_column, "")
        if not is_click and not is_populated_cell_value(value):
            continue

        try:
            locator = page.locator(selector).first
            if action_type == "upload":
                locator.wait_for(state="attached", timeout=5000)
            else:
                locator.wait_for(state="visible", timeout=5000)
                locator.scroll_into_view_if_needed()

            if is_click:
                pending_clicks.append((source_column, selector))
                continue

            resolved_type = infer_field_type(locator, action_type)
            applied_value = apply_field_value(page, locator, resolved_type, value, multiple=bool(mapping.get("multiple", False)))
            if applied_fields is not None:
                applied_fields.append(source_column)
            if status:
                status.log(f"{scope}: Đã xử lý '{source_column}' ({resolved_type})")

            after_selector = str(mapping.get("after_selector", "")).strip()
            if after_selector:
                pending_after_actions.append((source_column, after_selector))
        except Exception as exc:
            errors.append({"field": source_column, "message": str(exc)})
            if status:
                status.log(f"{scope}: Lỗi tại '{source_column}': {exc}", "error")
            break

    if errors:
        return errors

    for source_column, after_selector in pending_after_actions:
        try:
            _click_after_action(page, after_selector, table_mode, row_index)
        except Exception as exc:
            errors.append({"field": source_column, "message": str(exc)})
            if status:
                status.log(f"{scope}: Lỗi thao tác sau trường '{source_column}': {exc}", "error")
            return errors

    for source_column, selector in pending_clicks:
        try:
            click_target = page.locator(selector).first
            click_target.wait_for(state="attached", timeout=5000)
            click_target.scroll_into_view_if_needed()
            click_target.click(force=True, timeout=5000)
            if status:
                status.log(f"{scope}: Đã click '{source_column}'")
        except Exception as exc:
            errors.append({"field": source_column, "message": str(exc)})
            if status:
                status.log(f"{scope}: Lỗi click '{source_column}': {exc}", "error")
            break
    return errors


def _click_plan_selector(page, selector, row_index, label, timeout=5000):
    resolved_selector = resolve_row_selector(str(selector), row_index, True)
    locator = page.locator(resolved_selector).first
    locator.wait_for(state="attached", timeout=timeout)
    locator.scroll_into_view_if_needed()
    locator.click(force=True, timeout=timeout)
    return resolved_selector


def run_mapping_plan_core(excel_path: str, url: str, mapping_plan: dict, status: AutomationStatus | None = None, use_session: bool = False):
    """Run one parent form per parent key and its ordered, independently mapped detail tables."""
    setup_encoding()
    if status:
        status.is_running = True
        status.log(f"Khởi động luồng form chung + bảng chi tiết: {os.path.basename(excel_path)}")

    try:
        configuration_errors = validate_target_url(url)
        if configuration_errors:
            raise ValueError("Invalid target URL: " + "; ".join(configuration_errors))
        loaded = load_mapping_plan_workbook(excel_path, mapping_plan)
        plan = loaded["plan"]
        parent = plan["parent"]
        parent_rows = loaded["parent_rows"]
        details = loaded["detail_rows"]
        if status:
            status.total_rows = len(parent_rows)
            status.log(f"Đã kiểm tra workbook: {len(parent_rows)} parent, {len(plan['detail_tables'])} bảng chi tiết")

        with _PersistentPlaywrightSession() as playwright:
            browser = None
            context = None
            if use_session:
                user_data_dir = os.path.join(os.getcwd(), ".browser_session")
                context = _get_persistent_browser_context(playwright, user_data_dir)
                page = next((existing for existing in context.pages if not existing.is_closed()), None)
                if page is None:
                    page = context.new_page()
            else:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

            for parent_index, parent_row in enumerate(parent_rows, start=1):
                parent_key = str(parent_row[parent["key_column"]]).strip()
                parent_result = {
                    "parent_key": parent_key,
                    "row": parent_index,
                    "status": "running",
                    "errors": [],
                    "applied_fields": [],
                    "partial_state": False,
                    "tables": [],
                }
                if status:
                    status.current_row = parent_index
                    status.detail_results.append(parent_result)
                    status.row_results.append({"row": parent_index, "status": "running", "errors": []})
                    status.log(f"--- Parent {parent_index}/{len(parent_rows)} ({parent_key}) ---")

                try:
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(1500)
                    trigger_selector = str(plan.get("open_form_trigger", "")).strip()
                    if trigger_selector:
                        _click_plan_selector(page, trigger_selector, parent_index, "parent trigger")
                    errors = _apply_mapping_plan_fields(
                        page, parent["mappings"], parent_row, 1, status, f"Parent {parent_key}",
                        applied_fields=parent_result["applied_fields"],
                    )
                    parent_result["partial_state"] = bool(parent_result["applied_fields"])
                    parent_result["errors"].extend(errors)
                    if errors:
                        raise RuntimeError("Parent field mapping failed")

                    for table in plan["detail_tables"]:
                        table_id = table["id"].strip()
                        table_result = {"table_id": table_id, "name": table["name"], "status": "running", "rows": [], "errors": []}
                        parent_result["tables"].append(table_result)
                        detail_rows = details[table_id].get(parent_key, [])
                        if not detail_rows:
                            table_result["status"] = "skipped"
                            if status:
                                status.log(f"Parent {parent_key}: Bỏ qua bảng '{table['name']}' không có dòng")
                            continue

                        for detail_index, detail_row in enumerate(detail_rows, start=1):
                            row_result = {"row": detail_index, "status": "running", "errors": [], "applied_fields": [], "partial_state": False}
                            table_result["rows"].append(row_result)
                            scope = f"Parent {parent_key} / {table['name']} / dòng {detail_index}"
                            if status:
                                status.log(f"{scope}: bắt đầu")
                            try:
                                add_selector = str(table.get("add_row_selector", "")).strip()
                                if add_selector:
                                    _click_plan_selector(page, add_selector, detail_index, f"{table['name']} add row")
                                    row_result["partial_state"] = True
                                    table_result["partial_state"] = True
                                    parent_result["partial_state"] = True
                                    page.wait_for_timeout(300)

                                errors = _apply_mapping_plan_fields(
                                    page,
                                    table["mappings"],
                                    detail_row,
                                    detail_index,
                                    status,
                                    scope,
                                    table_mode=True,
                                    applied_fields=row_result["applied_fields"],
                                )
                                if row_result["applied_fields"]:
                                    row_result["partial_state"] = True
                                    table_result["partial_state"] = True
                                    parent_result["partial_state"] = True
                                row_result["errors"].extend(errors)
                                if errors:
                                    row_result["status"] = "failed"
                                    table_result["status"] = "failed"
                                    table_result["errors"].extend(errors)
                                    parent_result["errors"].extend(errors)
                                    raise RuntimeError(f"Detail row {detail_index} failed in table '{table_id}'")

                                row_save_selector = str(table.get("row_save_selector", "")).strip()
                                if row_save_selector:
                                    _click_plan_selector(page, row_save_selector, detail_index, f"{table['name']} row save", int(table.get("row_save_timeout", 8000)))
                                    row_result["partial_state"] = False
                                    table_result["partial_state"] = any(row["partial_state"] for row in table_result["rows"])
                                    parent_result["partial_state"] = True
                                    page.wait_for_timeout(500)
                                row_result["status"] = "completed"
                            except Exception as exc:
                                if row_result["status"] == "running":
                                    row_result["status"] = "failed"
                                    row_result["errors"].append({"field": "row", "message": str(exc)})
                                    table_result["errors"].extend(row_result["errors"])
                                    parent_result["errors"].extend(row_result["errors"])
                                table_result["status"] = "failed"
                                if status:
                                    status.log(f"{scope}: lỗi, dừng parent để tránh lưu trạng thái dở dang ({exc})", "error")
                                raise

                        table_result["status"] = "completed"

                    submit_selector = str(plan.get("submit_selector", "")).strip()
                    _click_plan_selector(page, submit_selector, parent_index, "parent submit")
                    page.wait_for_timeout(1000)
                    parent_result["status"] = "completed"
                    parent_result["partial_state"] = False
                    for completed_table in parent_result["tables"]:
                        completed_table["partial_state"] = False
                        for completed_row in completed_table["rows"]:
                            completed_row["partial_state"] = False
                    if status:
                        status.row_results[-1]["status"] = "completed"
                        status.row_results[-1]["partial_state"] = False
                        status.log(f"Parent {parent_key}: đã hoàn tất các bảng và submit", "success")
                except Exception as exc:
                    parent_result["status"] = "failed"
                    if status:
                        if status.row_results:
                            status.row_results[-1]["status"] = "failed"
                            status.row_results[-1]["partial_state"] = parent_result["partial_state"]
                            status.row_results[-1]["errors"].extend(parent_result["errors"] or [{"field": "parent", "message": str(exc)}])
                        if parent_result["partial_state"]:
                            status.log(
                                f"Parent {parent_key}: đã áp dụng một phần dữ liệu; có thể còn trạng thái chưa lưu trên trang.",
                                "warning",
                            )
                        if not parent_result["errors"]:
                            parent_result["errors"].append({"field": "parent", "message": str(exc)})
                        status.log(f"Parent {parent_key}: dừng do lỗi; chưa submit form", "error")
                    break

        if status:
            if status.has_errors:
                status.log("Luồng kết thúc có lỗi; parent đang lỗi chưa được submit. Hãy đối chiếu parent/table/row trước khi chạy lại.", "warning")
            else:
                status.log("Hoàn tất các parent và bảng chi tiết; hãy xác nhận dữ liệu đã được lưu trên website.", "success")
    except Exception as exc:
        if status:
            status.log(f"Lỗi chuẩn bị/chạy mapping plan: {exc}", "error")
        raise
    finally:
        if status:
            status.is_running = False
