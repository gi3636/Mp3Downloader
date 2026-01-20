#!/usr/bin/env python3
"""
修复已下载文件的封面

遍历 download 目录，根据文件名查找对应的 YouTube 视频封面
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run, TimeoutExpired

from config import YTDLP_BIN
from settings_service import get_download_dir

# 并行搜索的线程数
MAX_WORKERS = 4


def search_youtube_video(title: str) -> str | None:
    """通过标题搜索 YouTube 视频，获取封面"""
    # 清理标题中的特殊字符和序号
    clean_title = re.sub(r'^\d+\s*[-\.]\s*', '', title)  # 移除开头的序号
    clean_title = re.sub(r'[【】\[\]「」『』（）\(\)\|｜\-–—]', ' ', clean_title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:100]  # 增加长度限制
    
    if not clean_title or len(clean_title) < 3:
        return None
    
    # 使用 yt-dlp 搜索
    cmd = [
        str(YTDLP_BIN),
        f"ytsearch1:{clean_title}",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--socket-timeout", "8",
    ]
    
    try:
        res = run(cmd, capture_output=True, text=True, timeout=12)
        if res.returncode != 0:
            return None
        
        info = json.loads(res.stdout)
        entries = info.get("entries", [])
        if not entries:
            return None
        
        entry = entries[0]
        
        # 获取最佳封面 (优先使用 maxresdefault)
        thumbnails = entry.get("thumbnails", [])
        thumbnail = None
        
        # 按优先级查找封面
        for t in thumbnails:
            if not isinstance(t, dict):
                continue
            url = t.get("url", "")
            if not url or "no_thumbnail" in url:
                continue
            # 优先使用高清封面
            if "maxresdefault" in url or "hqdefault" in url:
                thumbnail = url
                break
            if not thumbnail:
                thumbnail = url
        
        if not thumbnail:
            thumbnail = entry.get("thumbnail")
        
        return thumbnail
    except TimeoutExpired:
        return None
    except Exception:
        return None


def fix_covers_for_job(job_dir: Path) -> int:
    """修复单个任务目录的封面（使用并行处理）"""
    thumbs_file = job_dir / "__track_thumbnails.json"
    meta_file = job_dir / "__meta.json"
    
    # 读取现有封面数据
    existing_thumbs = {}
    if thumbs_file.exists():
        try:
            existing_thumbs = json.loads(thumbs_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # 读取播放列表封面
    playlist_thumb = None
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            playlist_thumb = meta.get("thumbnail_url")
        except Exception:
            pass
    
    # 查找所有 MP3 文件
    mp3_files = list(job_dir.rglob("*.mp3"))
    if not mp3_files:
        return 0
    
    # 收集需要修复的文件
    to_fix = []
    new_thumbs = {}
    
    for mp3 in mp3_files:
        title = mp3.stem
        current_thumb = existing_thumbs.get(title)
        
        # 检查是否需要修复
        needs_fix = (
            not current_thumb or 
            current_thumb == playlist_thumb or
            "no_thumbnail" in (current_thumb or "")
        )
        
        if needs_fix:
            to_fix.append(title)
        else:
            new_thumbs[title] = current_thumb
    
    if not to_fix:
        return 0
    
    print(f"  需要修复 {len(to_fix)} 个封面，使用 {MAX_WORKERS} 线程并行处理...")
    
    fixed_count = 0
    completed = 0
    
    # 使用线程池并行搜索
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_title = {executor.submit(search_youtube_video, title): title for title in to_fix}
        
        for future in as_completed(future_to_title):
            title = future_to_title[future]
            completed += 1
            
            try:
                thumbnail = future.result()
                if thumbnail:
                    new_thumbs[title] = thumbnail
                    fixed_count += 1
                elif existing_thumbs.get(title):
                    new_thumbs[title] = existing_thumbs[title]
            except Exception:
                if existing_thumbs.get(title):
                    new_thumbs[title] = existing_thumbs[title]
            
            # 显示进度
            sys.stdout.write(f"\r  进度: {completed}/{len(to_fix)} (已修复: {fixed_count})")
            sys.stdout.flush()
    
    print()  # 换行
    
    # 保存更新后的封面数据
    if new_thumbs:
        thumbs_file.write_text(json.dumps(new_thumbs, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return fixed_count


def main():
    print("🔍 扫描下载目录...")
    
    download_dir = get_download_dir()
    print(f"📁 下载目录: {download_dir}")
    
    if not download_dir.exists():
        print("❌ 下载目录不存在")
        return
    
    job_dirs = [d for d in download_dir.iterdir() if d.is_dir()]
    
    if not job_dirs:
        print("❌ 没有找到任何下载任务")
        return
    
    total_fixed = 0
    
    for job_dir in job_dirs:
        # 检查是否有 MP3 文件
        mp3_count = len(list(job_dir.rglob("*.mp3")))
        if mp3_count == 0:
            continue
            
        print(f"\n📁 {job_dir.name} ({mp3_count} 首)")
        fixed = fix_covers_for_job(job_dir)
        total_fixed += fixed
        if fixed > 0:
            print(f"  ✅ 修复了 {fixed} 个封面")
        else:
            print(f"  ✓ 无需修复")
    
    print(f"\n🎉 完成！共修复 {total_fixed} 个封面")


if __name__ == "__main__":
    main()
