"""
VirtualCam Companion - 虚拟摄像头管理模块
负责虚拟摄像头的启动、停止、帧输出
"""

from __future__ import annotations

import platform
import threading
import time
from collections.abc import Callable
from typing import Any

import cv2  # type: ignore
import numpy as np  # type: ignore

from utils import get_log_file, setup_logger

logger = setup_logger("VirtualCam", get_log_file())


def get_driver_help_message() -> str:
    """获取针对当前操作系统的驱动安装与配置指南"""
    system = platform.system()
    if system == "Darwin":
        return (
            "未检测到 macOS 虚拟摄像头驱动\n\n"
            "macOS 13+ 需要 OBS Studio 30+ 的虚拟相机扩展支持。\n"
            "【一次性配置步骤】\n"
            "1. 安装 OBS Studio 30+ (https://obsproject.com 或 brew install --cask obs)\n"
            "2. 打开 OBS，点击右下角『启动虚拟摄像机』，然后点击『停止虚拟摄像机』\n"
            "   (系统若提示扩展授权，请在『系统设置 -> 隐私与安全性』中允许)\n"
            "3. 重新在 VirtualCam Companion 中点击启动即可。"
        )
    elif system == "Linux":
        return (
            "未检测到 Linux 虚拟摄像头设备 (/dev/video*)\n\n"
            "Linux 需要 v4l2loopback 内核模块支持。\n"
            "【快速配置步骤】\n"
            "1. 安装内核模块: sudo apt install v4l2loopback-dkms\n"
            '2. 加载模块: sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1\n'
            "3. 如需开机自动加载，请将 v4l2loopback 写入 /etc/modules"
        )
    else:
        return (
            "未检测到 Windows 虚拟摄像头驱动\n\n"
            "1. 建议重新运行 VirtualCamCompanion-Setup 安装包自动注册驱动\n"
            "2. 或安装 OBS Studio (https://obsproject.com)\n"
            "3. 或在管理员命令行运行 regsvr32 注册 obs-virtualcam-module64.dll"
        )


