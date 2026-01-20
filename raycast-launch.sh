#!/bin/bash

# @raycast.schemaVersion 1
# @raycast.title YouTube 下载器
# @raycast.mode fullOutput
# @raycast.icon 🎵
# @raycast.description 启动 YouTube 音乐下载器

PROJECT_DIR="/Users/fenggi/Documents/github/Mp3Downloader"
PORT=5001
LOG_FILE="/tmp/ytmusic-downloader.log"

cd "$PROJECT_DIR" || { echo "❌ 项目不存在"; exit 1; }

echo "🎵 启动中..."

# 自动构建前端（如有更新）
STATIC_JS=$(find static/assets -name "*.js" 2>/dev/null | head -1)
if [ -z "$STATIC_JS" ] || [ -n "$(find web/src -newer "$STATIC_JS" 2>/dev/null | head -1)" ]; then
    echo "📦 构建前端..."
    (cd web && npm run build --silent)
fi

# 关闭旧服务
OLD_PID=$(lsof -ti :$PORT 2>/dev/null)
[ -n "$OLD_PID" ] && kill $OLD_PID 2>/dev/null && sleep 1

# 启动服务
PORT=$PORT .venv/bin/python app.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 等待启动
for _ in {1..20}; do
    curl -s http://127.0.0.1:$PORT >/dev/null 2>&1 && break
    sleep 0.5
done

if curl -s http://127.0.0.1:$PORT >/dev/null 2>&1; then
    open http://127.0.0.1:$PORT
    echo "✅ 已启动: http://127.0.0.1:$PORT"
    echo "🛑 停止: kill $SERVER_PID"
else
    echo "❌ 启动失败，查看日志: cat $LOG_FILE"
    tail -10 "$LOG_FILE"
    exit 1
fi
