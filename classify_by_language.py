#!/usr/bin/env python3
"""
按语言分类音乐文件

分类规则：
- 日语：日文歌曲
- 中文：中文歌曲
- 英文：英文歌曲
- 音乐：纯音乐/无人声
"""

import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

CATEGORIES = ["日语", "中文", "英文", "音乐"]

def get_api_key() -> str:
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key
    
    config_file = Path.home() / ".mp3downloader" / "zhipu_api_key.txt"
    if config_file.exists():
        return config_file.read_text().strip()
    
    raise ValueError("未找到 API Key，请设置 ZHIPU_API_KEY 环境变量或在 ~/.mp3downloader/zhipu_api_key.txt 中配置")


def classify_single(api_key: str, song_name: str) -> tuple[str, str]:
    """对单首歌曲进行语言分类"""
    prompt = f"""请判断这首歌的语言类型，只能返回以下四个分类之一：
- 日语（日文歌曲）
- 中文（中文歌曲）
- 英文（英文歌曲）
- 音乐（纯音乐/无人声/BGM）

【歌曲名称】
{song_name}

【要求】
只返回分类名称（日语/中文/英文/音乐），不要其他文字。"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "system",
                "content": "你是一个音乐语言识别专家。只返回：日语、中文、英文、音乐 四个分类之一。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 20,
    }
    
    response = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=60)
    response.raise_for_status()
    result = response.json()
    
    category = result["choices"][0]["message"]["content"].strip()
    category = category.strip('"\'`').strip()
    
    # 标准化分类名
    if "日" in category:
        category = "日语"
    elif "中" in category:
        category = "中文"
    elif "英" in category:
        category = "英文"
    elif "音乐" in category or "纯" in category or "BGM" in category.upper():
        category = "音乐"
    else:
        category = "音乐"  # 默认
    
    return (song_name, category)


def classify_albums(music_dir: str, dry_run: bool = True):
    """
    对音乐目录中的专辑进行语言分类
    
    Args:
        music_dir: 音乐根目录
        dry_run: 如果为 True，只打印不实际移动
    """
    api_key = get_api_key()
    music_path = Path(music_dir)
    
    if not music_path.exists():
        print(f"目录不存在: {music_dir}")
        return
    
    # 收集所有专辑（子目录）
    albums = [d for d in music_path.iterdir() if d.is_dir() and d.name not in CATEGORIES]
    
    if not albums:
        print("没有找到需要分类的专辑")
        return
    
    print(f"找到 {len(albums)} 个专辑待分类\n")
    
    # 创建分类目录
    for cat in CATEGORIES:
        cat_dir = music_path / cat
        if not cat_dir.exists() and not dry_run:
            cat_dir.mkdir(exist_ok=True)
    
    # 并发分类
    results: dict[str, str] = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(classify_single, api_key, album.name): album
            for album in albums
        }
        
        for future in as_completed(futures):
            album = futures[future]
            try:
                _, category = future.result()
                results[album.name] = category
                print(f"  [{category}] {album.name}")
            except Exception as e:
                print(f"  [错误] {album.name}: {e}")
                results[album.name] = "音乐"  # 默认
    
    print("\n" + "="*50)
    print("分类结果汇总：")
    for cat in CATEGORIES:
        count = sum(1 for v in results.values() if v == cat)
        print(f"  {cat}: {count} 个专辑")
    
    if dry_run:
        print("\n[预览模式] 未实际移动文件")
        print("移除 --dry-run 参数以执行移动")
    else:
        print("\n开始移动文件...")
        moved = 0
        for album in albums:
            category = results.get(album.name, "音乐")
            target_dir = music_path / category / album.name
            if album != target_dir and not target_dir.exists():
                try:
                    shutil.move(str(album), str(target_dir))
                    moved += 1
                except Exception as e:
                    print(f"  移动失败 {album.name}: {e}")
        print(f"已移动 {moved} 个专辑")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="按语言分类音乐专辑")
    parser.add_argument("music_dir", nargs="?", help="音乐目录路径")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际移动文件")
    
    args = parser.parse_args()
    
    # 如果未指定目录，尝试从配置读取
    music_dir = args.music_dir
    if not music_dir:
        config_file = Path.home() / ".mp3downloader" / "config.json"
        if config_file.exists():
            import json
            config = json.loads(config_file.read_text())
            music_dir = config.get("music_directory")
    
    if not music_dir:
        print("请指定音乐目录路径")
        print("用法: python classify_by_language.py /path/to/music [--dry-run]")
        return
    
    classify_albums(music_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
