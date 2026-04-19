import logging
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import sys
import os
import threading

# Configure logging at the top
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_encoding():
    """Ensure stdout supports UTF-8 for Vietnamese characters."""
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class AutomationStatus:
    def __init__(self):
        self.is_running = False
        self.current_row = 0
        self.total_rows = 0
        self.logs = []
        self.screenshots = []

    def log(self, message, level="info"):
        self.logs.append({"msg": message, "level": level})
        logger.info(message)

def run_automation_core(excel_path: str, url: str, mappings: dict, submit_selector: str, status: AutomationStatus = None, use_session: bool = False, open_form_trigger: str = ""):
    """
    Core engine for automation with status tracking and error handling.
    """
    setup_encoding()
    if status:
        status.is_running = True
        status.log(f"Khởi động tiến trình cho file: {os.path.basename(excel_path)}")
    
    try:
        df = pd.read_excel(excel_path, dtype=str)
        df = df.fillna("")
        if status:
            status.total_rows = len(df)
    except Exception as e:
        if status: status.log(f"Lỗi đọc file: {e}", "error")
        raise

    try:
        with sync_playwright() as p:
            browser = None
            context = None
            logger.info("Đang khởi tạo engine đồng bộ Playwright...")
            
            if use_session:
                user_data_dir = os.path.join(os.getcwd(), ".browser_session")
                logger.info(f"Sử dụng Persistent Context: {user_data_dir}")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    no_viewport=True,
                    ignore_https_errors=True
                )
                page = context.pages[0] if context.pages else context.new_page()
            else:
                browser = p.chromium.launch(headless=False)
                logger.info("Đã mở trình duyệt Chromium (Chế độ hiển thị: Có)")
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
            
            logger.info("Đã tạo phiên trình duyệt và trang mới.")

            if status: status.log(f"Đang mở trang: {url}")
            try:
                page.goto(url, wait_until="load", timeout=60000)
                page.wait_for_timeout(3000) 
            except Exception as e:
                if status: status.log(f"Lỗi tải trang: {e}", "error")
                if context: context.close()
                if browser: browser.close()
                raise

            for index, row in df.iterrows():
                if status:
                    status.current_row = index + 1
                    status.log(f"--- Đang xử lý dòng {index + 1} ---")
                
                try:
                    # --- Step 0: Click global trigger to open modal/popup if specified ---
                    if open_form_trigger:
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

                    for col, mapping_data in mappings.items():
                        if col in row and row[col]:
                            val = str(row[col])
                            try:
                                # Handle backward compatibility
                                if isinstance(mapping_data, dict):
                                    selector = mapping_data.get("selector", "")
                                    action_type = mapping_data.get("type", "text")
                                else:
                                    selector = mapping_data
                                    action_type = "text"

                                if not selector: continue

                                # --- Step 2: Interact with the target element ---
                                el = page.locator(selector).first
                                try:
                                    el.wait_for(state="visible", timeout=5000)
                                    el.scroll_into_view_if_needed()
                                except:
                                    if status: status.log(f"Bỏ qua '{col}': Không hiển thị", "warning")
                                    continue

                                if action_type == "click":
                                    # Support multiple delimiters: / , ;
                                    import re
                                    items = [i.strip() for i in re.split(r'[/,;]', val) if i.strip()]
                                    
                                    for item in items:
                                        if item.lower() in ['x', 'v', '1', 'yes', 'true', 'checked']:
                                            el.click()
                                            if status: status.log(f"🖱️ Click trực tiếp '{col}'")
                                        else:
                                            try:
                                                # Exact text match with auto-scroll
                                                target = el.get_by_text(item, exact=True)
                                                if target.count() == 0:
                                                    target = page.get_by_text(item, exact=True)
                                                
                                                if target.count() > 0:
                                                    target.first.scroll_into_view_if_needed()
                                                    target.first.click()
                                                    if status: status.log(f"🖱️ Click chọn '{item}'")
                                                else:
                                                    el.click() # Fallback
                                            except:
                                                el.click()
                                    page.wait_for_timeout(300)

                                elif action_type == "selection":
                                    import re
                                    items = [i.strip() for i in re.split(r'[/,;]', val) if i.strip()]
                                    for item in items:
                                        try:
                                            # Strategy 1: Native HTML Select
                                            el.select_option(label=item, timeout=1000)
                                            if status: status.log(f"Chọn '{item}' (Native)")
                                        except:
                                            # Strategy 2: Custom Dropdown (AntD, MUI, etc.)
                                            el.click()
                                            page.wait_for_timeout(500)
                                            
                                            try:
                                                # Try to find and click the item by text on the whole page (Portals)
                                                option = page.get_by_text(item, exact=True).first
                                                if option.count() > 0:
                                                    option.scroll_into_view_if_needed()
                                                    option.click()
                                                    if status: status.log(f"Chọn '{item}'")
                                                else:
                                                    # Strategy 3: Searchable dropdown (Type + Enter)
                                                    el.type(item, delay=50)
                                                    page.wait_for_timeout(500)
                                                    page.keyboard.press("ArrowDown")
                                                    page.keyboard.press("Enter")
                                                    if status: status.log(f"Chọn '{item}' (Search)")
                                            except:
                                                page.keyboard.press("Enter")
                                        page.wait_for_timeout(300)
                                elif action_type == "upload":
                                    f_path = val.strip()
                                    if os.path.exists(f_path):
                                        try:
                                            # Strategy 1: Direct set (best for hidden inputs)
                                            el.set_input_files(f_path)
                                            if status: status.log(f"Đã upload: {os.path.basename(f_path)}")
                                        except:
                                            # Strategy 2: File Chooser
                                            try:
                                                with page.expect_file_chooser(timeout=3000) as fc_info:
                                                    el.click()
                                                file_chooser = fc_info.value
                                                file_chooser.set_files(f_path)
                                                if status: status.log(f"Đã upload (Chooser): {os.path.basename(f_path)}")
                                            except Exception as fe:
                                                if status: status.log(f"Lỗi upload: {fe}", "error")
                                    else:
                                        if status: status.log(f"File không thấy: {f_path}", "warning")
                                
                                else:
                                    # Default: text input
                                    # GUARD: Don't try to fill file inputs
                                    is_file_input = el.evaluate("node => node.tagName === 'INPUT' && node.type === 'file'")
                                    if is_file_input:
                                        if status: status.log(f"⚠️ '{col}' là ô File, hãy chọn loại 'Upload' thay vì 'Text'", "warning")
                                        continue

                                    el.click()
                                    page.wait_for_timeout(200)
                                    try:
                                        el.fill("")
                                        el.type(val, delay=100)
                                        if status: status.log(f"Điền '{val}' vào '{col}'")
                                    except Exception as fe:
                                        # If fill fails (e.g. read-only but focusable), try typing directly
                                        el.type(val, delay=100)
                                        if status: status.log(f"Gõ '{val}' vào '{col}'")
                                    page.wait_for_timeout(300)
                            except Exception as e:
                                if status: status.log(f"Lỗi tại '{col}': {e}", "error")

                    # Submit ONCE per row after all fields are filled
                    if submit_selector:
                        submit_btn = page.locator(submit_selector).first
                        logger.info(f"Tương tác: Đang nhấn nút gửi (Submit) '{submit_selector}'")
                        submit_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(1000)
                        submit_btn.click(force=True)
                        if status: status.log("Đã nhấn nút Submit thành công")
                        page.wait_for_timeout(3000)
                        
                except Exception as e:
                    if status: status.log(f"Lỗi xử lý dòng {index+1}: {e}", "error")

                # Navigate back for next entry if not the last one
                if index < len(df) - 1:
                    if status: status.log("Quay lại trang chính cho dòng tiếp theo...")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(2000)

            if status: 
                status.log("Hoàn thành tất cả dữ liệu!", "success")
            
            if context: context.close()
            if browser: browser.close()
            if status:
                status.is_running = False
    except Exception as e:
        if status: 
            status.log(f"Lỗi hệ thống Playwright: {e}", "error")
        raise
    finally:
        if status:
            status.is_running = False

