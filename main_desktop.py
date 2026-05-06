import logging
import pandas as pd
from pywinauto import Application, Desktop
import time
import os
import sys
import pyautogui

# Ensure status tracking is consistent with main.py
from main import AutomationStatus

logger = logging.getLogger(__name__)

def run_desktop_automation_core(excel_path: str, app_identifier: str, mappings: dict, submit_selector: str, status: AutomationStatus = None, use_session: bool = False, open_form_trigger: str = ""):
    """
    Core engine for Desktop Automation. Supports Selector, Global Mode, and Coordinates.
    """
    if status:
        status.is_running = True
        status.log(f"Khởi động tự động hóa Desktop (Chế độ: {'Toàn màn hình' if not app_identifier else app_identifier})")

    try:
        df = pd.read_excel(excel_path, dtype=str).fillna("")
        if status: status.total_rows = len(df)
        
        # Connect to specific app or use global Desktop
        app_main = None
        global_desktop = Desktop(backend="uia")
        
        if app_identifier and app_identifier.upper() != "DESKTOP":
            try:
                import re
                found = False
                for win in global_desktop.windows():
                    title = win.window_text()
                    if app_identifier.lower() in title.lower():
                        app_main = win
                        app_main.set_focus()
                        found = True
                        logger.info(f"Đã tìm thấy và kết nối cửa sổ: {title}")
                        if status: status.log(f"✅ Đã kết nối: {title}")
                        break
                
                if not found:
                    logger.info(f"Không tìm thấy cửa sổ '{app_identifier}', thử khởi động file...")
                    app_instance = Application(backend="uia").start(app_identifier)
                    time.sleep(5)
                    app_main = app_instance.top_window()
                    app_main.set_focus()
            except Exception as e:
                logger.warning(f"Chế độ Toàn màn hình (Lý do: {e})")
                if status: status.log("⚠️ Chế độ Toàn màn hình.", "warning")

        for index, row in df.iterrows():
            if status:
                status.current_row = index + 1
                status.log(f"--- Đang xử lý dòng {index + 1} ---")

            # --- Fill fields ---
            for col, mapping_data in mappings.items():
                if col in row and row[col]:
                    val = str(row[col])
                    selector = mapping_data.get("selector") if isinstance(mapping_data, dict) else mapping_data
                    action_type = mapping_data.get("type", "text") if isinstance(mapping_data, dict) else "text"
                    if not selector: continue

                    try:
                        # --- Coordinate Mode Fallback ---
                        if selector.startswith("coord:"):
                            try:
                                coords = selector.replace("coord:", "").split(",")
                                rx, ry = float(coords[0]) / 100.0, float(coords[1]) / 100.0
                                rect = app_main.rectangle() if app_main else global_desktop.rectangle()
                                target_x = rect.left + int((rect.right - rect.left) * rx)
                                target_y = rect.top + int((rect.bottom - rect.top) * ry)
                                
                                pyautogui.click(target_x, target_y)
                                time.sleep(0.5) # Chờ focus ổn định
                                
                                if action_type == "text":
                                    # Xóa dữ liệu cũ một cách chắc chắn
                                    pyautogui.hotkey('ctrl', 'a')
                                    time.sleep(0.2)
                                    pyautogui.press('backspace')
                                    time.sleep(0.2)
                                    pyautogui.typewrite(val)
                                
                                if status: status.log(f"📍 Đã dùng tọa độ cho '{col}'")
                                continue
                            except Exception as coord_err:
                                logger.error(f"Lỗi tọa độ: {coord_err}")

                        # --- Selector Mode ---
                        ctrl = None
                        search_targets = []
                        if app_main: search_targets.append(app_main)
                        search_targets.append(global_desktop)

                        for target in search_targets:
                            strategies = [
                                {"auto_id": selector}, {"name": selector}, {"title": selector},
                                {"control_type": selector}, {"class_name": selector}
                            ]
                            for s in strategies:
                                try:
                                    candidate = target.child_window(**s)
                                    if candidate.exists(timeout=0.5):
                                        ctrl = candidate
                                        break
                                except: continue
                            if ctrl: break
                        
                        if not ctrl:
                            if status: status.log(f"Bỏ qua '{col}': Không tìm thấy '{selector}'", "warning")
                            continue

                        # Perform Action
                        if action_type == "click":
                            ctrl.click_input()
                            if status: status.log(f"🖱️ Đã click '{col}'")
                        elif action_type == "selection":
                            try: ctrl.select(val)
                            except: ctrl.set_edit_text(val)
                            if status: status.log(f"✅ Đã chọn '{val}'")
                        else:
                            try:
                                # Try to clear text if possible
                                ctrl.set_focus()
                                time.sleep(0.2)
                                ctrl.type_keys("^a{BACKSPACE}")
                                time.sleep(0.1)
                                ctrl.set_edit_text(val)
                            except:
                                ctrl.type_keys(val, with_spaces=True)
                            if status: status.log(f"✍️ Đã điền '{val}'")
                    
                    except Exception as e:
                        if status: status.log(f"Lỗi tại '{col}': {e}", "error")

            # --- Submit row ---
            if submit_selector:
                try:
                    time.sleep(1.0) # Chờ dữ liệu điền xong hoàn toàn
                    # Support coordinate submit
                    if submit_selector.startswith("coord:"):
                        coords = submit_selector.replace("coord:", "").split(",")
                        rx, ry = float(coords[0]) / 100.0, float(coords[1]) / 100.0
                        rect = app_main.rectangle() if app_main else global_desktop.rectangle()
                        tx = rect.left + int((rect.right - rect.left) * rx)
                        ty = rect.top + int((rect.bottom - rect.top) * ry)
                        
                        pyautogui.moveTo(tx, ty, duration=0.2)
                        pyautogui.click(tx, ty)
                        if status: status.log("🚀 Đã nhấn Submit (Tọa độ)")
                        time.sleep(1.5)
                    else:
                        btn = None
                        search_targets = []
                        if app_main: search_targets.append(app_main)
                        search_targets.append(global_desktop)

                        for target in search_targets:
                            for s in [{"title": submit_selector}, {"name": submit_selector}, {"auto_id": submit_selector}]:
                                try:
                                    candidate = target.child_window(**s)
                                    if candidate.exists(timeout=0.5):
                                        btn = candidate
                                        break
                                except: continue
                            if btn: break

                        if btn:
                            btn.click_input()
                            if status: status.log("🚀 Đã nhấn nút Submit")
                            time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Không thể nhấn nút Submit: {e}")

        if status: 
            status.log("Hoàn thành tự động hóa Desktop!", "success")
            status.is_running = False

    except Exception as e:
        if status: status.log(f"Lỗi hệ thống Desktop: {e}", "error")
        logger.error(f"Desktop automation error: {e}")
    finally:
        if status: status.is_running = False

