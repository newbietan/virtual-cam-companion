"""
VirtualCam Companion - 配置管理模块
支持配置文件加载、保存、默认值
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from utils import get_app_data_dir


@dataclass
class AppConfig:
    """应用配置类"""

    # API 配置
    api_host: str = "127.0.0.1"
    api_port: int = 5566

    # 摄像头配置
    cam_width: int = 1280
    cam_height: int = 720
    cam_fps: int = 30
    cam_device: str | None = None  # 虚拟摄像头设备名或路径 (如 Linux 下 /dev/video10)
    cam_backend: str | None = None  # 后端类型 (obs / v4l2loopback / unitycapture / None 为自动)

    # 画面适配与处理配置
    fit_mode: str = "fit"  # 适配模式: fit (等比完整包含) / fill (等比裁剪填满) / stretch (强制拉伸)
    auto_resolution: bool = True  # 自动将摄像头分辨率适配为输入图片尺寸
    flip_horizontal: bool = False  # 水平镜像翻转 (纠正网页/会议软件的前置镜像)

    # 图片配置
    max_image_size_mb: int = 10
    supported_formats: list[str] = field(
        default_factory=lambda: ["jpg", "jpeg", "png", "bmp", "webp"]
    )

    # 用户配置
    last_image: str | None = None

    # GUI 配置
    window_width: int = 500
    window_height: int = 660
    theme: str = "dark"  # dark/light

    @classmethod
    def get_config_path(cls) -> str:
        """获取跨平台配置文件路径"""
        config_dir = get_app_data_dir()
        return os.path.join(config_dir, "config.json")

    @classmethod
    def load(cls, config_path: str | None = None) -> AppConfig:
        """
        从文件加载配置，缺失项使用默认值

        Args:
            config_path: 配置文件路径，None 则使用默认路径

        Returns:
            AppConfig 实例
        """
        if config_path is None:
            config_path = cls.get_config_path()

        config = cls()

        if not os.path.exists(config_path):
            return config

        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)

            # 只更新存在的字段，忽略未知字段
            valid_fields = set(cls.__dataclass_fields__)
            for key, value in data.items():
                if key in valid_fields:
                    setattr(config, key, value)

        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
        except Exception as e:
            print(f"配置加载失败: {e}")

        return config

    def save(self, config_path: str | None = None):
        """
        保存配置到文件

        Args:
            config_path: 配置文件路径，None 则使用默认路径
        """
        if config_path is None:
            config_path = self.get_config_path()

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"配置保存失败: {e}")

    def get_supported_extensions(self) -> list[str]:
        """获取支持的图片扩展名列表 (带点号)"""
        return [f".{ext}" for ext in self.supported_formats]

    def get_file_types(self) -> list:
        """获取文件选择器的文件类型过滤器"""
        exts = " ".join(f"*.{ext}" for ext in self.supported_formats)
        return [("图片文件", exts), ("所有文件", "*.*")]

    @property
    def api_address(self) -> str:
        """获取 API 完整地址"""
        return f"http://{self.api_host}:{self.api_port}"


# 全局配置实例
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = AppConfig.load()
    return _config
