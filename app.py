"""
YouTube 音乐下载器 - Flask 后端应用

功能:
- 解析 YouTube 链接，支持播放列表和单曲
- 创建下载任务，转换为 MP3 格式
- 实时进度追踪
- 音乐库管理 (列表、播放、删除)
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from config import YTDLP_BIN
from job_manager import JobManager
from settings_service import get_download_dir, get_all_settings, update_settings
from tracks_service import (
    b64_decode_path,
    list_mp3_tracks,
    read_job_meta,
    resolve_track_path,
)
from ytdlp_service import (
    fetch_playlists_from_channel,
    fetch_playlist_entries,
    looks_like_playlist_url,
)


# ========== Flask 应用初始化 ==========

app = Flask(__name__, static_folder="static", static_url_path="/")

# 任务管理器单例
_manager = JobManager()


# ========== 页面路由 ==========

@app.get("/")
def index():
    """返回前端页面"""
    return app.send_static_file("index.html")


# ========== API: 链接解析 ==========

@app.post("/api/resolve")
def resolve_url():
    """
    解析 YouTube 链接
    
    - 如果是播放列表链接，返回所有曲目供用户选择
    - 如果是频道链接，返回该频道的播放列表供用户选择
    - 如果是单曲，直接返回
    
    请求体: { "url": "https://..." }
    响应: { "mode": "direct"|"choose"|"playlist", ... }
    """
    if not YTDLP_BIN.exists():
        return jsonify({"error": f"找不到 yt-dlp: {YTDLP_BIN}"}), 500

    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()

    # 验证 URL
    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url 必须以 http:// 或 https:// 开头"}), 400

    # 如果是播放列表链接，获取所有曲目
    if looks_like_playlist_url(url):
        playlist_info = fetch_playlist_entries(url)
        if playlist_info and playlist_info.get("entries"):
            return jsonify({
                "mode": "playlist",
                "url": url,
                "playlist": playlist_info,
            })
        # 获取失败，当作单曲处理
        return jsonify({"mode": "direct", "url": url, "choices": []})

    # 尝试获取频道的播放列表
    choices = fetch_playlists_from_channel(url)
    
    if len(choices) == 0:
        # 没有找到播放列表，当作单曲处理
        return jsonify({"mode": "direct", "url": url, "choices": []})

    if len(choices) == 1:
        # 只有一个播放列表，获取其曲目
        playlist_info = fetch_playlist_entries(choices[0]["url"])
        if playlist_info and playlist_info.get("entries"):
            return jsonify({
                "mode": "playlist",
                "url": choices[0]["url"],
                "playlist": playlist_info,
            })
        return jsonify({"mode": "direct", "url": choices[0]["url"], "choices": []})

    # 多个播放列表，让用户选择
    return jsonify({"mode": "choose", "url": None, "choices": choices})


# ========== API: 任务管理 ==========

@app.post("/api/jobs")
def create_job():
    """
    创建下载任务
    
    请求体: 
      - { "url": "https://..." } - 下载整个播放列表
      - { "url": "https://...", "video_urls": [...], "video_titles": [...], "video_thumbnails": [...] }
      - { "url": "https://...", "force_single": true } - 强制下载单曲（忽略播放列表）
      
    响应: { "job_id": "xxx" }
    """
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    video_urls = data.get("video_urls")
    video_titles = data.get("video_titles")
    video_thumbnails = data.get("video_thumbnails")
    force_single = data.get("force_single", False)

    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url 必须以 http:// 或 https:// 开头"}), 400

    # 如果指定了 video_urls，则只下载选中的曲目
    if video_urls and isinstance(video_urls, list) and len(video_urls) > 0:
        job_id = _manager.create_job_with_urls(url, video_urls, video_titles, video_thumbnails)
    else:
        job_id = _manager.create_job(url, force_single=force_single)
    
    return jsonify({"job_id": job_id})


@app.get("/api/jobs")
def list_jobs():
    """
    获取所有任务列表
    
    响应: { "jobs": [...] }
    """
    jobs = _manager.list_jobs()
    result = []
    for job in jobs:
        result.append({
            "id": job.id,
            "url": job.url,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "progress": job.progress,
            "message": job.message,
            "meta": {
                "title": job.playlist_title,
                "thumbnail_url": job.thumbnail_url,
                "total_items": job.total_items,
            },
            "paused": job.paused,
        })
    return jsonify({"jobs": result})


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    """
    获取任务状态
    
    响应: 任务详情，包含进度、状态、元数据等
    """
    job = _manager.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    # 统计已下载文件数
    downloaded_count = 0
    if job.output_dir:
        try:
            downloaded_count = sum(1 for _ in Path(job.output_dir).rglob("*.mp3"))
        except Exception:
            pass

    return jsonify({
        "id": job.id,
        "url": job.url,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "progress": job.progress,
        "message": job.message,
        "meta": {
            "title": job.playlist_title,
            "thumbnail_url": job.thumbnail_url,
            "total_items": job.total_items,
            "current_item": job.current_item,
            "downloaded_count": downloaded_count,
        },
        "logs": job.logs,
        "download_items": job.download_items_dict,  # 每个下载项的状态
        "paused": job.paused,  # 是否暂停
        "download_url": f"/api/jobs/{job.id}/download" if job.zip_path and job.status in {"done", "canceled"} else None,
    })


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    """取消下载任务"""
    ok = _manager.cancel_job(job_id)
    if not ok:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/pause")
def pause_job(job_id: str):
    """暂停整个下载任务"""
    ok = _manager.pause_job(job_id)
    if not ok:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/resume")
def resume_job(job_id: str):
    """继续整个下载任务"""
    ok = _manager.resume_job(job_id)
    if not ok:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/items/<int:item_index>/pause")
def pause_job_item(job_id: str, item_index: int):
    """暂停单个下载项"""
    ok = _manager.pause_item(job_id, item_index)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/items/<int:item_index>/resume")
def resume_job_item(job_id: str, item_index: int):
    """继续单个下载项"""
    ok = _manager.resume_item(job_id, item_index)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/delete")
def delete_job(job_id: str):
    """删除任务及其文件"""
    _manager.delete_job(job_id)
    return jsonify({"ok": True})


@app.post("/api/jobs/<job_id>/open-folder")
def open_job_folder(job_id: str):
    """在系统文件管理器中打开任务的下载目录"""
    import subprocess
    import platform
    
    job_dir = get_download_dir() / job_id
    if not job_dir.exists():
        return jsonify({"error": "任务目录不存在"}), 404
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(job_dir)], check=True)
        elif system == "Windows":
            subprocess.run(["explorer", str(job_dir)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(job_dir)], check=True)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"无法打开目录: {e}"}), 500


@app.get("/api/jobs/disk-usage")
def get_disk_usage():
    """
    获取任务目录的磁盘使用情况
    
    响应: { "job_count": n, "total_mb": x, "total_gb": y }
    """
    usage = _manager.get_disk_usage()
    return jsonify(usage)


@app.post("/api/jobs/cleanup-old")
def cleanup_old_jobs():
    """
    清理超过指定天数的已完成任务
    
    请求体: { "max_age_days": 7 }  (可选，默认7天)
    响应: { "deleted_count": n, "freed_mb": x }
    """
    data = request.get_json(silent=True) or {}
    max_age_days = int(data.get("max_age_days", 7))
    
    if max_age_days < 0:
        return jsonify({"error": "max_age_days 必须大于等于 0"}), 400
    
    result = _manager.cleanup_old_jobs(max_age_days)
    return jsonify(result)


@app.post("/api/jobs/cleanup-all")
def cleanup_all_jobs():
    """
    清理所有已完成的任务（一键清理）
    
    响应: { "deleted_count": n, "freed_mb": x }
    """
    result = _manager.cleanup_all_completed_jobs()
    return jsonify(result)


@app.post("/api/settings/cleanup-downloads")
def cleanup_download_folders():
    """
    清理下载目录中的 hash 命名文件夹
    将 MP3 文件移动到以专辑名命名的文件夹，或移到"未分类"
    """
    import re
    import shutil
    
    download_dir = get_download_dir()
    hash_pattern = re.compile(r'^[0-9a-f]{32}$')  # 32位 hex hash
    
    moved_count = 0
    deleted_folders = 0
    errors = []
    
    for folder in list(download_dir.iterdir()):
        if not folder.is_dir():
            continue
        
        # 检查是否是 hash 命名的文件夹
        if not hash_pattern.match(folder.name):
            continue
        
        # 读取 job meta 获取专辑名
        meta_file = folder / "__job_meta.json"
        album_name = None
        if meta_file.exists():
            try:
                import json
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                album_name = meta.get("title")
            except Exception:
                pass
        
        # 如果没有专辑名，使用"未分类"
        if not album_name:
            album_name = "未分类"
        
        # 创建目标文件夹
        target_dir = download_dir / album_name
        target_dir.mkdir(exist_ok=True)
        
        # 移动所有 MP3 文件
        for mp3_file in folder.rglob("*.mp3"):
            dest_file = target_dir / mp3_file.name
            counter = 1
            while dest_file.exists():
                stem = mp3_file.stem
                suffix = mp3_file.suffix
                dest_file = target_dir / f"{stem} ({counter}){suffix}"
                counter += 1
            
            try:
                shutil.move(str(mp3_file), str(dest_file))
                moved_count += 1
            except Exception as e:
                errors.append(f"移动 {mp3_file.name} 失败: {e}")
        
        # 删除空的 hash 文件夹
        try:
            if folder.exists() and not any(folder.rglob("*.mp3")):
                shutil.rmtree(folder)
                deleted_folders += 1
        except Exception as e:
            errors.append(f"删除文件夹 {folder.name} 失败: {e}")
    
    return jsonify({
        "ok": True,
        "moved_count": moved_count,
        "deleted_folders": deleted_folders,
        "errors": errors if errors else None,
    })


@app.get("/api/jobs/<job_id>/download")
def download_job(job_id: str):
    """下载任务的 ZIP 文件"""
    job = _manager.get_job(job_id)
    if not job or not job.zip_path or job.status not in {"done", "canceled"}:
        return jsonify({"error": "not ready"}), 400

    return send_file(job.zip_path, as_attachment=True, download_name=f"{job_id}.zip")


# ========== API: 任务曲目管理 ==========

@app.get("/api/jobs/<job_id>/tracks")
def list_job_tracks(job_id: str):
    """获取任务的曲目列表"""
    job = _manager.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    
    if not job.output_dir:
        return jsonify({"tracks": []})

    tracks = list_mp3_tracks(Path(job.output_dir))
    
    # 构建下载项封面映射
    thumbnail_map = {}
    for item in (job.download_items or []):
        if item.thumbnail:
            # 用标题匹配
            thumbnail_map[item.title] = item.thumbnail
    
    # 添加流媒体 URL 和封面
    for t in tracks:
        t["stream_url"] = f"/api/jobs/{job_id}/tracks/{t['id']}/stream"
        # 优先使用下载项的封面，否则使用播放列表封面
        title = t.get("title", "")
        t["cover_url"] = thumbnail_map.get(title) or job.thumbnail_url
        del t["rel_path"]

    return jsonify({"tracks": tracks})


@app.get("/api/jobs/<job_id>/tracks/<track_id>/stream")
def stream_job_track(job_id: str, track_id: str):
    """流式播放任务中的曲目"""
    job = _manager.get_job(job_id)
    if not job or not job.output_dir:
        return jsonify({"error": "job not found"}), 404

    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "invalid track"}), 400

    fp = resolve_track_path(Path(job.output_dir), rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    return send_file(fp, mimetype="audio/mpeg", as_attachment=False)


@app.post("/api/jobs/<job_id>/tracks/<track_id>/delete")
def delete_job_track(job_id: str, track_id: str):
    """删除任务中的单个曲目"""
    job = _manager.get_job(job_id)
    if not job or not job.output_dir:
        return jsonify({"error": "job not found"}), 404

    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "invalid track"}), 400

    fp = resolve_track_path(Path(job.output_dir), rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    try:
        fp.unlink()
    except Exception:
        return jsonify({"error": "delete failed"}), 500

    # 标记 ZIP 需要重新生成
    _manager.invalidate_zip(job_id)

    return jsonify({"ok": True})


# ========== API: 音乐库管理 ==========

@app.get("/api/library/tracks")
def list_library_tracks():
    """获取音乐库所有曲目"""
    download_dir = get_download_dir()
    tracks = list_mp3_tracks(download_dir)
    
    for t in tracks:
        rel = t.get("rel_path")
        cover_url = None
        album_title = None
        
        # 尝试从元数据获取封面
        if isinstance(rel, str):
            parts = rel.split("/")
            if parts:
                job_folder = download_dir / parts[0]
                meta = read_job_meta(job_folder)
                if meta:
                    if meta.get("thumbnail_url"):
                        cover_url = str(meta.get("thumbnail_url"))
                    # 只有播放列表（有子目录，即 parts >= 3）才设置专辑标题
                    # 单曲格式: job_id/song.mp3 (2 parts)
                    # 播放列表格式: job_id/playlist_name/song.mp3 (3+ parts)
                    if len(parts) >= 3 and meta.get("title"):
                        album_title = str(meta.get("title"))
                
                # 尝试读取单曲封面 (从 track_thumbnails.json)
                track_thumbs_file = job_folder / "__track_thumbnails.json"
                if track_thumbs_file.exists():
                    try:
                        import json
                        import re
                        track_thumbs = json.loads(track_thumbs_file.read_text(encoding="utf-8"))
                        title = t.get("title", "")
                        # 先尝试直接匹配
                        if title in track_thumbs:
                            cover_url = track_thumbs[title]
                        else:
                            # 尝试去掉编号前缀匹配 (如 "460 - GOLDEN NIGHT" -> "GOLDEN NIGHT")
                            stripped = re.sub(r'^\d+\s*[-–—]\s*', '', title)
                            if stripped and stripped in track_thumbs:
                                cover_url = track_thumbs[stripped]
                    except Exception:
                        pass

        t["stream_url"] = f"/api/library/tracks/{t['id']}/stream"
        t["cover_url"] = cover_url
        t["album_title"] = album_title or t.get("album")
        del t["rel_path"]

    return jsonify({"tracks": tracks})


@app.get("/api/library/tracks/<track_id>/stream")
def stream_library_track(track_id: str):
    """流式播放音乐库中的曲目"""
    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "invalid track"}), 400

    fp = resolve_track_path(get_download_dir(), rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    return send_file(fp, mimetype="audio/mpeg", as_attachment=False)


@app.post("/api/library/tracks/<track_id>/delete")
def delete_library_track(track_id: str):
    """删除音乐库中的曲目"""
    download_dir = get_download_dir()
    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "invalid track"}), 400

    fp = resolve_track_path(download_dir, rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    try:
        fp.unlink()
    except Exception:
        return jsonify({"error": "delete failed"}), 500

    # 清理空目录
    try:
        parent = fp.parent
        while parent != download_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    except Exception:
        pass

    return jsonify({"ok": True})


# ========== API: 专辑（文件夹）管理 ==========

@app.get("/api/albums")
def list_albums():
    """获取所有专辑（下载目录中的文件夹）"""
    download_dir = get_download_dir()
    albums = []
    
    for folder in sorted(download_dir.iterdir()):
        if not folder.is_dir():
            continue
        
        # 统计 MP3 文件数量
        mp3_files = list(folder.rglob("*.mp3"))
        if not mp3_files:
            continue
        
        # 读取元数据获取封面
        cover_url = None
        meta_file = folder / "__meta.json"
        if meta_file.exists():
            try:
                import json
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                cover_url = meta.get("thumbnail_url")
            except Exception:
                pass
        
        albums.append({
            "id": folder.name,
            "name": folder.name,
            "track_count": len(mp3_files),
            "cover_url": cover_url,
        })
    
    return jsonify({"albums": albums})


@app.post("/api/albums")
def create_album():
    """创建新专辑（文件夹）"""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    
    if not name:
        return jsonify({"error": "名称不能为空"}), 400
    
    # 清理文件夹名中的非法字符
    safe_name = "".join(c for c in name if c not in r'\/:*?"<>|')
    if not safe_name:
        return jsonify({"error": "名称无效"}), 400
    
    download_dir = get_download_dir()
    album_path = download_dir / safe_name
    
    if album_path.exists():
        return jsonify({"error": "专辑已存在"}), 400
    
    try:
        album_path.mkdir(parents=True)
        return jsonify({
            "id": safe_name,
            "name": safe_name,
            "track_count": 0,
            "cover_url": None,
        })
    except Exception as e:
        return jsonify({"error": f"创建失败: {e}"}), 500


@app.put("/api/albums/<album_id>")
def rename_album(album_id: str):
    """重命名专辑"""
    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    
    if not new_name:
        return jsonify({"error": "名称不能为空"}), 400
    
    # 清理文件夹名中的非法字符
    safe_name = "".join(c for c in new_name if c not in r'\/:*?"<>|')
    if not safe_name:
        return jsonify({"error": "名称无效"}), 400
    
    download_dir = get_download_dir()
    old_path = download_dir / album_id
    new_path = download_dir / safe_name
    
    if not old_path.exists():
        return jsonify({"error": "专辑不存在"}), 404
    
    if new_path.exists() and old_path != new_path:
        return jsonify({"error": "目标名称已存在"}), 400
    
    try:
        old_path.rename(new_path)
        mp3_count = len(list(new_path.rglob("*.mp3")))
        return jsonify({
            "id": safe_name,
            "name": safe_name,
            "track_count": mp3_count,
        })
    except Exception as e:
        return jsonify({"error": f"重命名失败: {e}"}), 500


@app.delete("/api/albums/<album_id>")
def delete_album(album_id: str):
    """删除专辑及其所有曲目"""
    import shutil
    
    download_dir = get_download_dir()
    album_path = download_dir / album_id
    
    if not album_path.exists():
        return jsonify({"error": "专辑不存在"}), 404
    
    try:
        shutil.rmtree(album_path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"删除失败: {e}"}), 500


@app.post("/api/albums/<album_id>/tracks")
def move_track_to_album(album_id: str):
    """移动曲目到专辑"""
    data = request.get_json() or {}
    track_id = data.get("track_id", "")
    
    if not track_id:
        return jsonify({"error": "缺少 track_id"}), 400
    
    download_dir = get_download_dir()
    album_path = download_dir / album_id
    
    if not album_path.exists():
        return jsonify({"error": "专辑不存在"}), 404
    
    # 解析曲目路径
    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "无效的 track_id"}), 400
    
    src_path = resolve_track_path(download_dir, rel)
    if not src_path:
        return jsonify({"error": "曲目不存在"}), 404
    
    # 移动文件
    dest_path = album_path / src_path.name
    if dest_path.exists():
        return jsonify({"error": "目标位置已存在同名文件"}), 400
    
    try:
        import shutil
        shutil.move(str(src_path), str(dest_path))
        
        # 清理空目录
        parent = src_path.parent
        while parent != download_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"移动失败: {e}"}), 500


@app.delete("/api/albums/<album_id>/tracks/<track_id>")
def remove_track_from_album(album_id: str, track_id: str):
    """从专辑移除曲目（移动到根目录的 "未分类" 文件夹）"""
    import shutil
    
    download_dir = get_download_dir()
    album_path = download_dir / album_id
    
    if not album_path.exists():
        return jsonify({"error": "专辑不存在"}), 404
    
    # 解析曲目路径
    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "无效的 track_id"}), 400
    
    src_path = resolve_track_path(download_dir, rel)
    if not src_path:
        return jsonify({"error": "曲目不存在"}), 404
    
    # 创建 "未分类" 文件夹
    unsorted_path = download_dir / "未分类"
    unsorted_path.mkdir(exist_ok=True)
    
    # 移动文件
    dest_path = unsorted_path / src_path.name
    counter = 1
    while dest_path.exists():
        stem = src_path.stem
        suffix = src_path.suffix
        dest_path = unsorted_path / f"{stem} ({counter}){suffix}"
        counter += 1
    
    try:
        shutil.move(str(src_path), str(dest_path))
        
        # 清理空目录
        parent = src_path.parent
        while parent != download_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"移除失败: {e}"}), 500


@app.post("/api/albums/<album_id>/merge")
def merge_albums(album_id: str):
    """合并其他专辑到当前专辑"""
    import shutil
    
    data = request.get_json() or {}
    source_ids = data.get("source_ids", [])
    
    if not source_ids:
        return jsonify({"error": "缺少要合并的专辑"}), 400
    
    download_dir = get_download_dir()
    target_path = download_dir / album_id
    
    if not target_path.exists():
        return jsonify({"error": "目标专辑不存在"}), 404
    
    merged_count = 0
    errors = []
    
    for source_id in source_ids:
        source_path = download_dir / source_id
        if not source_path.exists():
            errors.append(f"专辑 {source_id} 不存在")
            continue
        
        if source_path == target_path:
            continue
        
        # 移动所有 MP3 文件
        for mp3_file in source_path.rglob("*.mp3"):
            dest_file = target_path / mp3_file.name
            counter = 1
            while dest_file.exists():
                stem = mp3_file.stem
                suffix = mp3_file.suffix
                dest_file = target_path / f"{stem} ({counter}){suffix}"
                counter += 1
            
            try:
                shutil.move(str(mp3_file), str(dest_file))
                merged_count += 1
            except Exception as e:
                errors.append(f"移动 {mp3_file.name} 失败: {e}")
        
        # 删除空的源文件夹
        try:
            if source_path.exists() and not any(source_path.rglob("*.mp3")):
                shutil.rmtree(source_path)
        except Exception:
            pass
    
    return jsonify({
        "ok": True,
        "merged_count": merged_count,
        "errors": errors if errors else None,
    })


# ========== API: AI 分类 ==========

@app.post("/api/ai/classify-preview")
def ai_classify_preview():
    """AI 分类预览 - 返回分类结果但不执行"""
    from ai_service import classify_songs
    
    data = request.get_json() or {}
    track_ids = data.get("track_ids", [])
    rule = data.get("rule", "").strip()
    
    if not track_ids:
        return jsonify({"error": "请选择要分类的歌曲"}), 400
    if not rule:
        return jsonify({"error": "请输入分类规则"}), 400
    
    download_dir = get_download_dir()
    
    # 获取歌曲名称
    song_names = []
    track_map = {}  # 歌曲名 -> track_id
    
    for track_id in track_ids:
        rel = b64_decode_path(track_id)
        if not rel:
            continue
        fp = resolve_track_path(download_dir, rel)
        if fp:
            name = fp.stem
            song_names.append(name)
            track_map[name] = track_id
    
    if not song_names:
        return jsonify({"error": "未找到有效的歌曲"}), 400
    
    try:
        classification = classify_songs(song_names, rule)
        
        # 将分类结果转换为包含 track_id 的格式
        result = {}
        for album, songs in classification.items():
            result[album] = []
            for song in songs:
                if song in track_map:
                    result[album].append({
                        "name": song,
                        "track_id": track_map[song]
                    })
        
        return jsonify({"classification": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"AI 分类失败: {e}"}), 500


@app.post("/api/ai/classify-execute")
def ai_classify_execute():
    """执行 AI 分类 - 移动文件到对应专辑"""
    import shutil
    
    data = request.get_json() or {}
    classification = data.get("classification", {})
    
    if not classification:
        return jsonify({"error": "缺少分类数据"}), 400
    
    download_dir = get_download_dir()
    moved_count = 0
    errors = []
    
    for album_name, tracks in classification.items():
        if not album_name or album_name == "未分类":
            continue
        
        # 创建专辑文件夹
        album_dir = download_dir / album_name
        album_dir.mkdir(exist_ok=True)
        
        for track in tracks:
            track_id = track.get("track_id")
            if not track_id:
                continue
            
            rel = b64_decode_path(track_id)
            if not rel:
                continue
            
            src_path = resolve_track_path(download_dir, rel)
            if not src_path:
                continue
            
            dest_path = album_dir / src_path.name
            counter = 1
            while dest_path.exists():
                stem = src_path.stem
                suffix = src_path.suffix
                dest_path = album_dir / f"{stem} ({counter}){suffix}"
                counter += 1
            
            try:
                shutil.move(str(src_path), str(dest_path))
                moved_count += 1
                
                # 清理空目录
                parent = src_path.parent
                while parent != download_dir and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
            except Exception as e:
                errors.append(f"移动 {src_path.name} 失败: {e}")
    
    return jsonify({
        "ok": True,
        "moved_count": moved_count,
        "errors": errors if errors else None,
    })


# ========== API: 播放列表管理 ==========

from playlist_service import (
    list_playlists,
    create_playlist,
    rename_playlist,
    delete_playlist,
    add_track_to_playlist,
)


@app.get("/api/playlists")
def get_playlists():
    """获取所有播放列表"""
    playlists = list_playlists()
    return jsonify({"playlists": playlists})


@app.post("/api/playlists")
def create_new_playlist():
    """创建新播放列表"""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    
    if not name:
        return jsonify({"error": "名称不能为空"}), 400
    
    playlist = create_playlist(name)
    return jsonify(playlist)


@app.put("/api/playlists/<playlist_id>")
def update_playlist(playlist_id: str):
    """重命名播放列表"""
    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    
    if not new_name:
        return jsonify({"error": "名称不能为空"}), 400
    
    playlist = rename_playlist(playlist_id, new_name)
    if not playlist:
        return jsonify({"error": "播放列表不存在"}), 404
    
    return jsonify(playlist)


@app.delete("/api/playlists/<playlist_id>")
def remove_playlist(playlist_id: str):
    """删除播放列表"""
    ok = delete_playlist(playlist_id)
    if not ok:
        return jsonify({"error": "播放列表不存在"}), 404
    
    return jsonify({"ok": True})


@app.post("/api/playlists/<playlist_id>/tracks")
def add_track(playlist_id: str):
    """添加歌曲到播放列表"""
    data = request.get_json() or {}
    track_id = data.get("track_id", "")
    
    if not track_id:
        return jsonify({"error": "缺少 track_id"}), 400
    
    ok = add_track_to_playlist(playlist_id, track_id)
    if not ok:
        return jsonify({"error": "添加失败"}), 400
    
    return jsonify({"ok": True})


# ========== API: 设置管理 ==========

@app.get("/api/settings")
def get_settings():
    """获取所有设置"""
    settings = get_all_settings()
    return jsonify(settings)


@app.post("/api/settings")
def save_settings():
    """保存设置"""
    data = request.get_json(silent=True) or {}
    
    # 验证下载目录
    download_dir = data.get("download_dir")
    if download_dir:
        # 展开用户目录
        expanded_path = Path(download_dir).expanduser()
        try:
            expanded_path.mkdir(parents=True, exist_ok=True)
            data["download_dir"] = str(expanded_path)
        except Exception as e:
            return jsonify({"error": f"无法创建目录: {e}"}), 400
    
    update_settings(data)
    return jsonify({"ok": True})


@app.post("/api/settings/check-migration")
def check_migration():
    """
    检查旧目录是否有文件需要迁移
    请求体: { "new_dir": "新目录路径" }
    """
    import shutil
    
    data = request.get_json(silent=True) or {}
    new_dir = data.get("new_dir", "").strip()
    
    if not new_dir:
        return jsonify({"error": "新目录不能为空"}), 400
    
    new_path = Path(new_dir).expanduser()
    old_path = get_download_dir()
    
    # 如果新旧路径相同，不需要迁移
    if new_path.resolve() == old_path.resolve():
        return jsonify({"need_migration": False, "file_count": 0, "total_size": 0})
    
    # 检查旧目录是否有文件
    file_count = 0
    total_size = 0
    
    if old_path.exists():
        for f in old_path.rglob("*"):
            if f.is_file():
                file_count += 1
                total_size += f.stat().st_size
    
    return jsonify({
        "need_migration": file_count > 0,
        "file_count": file_count,
        "total_size": total_size,
        "old_dir": str(old_path),
        "new_dir": str(new_path),
    })


@app.post("/api/settings/migrate-files")
def migrate_files():
    """
    将旧目录的文件迁移到新目录
    请求体: { "new_dir": "新目录路径", "delete_source": true/false }
    """
    import shutil
    
    data = request.get_json(silent=True) or {}
    new_dir = data.get("new_dir", "").strip()
    delete_source = data.get("delete_source", True)  # 默认删除源文件
    
    if not new_dir:
        return jsonify({"error": "新目录不能为空"}), 400
    
    new_path = Path(new_dir).expanduser()
    old_path = get_download_dir()
    
    # 如果新旧路径相同，不需要迁移
    if new_path.resolve() == old_path.resolve():
        return jsonify({"ok": True, "migrated_count": 0})
    
    # 确保新目录存在
    try:
        new_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({"error": f"无法创建新目录: {e}"}), 400
    
    # 迁移文件
    migrated_count = 0
    errors = []
    
    if old_path.exists():
        for item in old_path.iterdir():
            try:
                dest = new_path / item.name
                if item.is_dir():
                    if dest.exists():
                        # 合并目录内容
                        for sub in item.rglob("*"):
                            if sub.is_file():
                                rel = sub.relative_to(item)
                                sub_dest = dest / rel
                                sub_dest.parent.mkdir(parents=True, exist_ok=True)
                                if delete_source:
                                    shutil.move(str(sub), str(sub_dest))
                                else:
                                    shutil.copy2(str(sub), str(sub_dest))
                                migrated_count += 1
                        # 删除空的源目录（仅当 delete_source 为 True）
                        if delete_source:
                            shutil.rmtree(str(item), ignore_errors=True)
                    else:
                        if delete_source:
                            shutil.move(str(item), str(dest))
                        else:
                            shutil.copytree(str(item), str(dest))
                        migrated_count += 1
                else:
                    if delete_source:
                        shutil.move(str(item), str(dest))
                    else:
                        shutil.copy2(str(item), str(dest))
                    migrated_count += 1
            except Exception as e:
                errors.append(f"{item.name}: {e}")
    
    if errors:
        return jsonify({
            "ok": False,
            "migrated_count": migrated_count,
            "errors": errors[:5],  # 只返回前5个错误
        }), 500
    
    # 迁移完成后，尝试删除旧目录（仅当 delete_source 为 True 且目录为空）
    if delete_source:
        try:
            remaining = list(old_path.iterdir())
            # 过滤掉隐藏文件和系统文件
            remaining = [f for f in remaining if not f.name.startswith('.')]
            if not remaining:
                shutil.rmtree(str(old_path), ignore_errors=True)
        except Exception:
            pass
    
    return jsonify({"ok": True, "migrated_count": migrated_count})


@app.post("/api/settings/select-folder")
def select_folder():
    """
    打开文件夹选择对话框（仅在 Tauri 环境下有效）
    这个 API 返回一个提示，因为实际的文件夹选择需要在前端通过 Tauri API 完成
    """
    return jsonify({
        "message": "请使用 Tauri 文件对话框选择文件夹",
        "current_dir": str(get_download_dir())
    })


@app.post("/api/settings/open-folder")
def open_folder():
    """在系统文件管理器中打开下载目录"""
    import subprocess
    import platform
    
    download_dir = get_download_dir()
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(download_dir)], check=True)
        elif system == "Windows":
            subprocess.run(["explorer", str(download_dir)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(download_dir)], check=True)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": f"无法打开目录: {e}"}), 500


# ========== 启动入口 ==========

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
