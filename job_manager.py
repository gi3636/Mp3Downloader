"""
下载任务管理器

负责:
- 创建、取消、删除下载任务
- 管理下载进程
- 追踪下载进度
- 打包 ZIP 文件
"""

import os
import re
import shutil
import signal
import threading
import time
import uuid
import zipfile
from pathlib import Path
from subprocess import PIPE, Popen
from collections import deque

from config import ARCHIVE_FILE, JOBS_DIR, YTDLP_BIN, PROXY_URL
import db
from models import JobState, DownloadItem
from settings_service import get_download_dir
from tracks_service import write_job_meta, write_track_meta
from ytdlp_service import (
    fetch_playlist_metadata,
    fetch_single_metadata,
    looks_like_playlist_url,
    select_best_thumbnail_url,
)


# 正则表达式: 匹配下载进度百分比
# yt-dlp 输出格式: [download]  45.2% of 3.45MiB 或 [download] 100% of 3.45MiB
_PROGRESS_RE = re.compile(r"\[download\]\s+(?P<pct>\d+(?:\.\d+)?)%")

# 正则表达式: 匹配 ffmpeg 转换进度 (提取音频时)
# 格式: size=    1024kB time=00:01:23.45 bitrate= 128.0kbits/s
_FFMPEG_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

# 正则表达式: 匹配当前下载项目 (如 "Downloading item 3 of 10")
_ITEM_RE = re.compile(
    r"\[download\]\s+Downloading\s+(?:item|video)\s+(?P<idx>\d+)\s+of\s+(?P<total>\d+)",
    re.IGNORECASE,
)

# 并发下载数（默认 5，可通过环境变量调整）
_SELECTED_DOWNLOAD_CONCURRENCY = max(1, min(15, int(os.environ.get("MP3DL_SELECTED_CONCURRENCY", "5"))))
# 并行下载片段数（加速单个视频下载）
_CONCURRENT_FRAGMENTS = max(1, min(10, int(os.environ.get("MP3DL_CONCURRENT_FRAGMENTS", "4"))))


