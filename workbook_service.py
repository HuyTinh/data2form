"""Workbook storage, inspection, preview caching, and cache invalidation."""

import datetime
import logging
import os
import shutil

import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)

DATA_DIR = "stores"
os.makedirs(DATA_DIR, exist_ok=True)

DATA_CACHE = {}
WORKBOOK_CACHE = {}
SHEET_CACHE = {}


def inspect_workbook(file_path: str):
    sheet_metadata = []
    first_frame = None
    with pd.ExcelFile(file_path) as workbook:
        for sheet_name in workbook.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet_name, dtype=str).fillna("")
            if first_frame is None:
                first_frame = frame
            sheet_metadata.append({
                "name": sheet_name,
                "columns": frame.columns.tolist(),
                "total_rows": len(frame),
            })
            del frame
    if first_frame is None:
        raise ValueError("Workbook contains no worksheets")
    return sheet_metadata, first_frame


def upload_workbook(file):
    today = datetime.date.today().isoformat()
    store_dir = os.path.join(DATA_DIR, today)
    os.makedirs(store_dir, exist_ok=True)

    base_name, ext = os.path.splitext(file.filename)
    unique_filename = file.filename
    counter = 1
    while os.path.exists(os.path.join(store_dir, unique_filename)):
        unique_filename = f"{base_name}_{counter}{ext}"
        counter += 1

    file_path = os.path.join(store_dir, unique_filename)
    logger.info(f"Đang tải file: {file.filename} -> Đã lưu thành: {unique_filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        sheet_metadata, first_frame = inspect_workbook(file_path)
        if not sheet_metadata:
            raise ValueError("Workbook contains no worksheets")
        WORKBOOK_CACHE[unique_filename] = sheet_metadata
        first_sheet_name = sheet_metadata[0]["name"]
        SHEET_CACHE[(unique_filename, first_sheet_name)] = first_frame
        DATA_CACHE[unique_filename] = first_frame
        return {
            "filename": unique_filename,
            "rel_path": os.path.join(today, unique_filename),
            "columns": first_frame.columns.tolist(),
            "total_rows": len(first_frame),
            "sheets": sheet_metadata,
        }
    except Exception as exc:
        DATA_CACHE.pop(unique_filename, None)
        WORKBOOK_CACHE.pop(unique_filename, None)
        for cache_key in [key for key in SHEET_CACHE if key[0] == unique_filename]:
            SHEET_CACHE.pop(cache_key, None)
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {exc}") from exc


def clear_workbook_cache(filename: str):
    was_cached = filename in DATA_CACHE or filename in WORKBOOK_CACHE
    DATA_CACHE.pop(filename, None)
    WORKBOOK_CACHE.pop(filename, None)
    for cache_key in [key for key in SHEET_CACHE if key[0] == filename]:
        was_cached = True
        SHEET_CACHE.pop(cache_key, None)
    if was_cached:
        logger.info(f"Cleared cache for file: {filename}")
        return {"status": "cleared"}
    return {"status": "not_in_cache"}


def find_uploaded_file(filename: str):
    for root, _dirs, files in os.walk(DATA_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


def get_cached_sheet(filename: str, sheet_name: str | None = None):
    sheet_metadata = WORKBOOK_CACHE.get(filename)
    if sheet_metadata is None:
        found_path = find_uploaded_file(filename)
        if not found_path:
            raise HTTPException(status_code=404, detail=f"File '{filename}' không thấy trong '{DATA_DIR}'")
        try:
            sheet_metadata, first_frame = inspect_workbook(found_path)
            WORKBOOK_CACHE[filename] = sheet_metadata
            DATA_CACHE[filename] = first_frame
            SHEET_CACHE[(filename, sheet_metadata[0]["name"])] = first_frame
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error reading Excel: {exc}") from exc

    if sheet_name is None:
        if filename in DATA_CACHE:
            return DATA_CACHE[filename]
        raise HTTPException(status_code=400, detail="Workbook contains no worksheets")

    if not any(sheet["name"] == sheet_name for sheet in sheet_metadata):
        raise HTTPException(status_code=404, detail=f"Worksheet '{sheet_name}' not found in '{filename}'")
    cache_key = (filename, sheet_name)
    if cache_key not in SHEET_CACHE:
        found_path = find_uploaded_file(filename)
        if not found_path:
            raise HTTPException(status_code=404, detail=f"File '{filename}' không thấy trong '{DATA_DIR}'")
        try:
            SHEET_CACHE[cache_key] = pd.read_excel(found_path, sheet_name=sheet_name, dtype=str).fillna("")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error reading worksheet '{sheet_name}': {exc}") from exc
    return SHEET_CACHE[cache_key]


def get_preview(filename: str, page: int = 1, page_size: int = 20, query: str = "", sheet_name: str | None = None):
    df = get_cached_sheet(filename, sheet_name)
    if query:
        mask = df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)
        df = df[mask]

    total_filtered = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": df.iloc[start:end].to_dict(orient="records"),
        "total": total_filtered,
    }
