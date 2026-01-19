# 🎵 YouTube 音乐下载器

一个本地运行的 YouTube 音乐下载工具，支持播放列表/专辑下载，转换为高品质 MP3。

## ✨ 功能特性

- 📥 **专辑/播放列表下载** - 支持整个播放列表批量下载
- 🎨 **专辑封面显示** - 自动获取并显示专辑封面
- 📊 **实时进度条** - 显示下载进度和当前曲目
- 🎵 **在线播放** - 内置播放器，支持播放已下载音乐
- 📚 **音乐库管理** - 管理所有已下载的音乐
- 🔀 **随机播放** - 支持顺序/随机播放模式
- 🗑️ **删除功能** - 支持删除单曲或整个任务
- ❌ **取消下载** - 支持取消正在进行的下载

## 🚀 快速开始

### 环境要求

- Python 3.10+
- macOS（项目内置 `yt-dlp_macos`）
- `ffmpeg`（用于音频转换）
- Node.js 18+（用于前端 Vite + React 构建）

### 1. 安装依赖

```bash
# 安装 ffmpeg（macOS）
brew install ffmpeg

# 初始化（创建 venv + 安装依赖 + 设置 yt-dlp 可执行权限）
make init
```

### 2. 启动服务

```bash
make run
```

`make run` 会自动：

- 构建前端（`web/` → 输出到 `static/`）
- 启动 Flask 服务

默认端口为 `5000`，如需修改：

```bash
PORT=8080 make run
```

### 3. 打开浏览器

访问 http://127.0.0.1:5000

## 🧭 使用说明

### 下载页面

1. 粘贴 YouTube 链接（支持播放列表 / 单个视频 / 频道链接）
2. 若粘贴的是频道链接，会弹出“选择专辑/播放列表”的窗口
3. 点击“开始下载”
4. 下载过程中可看到进度条、状态与已下载数量
5. 下载完成后：
   - 可在页面内直接播放
   - 可下载 ZIP（打包已下载的 mp3）

### 音乐库页面

- 查看所有已下载的音乐
- 支持播放/暂停、上一首/下一首、随机播放
- 支持删除单首歌曲

## 📁 项目结构

```
├── app.py              # Flask 主应用，API 路由
├── config.py           # 配置常量
├── models.py           # 数据模型定义
├── job_manager.py      # 下载任务管理器
├── ytdlp_service.py    # yt-dlp 命令封装
├── tracks_service.py   # 曲目文件服务
├── web/                # 前端源码（Vite + React）
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
├── static/
│   ├── index.html      # 前端构建产物（由 Vite 生成）
│   ├── assets/         # 前端构建产物
│   └── styles.css      # 公共样式（复用）
├── download/           # 下载的 MP3 文件
├── jobs/               # 任务临时文件
└── yt-dlp_macos        # yt-dlp 可执行文件
```

## 🔧 技术栈

- **后端**: Python + Flask
- **前端**: Vite + React + TypeScript + Lucide Icons
- **下载**: yt-dlp
- **音频处理**: ffmpeg + mutagen

## 📝 使用说明

1. 粘贴 YouTube 播放列表或视频链接
2. 如果是频道链接，会弹出专辑选择框
3. 点击"开始下载"
4. 等待下载完成，可实时查看进度
5. 下载完成后可在线播放或下载 ZIP

## 🧩 常见问题（FAQ）

### 1) 报错提示需要 ffmpeg

- **现象**：任务失败，日志里出现 `ffmpeg` 相关错误
- **解决**：安装并确认可执行

```bash
brew install ffmpeg
ffmpeg -version
```

### 2) `Permission denied: yt-dlp_macos`

- **原因**：`yt-dlp_macos` 没有可执行权限
- **解决**：

```bash
chmod +x ./yt-dlp_macos
```

（`make init` 会自动执行一次）

### 3) 端口被占用

- **现象**：启动时报 `Address already in use`
- **解决**：换端口启动：

```bash
PORT=8080 make run
```

### 4) 下载文件保存在哪里？

- **MP3 目录**：`./download/`
- **任务临时文件 / ZIP**：`./jobs/`

## ⚠️ 注意事项

- 需要安装 ffmpeg 才能转换音频格式
- 本工具仅供个人学习使用
- 请遵守相关法律法规和平台服务条款
