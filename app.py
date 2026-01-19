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

from config import DOWNLOAD_DIR, YTDLP_BIN
from job_manager import JobManager
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
      
    响应: { "job_id": "xxx" }
    """
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    video_urls = data.get("video_urls")
    video_titles = data.get("video_titles")
    video_thumbnails = data.get("video_thumbnails")

    if not url:
        return jsonify({"error": "url 不能为空"}), 400

    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url 必须以 http:// 或 https:// 开头"}), 400

    # 如果指定了 video_urls，则只下载选中的曲目
    if video_urls and isinstance(video_urls, list) and len(video_urls) > 0:
        job_id = _manager.create_job_with_urls(url, video_urls, video_titles, video_thumbnails)
    else:
        job_id = _manager.create_job(url)
    
    return jsonify({"job_id": job_id})


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
    tracks = list_mp3_tracks(DOWNLOAD_DIR)
    
    for t in tracks:
        rel = t.get("rel_path")
        cover_url = None
        album_title = None
        
        # 尝试从元数据获取封面
        if isinstance(rel, str):
            parts = rel.split("/")
            if parts:
                job_folder = DOWNLOAD_DIR / parts[0]
                meta = read_job_meta(job_folder)
                if meta:
                    if meta.get("thumbnail_url"):
                        cover_url = str(meta.get("thumbnail_url"))
                    if meta.get("title"):
                        album_title = str(meta.get("title"))
                
                # 尝试读取单曲封面 (从 track_thumbnails.json)
                track_thumbs_file = job_folder / "__track_thumbnails.json"
                if track_thumbs_file.exists():
                    try:
                        import json
                        track_thumbs = json.loads(track_thumbs_file.read_text(encoding="utf-8"))
                        title = t.get("title", "")
                        if title in track_thumbs:
                            cover_url = track_thumbs[title]
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

    fp = resolve_track_path(DOWNLOAD_DIR, rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    return send_file(fp, mimetype="audio/mpeg", as_attachment=False)


@app.post("/api/library/tracks/<track_id>/delete")
def delete_library_track(track_id: str):
    """删除音乐库中的曲目"""
    rel = b64_decode_path(track_id)
    if not rel:
        return jsonify({"error": "invalid track"}), 400

    fp = resolve_track_path(DOWNLOAD_DIR, rel)
    if not fp:
        return jsonify({"error": "file not found"}), 404

    try:
        fp.unlink()
    except Exception:
        return jsonify({"error": "delete failed"}), 500

    # 清理空目录
    try:
        parent = fp.parent
        while parent != DOWNLOAD_DIR and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    except Exception:
        pass

    return jsonify({"ok": True})


# ========== 启动入口 ==========

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
