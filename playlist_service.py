"""
播放列表服务模块

提供:
- 创建播放列表
- 重命名播放列表
- 添加/删除歌曲
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from settings_service import get_download_dir


def _get_playlists_file() -> Path:
    """获取播放列表配置文件路径"""
    return get_download_dir() / "__playlists.json"


def _load_playlists() -> dict:
    """加载播放列表配置"""
    playlists_file = _get_playlists_file()
    if not playlists_file.exists():
        return {"playlists": []}
    try:
        return json.loads(playlists_file.read_text(encoding="utf-8"))
    except Exception:
        return {"playlists": []}


def _save_playlists(data: dict) -> None:
    """保存播放列表配置"""
    playlists_file = _get_playlists_file()
    playlists_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_playlists() -> list[dict]:
    """获取所有播放列表"""
    data = _load_playlists()
    playlists = data.get("playlists", [])
    
    # 添加曲目数量
    download_dir = get_download_dir()
    for pl in playlists:
        folder = download_dir / pl.get("folder", "")
        if folder.exists():
            pl["track_count"] = len(list(folder.rglob("*.mp3")))
        else:
            pl["track_count"] = 0
    
    return playlists


def create_playlist(name: str) -> dict:
    """
    创建新播放列表
    
    Args:
        name: 播放列表名称
        
    Returns:
        新创建的播放列表信息
    """
    data = _load_playlists()
    playlists = data.get("playlists", [])
    
    # 生成唯一 ID 和文件夹名
    playlist_id = uuid.uuid4().hex[:8]
    folder_name = f"playlist_{playlist_id}"
    
    # 创建文件夹
    download_dir = get_download_dir()
    folder_path = download_dir / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # 创建元数据
    meta = {
        "title": name,
        "thumbnail_url": None,
    }
    meta_file = folder_path / "__meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    
    # 添加到列表
    playlist = {
        "id": playlist_id,
        "name": name,
        "folder": folder_name,
    }
    playlists.append(playlist)
    data["playlists"] = playlists
    _save_playlists(data)
    
    playlist["track_count"] = 0
    return playlist


def rename_playlist(playlist_id: str, new_name: str) -> Optional[dict]:
    """
    重命名播放列表
    
    Args:
        playlist_id: 播放列表 ID
        new_name: 新名称
        
    Returns:
        更新后的播放列表信息，不存在返回 None
    """
    data = _load_playlists()
    playlists = data.get("playlists", [])
    
    for pl in playlists:
        if pl.get("id") == playlist_id:
            pl["name"] = new_name
            _save_playlists(data)
            
            # 更新文件夹内的元数据
            download_dir = get_download_dir()
            folder = download_dir / pl.get("folder", "")
            if folder.exists():
                meta_file = folder / "__meta.json"
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
                    meta["title"] = new_name
                    meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
                pl["track_count"] = len(list(folder.rglob("*.mp3")))
            else:
                pl["track_count"] = 0
            
            return pl
    
    return None


def delete_playlist(playlist_id: str) -> bool:
    """
    删除播放列表（保留或删除歌曲可选）
    
    Args:
        playlist_id: 播放列表 ID
        
    Returns:
        是否成功删除
    """
    data = _load_playlists()
    playlists = data.get("playlists", [])
    
    for i, pl in enumerate(playlists):
        if pl.get("id") == playlist_id:
            folder = get_download_dir() / pl.get("folder", "")
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            
            playlists.pop(i)
            data["playlists"] = playlists
            _save_playlists(data)
            return True
    
    return False


def add_track_to_playlist(playlist_id: str, track_id: str) -> bool:
    """
    添加歌曲到播放列表（复制文件）
    
    Args:
        playlist_id: 播放列表 ID
        track_id: 歌曲 ID (base64 编码的相对路径)
        
    Returns:
        是否成功添加
    """
    from tracks_service import b64_decode_path, resolve_track_path
    
    data = _load_playlists()
    playlists = data.get("playlists", [])
    
    # 查找播放列表
    playlist = None
    for pl in playlists:
        if pl.get("id") == playlist_id:
            playlist = pl
            break
    
    if not playlist:
        return False
    
    # 解析源文件路径
    download_dir = get_download_dir()
    rel_path = b64_decode_path(track_id)
    if not rel_path:
        return False
    
    src_path = resolve_track_path(download_dir, rel_path)
    if not src_path:
        return False
    
    # 复制到播放列表文件夹
    dest_folder = download_dir / playlist.get("folder", "")
    if not dest_folder.exists():
        dest_folder.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_folder / src_path.name
    
    # 如果已存在同名文件，添加序号
    if dest_path.exists():
        base = src_path.stem
        ext = src_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_folder / f"{base} ({counter}){ext}"
            counter += 1
    
    try:
        shutil.copy2(src_path, dest_path)
        
        # 复制封面信息
        _copy_track_thumbnail(download_dir, rel_path, dest_folder, dest_path.name)
        
        return True
    except Exception:
        return False


def _copy_track_thumbnail(download_dir: Path, src_rel_path: str, dest_folder: Path, dest_filename: str) -> None:
    """复制歌曲封面信息到播放列表"""
    import re
    
    parts = src_rel_path.split("/")
    if not parts:
        return
    
    # 读取源封面信息
    src_job_folder = download_dir / parts[0]
    src_thumbs_file = src_job_folder / "__track_thumbnails.json"
    
    if not src_thumbs_file.exists():
        return
    
    try:
        src_thumbs = json.loads(src_thumbs_file.read_text(encoding="utf-8"))
    except Exception:
        return
    
    # 获取源文件的封面
    src_title = Path(src_rel_path).stem
    cover_url = src_thumbs.get(src_title)
    
    if not cover_url:
        # 尝试去掉编号前缀匹配
        stripped = re.sub(r'^\d+\s*[-–—]\s*', '', src_title)
        cover_url = src_thumbs.get(stripped)
    
    if not cover_url:
        return
    
    # 保存到目标播放列表
    dest_thumbs_file = dest_folder / "__track_thumbnails.json"
    try:
        dest_thumbs = json.loads(dest_thumbs_file.read_text(encoding="utf-8")) if dest_thumbs_file.exists() else {}
    except Exception:
        dest_thumbs = {}
    
    # 使用目标文件名（不含扩展名）作为 key
    dest_title = Path(dest_filename).stem
    dest_thumbs[dest_title] = cover_url
    
    try:
        dest_thumbs_file.write_text(json.dumps(dest_thumbs, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