def get_element_at_cursor():
    """Helper for Smart Picker: Identifying desktop element under mouse with coordinates."""
    try:
        import win32api
        x, y = win32api.GetCursorPos()
        desktop = Desktop(backend="uia")
        elem = desktop.from_point(x, y)
        
        # Lấy window chứa phần tử này để tính tọa độ phần trăm
        top_win = elem.top_level_parent()
        rect = top_win.rectangle()
        rel_x = int(((x - rect.left) / (rect.right - rect.left)) * 100)
        rel_y = int(((y - rect.top) / (rect.bottom - rect.top)) * 100)

        # Try to find the best identifier, if current element has nothing, try parents
        curr = elem
        best_id = ""
        best_name = ""
        for _ in range(3):
            best_id = getattr(curr.element_info, 'automation_id', "")
            best_name = getattr(curr.element_info, 'name', "")
            if best_id or best_name:
                break
            curr = curr.parent()
            if not curr: break

        return {
            "auto_id": best_id or "",
            "name": best_name or "",
            "control_type": getattr(elem.element_info, 'control_type', ""),
            "class_name": getattr(elem.element_info, 'class_name', ""),
            "rel_x": rel_x,
            "rel_y": rel_y,
            "rectangle": str(elem.rectangle())
        }
    except Exception as e:
        logger.error(f"Picker Error: {e}")
        return None
