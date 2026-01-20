#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title 打开 YouTube 音乐下载器
# @raycast.mode silent

# Optional parameters:
# @raycast.icon 🌐
# @raycast.packageName YouTube Music Downloader

# Documentation:
# @raycast.description 在浏览器中打开 YouTube 音乐下载器
# @raycast.author Your Name

# 检查服务是否运行
if ! curl -s http://127.0.0.1:5000 > /dev/null 2>&1; then
    echo "⚠️  服务未运行，请先执行「启动 YouTube 音乐下载器」"
    exit 1
fi

# 打开浏览器
open http://127.0.0.1:5000

echo "✅ 已在浏览器中打开"
