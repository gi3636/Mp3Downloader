"""
应用配置

定义全局路径和配置常量
支持通过环境变量覆盖默认配置（用于打包后的应用）
"""

import os
from pathlib import Path


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# yt-dlp 可执行文件路径 (支持环境变量覆盖)
_ytdlp_env = os.environ.get("YTDLP_BIN")
if _ytdlp_env:
    YTDLP_BIN = Path(_ytdlp_env)
else:
    YTDLP_BIN = BASE_DIR / "yt-dlp_macos"

# 任务目录 (存放 ZIP 等临时文件)
_jobs_env = os.environ.get("JOBS_DIR")
if _jobs_env:
    JOBS_DIR = Path(_jobs_env)
else:
    JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# 下载存档文件 (避免重复下载)
ARCHIVE_FILE = JOBS_DIR.parent / "downloaded.txt"

# 下载目录 (存放 MP3 文件)
_download_env = os.environ.get("DOWNLOAD_DIR")
if _download_env:
    DOWNLOAD_DIR = Path(_download_env)
else:
    DOWNLOAD_DIR = BASE_DIR / "download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 代理配置 (可选，用于加速 YouTube 访问)
# 格式: http://host:port 或 socks5://host:port
PROXY_URL = os.environ.get("YTDLP_PROXY", "")

# 打印配置信息（调试用）
if os.environ.get("DEBUG"):
    print(f"[Config] BASE_DIR: {BASE_DIR}")
    print(f"[Config] YTDLP_BIN: {YTDLP_BIN}")
    print(f"[Config] JOBS_DIR: {JOBS_DIR}")
    print(f"[Config] DOWNLOAD_DIR: {DOWNLOAD_DIR}")
