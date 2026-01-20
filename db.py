"""
SQLite 数据库模块 - 任务持久化存储
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from config import BASE_DIR
from models import JobState, DownloadItem

# 数据库文件路径
DB_PATH = BASE_DIR / "jobs.db"

# 线程本地存储，每个线程一个连接
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """获取当前线程的数据库连接"""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            created_at REAL,
            updated_at REAL,
            progress REAL DEFAULT 0,
            message TEXT DEFAULT '',
            output_dir TEXT,
            zip_path TEXT,
            playlist_title TEXT,
            thumbnail_url TEXT,
            total_items INTEGER,
            current_item INTEGER,
            current_item_progress REAL DEFAULT 0,
            cancel_requested INTEGER DEFAULT 0,
            paused INTEGER DEFAULT 0,
            force_single INTEGER DEFAULT 0,
            download_items_json TEXT DEFAULT '[]'
        )
    """)
    conn.commit()


def save_job(job: JobState):
    """保存任务到数据库"""
    conn = get_connection()
    
    # 序列化 download_items
    items_json = json.dumps([item.to_dict() for item in job.download_items], ensure_ascii=False)
    
    conn.execute("""
        INSERT OR REPLACE INTO jobs (
            id, url, status, created_at, updated_at, progress, message,
            output_dir, zip_path, playlist_title, thumbnail_url,
            total_items, current_item, current_item_progress,
            cancel_requested, paused, force_single, download_items_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job.id, job.url, job.status, job.created_at, job.updated_at,
        job.progress, job.message, job.output_dir, job.zip_path,
        job.playlist_title, job.thumbnail_url, job.total_items,
        job.current_item, job.current_item_progress,
        1 if job.cancel_requested else 0,
        1 if job.paused else 0,
        1 if job.force_single else 0,
        items_json
    ))
    conn.commit()


def load_job(job_id: str) -> Optional[JobState]:
    """从数据库加载任务"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return _row_to_job(row)


def load_all_jobs() -> list[JobState]:
    """从数据库加载所有任务"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [_row_to_job(row) for row in rows]


def delete_job(job_id: str):
    """从数据库删除任务"""
    conn = get_connection()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()


def _row_to_job(row: sqlite3.Row) -> JobState:
    """将数据库行转换为 JobState 对象"""
    # 反序列化 download_items
    items_json = row["download_items_json"] or "[]"
    items_data = json.loads(items_json)
    download_items = [
        DownloadItem(
            index=item.get("index", 0),
            title=item.get("title", ""),
            url=item.get("url", ""),
            thumbnail=item.get("thumbnail"),
            status=item.get("status", "pending"),
            progress=item.get("progress", 0),
            error_msg=item.get("error_msg"),
        )
        for item in items_data
    ]
    
    job = JobState(
        id=row["id"],
        url=row["url"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        progress=row["progress"] or 0,
        message=row["message"] or "",
        output_dir=row["output_dir"],
        zip_path=row["zip_path"],
        playlist_title=row["playlist_title"],
        thumbnail_url=row["thumbnail_url"],
        total_items=row["total_items"],
        current_item=row["current_item"],
        current_item_progress=row["current_item_progress"] or 0,
        cancel_requested=bool(row["cancel_requested"]),
        download_items=download_items,
        paused=bool(row["paused"]),
        force_single=bool(row["force_single"]),
    )
    return job


# 初始化数据库
init_db()
