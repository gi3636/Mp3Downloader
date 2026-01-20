#!/usr/bin/env python3
"""
清理下载文件夹中的 hash 命名文件夹

将 MP3 文件移动到以专辑名命名的文件夹，无专辑名的移到"未分类"
"""

import json
import re
import shutil
from pathlib import Path

from settings_service import get_download_dir


def cleanup_hash_folders():
    download_dir = get_download_dir()
    hash_pattern = re.compile(r'^[0-9a-f]{32}$')  # 32位 hex hash
    
    moved_count = 0
    deleted_folders = 0
    
    print(f"扫描目录: {download_dir}")
    print("-" * 50)
    
    for folder in sorted(download_dir.iterdir()):
        if not folder.is_dir():
            continue
        
        # 检查是否是 hash 命名的文件夹
        if not hash_pattern.match(folder.name):
            continue
        
        print(f"\n发现 hash 文件夹: {folder.name}")
        
        # 读取 job meta 获取专辑名
        meta_file = folder / "__job_meta.json"
        album_name = None
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                album_name = meta.get("title")
                print(f"  专辑名: {album_name}")
            except Exception as e:
                print(f"  读取 meta 失败: {e}")
        
        # 如果没有专辑名，使用"未分类"
        if not album_name:
            album_name = "未分类"
            print(f"  无专辑名，使用: {album_name}")
        
        # 创建目标文件夹
        target_dir = download_dir / album_name
        target_dir.mkdir(exist_ok=True)
        
        # 移动所有 MP3 文件
        mp3_files = list(folder.rglob("*.mp3"))
        print(f"  找到 {len(mp3_files)} 个 MP3 文件")
        
        for mp3_file in mp3_files:
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
                print(f"    移动: {mp3_file.name}")
            except Exception as e:
                print(f"    移动失败: {mp3_file.name} - {e}")
        
        # 删除空的 hash 文件夹
        try:
            if folder.exists() and not any(folder.rglob("*.mp3")):
                shutil.rmtree(folder)
                deleted_folders += 1
                print(f"  已删除文件夹")
        except Exception as e:
            print(f"  删除文件夹失败: {e}")
    
    print("\n" + "=" * 50)
    print(f"完成！移动了 {moved_count} 首曲目，删除了 {deleted_folders} 个空文件夹")


if __name__ == "__main__":
    cleanup_hash_folders()
