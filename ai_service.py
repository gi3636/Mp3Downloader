"""
AI 分类服务

使用智谱 AI 根据用户指定的规则对歌曲进行分类
支持逐首分类 + 并发处理，避免 token 限制
"""

import json
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def get_api_key() -> Optional[str]:
    """获取 API Key"""
    import os
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key
    
    config_file = Path.home() / ".mp3downloader" / "zhipu_api_key.txt"
    if config_file.exists():
        return config_file.read_text().strip()
    
    return None


def _classify_single_song(
    api_key: str,
    song_name: str,
    classification_rule: str,
    existing_categories: list[str]
) -> tuple[str, str]:
    """
    对单首歌曲进行分类
    
    Returns:
        (歌曲名, 分类名)
    """
    categories_hint = ""
    if existing_categories:
        categories_hint = f"\n\n【现有分类】\n{', '.join(existing_categories)}\n优先使用现有分类，避免创建相似的新分类。"
    
    prompt = f"""请根据分类规则对这首歌进行分类：

【分类规则】
{classification_rule}{categories_hint}

【歌曲】
{song_name}

【要求】
只返回分类名称，不要其他文字。如果无法确定，返回"未分类"。"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "system",
                "content": "你是一个音乐分类专家。只返回分类名称，不要其他文字。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 50,
    }
    
    response = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=600)
    response.raise_for_status()
    result = response.json()
    
    category = result["choices"][0]["message"]["content"].strip()
    # 清理可能的引号和多余字符
    category = category.strip('"\'`').strip()
    if not category:
        category = "未分类"
    
    return (song_name, category)


def _merge_similar_categories(classification: dict[str, list[str]], api_key: str) -> dict[str, list[str]]:
    """
    合并相似的分类
    """
    categories = list(classification.keys())
    if len(categories) <= 1:
        return classification
    
    prompt = f"""以下是一些音乐分类名称，请将相似或重复的分类合并：

【分类列表】
{json.dumps(categories, ensure_ascii=False)}

【要求】
1. 返回 JSON 格式的映射关系
2. 格式: {{"原分类名": "合并后的分类名", ...}}
3. 如果分类不需要合并，映射到自身
4. 只返回 JSON，不要其他文字"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    try:
        response = requests.post(ZHIPU_API_URL, headers=headers, json=data, timeout=600)
        response.raise_for_status()
        result = response.json()
        
        content = result["choices"][0]["message"]["content"].strip()
        # 解析 JSON
        if "```" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            content = content[start:end]
        
        mapping = json.loads(content)
        
        # 应用映射
        merged: dict[str, list[str]] = {}
        for old_cat, songs in classification.items():
            new_cat = mapping.get(old_cat, old_cat)
            if new_cat not in merged:
                merged[new_cat] = []
            merged[new_cat].extend(songs)
        
        return merged
    except Exception:
        # 合并失败，返回原分类
        return classification


def classify_songs(song_names: list[str], classification_rule: str) -> dict:
    """
    使用 AI 对歌曲进行分类（并发逐首分类）
    
    Args:
        song_names: 歌曲名称列表
        classification_rule: 用户指定的分类规则
    
    Returns:
        分类结果字典 {"专辑名": ["歌曲1", "歌曲2"], ...}
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("未配置智谱 AI API Key")
    
    if not song_names:
        return {}
    
    # 并发分类
    classification: dict[str, list[str]] = {}
    existing_categories: list[str] = []
    
    # 使用线程池并发处理，但限制并发数避免 API 限流
    max_workers = min(5, len(song_names))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 分批处理，每批完成后更新现有分类
        batch_size = 10
        for i in range(0, len(song_names), batch_size):
            batch = song_names[i:i + batch_size]
            
            futures = {
                executor.submit(
                    _classify_single_song,
                    api_key,
                    song,
                    classification_rule,
                    existing_categories.copy()
                ): song
                for song in batch
            }
            
            for future in as_completed(futures):
                try:
                    song_name, category = future.result()
                    if category not in classification:
                        classification[category] = []
                        existing_categories.append(category)
                    classification[category].append(song_name)
                except Exception as e:
                    # 单首失败，放入未分类
                    song = futures[future]
                    if "未分类" not in classification:
                        classification["未分类"] = []
                    classification["未分类"].append(song)
    
    # 合并相似分类
    if len(classification) > 3:
        classification = _merge_similar_categories(classification, api_key)
    
    return classification
