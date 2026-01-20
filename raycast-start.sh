#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title 启动 YouTube 音乐下载器
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🎵
# @raycast.packageName YouTube Music Downloader

# Documentation:
# @raycast.description 启动 YouTube 音乐下载器服务
# @raycast.author Your Name

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🎵 启动 YouTube 音乐下载器..."
echo "📁 项目目录: $SCRIPT_DIR"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "⚠️  虚拟环境不存在，正在初始化..."
    make init
fi

# 检查前端构建
if [ ! -f "static/index.html" ]; then
    echo "⚠️  前端未构建，正在构建..."
    make web_build
fi

# 启动服务
echo "🚀 启动服务器..."
echo "📍 访问地址: http://127.0.0.1:5001"
echo ""
echo "按 Ctrl+C 停止服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PORT=5001 .venv/bin/python app.py
