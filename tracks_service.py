"""
曲目服务模块

提供:
- MP3 文件扫描与列表
- 文件路径编解码 (Base64)
- 元数据读写
"""

import base64
import json
import os
from pathlib import Path

from mutagen.mp3 import MP3


def b64_encode_path(rel_path: str) -> str:
    """
    将相对路径编码为 URL 安全的 Base64 字符串
    
    用于生成曲目 ID，避免 URL 中出现特殊字符
    
    Args:
        rel_path: 相对路径
        
    Returns:
        Base64 编码的字符串
    """
    token = base64.urlsafe_b64encode(rel_path.encode("utf-8")).decode("ascii")
    return token.rstrip("=")


def b64_decode_path(token: str) -> str | None:
    """
    将 Base64 字符串解码为相对路径
    
    Args:
        token: Base64 编码的字符串
        
    Returns:
        相对路径，解码失败返回 None
    """
    if not token:
        return None
    
    # 补齐 padding
    pad = "=" * ((4 - (len(token) % 4)) % 4)
    
    try:
        raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
        return raw.decode("utf-8")
    except Exception:
        return None


def list_mp3_tracks(output_dir: Path) -> list[dict]:
    """
    扫描目录下的所有 MP3 文件
    
    Args:
        output_dir: 扫描目录
        
    Returns:
        曲目列表，每项包含 id, title, duration_seconds, rel_path, album, created_at, size_bytes
    """
    tracks: list[dict] = []
    
    if not output_dir.exists():
        return tracks

    for fp in sorted(output_dir.rglob("*.mp3")):
        if not fp.is_file():
            continue

        try:
            rel = fp.relative_to(output_dir).as_posix()
        except Exception:
            continue

        # 获取时长
        duration_seconds = None
        try:
            audio = MP3(fp)
            if audio and audio.info and audio.info.length:
                duration_seconds = int(audio.info.length)
        except Exception:
            pass

        # 获取专辑名 (从路径中提取)
        album = None
        parts = rel.split("/")
        if len(parts) >= 2:
            # 格式: job_id/album_name/track.mp3
            album = parts[1] if len(parts) >= 3 else parts[0]
        
        # 获取创建时间
        created_at = None
        try:
            created_at = fp.stat().st_ctime
        except Exception:
            pass

        # 获取文件大小
        size_bytes = None
        try:
            size_bytes = fp.stat().st_size
        except Exception:
            pass

        tracks.append({
            "id": b64_encode_path(rel),
            "title": fp.stem,
            "duration_seconds": duration_seconds,
            "rel_path": rel,
            "album": album,
            "created_at": created_at,
            "size_bytes": size_bytes,
        })

    return tracks


def resolve_track_path(output_dir: Path, rel_path: str) -> Path | None:
    """
    安全地解析曲目文件路径
    
    防止路径遍历攻击，确保文件在指定目录内
    
    Args:
        output_dir: 基础目录
        rel_path: 相对路径
        
    Returns:
        完整文件路径，无效返回 None
    """
    if not rel_path:
        return None

    # 检查空字节注入
    if "\x00" in rel_path:
        return None

    p = Path(rel_path)
    
    # 禁止绝对路径
    if p.is_absolute():
        return None

    # 解析完整路径
    full = (output_dir / p).resolve()
    
    try:
        base = output_dir.resolve()
    except Exception:
        return None

    # 确保在基础目录内
    if not str(full).startswith(str(base) + os.sep) and full != base:
        return None

    # 只允许 MP3 文件
    if full.suffix.lower() != ".mp3":
        return None
    
    if not full.exists() or not full.is_file():
        return None

    return full


def write_track_meta(output_dir: Path, track_rel_path: str, thumbnail_url: str | None) -> None:
    """
    写入单曲封面元数据
    
    Args:
        output_dir: 输出目录
        track_rel_path: 曲目相对路径
        thumbnail_url: 封面图 URL
    """
    if not thumbnail_url:
        return
    try:
        meta_dir = output_dir / "__track_meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        # 使用 base64 编码的路径作为文件名
        meta_file = meta_dir / f"{b64_encode_path(track_rel_path)}.json"
        meta_file.write_text(json.dumps({"thumbnail_url": thumbnail_url}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def read_track_meta(output_dir: Path, track_rel_path: str) -> dict | None:
    """
    读取单曲封面元数据
    
    Args:
        output_dir: 输出目录
        track_rel_path: 曲目相对路径
        
    Returns:
        元数据字典，不存在返回 None
    """
    try:
        meta_dir = output_dir / "__track_meta"
        meta_file = meta_dir / f"{b64_encode_path(track_rel_path)}.json"
        if not meta_file.exists():
            return None
        raw = meta_file.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return None


def write_job_meta(output_dir: Path, title: str | None, thumbnail_url: str | None) -> None:
    """
    写入任务元数据文件
    
    Args:
        output_dir: 输出目录
        title: 专辑/播放列表标题
        thumbnail_url: 封面图 URL
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        meta_path = output_dir / "__meta.json"
        meta = {
            "title": title,
            "thumbnail_url": thumbnail_url,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def read_job_meta(output_dir: Path) -> dict | None:
    """
    读取任务元数据文件
    
    Args:
        output_dir: 输出目录
        
    Returns:
        元数据字典，不存在或读取失败返回 None
    """
    try:
        meta_path = output_dir / "__meta.json"
        if not meta_path.exists():
            return None
        raw = meta_path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return None
