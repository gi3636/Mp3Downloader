"""
应用配置

定义全局路径和配置常量
"""

from pathlib import Path


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# yt-dlp 可执行文件路径
YTDLP_BIN = BASE_DIR / "yt-dlp_macos"

# 任务目录 (存放 ZIP 等临时文件)
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# 下载存档文件 (避免重复下载)
ARCHIVE_FILE = BASE_DIR / "downloaded.txt"

# 下载目录 (存放 MP3 文件)
DOWNLOAD_DIR = BASE_DIR / "download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
