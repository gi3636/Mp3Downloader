PYTHON ?= python3
VENV ?= .venv
PORT ?= 5000
WEB_DIR ?= web

.PHONY: init venv deps web_deps web_build run clean

init: venv deps
	chmod +x ./yt-dlp_macos || true
	@if ! command -v ffmpeg >/dev/null 2>&1; then \
		echo "ffmpeg 未检测到：建议执行 brew install ffmpeg"; \
	fi

venv:
	$(PYTHON) -m venv $(VENV)

deps: venv
	$(VENV)/bin/pip install -r requirements.txt

web_deps:
	@command -v npm >/dev/null 2>&1 || (echo "未检测到 npm，请先安装 Node.js" && exit 1)
	@[ -d "$(WEB_DIR)" ] || (echo "前端目录 $(WEB_DIR) 不存在" && exit 1)
	@if [ ! -d "$(WEB_DIR)/node_modules" ]; then \
		cd $(WEB_DIR) && npm install; \
	else \
		echo "前端依赖已存在：跳过 npm install"; \
	fi

web_build: web_deps
	cd $(WEB_DIR) && npm run build

run: init web_build
	PORT=$(PORT) $(VENV)/bin/python app.py

clean:
	rm -rf $(VENV) jobs
