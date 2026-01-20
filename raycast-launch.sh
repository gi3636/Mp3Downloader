#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title YouTube 下载器
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🎵
# @raycast.packageName YouTube Downloader

# Documentation:
# @raycast.description 启动 YouTube 音乐下载器并打开浏览器
# @raycast.author fenggi

# 项目目录（写死路径）
PROJECT_DIR="/Users/fenggi/Documents/github/Mp3Downloader"
PORT=5001

cd "$PROJECT_DIR" || { echo "❌ 项目目录不存在: $PROJECT_DIR"; exit 1; }

echo "🎵 启动 YouTube 音乐下载器..."
echo "📁 项目目录: $PROJECT_DIR"
echo ""

# 检查是否需要重新构建前端
STATIC_JS=$(find "$PROJECT_DIR/static/assets" -name "*.js" -type f 2>/dev/null | head -1)
WEB_SRC_NEWEST=$(find "$PROJECT_DIR/web/src" -type f -newer "$STATIC_JS" 2>/dev/null | head -1)

if [ -n "$WEB_SRC_NEWEST" ] || [ ! -f "$STATIC_JS" ]; then
    echo "📦 检测到前端代码更新，正在重新构建..."
    cd "$PROJECT_DIR/web" && npm run build
    cd "$PROJECT_DIR"
    echo "✅ 前端构建完成"
    echo ""
fi

# 检查端口是否被占用，如果是则关闭旧服务
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 $PORT 已被占用，正在关闭旧服务..."
    OLD_PIDS=$(lsof -ti :$PORT -sTCP:LISTEN)
    kill $OLD_PIDS 2>/dev/null
    sleep 1
    # 强制杀掉
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        kill -9 $OLD_PIDS 2>/dev/null
        sleep 1
    fi
    echo "✅ 已关闭旧服务"
fi

# 后台启动服务
echo "� 启动服务器..."
PORT=$PORT .venv/bin/python app.py > /tmp/ytmusic-downloader.log 2>&1 &
SERVER_PID=$!

# 等待服务启动
echo "⏳ 等待服务启动..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:$PORT > /dev/null 2>&1; then
        echo "✅ 服务启动成功！"
        echo "📍 访问地址: http://127.0.0.1:$PORT"
        echo ""
        
        # 打开浏览器
        open http://127.0.0.1:$PORT
        
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✨ 启动完成！"
        echo "🛑 停止服务: kill $SERVER_PID"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        exit 0
    fi
    sleep 0.5
done

echo "❌ 服务启动失败"
echo "📝 查看日志: cat /tmp/ytmusic-downloader.log"
cat /tmp/ytmusic-downloader.log | tail -20
exit 1
