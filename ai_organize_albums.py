#!/usr/bin/env python3
"""
使用 AI 自动整理专辑

使用智谱 AI 分析歌曲名称，推断它们应该属于哪个专辑，并自动整理文件。
"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

import requests

from settings_service import get_download_dir


# 智谱 AI API 配置
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def get_api_key() -> Optional[str]:
    """获取 API Key（从环境变量或配置文件）"""
    # 优先从环境变量读取
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key
    
    # 从配置文件读取
    config_file = Path.home() / ".mp3downloader" / "zhipu_api_key.txt"
    if config_file.exists():
        return config_file.read_text().strip()
    
    return None


def save_api_key(key: str):
    """保存 API Key 到配置文件"""
    config_dir = Path.home() / ".mp3downloader"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "zhipu_api_key.txt"
    config_file.write_text(key)
    print(f"API Key 已保存到: {config_file}")


def call_zhipu_ai(api_key: str, prompt: str) -> Optional[str]:
    """调用智谱 AI API"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "glm-4-flash",  # 使用免费的 flash 模型
        "messages": [
            {
                "role": "system",
                "content": "你是一个音乐分类专家。根据歌曲名称列表，分析它们可能属于的专辑或歌手，并给出分组建议。"
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.3,
    }
    
    try:
        response = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"API 调用失败: {e}")
        return None


def get_song_list(download_dir: Path) -> list[tuple[Path, str]]:
    """获取所有未分类的歌曲"""
    songs = []
    
    # 扫描根目录下的 MP3 文件
    for mp3_file in download_dir.glob("*.mp3"):
        songs.append((mp3_file, mp3_file.stem))
    
    # 扫描 "未分类" 文件夹
    unsorted_dir = download_dir / "未分类"
    if unsorted_dir.exists():
        for mp3_file in unsorted_dir.glob("*.mp3"):
            songs.append((mp3_file, mp3_file.stem))
    
    return songs


def parse_ai_response(response: str) -> dict[str, list[str]]:
    """解析 AI 返回的分组结果"""
    groups = {}
    
    # 尝试解析 JSON 格式
    try:
        # 查找 JSON 代码块
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
            return json.loads(json_str)
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
            return json.loads(json_str)
        else:
            # 尝试直接解析
            return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    print("警告: 无法解析 AI 响应为 JSON，跳过整理")
    return {}


def organize_songs(download_dir: Path, groups: dict[str, list[str]], songs: list[tuple[Path, str]]):
    """根据分组结果整理歌曲"""
    # 创建歌曲名到文件路径的映射
    song_map = {name: path for path, name in songs}
    
    moved_count = 0
    
    for album_name, song_names in groups.items():
        if not album_name or album_name in ("未知", "其他", "未分类"):
            continue
        
        # 创建专辑文件夹
        album_dir = download_dir / album_name
        album_dir.mkdir(exist_ok=True)
        
        for song_name in song_names:
            if song_name not in song_map:
                # 尝试模糊匹配
                for name, path in song_map.items():
                    if song_name in name or name in song_name:
                        song_map[song_name] = path
                        break
            
            if song_name in song_map:
                src_path = song_map[song_name]
                dest_path = album_dir / src_path.name
                
                if src_path.exists() and not dest_path.exists():
                    try:
                        shutil.move(str(src_path), str(dest_path))
                        moved_count += 1
                        print(f"  移动: {src_path.name} -> {album_name}/")
                    except Exception as e:
                        print(f"  移动失败: {src_path.name} - {e}")
    
    return moved_count


def main():
    print("=" * 60)
    print("AI 专辑整理工具")
    print("=" * 60)
    
    # 获取 API Key
    api_key = get_api_key()
    if not api_key:
        print("\n未找到智谱 AI API Key。")
        print("请输入你的 API Key (从 https://open.bigmodel.cn 获取):")
        api_key = input("> ").strip()
        if not api_key:
            print("错误: API Key 不能为空")
            return
        save_api_key(api_key)
    
    # 获取歌曲列表
    download_dir = get_download_dir()
    songs = get_song_list(download_dir)
    
    if not songs:
        print("\n没有找到需要整理的歌曲。")
        return
    
    print(f"\n找到 {len(songs)} 首待整理的歌曲:")
    for _, name in songs[:10]:
        print(f"  - {name}")
    if len(songs) > 10:
        print(f"  ... 以及其他 {len(songs) - 10} 首")
    
    # 构建 prompt
    song_names = [name for _, name in songs]
    prompt = f"""以下是一组歌曲名称列表，请分析它们可能属于的专辑或歌手，并给出分组建议。

歌曲列表:
{json.dumps(song_names, ensure_ascii=False, indent=2)}

请以 JSON 格式返回分组结果，格式如下:
{{
  "专辑名或歌手名1": ["歌曲1", "歌曲2"],
  "专辑名或歌手名2": ["歌曲3", "歌曲4"]
}}

注意:
1. 如果歌曲名包含明确的专辑或歌手信息，请使用它
2. 如果无法确定，可以根据风格或语言进行分组
3. 返回的歌曲名必须与输入列表中的完全一致
4. 只返回 JSON，不要其他文字"""

    print("\n正在调用 AI 分析...")
    response = call_zhipu_ai(api_key, prompt)
    
    if not response:
        print("AI 分析失败")
        return
    
    print("\nAI 分析结果:")
    print("-" * 40)
    print(response)
    print("-" * 40)
    
    # 解析结果
    groups = parse_ai_response(response)
    
    if not groups:
        print("无法解析 AI 结果")
        return
    
    print(f"\n识别出 {len(groups)} 个专辑分组:")
    for album, songs_in_album in groups.items():
        print(f"  [{album}] - {len(songs_in_album)} 首")
    
    # 确认是否执行
    print("\n是否按照以上分组整理文件? (y/n)")
    confirm = input("> ").strip().lower()
    
    if confirm != "y":
        print("已取消")
        return
    
    # 执行整理
    print("\n开始整理...")
    moved_count = organize_songs(download_dir, groups, songs)
    
    print(f"\n完成! 已移动 {moved_count} 首歌曲")


if __name__ == "__main__":
    main()
