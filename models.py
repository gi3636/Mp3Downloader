"""
数据模型定义
"""

import time
from dataclasses import dataclass, field


@dataclass
class DownloadItem:
    """
    单个下载项状态
    
    Attributes:
        index: 序号
        title: 标题
        url: 视频 URL
        thumbnail: 封面图 URL
        status: 状态 (pending|downloading|done|error|skipped|paused)
        progress: 下载进度 (0-100)
        error_msg: 错误信息
    """
    index: int
    title: str
    url: str
    thumbnail: str | None = None
    status: str = "pending"  # pending|downloading|done|error|skipped|paused
    progress: float = 0.0
    error_msg: str | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "url": self.url,
            "thumbnail": self.thumbnail,
            "status": self.status,
            "progress": self.progress,
            "error_msg": self.error_msg,
        }


@dataclass
class JobState:
    """
    下载任务状态
    
    Attributes:
        id: 任务唯一标识
        url: 下载链接
        status: 状态 (queued|running|done|error|canceled|canceling)
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
        progress: 总体进度 (0-100)
        message: 状态消息
        logs: 日志行列表
        output_dir: 输出目录路径
        zip_path: ZIP 文件路径
        playlist_title: 播放列表/专辑标题
        thumbnail_url: 封面图 URL
        total_items: 总曲目数
        current_item: 当前下载项目索引
        current_item_progress: 当前项目下载进度 (0-100)
        cancel_requested: 是否请求取消
        download_items: 下载项列表
    """
    id: str
    url: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    progress: float = 0.0
    message: str = ""
    logs: list[str] = field(default_factory=list)
    output_dir: str | None = None
    zip_path: str | None = None
    playlist_title: str | None = None
    thumbnail_url: str | None = None
    total_items: int | None = None
    current_item: int | None = None
    current_item_progress: float = 0.0
    cancel_requested: bool = False
    download_items: list[DownloadItem] = field(default_factory=list)
    paused: bool = False  # 是否暂停整个任务
    paused_items: set[int] = field(default_factory=set)  # 暂停的单个项目索引
    
    @property
    def download_items_dict(self) -> list[dict]:
        return [item.to_dict() for item in self.download_items]
