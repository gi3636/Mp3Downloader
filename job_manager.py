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

from config import ARCHIVE_FILE, DOWNLOAD_DIR, JOBS_DIR, YTDLP_BIN
from models import JobState, DownloadItem
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

_SELECTED_DOWNLOAD_CONCURRENCY = int(os.environ.get("MP3DL_SELECTED_CONCURRENCY", "3"))


class JobManager:
    """
    下载任务管理器
    
    线程安全，支持并发任务管理
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}
        self._procs: dict[str, set[Popen]] = {}

    # ========== 公共接口 ==========

    def create_job(self, url: str) -> str:
        """
        创建新的下载任务 (下载整个播放列表)
        
        Args:
            url: YouTube 链接
            
        Returns:
            任务 ID
        """
        job_id = uuid.uuid4().hex
        job = JobState(id=job_id, url=url, message="已创建任务")
        
        with self._lock:
            self._jobs[job_id] = job

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

        # 启动后台下载线程
        thread = threading.Thread(target=self._run_job, args=(job_id, video_urls), daemon=True)
        thread.start()
        
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        """获取任务状态"""
        with self._lock:
            return self._jobs.get(job_id)

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
        job_dir = JOBS_DIR / job_id
        output_dir = DOWNLOAD_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.output_dir = str(output_dir)
                job.updated_at = time.time()

        # 判断是播放列表还是单曲
        is_playlist = looks_like_playlist_url(job.url)

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

        workers = max(1, min(8, _SELECTED_DOWNLOAD_CONCURRENCY))
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
        完成任务：检查状态并打包 ZIP
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

    def _fetch_playlist_meta(self, job_id: str, url: str, output_dir: Path) -> None:
        """获取播放列表元数据"""
        meta = fetch_playlist_metadata(url)
        if not meta:
            return

        title = meta.get("title")
        total = meta.get("playlist_count")
        if total is None:
            entries = meta.get("entries")
            if isinstance(entries, list):
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
