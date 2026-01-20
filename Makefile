PYTHON ?= python3
VENV ?= .venv
PORT ?= 5001
WEB_DIR ?= web
TAURI_DIR ?= tauri-app
DIST_DIR ?= dist

# 检测系统架构
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),arm64)
    ARCH := aarch64-apple-darwin
else
    ARCH := x86_64-apple-darwin
endif

.PHONY: init venv deps web_deps web_build run clean pyinstaller tauri_build bundle help

# ========== 开发环境 ==========
init: venv deps
	chmod +x ./yt-dlp_macos || true
	@if ! command -v ffmpeg >/dev/null 2>&1; then \
		echo "⚠️  ffmpeg 未检测到：建议执行 brew install ffmpeg"; \
	fi

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "📦 创建虚拟环境..."; \
		$(PYTHON) -m venv $(VENV); \
	fi

deps: venv
	@echo "📦 安装 Python 依赖..."
	$(VENV)/bin/pip install -q -r requirements.txt

web_deps:
	@command -v npm >/dev/null 2>&1 || (echo "❌ 未检测到 npm，请先安装 Node.js" && exit 1)
	@[ -d "$(WEB_DIR)" ] || (echo "❌ 前端目录 $(WEB_DIR) 不存在" && exit 1)
	@if [ ! -d "$(WEB_DIR)/node_modules" ]; then \
		echo "📦 安装前端依赖..."; \
		cd $(WEB_DIR) && npm install; \
	fi

tauri_deps:
	@if [ ! -d "$(TAURI_DIR)/node_modules" ]; then \
		echo "📦 安装 Tauri 依赖..."; \
		cd $(TAURI_DIR) && npm install; \
	fi

web_build: web_deps
	@echo "🔨 构建前端..."
	cd $(WEB_DIR) && npm run build
	@echo "✅ 前端构建完成"

run: init web_build
	@echo "🚀 启动开发服务器..."
	PORT=$(PORT) $(VENV)/bin/python app.py

# ========== 打包 ==========

# 安装 PyInstaller
pyinstaller_deps: deps
	@echo "� 安装 PyInstaller..."
	$(VENV)/bin/pip install -q pyinstaller

# 用 PyInstaller 打包 Python 后端
pyinstaller: pyinstaller_deps
	@echo "📦 打包 Python 后端..."
	@rm -rf dist build *.spec
	$(VENV)/bin/pyinstaller \
		--name ytmusic-backend \
		--onefile \
		--noconfirm \
		--clean \
		--add-data "static:static" \
		--hidden-import flask \
		--hidden-import werkzeug \
		--hidden-import jinja2 \
		--hidden-import markupsafe \
		app.py
	@echo "✅ Python 后端打包完成: dist/ytmusic-backend"

# 准备 Tauri 资源
prepare_binaries: pyinstaller
	@echo "📋 准备 Tauri 二进制文件..."
	@mkdir -p $(TAURI_DIR)/src-tauri/binaries
	@# 复制后端可执行文件 (Tauri sidecar 命名规则: name-target_triple)
	cp dist/ytmusic-backend $(TAURI_DIR)/src-tauri/binaries/ytmusic-backend-$(ARCH)
	@# 复制 yt-dlp
	cp yt-dlp_macos $(TAURI_DIR)/src-tauri/binaries/yt-dlp-$(ARCH)
	@# 设置执行权限
	chmod +x $(TAURI_DIR)/src-tauri/binaries/*
	@echo "✅ 二进制文件准备完成"
	@ls -la $(TAURI_DIR)/src-tauri/binaries/

# 构建 Tauri 应用
tauri_build: web_build prepare_binaries tauri_deps
	@echo "🚀 构建 Tauri 应用..."
	cd $(TAURI_DIR) && npm run tauri build
	@echo ""
	@echo "=========================================="
	@echo "✅ 打包完成!"
	@echo "=========================================="
	@ls -la $(TAURI_DIR)/src-tauri/target/release/bundle/macos/*.app 2>/dev/null || true

# 完整打包流程 (别名)
bundle: tauri_build

# 开发模式运行 Tauri (使用 Python 后端)
tauri_dev: web_build tauri_deps
	@echo "🚀 启动 Tauri 开发模式..."
	@echo "⚠️  请确保 Flask 后端已在另一个终端运行: make run"
	cd $(TAURI_DIR) && npm run tauri dev

# ========== 清理 ==========
clean:
	@echo "🧹 清理所有构建文件..."
	rm -rf $(VENV) jobs dist build *.spec
	rm -rf $(TAURI_DIR)/src-tauri/binaries
	rm -rf $(TAURI_DIR)/src-tauri/target
	@echo "✅ 清理完成"

clean_build:
	@echo "🧹 清理构建文件..."
	rm -rf dist build *.spec
	rm -rf $(TAURI_DIR)/src-tauri/binaries
	rm -rf $(TAURI_DIR)/src-tauri/target/release
	@echo "✅ 清理完成"

# ========== 帮助 ==========
help:
	@echo ""
	@echo "YouTube 音乐下载器 - 构建命令"
	@echo "=============================="
	@echo ""
	@echo "开发命令:"
	@echo "  make init        - 初始化开发环境 (Python + 依赖)"
	@echo "  make run         - 运行开发服务器 (Flask)"
	@echo "  make web_build   - 构建前端"
	@echo "  make tauri_dev   - Tauri 开发模式 (需先运行 make run)"
	@echo ""
	@echo "打包命令:"
	@echo "  make bundle      - 完整打包桌面应用 ⭐"
	@echo "  make pyinstaller - 只打包 Python 后端"
	@echo ""
	@echo "清理命令:"
	@echo "  make clean       - 清理所有构建文件"
	@echo "  make clean_build - 只清理构建产物"
	@echo ""
	@echo "当前架构: $(ARCH)"
	@echo ""
