"""SQLite persistence for presets and automation history."""

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)
DEFAULT_DB_PATH = "automation.db"


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS presets (
        url TEXT PRIMARY KEY,
        submit_selector TEXT,
        use_session INTEGER,
        mappings TEXT,
        open_form_trigger TEXT DEFAULT '',
        mapping_plan TEXT,
        saved_at TEXT
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        rel_path TEXT,
        start_time TEXT,
        total_rows INTEGER,
        status TEXT,
        logs TEXT
    )""")
    try:
        cursor.execute("ALTER TABLE presets ADD COLUMN open_form_trigger TEXT DEFAULT ''")
    except Exception:
        pass
    preset_columns = {row[1] for row in cursor.execute("PRAGMA table_info(presets)").fetchall()}
    if "mapping_plan" not in preset_columns:
        cursor.execute("ALTER TABLE presets ADD COLUMN mapping_plan TEXT")
    conn.commit()
    conn.close()


def get_preset(url: str, db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM presets WHERE url = ?", (url,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["mappings"] = json.loads(result["mappings"])
    result["open_form_trigger"] = result.get("open_form_trigger", "") or ""
    result["mapping_plan"] = json.loads(result["mapping_plan"]) if result.get("mapping_plan") else None
    return result


def save_preset(request: dict[str, Any], db_path: str = DEFAULT_DB_PATH):
    logger.info(f"Đang lưu/cập nhật cấu hình cho URL: {request.get('url')}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""INSERT OR REPLACE INTO presets (url, submit_selector, use_session, mappings, open_form_trigger, mapping_plan, saved_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (
                  request['url'],
                  request.get('submit_selector', ''),
                  int(request.get('use_session', False)),
                  json.dumps(request.get('mappings', {})),
                  request.get('open_form_trigger', ''),
                  json.dumps(request['mapping_plan']) if request.get('mapping_plan') is not None else None,
                  request['saved_at'],
              ))
    conn.commit()
    conn.close()
    logger.info("Lưu cấu hình thành công.")
    return {"status": "saved"}


def get_history(db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, rel_path, start_time, total_rows, status FROM history ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_history_logs(item_id: int, db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT logs FROM history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return []
    try:
        logs = json.loads(row[0])
        normalized = []
        for entry in logs:
            if isinstance(entry, dict):
                message = entry.get("message") or entry.get("msg") or ""
                normalized.append({
                    "time": entry.get("time", ""),
                    "message": message,
                    "msg": message,
                    "level": entry.get("level", "info"),
                })
            else:
                message = str(entry)
                normalized.append({"time": "", "message": message, "msg": message, "level": "info"})
        return normalized
    except Exception:
        return []


def get_history_rel_path(item_id: int, db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT rel_path FROM history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def save_run_history(
    filename: str,
    rel_path: str,
    start_time: str,
    total_rows: int,
    status: str,
    logs: list[dict[str, Any]],
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO history (filename, rel_path, start_time, total_rows, status, logs)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (filename, rel_path, start_time, total_rows, status, json.dumps(logs)))
    conn.commit()
    conn.close()
