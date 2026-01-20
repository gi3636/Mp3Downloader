#!/usr/bin/env python3
"""
修复已下载文件的封面

遍历 download 目录，根据文件名查找对应的 YouTube 视频封面
"""

import json
import re
import sys
from pathlib import Path
from subprocess import run, TimeoutExpired

from config import DOWNLOAD_DIR, YTDLP_BIN


def search_youtube_video(title: str) -> str | None:
    """通过标题搜索 YouTube 视频，获取封面"""
    # 清理标题中的特殊字符
    clean_title = re.sub(r'[【】\[\]「」『』（）\(\)\|｜]', ' ', title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:80]  # 限制长度
    
    # 使用 yt-dlp 搜索
    cmd = [
        str(YTDLP_BIN),
        f"ytsearch1:{clean_title}",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--socket-timeout", "10",
    ]
    
    try:
        res = run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return None
        
        info = json.loads(res.stdout)
        entries = info.get("entries", [])
        if not entries:
            return None
        
        entry = entries[0]
        
        # 获取最佳封面
        thumbnail = entry.get("thumbnail")
        if not thumbnail:
            thumbs = entry.get("thumbnails", [])
            if thumbs:
                best = None
                best_area = -1
                for t in thumbs:
                    if not isinstance(t, dict):
                        continue
                    url = t.get("url")
                    if not url or "no_thumbnail" in url:
                        continue
                    w = t.get("width") or 0
                    h = t.get("height") or 0
                    area = int(w) * int(h)
                    if area >= best_area:
                        best_area = area
                        best = url
                thumbnail = best
        
        return thumbnail
    except TimeoutExpired:
        return None
    except Exception:
        return None


def fix_covers_for_job(job_dir: Path) -> int:
    """修复单个任务目录的封面"""
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
    
    fixed_count = 0
    new_thumbs = {}
    
    for i, mp3 in enumerate(mp3_files):
        title = mp3.stem
        
        # 检查是否需要修复
        current_thumb = existing_thumbs.get(title)
        needs_fix = (
            not current_thumb or 
            current_thumb == playlist_thumb or
            "no_thumbnail" in (current_thumb or "")
        )
        
        if not needs_fix:
            new_thumbs[title] = current_thumb
            continue
        
        sys.stdout.write(f"\r  [{i+1}/{len(mp3_files)}] 搜索: {title[:50]}...")
        sys.stdout.flush()
        
        thumbnail = search_youtube_video(title)
        
        if thumbnail:
            new_thumbs[title] = thumbnail
            fixed_count += 1
        elif current_thumb:
            new_thumbs[title] = current_thumb
    
    print()  # 换行
    
    # 保存更新后的封面数据
    if new_thumbs:
        thumbs_file.write_text(json.dumps(new_thumbs, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return fixed_count


def main():
    print("🔍 扫描下载目录...")
    
    if not DOWNLOAD_DIR.exists():
        print("❌ 下载目录不存在")
        return
    
    job_dirs = [d for d in DOWNLOAD_DIR.iterdir() if d.is_dir()]
    
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