class VirtualCamManager:
    """跨平台虚拟摄像头管理器"""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        device: str | None = None,
        backend: str | None = None,
    ):
        """
        初始化摄像头管理器

        Args:
            width: 画面宽度
            height: 画面高度
            fps: 帧率
            device: 设备名称或路径 (Linux 可传 /dev/video10)
            backend: 指定后端 (obs / v4l2loopback / unitycapture / None 为自动)
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._device = device
        self._backend = backend

        self._cam = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._image: np.ndarray | None = None
        self._lock = threading.Lock()
        self._device_name = ""

        # 事件回调 (支持 UI 监听 API 触发的变化)
        self.on_image_changed: Callable[[np.ndarray], None] | None = None
        self.on_status_changed: Callable[[bool, str], None] | None = None

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device(self) -> str | None:
        return self._device

    @property
    def backend(self) -> str | None:
        return self._backend

    @property
    def is_running(self) -> bool:
        return self._running and self._cam is not None

    @property
    def has_image(self) -> bool:
        return self._image is not None

    def set_image(self, image_path_or_array) -> bool:
        """
        设置要输出的图片

        Args:
            image_path_or_array: 文件路径 (str) 或 numpy 数组 (BGR)

        Returns:
            是否成功
        """
        with self._lock:
            if isinstance(image_path_or_array, str):
                img = cv2.imread(image_path_or_array)
                if img is None:
                    logger.error(f"无法读取图片: {image_path_or_array}")
                    return False
                self._image = img
                logger.info(f"已加载图片: {image_path_or_array}")
            elif isinstance(image_path_or_array, np.ndarray):
                self._image = image_path_or_array
                img = image_path_or_array
                logger.info("已设置图片数据")
            else:
                logger.error(f"不支持的图片类型: {type(image_path_or_array)}")
                return False

        # 触发图片更新回调通知外部 (例如 UI 刷新)
        if self.on_image_changed and img is not None:
            try:
                self.on_image_changed(img)
            except Exception as e:
                logger.warning(f"图片变更回调执行异常: {e}")

        return True

    def start(
        self,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        device: str | None = None,
        backend: str | None = None,
    ) -> tuple[bool, str]:
        """
        启动虚拟摄像头

        Args:
            width: 画面宽度 (None 使用默认值)
            height: 画面高度 (None 使用默认值)
            fps: 帧率 (None 使用默认值)
            device: 设备名称或路径
            backend: 后端类型

        Returns:
            (成功与否, 消息)
        """
        if self._running:
            return True, "已在运行"

        # 更新参数
        if width is not None:
            self._width = width
        if height is not None:
            self._height = height
        if fps is not None:
            self._fps = fps
        if device is not None:
            self._device = device
        if backend is not None:
            self._backend = backend

        # 确保有图片可输出
        with self._lock:
            if self._image is None:
                self._create_placeholder()

        try:
            import pyvirtualcam  # type: ignore

            cam_kwargs: dict[str, Any] = {
                "width": self._width,
                "height": self._height,
                "fps": self._fps,
            }
            if self._backend:
                cam_kwargs["backend"] = self._backend
            if self._device:
                cam_kwargs["device"] = self._device

            self._cam = pyvirtualcam.Camera(**cam_kwargs)
            self._device_name = getattr(self._cam, "device", "Virtual Camera")
            self._running = True

            self._thread = threading.Thread(target=self._frame_loop, daemon=True)
            self._thread.start()

            msg = f"虚拟摄像头已启动: {self._device_name}"
            logger.info(msg)

            if self.on_status_changed:
                try:
                    self.on_status_changed(True, msg)
                except Exception as e:
                    logger.warning(f"状态变更回调执行异常: {e}")

            return True, msg

        except ImportError:
            err_msg = "未安装 pyvirtualcam 模块，请运行: pip install pyvirtualcam"
            logger.error(err_msg)
            return False, err_msg
        except Exception as e:
            err = str(e)
            logger.error(f"启动虚拟摄像头失败 ({platform.system()}): {err}")

            help_guide = get_driver_help_message()
            if any(
                k in err.lower()
                for k in [
                    "no virtual camera",
                    "backend",
                    "cannot find",
                    "device",
                    "v4l2",
                ]
            ):
                return False, f"{help_guide}\n\n[详细错误]: {err}"
            return False, f"启动失败: {err}\n\n{help_guide}"

    def _create_placeholder(self):
        """创建默认占位画面"""
        self._image = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        text = "Virtual Camera"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (self._width - text_size[0]) // 2
        text_y = (self._height + text_size[1]) // 2
        cv2.putText(
            self._image,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (108, 99, 255),
            thickness,
        )
        logger.info("已创建默认占位画面")

    def _frame_loop(self):
        """帧输出循环"""
        frame_duration = 1.0 / self._fps

        while self._running and self._cam:
            try:
                with self._lock:
                    img = self._image

                if img is not None:
                    frame = cv2.resize(img, (self._cam.width, self._cam.height))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self._cam.send(frame)
                    self._cam.sleep_until_next_frame()
                else:
                    time.sleep(frame_duration)

            except Exception as e:
                logger.error(f"帧输出错误: {e}")
                time.sleep(0.1)

    def stop(self):
        """停止虚拟摄像头"""
        if not self._running:
            return

        logger.info("正在停止虚拟摄像头...")
        self._running = False

        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

        if self._cam:
            try:
                self._cam.close()
            except Exception as e:
                logger.warning(f"关闭摄像头时出错: {e}")
            self._cam = None

        self._device_name = ""
        logger.info("虚拟摄像头已停止")

        if self.on_status_changed:
            try:
                self.on_status_changed(False, "已停止")
            except Exception as e:
                logger.warning(f"状态变更回调执行异常: {e}")

    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "running": self.is_running,
            "device": self._device_name,
            "has_image": self.has_image,
            "width": self._width,
            "height": self._height,
            "fps": self._fps,
            "platform": platform.system(),
        }
