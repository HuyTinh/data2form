import os
import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from main import AutomationStatus, run_automation_core, run_mapping_plan_core
from mapping_plan import load_mapping_plan_workbook
import persistence
from request_security import ALLOWED_DEV_ORIGINS, is_loopback_origin, is_safe_mutation_request
from selector_picker import run_selector_picker as _run_selector_picker
from workbook_service import (
    DATA_CACHE,
    DATA_DIR,
    SHEET_CACHE,
    WORKBOOK_CACHE,
    clear_workbook_cache,
    find_uploaded_file as _find_uploaded_file,
    get_preview as _get_workbook_preview,
    upload_workbook,
)


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

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Data2Form API", lifespan=lifespan)

# Allow CORS for development with Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_DEV_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_cross_site_mutations(request, call_next):
    request_origin = f"{request.url.scheme}://{request.url.netloc}"
    if not is_loopback_origin(request_origin):
        return JSONResponse(status_code=403, content={"detail": "Data2Form is only available from loopback hosts"})
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if not is_safe_mutation_request(
            request.headers.get("origin"),
            request_origin,
            request.headers.get("sec-fetch-site"),
        ):
            return JSONResponse(status_code=403, content={"detail": "Cross-site mutations are not allowed"})
    return await call_next(request)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount React built assets if available
DIST_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(DIST_DIR) and os.path.exists(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    if os.path.exists("static/favicon.ico"):
        return FileResponse("static/favicon.ico")
    return FileResponse("static/favicon.png")

class PickRequest(BaseModel):
    url: str
    use_session: bool = False

class PickerTarget(BaseModel):
    id: str
    label: str

class PickSelectorsRequest(PickRequest):
    target_count: int = Field(ge=1, le=100)
    target_labels: list[str] = Field(default_factory=list)
    targets: list[PickerTarget] = Field(default_factory=list)

class RunRequest(BaseModel):
    filename: str
    url: str
    submit_selector: str = ""
    open_form_trigger: str = ""
    mappings: dict = Field(default_factory=dict)
    mapping_plan: dict | None = None
    use_session: bool = False
    table_mode: bool = False
    row_save_selector: str = ""
    row_save_timeout: int = 8000  # milliseconds


@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(DIST_DIR, "index.html")
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `npm run build` in the frontend directory.",
        ) from exc


DB_PATH = "automation.db"

def init_db():
    persistence.init_db(DB_PATH)

init_db()

@app.get("/api/presets")
def get_preset(url: str):
    return persistence.get_preset(url, DB_PATH)

@app.post("/api/presets")
def save_preset(req: dict):
    return persistence.save_preset(req, DB_PATH)

@app.get("/api/history")
def get_history():
    return persistence.get_history(DB_PATH)

@app.get("/api/history/{item_id}/logs")
def get_history_logs(item_id: int):
    return persistence.get_history_logs(item_id, DB_PATH)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    return upload_workbook(file)

@app.get("/api/download/{item_id}")
def download_history_file(item_id: int):
    import zipfile
    import io
    from fastapi.responses import StreamingResponse

    row = persistence.get_history_rel_path(item_id, DB_PATH)

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
    return clear_workbook_cache(filename)


@app.get("/api/preview")
def get_preview(filename: str, page: int = 1, page_size: int = 20, query: str = "", sheet_name: str | None = None):
    return _get_workbook_preview(filename, page, page_size, query, sheet_name)




@app.post("/api/pick-selector")
def pick_selector(req: PickRequest):
    selections = _run_selector_picker(req.url, req.use_session, [{"id": "single", "label": "Selector"}])
    return {"selector": selections[0]["selector"] if selections else None}


@app.post("/api/pick-selectors")
def pick_selectors(req: PickSelectorsRequest):
    if req.targets:
        targets = [{"id": target.id.strip(), "label": target.label.strip()} for target in req.targets]
        ids = [target["id"] for target in targets]
        if len(targets) != req.target_count or any(not target["id"] or not target["label"] for target in targets):
            raise HTTPException(status_code=422, detail="targets must provide a unique id and label for every requested field")
        if len(ids) != len(set(ids)):
            raise HTTPException(status_code=422, detail="target ids must be unique")
        allow_any_target = True
    else:
        if req.target_labels and len(req.target_labels) != req.target_count:
            raise HTTPException(status_code=422, detail="target_labels length must match target_count")
        targets = [
            {"id": str(index), "label": label or f"Ô {index + 1}"}
            for index, label in enumerate(req.target_labels[:req.target_count])
        ]
        if not targets:
            targets = [{"id": str(index), "label": f"Ô {index + 1}"} for index in range(req.target_count)]
        allow_any_target = False

    selections = _run_selector_picker(req.url, req.use_session, targets, allow_any_target)
    response = {"selectors": [selection["selector"] for selection in selections]}
    if req.targets:
        response["selections"] = selections
    return response


# Global status tracker
current_status = AutomationStatus()

@app.get("/api/status")
def get_status():
    normalized_logs = []
    for l in current_status.logs[-20:]:
        msg_text = l.get("message") or l.get("msg") or ""
        normalized_logs.append({
            "time": l.get("time", ""),
            "message": msg_text,
            "msg": msg_text,
            "level": l.get("level", "info")
        })
    return {
        "is_running": current_status.is_running,
        "current_row": current_status.current_row,
        "total_rows": current_status.total_rows,
        "logs": normalized_logs,
        "screenshots": current_status.screenshots,
        "row_results": current_status.row_results,
        "detail_results": current_status.detail_results,
    }

@app.post("/api/run")
def run_automation(req: RunRequest):
    if current_status.is_running:
        raise HTTPException(status_code=400, detail="Automation is already running")
        
    found_path = _find_uploaded_file(req.filename)
    if not found_path:
        raise HTTPException(status_code=404, detail="File not found")

    if req.mapping_plan is not None:
        try:
            load_mapping_plan_workbook(found_path, req.mapping_plan)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    
    file_path = found_path
    rel_path = os.path.relpath(found_path, DATA_DIR)
        
    # Reset status
    current_status.__init__()
    
    # Run in background thread
    def wrapped_run():
        import datetime
        start_time = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        logger.info(f"--- BẮT ĐẦU LUỒNG TỰ ĐỘNG HÓA ---")
        logger.info(f"File xử lý: {req.filename}")
        logger.info(f"URL mục tiêu: {req.url}")
        
        try:
            if req.mapping_plan is not None:
                run_mapping_plan_core(file_path, req.url, req.mapping_plan, current_status, req.use_session)
            else:
                run_automation_core(file_path, req.url, req.mappings, req.submit_selector, current_status, req.use_session, req.open_form_trigger, req.table_mode, req.row_save_selector, req.row_save_timeout)
        except Exception as e:
            logger.error(f"NGUY HIỂM: Luồng tự động hóa thất bại: {e}")
        finally:
            logger.info("Đang lưu lịch sử thực thi vào cơ sở dữ liệu...")
            final_status = "Success" if not current_status.has_errors else "Completed with errors"
            persistence.save_run_history(
                req.filename,
                rel_path,
                start_time,
                current_status.total_rows,
                final_status,
                current_status.logs,
                DB_PATH,
            )
            logger.info(f"--- LUỒNG TỰ ĐỘNG HÓA KẾT THÚC (Trạng thái: {final_status}) ---")

    logger.info("Đang chuyển tác vụ tự động hóa vào luồng chạy ngầm...")
    thread = threading.Thread(target=wrapped_run)
    thread.daemon = True
    thread.start()
    
    return {"status": "started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
