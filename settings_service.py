"""
用户设置服务

持久化用户配置到 JSON 文件
"""

import json
import os
from pathlib import Path
from typing import Any


# 设置文件路径 (存放在用户目录下)
SETTINGS_DIR = Path.home() / ".mp3downloader"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# 默认设置
DEFAULT_SETTINGS = {
    "download_dir": str(Path.home() / "Downloads" / "Mp3Downloader"),
}


def _ensure_settings_dir():
    """确保设置目录存在"""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_settings() -> dict:
    """加载设置文件"""
    _ensure_settings_dir()
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 合并默认设置（确保新增的设置项有默认值）
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()


def _save_settings(settings: dict):
    """保存设置到文件"""
    _ensure_settings_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_setting(key: str, default: Any = None) -> Any:
    """获取单个设置项"""
    settings = _load_settings()
    return settings.get(key, default)


def get_all_settings() -> dict:
    """获取所有设置"""
    return _load_settings()


def update_setting(key: str, value: Any):
    """更新单个设置项"""
    settings = _load_settings()
    settings[key] = value
    _save_settings(settings)


def update_settings(updates: dict):
    """批量更新设置"""
    settings = _load_settings()
    settings.update(updates)
    _save_settings(settings)


def get_download_dir() -> Path:
    """获取下载目录（确保目录存在）"""
    dir_str = get_setting("download_dir", DEFAULT_SETTINGS["download_dir"])
    download_dir = Path(dir_str).expanduser()
    download_dir.mkdir(parents=True, exist_ok=True)
    return download_dir
