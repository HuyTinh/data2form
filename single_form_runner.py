"""Single-form and repeated-row automation runner."""

import logging
import os

import pandas as pd

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
    validate_mappings,
    validate_target_url,
)
from selector_utils import resolve_row_selector

logger = logging.getLogger(__name__)


def run_automation_core(excel_path: str, url: str, mappings: dict, submit_selector: str, status: AutomationStatus = None, use_session: bool = False, open_form_trigger: str = "", table_mode: bool = False, row_save_selector: str = "", row_save_timeout: int = 8000):
    """
    Core engine for automation with status tracking and error handling.
    """
    setup_encoding()
    if status:
        status.is_running = True
        status.log(f"Khởi động tiến trình cho file: {os.path.basename(excel_path)}")

    try:
        df = pd.read_excel(excel_path, engine='openpyxl', dtype=str).fillna("")
        total = len(df)
        cols = list(df.columns)
        if status:
            status.total_rows = total
            status.log(f"📊 Excel: Tìm thấy {total} dòng và {len(cols)} cột: {', '.join(cols)}")

        # Normalize mappings: auto-detect inverted mappings { selector: col_name } from older/misconfigured presets
        if mappings:
            normalized_mappings = {}
            for k, v in mappings.items():
                col_val = v if isinstance(v, str) else (v.get("column") if isinstance(v, dict) else "")
                if k not in df.columns and col_val in df.columns:
                    normalized_mappings[col_val] = k if isinstance(v, str) else v
                else:
                    normalized_mappings[k] = v
            mappings = normalized_mappings

    except Exception as e:
        if status: status.log(f"Lỗi đọc file: {e}", "error")
        raise

    configuration_errors = validate_mappings(mappings, cols) + validate_target_url(url)
    if configuration_errors:
        if status:
            for error in configuration_errors:
                status.log(f"Cấu hình không hợp lệ: {error}", "error")
            status.is_running = False
            return
        raise ValueError("Invalid automation configuration: " + "; ".join(configuration_errors))

    try:
        with _PersistentPlaywrightSession() as p:
            browser = None
            context = None
            logger.info("Đang khởi tạo engine đồng bộ Playwright...")

            if use_session:
                user_data_dir = os.path.join(os.getcwd(), ".browser_session")
                logger.info(f"Sử dụng Persistent Context: {user_data_dir}")
                context = _get_persistent_browser_context(p, user_data_dir)
                page = next((existing for existing in context.pages if not existing.is_closed()), None)
                if page is None:
                    page = context.new_page()
            else:
                browser = p.chromium.launch(headless=False)
                logger.info("Đã mở trình duyệt Chromium (Chế độ hiển thị: Có)")
                context = browser.new_context()
                page = context.new_page()

            logger.info("Đã tạo phiên trình duyệt và trang mới.")

            if status: status.log(f"Đang mở trang: {url}")
            try:
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(3000)
            except Exception as e:
                if status: status.log(f"Lỗi tải trang: {e}", "error")
                raise

            if table_mode and status:
                status.log("📋 Chế độ lặp theo hàng: ánh xạ dữ liệu vào từng hàng đã cấu hình")

            for index, row in df.iterrows():
                row_index = index + 1  # 1-based for CSS :nth-child()
                row_result = {"row": row_index, "status": "running", "errors": []}
                if status:
                    status.row_results.append(row_result)
                    status.current_row = row_index
                    row_data_str = ", ".join([f"{k}: {v}" for k, v in row.to_dict().items()])
                    status.log(f"--- 🚀 Đang xử lý dòng {row_index}/{status.total_rows} ---")
                    status.log(f"📦 Dữ liệu: {row_data_str}")

                try:
                    # --- Step 0: Click global trigger to open modal/popup if specified (not used in table_mode) ---
                    if open_form_trigger and not table_mode:
                        try:
                            trigger_el = page.locator(open_form_trigger).first
                            trigger_el.wait_for(state="visible", timeout=5000)
                            trigger_el.scroll_into_view_if_needed()
                            trigger_el.click()
                            if status: status.log(f"⚡ Đã click trigger để mở form")

                            # SMART WAIT: Instead of fixed 1.5s, wait for the first mapped field to appear
                            first_selector = next(iter(mappings.values()))
                            if isinstance(first_selector, dict): first_selector = first_selector.get("selector")
                            if first_selector:
                                try:
                                    page.locator(first_selector).first.wait_for(state="visible", timeout=5000)
                                except:
                                    page.wait_for_timeout(1000) # Fallback
                        except Exception as te:
                            if status: status.log(f"⚠️ Trigger click thất bại: {te}", "warning")
                            logger.warning(f"Trigger click failed: {te}")

                    pending_after_actions = []
                    pending_click_actions = []
                    for col, mapping_data in mappings.items():
                        if isinstance(mapping_data, dict):
                            selector = mapping_data.get("selector", "")
                            action_type = mapping_data.get("type", "text")
                            after_selector = mapping_data.get("after_selector", "")
                            multiple = bool(mapping_data.get("multiple", False))
                        else:
                            selector = mapping_data
                            action_type = "text"
                            after_selector = ""
                            multiple = False

                        configured_type = normalize_field_type(action_type)
                        is_click = configured_type == "click"
                        cell_has_value = col in row and is_populated_cell_value(row[col])
                        # Zero and False are valid data; only empty strings and NaN-like cells are skipped.
                        if cell_has_value or is_click:
                            val = str(row[col]) if cell_has_value else "click"
                            field_action_succeeded = False
                            try:
                                if not selector: continue

                                selector = resolve_row_selector(selector, row_index, table_mode)

                                if is_click:
                                    pending_click_actions.append((col, selector))
                                    continue

                                # --- Step 2: Interact with the target element ---
                                el = page.locator(selector).first
                                resolved_type = infer_field_type(el, configured_type)
                                if resolved_type != "upload":
                                    # Non-click actions require element to be visible
                                    try:
                                        el.wait_for(state="visible", timeout=5000)
                                        el.scroll_into_view_if_needed()
                                    except Exception:
                                        page.wait_for_timeout(500)
                                        row_result["errors"].append({"field": col, "message": "Field is not visible"})
                                        if status: status.log(f"Bỏ qua '{col}': Không hiển thị", "warning")
                                        continue
                                else:
                                    # Upload controls may be hidden; wait until the input exists in the DOM.
                                    try:
                                        el.wait_for(state="attached", timeout=5000)
                                    except Exception:
                                        page.wait_for_timeout(500)
                                        row_result["errors"].append({"field": col, "message": "Field is not in the DOM"})
                                        if status: status.log(f"Bỏ qua '{col}': Không tìm thấy trong DOM", "warning")
                                        continue

                                applied_value = apply_field_value(page, el, resolved_type, val, multiple=multiple)
                                if status:
                                    if resolved_type == "click":
                                        status.log(f"🖱️ Đã click '{col}'")
                                    elif resolved_type == "upload":
                                        status.log(f"Đã tải file cho '{col}': {applied_value}")
                                    elif resolved_type == "checkbox":
                                        status.log(f"Đã cập nhật checkbox '{col}' = {applied_value}")
                                    else:
                                        status.log(f"Đã xử lý '{col}' ({resolved_type})")
                                field_action_succeeded = True
                            except Exception as e:
                                row_result["errors"].append({"field": col, "message": str(e)})
                                if status: status.log(f"Lỗi tại '{col}': {e}", "error")

                            # --- After action: click a follow-up selector if configured ---
                            if after_selector and field_action_succeeded:
                                if table_mode:
                                    pending_after_actions.append((col, after_selector))
                                else:
                                    try:
                                        _click_after_action(page, after_selector, table_mode, row_index)
                                        if status: status.log(f"↪️ After click '{col}'")
                                        page.wait_for_timeout(500)
                                    except Exception as ae:
                                        row_result["errors"].append({"field": col, "message": str(ae)})
                                        if status: status.log(f"⚠️ After click '{col}' thất bại: {ae}", "warning")

                    # Never trigger save actions after a row has a field-level failure.
                    for col, after_sel in (pending_after_actions if not row_result["errors"] else []):
                        if row_result["errors"]:
                            break
                        try:
                            _click_after_action(page, after_sel, table_mode, row_index)
                            if status: status.log(f"↪️ After click '{col}'")
                            page.wait_for_timeout(500)
                        except Exception as ae:
                            row_result["errors"].append({"field": col, "message": str(ae)})
                            if status: status.log(f"⚠️ After click '{col}' thất bại: {ae}", "warning")

                    if pending_after_actions and row_result["errors"] and status:
                        status.log(f"Bỏ qua thao tác sau cùng của dòng {row_index} do có lỗi mapping", "warning")

                    # Click actions may save a row, so defer them until every field succeeded.
                    if pending_click_actions and not row_result["errors"]:
                        for col, click_selector in pending_click_actions:
                            try:
                                click_target = page.locator(click_selector).first
                                click_target.wait_for(state="attached", timeout=5000)
                                click_target.scroll_into_view_if_needed()
                                click_target.click(force=True, timeout=5000)
                                if status: status.log(f"🖱️ Đã click '{col}'")
                            except Exception as click_error:
                                row_result["errors"].append({"field": col, "message": str(click_error)})
                                if status: status.log(f"Lỗi click '{col}': {click_error}", "error")
                                break
                    elif pending_click_actions and status:
                        status.log(f"Bỏ qua click action của dòng {row_index} do có lỗi trường", "warning")

                    # --- Per-row Save button (Table Mode) ---
                    if table_mode and row_save_selector and not row_result["errors"]:
                        save_sel = resolve_row_selector(row_save_selector, row_index, table_mode)
                        try:
                            save_btn = page.locator(save_sel).first
                            save_btn.wait_for(state="attached", timeout=row_save_timeout)
                            save_btn.scroll_into_view_if_needed()
                            page.wait_for_timeout(300)
                            try:
                                save_btn.wait_for(state="visible", timeout=min(3000, row_save_timeout))
                            except Exception:
                                pass
                            save_btn.click(force=True)
                            if status: status.log(f"💾 Đã nhấn Lưu hàng {row_index}")
                            page.wait_for_timeout(1500)
                        except Exception as se:
                            # Fallback to JS click if standard click fails
                            try:
                                save_btn = page.locator(save_sel).first
                                save_btn.evaluate("el => el.click()")
                                if status: status.log(f"💾 Đã nhấn Lưu hàng {row_index} (JS click)")
                                page.wait_for_timeout(1500)
                            except Exception:
                                row_result["errors"].append({"field": "row_save", "message": str(se)})
                                if status: status.log(f"⚠️ Lỗi click Lưu hàng {row_index} (timeout={row_save_timeout}ms): {se}", "warning")
                    elif table_mode and row_save_selector and row_result["errors"]:
                        if status: status.log(f"Bỏ qua lưu hàng {row_index} do có lỗi trường", "warning")

                    # --- Global Submit (single-form mode only) ---
                    elif not table_mode and submit_selector and not row_result["errors"]:
                        submit_btn = page.locator(submit_selector).first
                        logger.info(f"Tương tác: Đang nhấn nút gửi (Submit) '{submit_selector}'")
                        submit_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(1000)
                        submit_btn.click(force=True)
                        if status: status.log("Đã nhấn nút Submit thành công")
                        page.wait_for_timeout(3000)

                except Exception as e:
                    row_result["errors"].append({"field": "row", "message": str(e)})
                    if status: status.log(f"Lỗi xử lý dòng {row_index}: {e}", "error")

                row_result["status"] = "failed" if row_result["errors"] else "completed"

                # Navigate back for next entry (only in single-form mode, not table mode)
                if not table_mode and index < len(df) - 1:
                    if status: status.log("Quay lại trang chính cho dòng tiếp theo...")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(2000)

            if status:
                if status.has_errors:
                    status.log("Đã xử lý xong nhưng có dòng/trường lỗi hoặc bị bỏ qua; hãy kiểm tra log trước khi xác nhận.", "warning")
                else:
                    status.log("Hoàn tất các thao tác; hãy kiểm tra xác nhận/lưu trên website.", "success")

            if status:
                status.is_running = False
    except Exception as e:
        if status:
            status.log(f"Lỗi hệ thống Playwright: {e}", "error")
        raise
    finally:
        if status:
            status.is_running = False
