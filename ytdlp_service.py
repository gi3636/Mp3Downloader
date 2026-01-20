"""
yt-dlp 服务模块

封装 yt-dlp 命令行工具的调用，提供:
- URL 类型判断
- 播放列表/单曲元数据获取
- 频道播放列表获取
"""

import json
import re
from subprocess import run

from config import YTDLP_BIN, PROXY_URL


# 正则表达式: 匹配播放列表 URL 参数
_PLAYLIST_URL_RE = re.compile(r"(^|[?&])list=", re.IGNORECASE)


def _get_proxy_args() -> list[str]:
    """获取代理相关的命令行参数"""
    if PROXY_URL:
        return ["--proxy", PROXY_URL]
    return []


def looks_like_playlist_url(url: str) -> bool:
    """
    判断 URL 是否为播放列表链接
    
    Args:
        url: YouTube URL
        
    Returns:
        是否为播放列表
    """
    if not url:
        return False
    if _PLAYLIST_URL_RE.search(url):
        return True
    if "/playlist" in url:
        return True
    return False


def to_playlists_tab_url(url: str) -> str:
    """
    将频道 URL 转换为播放列表标签页 URL
    
    Args:
        url: 频道 URL
        
    Returns:
        播放列表标签页 URL
    """
    u = (url or "").strip()
    if not u:
        return u
    if "/playlists" in u:
        return u
    return u.rstrip("/") + "/playlists"


def fetch_playlists_from_channel(url: str) -> list[dict]:
    """
    获取频道的所有播放列表
    
    Args:
        url: 频道 URL
        
    Returns:
        播放列表列表，每项包含 title 和 url
    """
    playlists_url = to_playlists_tab_url(url)
    if not playlists_url:
        return []

    cmd = [
        str(YTDLP_BIN),
        "--dump-single-json",
        "--skip-download",
        "--flat-playlist",
        "--no-warnings",
        "--socket-timeout", "15",
        *_get_proxy_args(),
        playlists_url,
    ]

    res = run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return []

    raw = (res.stdout or "").strip()
    if not raw:
        return []

    try:
        info = json.loads(raw)
    except Exception:
        return []

    entries = info.get("entries")
    if not isinstance(entries, list):
        return []

    # 提取播放列表
    choices: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        
        title = entry.get("title")
        wurl = entry.get("webpage_url") or entry.get("url")
        
        if not wurl:
            continue
        
        wurl = str(wurl)
        if not looks_like_playlist_url(wurl):
            continue
        
        choices.append({
            "title": str(title) if title else wurl,
            "url": wurl,
        })

    # 去重
    unique: dict[str, dict] = {}
    for c in choices:
        unique[c["url"]] = c
    
    return list(unique.values())


def select_best_thumbnail_url(info: dict) -> str | None:
    """
    从元数据中选择最佳缩略图 URL
    
    优先选择分辨率最高的缩略图
    
    Args:
        info: yt-dlp 返回的元数据
        
    Returns:
        缩略图 URL，未找到返回 None
    """
    thumbs = info.get("thumbnails")
    
    if isinstance(thumbs, list) and thumbs:
        best = None
        best_area = -1
        
        for t in thumbs:
            if not isinstance(t, dict):
                continue
            
            url = t.get("url")
            if not url:
                continue
            
            # 计算面积
            w = t.get("width") or 0
            h = t.get("height") or 0
            try:
                area = int(w) * int(h)
            except Exception:
                area = 0
            
            if area >= best_area:
                best_area = area
                best = url
        
        if best:
            return str(best)

    # 回退到默认缩略图
    if info.get("thumbnail"):
        return str(info.get("thumbnail"))

    return None


def fetch_playlist_metadata(url: str) -> dict | None:
    """
    获取播放列表元数据
    
    Args:
        url: 播放列表 URL
        
    Returns:
        元数据字典，失败返回 None
    """
    cmd = [
        str(YTDLP_BIN),
        "--dump-single-json",
        "--skip-download",
        "--flat-playlist",
        "--no-warnings",
        "--socket-timeout", "15",
        *_get_proxy_args(),
        url,
    ]

    res = run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None

    raw = (res.stdout or "").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


def fetch_playlist_entries(url: str) -> dict | None:
    """
    获取播放列表的所有条目详情
    
    Args:
        url: 播放列表 URL
        
    Returns:
        包含 title, thumbnail, entries 的字典
    """
    cmd = [
        str(YTDLP_BIN),
        "--dump-single-json",
        "--skip-download",
        "--flat-playlist",
        "--no-warnings",
        "--socket-timeout", "15",
        *_get_proxy_args(),
        url,
    ]

    res = run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None

    raw = (res.stdout or "").strip()
    if not raw:
        return None

    try:
        info = json.loads(raw)
    except Exception:
        return None

    entries = info.get("entries") or []
    items = []
    
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        
        video_id = entry.get("id") or entry.get("url")
        title = entry.get("title") or f"Track {idx + 1}"
        duration = entry.get("duration")
        video_url = entry.get("url") or entry.get("webpage_url")
        
        # 获取缩略图：优先从 thumbnails 数组获取最佳质量
        thumbnail = entry.get("thumbnail")
        if not thumbnail:
            thumbs = entry.get("thumbnails")
            if isinstance(thumbs, list) and thumbs:
                # 选择最大的缩略图
                best = None
                best_area = -1
                for t in thumbs:
                    if not isinstance(t, dict):
                        continue
                    t_url = t.get("url")
                    if not t_url:
                        continue
                    # 跳过 no_thumbnail 占位图
                    if "no_thumbnail" in t_url:
                        continue
                    w = t.get("width") or 0
                    h = t.get("height") or 0
                    try:
                        area = int(w) * int(h)
                    except Exception:
                        area = 0
                    if area >= best_area:
                        best_area = area
                        best = t_url
                thumbnail = best
        
        # 构建完整 URL
        if video_id and not video_url:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        items.append({
            "index": idx + 1,
            "id": video_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "url": video_url,
        })

    # 使用实际获取到的条目数量，而不是 playlist_count
    # 因为 YouTube Mix 等动态播放列表的 playlist_count 可能远大于实际能获取的数量
    actual_count = len(items)

    return {
        "title": info.get("title"),
        "thumbnail": select_best_thumbnail_url(info),
        "total": actual_count,  # 使用实际数量
        "entries": items,
    }


def fetch_single_metadata(url: str) -> dict | None:
    """
    获取单个视频元数据
    
    Args:
        url: 视频 URL
        
    Returns:
        元数据字典，失败返回 None
    """
    cmd = [
        str(YTDLP_BIN),
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-playlist",
        "--socket-timeout", "15",
        *_get_proxy_args(),
        url,
    ]

    res = run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None

    raw = (res.stdout or "").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None
