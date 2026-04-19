import os
import shutil
import logging
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
from playwright.sync_api import sync_playwright

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Filter out frequent polling logs from uvicorn
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Check if the log is an access log and contains /api/status or /api/history
        return "/api/status" not in record.getMessage() and "/api/history" not in record.getMessage()

# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# Safer encoding setup
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cleanup only error screenshots on startup, keep data/ for history
    if os.path.exists("static"):
        for f in os.listdir("static"):
            if f.endswith(".png"):
                try: os.remove(os.path.join("static", f))
                except: pass
    yield

app = FastAPI(title="Data2Form API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

DATA_DIR = "stores"
os.makedirs(DATA_DIR, exist_ok=True)

class PickRequest(BaseModel):
    url: str
    use_session: bool = False

class RunRequest(BaseModel):
    filename: str
    url: str
    submit_selector: str
    open_form_trigger: str = ""
    mappings: dict
    use_session: bool = False

@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")

import sqlite3

DB_PATH = "automation.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Table for Presets (URL -> Config)
    c.execute("""CREATE TABLE IF NOT EXISTS presets (
        url TEXT PRIMARY KEY,
        submit_selector TEXT,
        use_session INTEGER,
        mappings TEXT,
        open_form_trigger TEXT DEFAULT '',
        saved_at TEXT
    )""")
    # Table for History
    c.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        rel_path TEXT,
        start_time TEXT,
        total_rows INTEGER,
        status TEXT,
        logs TEXT
    )""")
    # Migrate: add open_form_trigger column if not exists
    try:
        c.execute("ALTER TABLE presets ADD COLUMN open_form_trigger TEXT DEFAULT ''")
    except:
        pass  # Column already exists
    conn.commit()
    conn.close()

init_db()

DATA_CACHE = {}

@app.get("/api/presets")
def get_preset(url: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM presets WHERE url = ?", (url,))
    row = c.fetchone()
    conn.close()
    if row:
        res = dict(row)
        import json
        res['mappings'] = json.loads(res['mappings'])
        res['open_form_trigger'] = res.get('open_form_trigger', '') or ''
        return res
    return None

@app.post("/api/presets")
def save_preset(req: dict):
    logger.info(f"Đang lưu/cập nhật cấu hình cho URL: {req.get('url')}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    import json
    c.execute("""INSERT OR REPLACE INTO presets (url, submit_selector, use_session, mappings, open_form_trigger, saved_at)
                 VALUES (?, ?, ?, ?, ?, ?)""", 
              (req['url'], req['submit_selector'], int(req['use_session']), json.dumps(req['mappings']), req.get('open_form_trigger', ''), req['saved_at']))
    conn.commit()
    conn.close()
    logger.info("Lưu cấu hình thành công.")
    return {"status": "saved"}

@app.get("/api/history")
def get_history():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, filename, rel_path, start_time, total_rows, status FROM history ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

import json

@app.get("/api/history/{item_id}/logs")
def get_history_logs(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT logs FROM history WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    import datetime
    today = datetime.date.today().isoformat()
    store_dir = os.path.join(DATA_DIR, today)
    os.makedirs(store_dir, exist_ok=True)
    
    # Clean filename handling
    base_name, ext = os.path.splitext(file.filename)
    unique_filename = file.filename
    counter = 1
    
    # Check if file exists, if so, append (1), (2)...
    while os.path.exists(os.path.join(store_dir, unique_filename)):
        unique_filename = f"{base_name}_{counter}{ext}"
        counter += 1
        
    file_path = os.path.join(store_dir, unique_filename)
    logger.info(f"Đang tải file: {file.filename} -> Đã lưu thành: {unique_filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        df = pd.read_excel(file_path, dtype=str).fillna("")
        DATA_CACHE[unique_filename] = df
        columns = df.columns.tolist()
        return {
            "filename": unique_filename, 
            "rel_path": os.path.join(today, unique_filename),
            "columns": columns,
            "total_rows": len(df)
        }
    except Exception as e:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")

@app.get("/api/download/{item_id}")
def download_history_file(item_id: int):
    import zipfile
    import io
    from fastapi.responses import StreamingResponse

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rel_path FROM history WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="History record not found")
    
    rel_path = row[0]
    full_path = os.path.join(DATA_DIR, rel_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File no longer exists on disk")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.write(full_path, os.path.basename(full_path))
    
    zip_buffer.seek(0)
    filename_zip = f"{os.path.basename(full_path)}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={filename_zip}"}
    )

@app.post("/api/clear-cache")
def clear_cache(filename: str):
    if filename in DATA_CACHE:
        del DATA_CACHE[filename]
        logger.info(f"Cleared cache for file: {filename}")
        return {"status": "cleared"}
    return {"status": "not_in_cache"}
@app.get("/api/preview")
def get_preview(filename: str, page: int = 1, page_size: int = 20, query: str = ""):
    if filename not in DATA_CACHE:
        found_path = None
        if os.path.exists(DATA_DIR):
            for root, dirs, files in os.walk(DATA_DIR):
                if filename in files:
                    found_path = os.path.join(root, filename)
                    break
        
        if found_path:
            try:
                DATA_CACHE[filename] = pd.read_excel(found_path, dtype=str).fillna("")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error reading Excel: {e}")
        else:
            raise HTTPException(status_code=404, detail=f"File '{filename}' không thấy trong '{DATA_DIR}'")
            
    df = DATA_CACHE[filename]
    
    # Filtering
    if query:
        # Filter trên tất cả các cột
        mask = df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)
        df = df[mask]
    
    total_filtered = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    
    rows = df.iloc[start:end].to_dict(orient="records")
    return {
        "data": rows,
        "total": total_filtered
    }

@app.post("/api/pick-selector")
def pick_selector(req: PickRequest):
    inject_script = r"""
    () => {
        return new Promise((resolve) => {
            // Container for UI
            const ui = document.createElement('div');
            ui.id = 'd2f-picker-ui';
            Object.assign(ui.style, {
                position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)',
                zIndex: '2147483647', background: 'rgba(255, 255, 255, 0.95)',
                padding: '12px 20px', borderRadius: '12px', boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
                display: 'flex', gap: '15px', alignItems: 'center',
                fontFamily: '"Outfit", sans-serif', border: '1px solid #3498db',
                backdropFilter: 'blur(10px)', transition: 'all 0.3s ease'
            });

            const statusInfo = document.createElement('div');
            statusInfo.innerHTML = '<strong style="color: #2c3e50;">D2F Picker:</strong> <span id="picker-mode-text" style="color: #e67e22;">Đang điều hướng...</span>';
            statusInfo.style.fontSize = '14px';

            const pickBtn = document.createElement('button');
            pickBtn.innerText = '🎯 Bắt đầu chọn';
            Object.assign(pickBtn.style, {
                padding: '8px 16px', background: '#3498db', color: 'white',
                border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold'
            });

            const cancelBtn = document.createElement('button');
            cancelBtn.innerText = 'Đóng';
            Object.assign(cancelBtn.style, {
                padding: '8px 16px', background: '#95a5a6', color: 'white',
                border: 'none', borderRadius: '6px', cursor: 'pointer'
            });

            ui.appendChild(statusInfo);
            ui.appendChild(pickBtn);
            ui.appendChild(cancelBtn);
            document.body.appendChild(ui);

            // Overlay for picking
            const overlay = document.createElement('div');
            Object.assign(overlay.style, {
                position: 'fixed', top: '0', left: '0', width: '100vw', height: '100vh',
                zIndex: '2147483646', cursor: 'crosshair', pointerEvents: 'none',
                border: '4px solid #e67e22', boxSizing: 'border-box', display: 'none'
            });
            document.body.appendChild(overlay);

            let isPicking = false;
            let lastHovered = null;
            let originalOutline = '';

            const getPath = (el) => {
                if (el.id) return `#${CSS.escape(el.id)}`;
                if (el.name) return `[name="${CSS.escape(el.name)}"]`;
                if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\s+/).filter(c => c && !c.includes(':'));
                    for (let cls of classes) {
                        try {
                            const selector = `.${CSS.escape(cls)}`;
                            if (document.querySelectorAll(selector).length === 1) return selector;
                        } catch(e) {}
                    }
                }
                let path = el.tagName.toLowerCase();
                let parent = el.parentNode;
                if (parent && parent !== document) {
                    let children = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                    if (children.length > 1) {
                        let index = children.indexOf(el) + 1;
                        path += `:nth-of-type(${index})`;
                    }
                    path = getPath(parent) + ' > ' + path;
                }
                return path;
            };

            const mouseMoveHandler = (e) => {
                if (!isPicking) return;
                const el = document.elementFromPoint(e.clientX, e.clientY);
                if (el && el !== overlay && !ui.contains(el) && el !== lastHovered) {
                    if (lastHovered) lastHovered.style.outline = originalOutline;
                    lastHovered = el;
                    originalOutline = el.style.outline;
                    el.style.outline = '3px solid #e74c3c';
                }
            };

            const clickHandler = (e) => {
                if (!isPicking) return;
                if (ui.contains(e.target)) return;

                try {
                    e.preventDefault(); e.stopPropagation();
                    let el = document.elementFromPoint(e.clientX, e.clientY);
                    
                    if (el && el !== overlay && !ui.contains(el)) {
                        const tagName = el.tagName ? el.tagName.toUpperCase() : '';
                        if (!['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(tagName)) {
                            const innerInput = el.querySelector('input, textarea, select, button');
                            if (innerInput) el = innerInput;
                        }

                        const selector = getPath(el);
                        cleanup();
                        resolve(selector);
                    }
                } catch (err) { console.error('Picker Error:', err); }
            };

            const cleanup = () => {
                if (lastHovered) lastHovered.style.outline = originalOutline;
                window.removeEventListener('mousemove', mouseMoveHandler);
                window.removeEventListener('click', clickHandler, true);
                if (document.body.contains(overlay)) document.body.removeChild(overlay);
                if (document.body.contains(ui)) document.body.removeChild(ui);
            };

            pickBtn.onclick = () => {
                isPicking = !isPicking;
                if (isPicking) {
                    pickBtn.innerText = '⏸️ Đang chọn (Click để dừng)';
                    pickBtn.style.background = '#e67e22';
                    overlay.style.display = 'block';
                    document.getElementById('picker-mode-text').innerText = 'Hãy nhấp vào phần tử cần chọn';
                    document.getElementById('picker-mode-text').style.color = '#e74c3c';
                } else {
                    pickBtn.innerText = '🎯 Bắt đầu chọn';
                    pickBtn.style.background = '#3498db';
                    overlay.style.display = 'none';
                    document.getElementById('picker-mode-text').innerText = 'Đang điều hướng...';
                    document.getElementById('picker-mode-text').style.color = '#e67e22';
                    if (lastHovered) lastHovered.style.outline = originalOutline;
                }
            };

            cancelBtn.onclick = () => {
                cleanup();
                resolve(null);
            };

            window.addEventListener('mousemove', mouseMoveHandler);
            window.addEventListener('click', clickHandler, true);
        });
    }
    """
    
    # Use a persistent context to remember login sessions if requested
    user_data_dir = os.path.join(os.getcwd(), ".browser_session")
    
    with sync_playwright() as p:
        browser = None
        context = None
        try:
            if req.use_session:
                logger.info(f"Khởi động bộ chọn (Persistent Context) cho URL: {req.url}")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    no_viewport=True,
                    ignore_https_errors=True
                )
                page = context.pages[0] if context.pages else context.new_page()
            else:
                logger.info(f"Khởi động bộ chọn (Clean Context) cho URL: {req.url}")
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
            
            page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
            logger.info("Đã tải xong trang. Chờ người dùng chọn phần tử...")
            selector = page.evaluate(inject_script)
            logger.info(f"Người dùng đã chọn Selector: {selector}")
            return {"selector": selector}
        except Exception as e:
            logger.error(f"Lỗi bộ chọn: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
            logger.info("Đã đóng phiên trình duyệt bộ chọn.")

import threading
from main import run_automation_core, AutomationStatus

# Global status tracker
current_status = AutomationStatus()

@app.get("/api/status")
def get_status():
    return {
        "is_running": current_status.is_running,
        "current_row": current_status.current_row,
        "total_rows": current_status.total_rows,
        "logs": current_status.logs[-20:], # Return last 20 logs
        "screenshots": current_status.screenshots
    }

@app.post("/api/run")
def run_automation(req: RunRequest):
    if current_status.is_running:
        raise HTTPException(status_code=400, detail="Automation is already running")
        
    # Tìm file thực tế trên ổ đĩa (vì có thể nằm trong folder ngày)
    found_path = None
    for root, dirs, files in os.walk(DATA_DIR):
        if req.filename in files:
            found_path = os.path.join(root, req.filename)
            break
            
    if not found_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = found_path
    rel_path = os.path.relpath(found_path, DATA_DIR)
        
    # Reset status
    current_status.__init__()
    
    # Run in background thread
    def wrapped_run():
        import datetime
        import json
        start_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        logger.info(f"--- BẮT ĐẦU LUỒNG TỰ ĐỘNG HÓA ---")
        logger.info(f"File xử lý: {req.filename}")
        logger.info(f"URL mục tiêu: {req.url}")
        
        try:
            run_automation_core(file_path, req.url, req.mappings, req.submit_selector, current_status, req.use_session, req.open_form_trigger)
        except Exception as e:
            logger.error(f"NGUY HIỂM: Luồng tự động hóa thất bại: {e}")
        finally:
            logger.info("Đang lưu lịch sử thực thi vào cơ sở dữ liệu...")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            final_status = "Success" if all(l['level'] != 'error' for l in current_status.logs) else "Completed with errors"
            c.execute("""INSERT INTO history (filename, rel_path, start_time, total_rows, status, logs)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (req.filename, rel_path, start_time, current_status.total_rows, 
                       final_status, json.dumps(current_status.logs)))
            conn.commit()
            conn.close()
            logger.info(f"--- LUỒNG TỰ ĐỘNG HÓA KẾT THÚC (Trạng thái: {final_status}) ---")

    logger.info("Đang chuyển tác vụ tự động hóa vào luồng chạy ngầm...")
    thread = threading.Thread(target=wrapped_run)
    thread.daemon = True
    thread.start()
    
    return {"status": "started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