class JobManager:
    """
    下载任务管理器
    
    线程安全，支持并发任务管理
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}
        self._procs: dict[str, set[Popen]] = {}
        
        # 从数据库加载已有任务
        self._load_jobs_from_db()
        
        # 启动时自动清理超过 7 天的旧任务
        self._auto_cleanup_on_start()

    def _auto_cleanup_on_start(self):
        """启动时自动清理超过 7 天的旧任务"""
        try:
            result = self.cleanup_old_jobs(max_age_days=7)
            if result['deleted_count'] > 0:
                print(f"[JobManager] 自动清理了 {result['deleted_count']} 个旧任务，释放 {result['freed_mb']} MB")
        except Exception as e:
            print(f"[JobManager] 自动清理失败: {e}")

    def _load_jobs_from_db(self):
        """从数据库加载已有任务"""
        try:
            jobs = db.load_all_jobs()
            for job in jobs:
                # 只加载非运行中的任务（运行中的任务需要重新开始）
                if job.status in ('done', 'error', 'canceled'):
                    self._jobs[job.id] = job
                elif job.status in ('running', 'queued'):
                    # 运行中的任务标记为已取消（因为服务重启了）
                    job.status = 'canceled'
                    job.message = '服务重启，任务已取消'
                    self._jobs[job.id] = job
                    db.save_job(job)
        except Exception as e:
            print(f"加载任务失败: {e}")

    def _save_job(self, job: JobState):
        """保存任务到数据库"""
        try:
            db.save_job(job)
        except Exception as e:
            print(f"保存任务失败: {e}")

    # ========== 公共接口 ==========

    def create_job(self, url: str, force_single: bool = False) -> str:
        """
        创建新的下载任务 (下载整个播放列表)
        
        Args:
            url: YouTube 链接
            force_single: 强制作为单曲下载，忽略播放列表参数
            
        Returns:
            任务 ID
        """
        job_id = uuid.uuid4().hex
        job = JobState(id=job_id, url=url, message="已创建任务")
        job.force_single = force_single
        
        with self._lock:
            self._jobs[job_id] = job
        
        # 保存到数据库
        self._save_job(job)

        # 启动后台下载线程
        thread = threading.Thread(target=self._run_job, args=(job_id, None), daemon=True)
        thread.start()
        
        return job_id

    def create_job_with_urls(self, playlist_url: str, video_urls: list[str], video_titles: list[str] | None = None, video_thumbnails: list[str] | None = None) -> str:
        """
        创建新的下载任务 (只下载选中的曲目)
        
        Args:
            playlist_url: 播放列表 URL (用于获取元数据)
            video_urls: 选中的视频 URL 列表
            video_titles: 选中的视频标题列表
            video_thumbnails: 选中的视频封面列表
            
        Returns:
            任务 ID
        """
        job_id = uuid.uuid4().hex
        
        # 创建下载项列表
        download_items = []
        for idx, url in enumerate(video_urls):
            title = video_titles[idx] if video_titles and idx < len(video_titles) else f"Track {idx + 1}"
            thumbnail = video_thumbnails[idx] if video_thumbnails and idx < len(video_thumbnails) else None
            download_items.append(DownloadItem(
                index=idx + 1,
                title=title,
                url=url,
                thumbnail=thumbnail,
                status="pending"
            ))
        
        job = JobState(
            id=job_id, 
            url=playlist_url, 
            message=f"已创建任务 (选中 {len(video_urls)} 首)",
            total_items=len(video_urls),
            download_items=download_items,
        )
        
        with self._lock:
            self._jobs[job_id] = job
        
        # 保存到数据库
        self._save_job(job)

        # 启动后台下载线程
        thread = threading.Thread(target=self._run_job, args=(job_id, video_urls), daemon=True)
        thread.start()
        
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        """获取任务状态"""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobState]:
        """获取所有任务列表"""
        with self._lock:
            return list(self._jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        """
        取消下载任务
        
        Returns:
            是否成功找到并取消任务
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            
            job.cancel_requested = True
            
            if job.status == "queued":
                job.status = "canceled"
                job.message = "已取消"
            elif job.status == "running":
                job.status = "canceling"
                job.message = "取消中..."
            
            job.updated_at = time.time()

        self._terminate_process(job_id)
        return True

    def pause_job(self, job_id: str) -> bool:
        """暂停整个下载任务"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.paused = True
            job.message = "已暂停"
            # 将正在下载的项标记为暂停（终止进程后会停在该状态）
            for it in job.download_items:
                if it.status == "downloading":
                    it.status = "paused"
            self._update_progress_from_items(job)
            job.updated_at = time.time()

        # 立即终止该任务所有下载子进程（并发下载时必须这样才能真正“暂停”）
        self._terminate_process(job_id)
        return True

    def resume_job(self, job_id: str) -> bool:
        """继续整个下载任务"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.paused = False
            job.message = "继续下载"
            job.updated_at = time.time()
        return True

    def pause_item(self, job_id: str, item_index: int) -> bool:
        """暂停单个下载项"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.paused_items.add(item_index)
            # 更新该项状态
            for item in job.download_items:
                if item.index == item_index and item.status == "pending":
                    item.status = "paused"
            job.updated_at = time.time()
        return True

    def resume_item(self, job_id: str, item_index: int) -> bool:
        """继续单个下载项"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.paused_items.discard(item_index)
            # 更新该项状态
            for item in job.download_items:
                if item.index == item_index and item.status == "paused":
                    item.status = "pending"
            job.updated_at = time.time()
        return True

    def delete_job(self, job_id: str) -> None:
        """删除任务及其所有文件"""
        with self._lock:
            job = self._jobs.get(job_id)
            output_dir = job.output_dir if job else None

        # 如果任务正在运行，先取消
        if job and job.status in {"running", "canceling"}:
            with self._lock:
                job.cancel_requested = True
                job.status = "canceling"
                job.message = "取消中..."
                job.updated_at = time.time()
            
            self._terminate_process(job_id)
            time.sleep(0.2)

        # 从内存中移除
        with self._lock:
            self._procs.pop(job_id, None)
            self._jobs.pop(job_id, None)
        
        # 从数据库中删除
        try:
            db.delete_job(job_id)
        except Exception as e:
            print(f"删除任务数据库记录失败: {e}")

        # 删除任务目录
        job_dir = JOBS_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

        # 删除下载目录
        if output_dir:
            try:
                out_path = Path(output_dir)
                if out_path.exists():
                    shutil.rmtree(out_path, ignore_errors=True)
            except Exception:
                pass

    def invalidate_zip(self, job_id: str) -> None:
        """标记 ZIP 文件需要重新生成 (当删除曲目后调用)"""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.zip_path:
                job.zip_path = None
                job.updated_at = time.time()

    def cleanup_old_jobs(self, max_age_days: int = 7) -> dict:
        """
        清理超过指定天数的已完成任务
        
        Args:
            max_age_days: 最大保留天数，默认 7 天
            
        Returns:
            清理结果统计
        """
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        jobs_to_delete = []
        with self._lock:
            for job_id, job in self._jobs.items():
                # 只清理已完成/已取消/错误的任务
                if job.status not in ('done', 'canceled', 'error'):
                    continue
                # 检查任务年龄
                age = now - job.updated_at
                if age > max_age_seconds:
                    jobs_to_delete.append(job_id)
        
        deleted_count = 0
        freed_bytes = 0
        
        for job_id in jobs_to_delete:
            # 计算释放的空间
            job_dir = JOBS_DIR / job_id
            if job_dir.exists():
                for f in job_dir.rglob('*'):
                    if f.is_file():
                        freed_bytes += f.stat().st_size
            
            # 删除任务
            self.delete_job(job_id)
            deleted_count += 1
        
        return {
            'deleted_count': deleted_count,
            'freed_bytes': freed_bytes,
            'freed_mb': round(freed_bytes / (1024 * 1024), 2),
        }

    def cleanup_all_completed_jobs(self) -> dict:
        """
        清理所有已完成的任务（一键清理）
        
        Returns:
            清理结果统计
        """
        jobs_to_delete = []
        with self._lock:
            for job_id, job in self._jobs.items():
                # 只清理已完成/已取消/错误的任务
                if job.status in ('done', 'canceled', 'error'):
                    jobs_to_delete.append(job_id)
        
        deleted_count = 0
        freed_bytes = 0
        
        for job_id in jobs_to_delete:
            # 计算释放的空间
            job_dir = JOBS_DIR / job_id
            if job_dir.exists():
                for f in job_dir.rglob('*'):
                    if f.is_file():
                        freed_bytes += f.stat().st_size
            
            # 删除任务
            self.delete_job(job_id)
            deleted_count += 1
        
        return {
            'deleted_count': deleted_count,
            'freed_bytes': freed_bytes,
            'freed_mb': round(freed_bytes / (1024 * 1024), 2),
        }

    def get_disk_usage(self) -> dict:
        """
        获取任务目录的磁盘使用情况
        
        Returns:
            磁盘使用统计
        """
        total_bytes = 0
        job_count = 0
        
        if JOBS_DIR.exists():
            for job_dir in JOBS_DIR.iterdir():
                if job_dir.is_dir():
                    job_count += 1
                    for f in job_dir.rglob('*'):
                        if f.is_file():
                            total_bytes += f.stat().st_size
        
        return {
            'job_count': job_count,
            'total_bytes': total_bytes,
            'total_mb': round(total_bytes / (1024 * 1024), 2),
            'total_gb': round(total_bytes / (1024 * 1024 * 1024), 2),
        }

    # ========== 内部方法 ==========

    def _append_log(self, job: JobState, line: str) -> None:
        """添加日志行到任务"""
        line = line.rstrip("\n")
        if not line:
            return

        # 限制单行长度
        if len(line) > 2000:
            line = line[:2000] + "…"

        job.logs.append(line)
        
        # 限制日志总数
        if len(job.logs) > 400:
            job.logs = job.logs[-400:]

    def _extract_video_id(self, url: str) -> str | None:
        """从 YouTube URL 提取视频 ID"""
        import re
        # 匹配各种 YouTube URL 格式
        patterns = [
            r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:embed/|shorts/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _update_progress(self, job: JobState) -> None:
        """根据当前项目和进度计算总体进度"""
        if not job.total_items or job.total_items <= 0:
            return
        if not job.current_item or job.current_item <= 0:
            return

        item_idx = min(job.current_item, job.total_items)
        item_pct = max(0.0, min(100.0, job.current_item_progress))
        overall = ((item_idx - 1) + (item_pct / 100.0)) / job.total_items * 100.0
        job.progress = max(job.progress, min(100.0, overall))

    def _update_progress_from_items(self, job: JobState) -> None:
        if not job.total_items or job.total_items <= 0:
            return
        if not job.download_items:
            return

        total = max(1, job.total_items)
        s = 0.0
        done_count = 0
        active_pct = 0.0
        for it in job.download_items:
            pct = 0.0
            if it.status in {"done", "skipped"}:
                pct = 100.0
                done_count += 1
            elif it.status == "downloading":
                try:
                    pct = float(it.progress or 0)
                except Exception:
                    pct = 0.0
                pct = max(0.0, min(100.0, pct))
                active_pct = max(active_pct, pct)
            elif it.status == "paused":
                pct = 0.0
            elif it.status == "error":
                pct = max(0.0, min(100.0, float(it.progress or 0)))
            else:
                pct = max(0.0, min(100.0, float(it.progress or 0)))
            s += pct

        job.progress = max(job.progress, min(100.0, s / total))
        job.current_item = done_count + (1 if active_pct > 0 else 0)
        job.current_item_progress = active_pct

    def _package_zip(self, job_id: str, output_dir: Path) -> str | None:
        """
        将下载的 MP3 文件打包为 ZIP
        
        Returns:
            ZIP 文件路径，失败返回 None
        """
        job_dir = JOBS_DIR / job_id
        zip_path = job_dir / "mp3.zip"

        # 确定打包根目录
        playlist_folders = [p for p in output_dir.iterdir() if p.is_dir()] if output_dir.exists() else []
        payload_root = playlist_folders[0] if len(playlist_folders) == 1 else output_dir

        try:
            if zip_path.exists():
                zip_path.unlink()
            
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                if payload_root.exists():
                    for file_path in payload_root.rglob("*"):
                        if file_path.is_file() and file_path.suffix.lower() == ".mp3":
                            arcname = file_path.relative_to(payload_root.parent)
                            zf.write(file_path, arcname.as_posix())
        except Exception:
            return None

        return str(zip_path) if zip_path.exists() else None

    def _terminate_process(self, job_id: str) -> bool:
        """终止下载进程"""
        with self._lock:
            procs = list(self._procs.get(job_id, set()))

        if not procs:
            return False

        ok = True

        for proc in procs:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    ok = False
                    continue

        for proc in procs:
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        ok = False

        with self._lock:
            self._procs.pop(job_id, None)

        return ok

    def _run_job(self, job_id: str, selected_urls: list[str] | None = None) -> None:
        """
        执行下载任务 (在后台线程中运行)
        
        Args:
            job_id: 任务 ID
            selected_urls: 选中的视频 URL 列表，None 表示下载全部
        
        流程:
        1. 获取元数据 (标题、封面、曲目数)
        2. 启动 yt-dlp 下载进程
        3. 实时解析输出，更新进度
        4. 下载完成后打包 ZIP
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = "running"
            job.updated_at = time.time()

        # 检查 yt-dlp 是否存在
        if not YTDLP_BIN.exists():
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "error"
                    job.message = f"找不到 yt-dlp: {YTDLP_BIN}"
                    job.updated_at = time.time()
            return

        # 创建目录
        # 下载到 JOBS_DIR 临时目录，完成后移动到用户下载目录
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        # output_dir 指向临时目录，完成后移动到用户下载目录
        output_dir = job_dir

        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.output_dir = str(output_dir)
                job.updated_at = time.time()

        # 判断是播放列表还是单曲
        # 如果设置了 force_single，则强制作为单曲处理
        is_playlist = False if job.force_single else looks_like_playlist_url(job.url)

        # 获取元数据并设置输出模板
        if is_playlist:
            output_tpl = str(output_dir / "%(playlist_title)s" / "%(playlist_index)03d - %(title)s.%(ext)s")
            self._fetch_playlist_meta(job_id, job.url, output_dir)
        else:
            output_tpl = str(output_dir / "%(title)s.%(ext)s")
            self._fetch_single_meta(job_id, job.url, output_dir)

        # 如果是选择性下载，逐个下载选中的视频
        if selected_urls and len(selected_urls) > 0:
            self._run_selected_downloads(job_id, selected_urls, output_dir)
            return

        # 构建 yt-dlp 命令 (下载整个播放列表)
        proxy_args = ["--proxy", PROXY_URL] if PROXY_URL else []
        cmd = [
            str(YTDLP_BIN),
            "--yes-playlist" if is_playlist else "--no-playlist",
            "--download-archive", str(ARCHIVE_FILE),
            "--no-overwrites",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--newline",
            "--no-mtime",
            "--concurrent-fragments", str(_CONCURRENT_FRAGMENTS),
            "--retries", "3",
            "--socket-timeout", "15",
            *proxy_args,
            "--output", output_tpl,
            job.url,
        ]

        self._execute_download(job_id, cmd, output_dir)

    def _run_selected_downloads(self, job_id: str, video_urls: list[str], output_dir: Path) -> None:
        """
        下载选中的视频列表
        
        Args:
            job_id: 任务 ID
            video_urls: 视频 URL 列表
            output_dir: 输出目录
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.total_items = len(video_urls)
            job.current_item = 0
            job.updated_at = time.time()

        # 获取播放列表标题作为文件夹名
        playlist_title = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                playlist_title = job.playlist_title

        folder_name = playlist_title or "Selected"
        # 清理文件夹名中的非法字符
        folder_name = "".join(c for c in folder_name if c not in r'\/:*?"<>|')
        
        output_tpl = str(output_dir / folder_name / "%(title)s.%(ext)s")
        
        # 读取已下载的视频 ID 列表
        downloaded_ids = set()
        if ARCHIVE_FILE.exists():
            try:
                for line in ARCHIVE_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # 格式: "youtube VIDEO_ID"
                        parts = line.split()
                        if len(parts) >= 2:
                            downloaded_ids.add(parts[1])
            except Exception:
                pass

        q: deque[int] = deque(range(len(video_urls)))
        q_lock = threading.Lock()

        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for idx, video_url in enumerate(video_urls):
                    video_id = self._extract_video_id(video_url)
                    if video_id and video_id in downloaded_ids and idx < len(job.download_items):
                        job.download_items[idx].status = "done"
                        job.download_items[idx].progress = 100
                self._update_progress_from_items(job)
                job.updated_at = time.time()

        def worker() -> None:
            while True:
                with self._lock:
                    j = self._jobs.get(job_id)
                    if not j or j.cancel_requested:
                        return
                    paused = j.paused

                if paused:
                    time.sleep(0.5)
                    continue

                with q_lock:
                    if not q:
                        return
                    idx = q.popleft()

                with self._lock:
                    j = self._jobs.get(job_id)
                    if not j or j.cancel_requested:
                        return
                    item_index = idx + 1
                    if item_index in j.paused_items:
                        if idx < len(j.download_items):
                            j.download_items[idx].status = "paused"
                        j.updated_at = time.time()
                        with q_lock:
                            q.append(idx)
                        time.sleep(0.5)
                        continue

                    if idx < len(j.download_items) and j.download_items[idx].status == "done":
                        continue

                    if idx < len(j.download_items):
                        j.download_items[idx].status = "downloading"
                        j.download_items[idx].progress = 0
                    j.updated_at = time.time()

                video_url = video_urls[idx]
                proxy_args = ["--proxy", PROXY_URL] if PROXY_URL else []
                cmd = [
                    str(YTDLP_BIN),
                    "--no-playlist",
                    "--download-archive", str(ARCHIVE_FILE),
                    "--no-overwrites",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--audio-quality", "0",
                    "--newline",
                    "--no-mtime",
                    "--concurrent-fragments", str(_CONCURRENT_FRAGMENTS),
                    "--retries", "3",
                    "--socket-timeout", "15",
                    *proxy_args,
                    "--output", output_tpl,
                    video_url,
                ]

                success = self._execute_single_download(job_id, cmd, idx)

                with self._lock:
                    j = self._jobs.get(job_id)
                    if not j:
                        return
                    if idx < len(j.download_items):
                        if success:
                            j.download_items[idx].status = "done"
                            j.download_items[idx].progress = 100
                        elif j.cancel_requested:
                            j.download_items[idx].status = "skipped"
                        elif j.paused or (idx + 1) in j.paused_items:
                            # 被“暂停全部”终止/或该项暂停：重新排队稍后再下
                            j.download_items[idx].status = "paused"
                            with q_lock:
                                q.append(idx)
                        else:
                            j.download_items[idx].status = "error"
                    self._update_progress_from_items(j)
                    j.updated_at = time.time()

                if not success:
                    with self._lock:
                        j = self._jobs.get(job_id)
                        if j and j.cancel_requested:
                            return

                # 如果是暂停导致的失败，避免忙等
                with self._lock:
                    j = self._jobs.get(job_id)
                    if j and j.paused and not j.cancel_requested:
                        time.sleep(0.5)

        workers = max(1, min(15, _SELECTED_DOWNLOAD_CONCURRENCY))
        threads: list[threading.Thread] = []
        for _ in range(workers):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # 完成后打包
        self._save_track_thumbnails(job_id, output_dir)
        self._finalize_job(job_id, output_dir)

    def _save_track_thumbnails(self, job_id: str, output_dir: Path) -> None:
        """保存每个曲目的封面 URL 到文件"""
        import json
        
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not job.download_items:
                return
            
            # 构建标题到封面的映射
            thumbnails = {}
            for item in job.download_items:
                if item.thumbnail and item.title:
                    thumbnails[item.title] = item.thumbnail
        
        if not thumbnails:
            return
        
        try:
            thumbs_file = output_dir / "__track_thumbnails.json"
            thumbs_file.write_text(json.dumps(thumbnails, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _execute_single_download(self, job_id: str, cmd: list[str], item_index: int) -> bool:
        """
        执行单个视频下载
        
        Returns:
            是否成功
        """
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, bufsize=1, start_new_session=True)
        except Exception as e:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    self._append_log(job, f"[err] 启动下载失败: {e}")
                    if item_index < len(job.download_items):
                        job.download_items[item_index].error_msg = str(e)
            return False

        with self._lock:
            self._procs.setdefault(job_id, set()).add(proc)

        # 读取输出
        def read_output(stream, prefix: str) -> None:
            for raw in iter(stream.readline, ""):
                line = raw.rstrip("\n")
                with self._lock:
                    j = self._jobs.get(job_id)
                    if not j:
                        continue
                    self._append_log(j, f"{prefix}{line}")
                    
                    # 解析下载进度
                    match_pct = _PROGRESS_RE.search(line)
                    if match_pct:
                        try:
                            pct = float(match_pct.group("pct"))
                            # 更新当前下载项进度
                            if item_index < len(j.download_items):
                                j.download_items[item_index].progress = pct
                            self._update_progress_from_items(j)
                        except ValueError:
                            pass
                    
                    j.updated_at = time.time()

        t_out = threading.Thread(target=read_output, args=(proc.stdout, ""), daemon=True)
        t_err = threading.Thread(target=read_output, args=(proc.stderr, "[err] "), daemon=True)
        t_out.start()
        t_err.start()

        rc = proc.wait()
        t_out.join(timeout=1)
        t_err.join(timeout=1)

        with self._lock:
            s = self._procs.get(job_id)
            if s is not None:
                s.discard(proc)
                if not s:
                    self._procs.pop(job_id, None)

        return rc == 0

    def _finalize_job(self, job_id: str, output_dir: Path) -> None:
        """
        完成任务：移动文件到用户下载目录，检查状态并打包 ZIP
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            
            if job.cancel_requested:
                job.status = "canceled"
                job.message = "已取消"
                job.updated_at = time.time()
                self._try_package_zip(job_id, output_dir)
                return

        # 将 MP3 文件移动到用户下载目录
        final_dir = self._move_to_download_dir(job_id, output_dir)

        # 打包 ZIP (从最终目录打包)
        zip_path = self._package_zip(job_id, final_dir)
        if not zip_path:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "error"
                    job.message = "打包 ZIP 失败"
                    job.updated_at = time.time()
            return

        # 更新 output_dir 为最终目录
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.output_dir = str(final_dir)

        # 标记完成
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.progress = 100.0
                job.message = "完成"
                job.zip_path = zip_path
                job.updated_at = time.time()
        
        # 保存到数据库
        if job:
            self._save_job(job)

    def _move_to_download_dir(self, job_id: str, temp_dir: Path) -> Path:
        """
        将 MP3 文件从临时目录移动到用户下载目录
        
        使用播放列表/专辑标题作为文件夹名，而不是 job_id
        
        Args:
            job_id: 任务 ID
            temp_dir: 临时目录 (JOBS_DIR/job_id)
            
        Returns:
            最终目录路径
        """
        import json
        
        # 尝试从元数据获取标题作为文件夹名
        folder_name = job_id  # 默认使用 job_id
        meta_file = temp_dir / "__meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                title = meta.get("title")
                if title:
                    # 清理文件夹名中的非法字符
                    folder_name = "".join(c for c in title if c not in r'\/:*?"<>|')
                    folder_name = folder_name.strip()
                    if not folder_name:
                        folder_name = job_id
            except Exception:
                pass
        
        # 如果临时目录中有子文件夹（播放列表下载的情况），使用子文件夹名
        subdirs = [d for d in temp_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]
        if len(subdirs) == 1:
            folder_name = subdirs[0].name
        
        # 确保文件夹名唯一（如果已存在，添加数字后缀）
        download_dir = get_download_dir()
        final_dir = download_dir / folder_name
        if final_dir.exists():
            counter = 1
            while (download_dir / f"{folder_name} ({counter})").exists():
                counter += 1
            final_dir = download_dir / f"{folder_name} ({counter})"
        
        final_dir.mkdir(parents=True, exist_ok=True)
        
        # 移动所有 MP3 文件
        for mp3_file in temp_dir.rglob("*.mp3"):
            # 计算相对路径（跳过播放列表子文件夹层级）
            rel_path = mp3_file.relative_to(temp_dir)
            parts = rel_path.parts
            
            # 如果路径是 "播放列表名/文件.mp3"，直接放到根目录
            if len(parts) == 2 and len(subdirs) == 1:
                dest_path = final_dir / parts[1]
            else:
                dest_path = final_dir / rel_path
            
            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.move(str(mp3_file), str(dest_path))
            except Exception:
                # 如果移动失败，尝试复制
                try:
                    shutil.copy2(str(mp3_file), str(dest_path))
                    mp3_file.unlink()
                except Exception:
                    pass
        
        # 复制元数据文件到最终目录
        for meta_file_name in ["__meta.json", "__track_thumbnails.json"]:
            src = temp_dir / meta_file_name
            if src.exists():
                try:
                    shutil.copy2(str(src), str(final_dir / meta_file_name))
                except Exception:
                    pass
        
        return final_dir

    def _execute_download(self, job_id: str, cmd: list[str], output_dir: Path) -> None:
        """
        执行下载命令 (用于整个播放列表下载)
        """
        # 启动下载进程
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, text=True, bufsize=1, start_new_session=True)
        except Exception as e:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "error"
                    job.message = f"启动下载失败: {e}"
                    job.updated_at = time.time()
            return

        with self._lock:
            self._procs.setdefault(job_id, set()).add(proc)

        # 启动输出读取线程
        def read_output(stream, prefix: str) -> None:
            for raw in iter(stream.readline, ""):
                line = raw.rstrip("\n")
                with self._lock:
                    j = self._jobs.get(job_id)
                    if not j:
                        continue
                    
                    self._append_log(j, f"{prefix}{line}")
                    
                    # 解析下载项目
                    match_item = _ITEM_RE.search(line)
                    if match_item:
                        try:
                            j.current_item = int(match_item.group("idx"))
                            j.total_items = int(match_item.group("total"))
                        except Exception:
                            pass
                    
                    # 解析下载进度
                    match_pct = _PROGRESS_RE.search(line)
                    if match_pct:
                        try:
                            pct = float(match_pct.group("pct"))
                            j.current_item_progress = pct
                            if not j.total_items:
                                j.total_items = 1
                            if not j.current_item:
                                j.current_item = 1
                            self._update_progress(j)
                        except ValueError:
                            pass
                    
                    j.updated_at = time.time()

        t_out = threading.Thread(target=read_output, args=(proc.stdout, ""), daemon=True)
        t_err = threading.Thread(target=read_output, args=(proc.stderr, "[err] "), daemon=True)
        t_out.start()
        t_err.start()

        # 等待进程结束
        rc = proc.wait()
        t_out.join(timeout=1)
        t_err.join(timeout=1)

        with self._lock:
            s = self._procs.get(job_id)
            if s is not None:
                s.discard(proc)
                if not s:
                    self._procs.pop(job_id, None)

        # 处理结果
        if rc != 0:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    if job.cancel_requested:
                        job.status = "canceled"
                        job.message = "已取消"
                    else:
                        job.status = "error"
                        job.message = f"下载失败 (退出码 {rc})，请检查是否安装了 ffmpeg"
                    job.updated_at = time.time()

            # 即使失败也尝试打包已下载的文件
            self._try_package_zip(job_id, output_dir)
            return

        # 打包 ZIP
        zip_path = self._package_zip(job_id, output_dir)
        if not zip_path:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "error"
                    job.message = "打包 ZIP 失败"
                    job.updated_at = time.time()
            return

        # 标记完成
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.progress = 100.0
                job.message = "完成"
                job.zip_path = zip_path
                job.updated_at = time.time()
        
        # 保存到数据库
        if job:
            self._save_job(job)

    def _fetch_playlist_meta(self, job_id: str, url: str, output_dir: Path) -> None:
        """获取播放列表元数据"""
        meta = fetch_playlist_metadata(url)
        if not meta:
            return

        title = meta.get("title")
        entries = meta.get("entries")
        total = meta.get("playlist_count")
        if total is None and isinstance(entries, list):
            total = len(entries)

        thumb_url = select_best_thumbnail_url(meta)

        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.playlist_title = str(title) if title else job.playlist_title
                job.thumbnail_url = thumb_url or job.thumbnail_url
                try:
                    job.total_items = int(total) if total else job.total_items
                except Exception:
                    pass
                job.updated_at = time.time()

        write_job_meta(output_dir, str(title) if title else None, thumb_url)
        
        # 保存每个曲目的封面 URL
        if isinstance(entries, list) and entries:
            import json
            thumbnails = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_title = entry.get("title")
                entry_thumb = select_best_thumbnail_url(entry)
                if entry_title and entry_thumb:
                    thumbnails[entry_title] = entry_thumb
            
            if thumbnails:
                try:
                    thumbs_file = output_dir / "__track_thumbnails.json"
                    thumbs_file.write_text(json.dumps(thumbnails, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

    def _fetch_single_meta(self, job_id: str, url: str, output_dir: Path) -> None:
        """获取单曲元数据"""
        meta = fetch_single_metadata(url)
        if not meta:
            return

        title = meta.get("title")
        thumb_url = select_best_thumbnail_url(meta)

        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.playlist_title = str(title) if title else job.playlist_title
                job.thumbnail_url = thumb_url or job.thumbnail_url
                job.total_items = 1
                job.current_item = 1
                job.updated_at = time.time()

        write_job_meta(output_dir, str(title) if title else None, thumb_url)

    def _try_package_zip(self, job_id: str, output_dir: Path) -> None:
        """尝试打包 ZIP (用于失败/取消后)"""
        if not output_dir.exists():
            return
        
        zip_path = self._package_zip(job_id, output_dir)
        if zip_path:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.zip_path = zip_path
