"""
VirtualCam Companion - 虚拟摄像头管理模块
负责虚拟摄像头的启动、停止、帧输出与图像适配优化
"""

from __future__ import annotations

import math
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
        fit_mode: str = "fit",
        auto_resolution: bool = True,
        flip_horizontal: bool = False,
    ):
        """
        初始化摄像头管理器

        Args:
            width: 画面宽度 (默认)
            height: 画面高度 (默认)
            fps: 帧率
            device: 设备名称或路径 (Linux 可传 /dev/video10)
            backend: 指定后端 (obs / v4l2loopback / unitycapture / None 为自动)
            fit_mode: 图像适配模式 ("fit": 等比完整包含, "fill": 居中裁剪填满, "stretch": 强制拉伸)
            auto_resolution: 是否自动根据图片真实尺寸自适应摄像头分辨率
            flip_horizontal: 是否开启水平镜像翻转 (纠正网页/前端默认前置镜像)
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._device = device
        self._backend = backend
        self._fit_mode = fit_mode if fit_mode in ("fit", "fill", "stretch") else "fit"
        self._auto_resolution = auto_resolution
        self._flip_horizontal = flip_horizontal

        self._cam = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._image: np.ndarray | None = None  # 原始图像 (BGR)
        self._cached_frame: np.ndarray | None = None  # 预处理好的当前输出帧 (RGB)
        self._lock = threading.Lock()
        self._device_name = ""

        # 事件回调 (支持 UI 监听 API 或内部触发的变化)
        self.on_image_changed: Callable[[np.ndarray], None] | None = None
        self.on_status_changed: Callable[[bool, str], None] | None = None

    @staticmethod
    def compute_safe_resolution(
        w: int, h: int, max_dim: int = 1920, min_dim: int = 2
    ) -> tuple[int, int]:
        """
        根据输入图片的原始尺寸计算符合系统级虚拟相机驱动要求的合规分辨率
        (保证偶数像素对齐，限制在合理性能边界内，完全保留原始宽高比)
        """
        if w <= 0 or h <= 0:
            return 1280, 720

        # 超大分辨率等比缩减，防止显存与推流帧率下降
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            w = int(round(w * scale))
            h = int(round(h * scale))

        # 视频编解码器与虚拟相机驱动（如 DirectShow/V4L2）要求分辨率必须为偶数
        w = max(min_dim, w & ~1)
        h = max(min_dim, h & ~1)
        return w, h

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

    @property
    def raw_image_size(self) -> tuple[int, int] | None:
        """获取当前加载的原始图片分辨率 (宽, 高)"""
        with self._lock:
            if self._image is not None:
                return (self._image.shape[1], self._image.shape[0])
            return None

    @property
    def fit_mode(self) -> str:
        return self._fit_mode

    @fit_mode.setter
    def fit_mode(self, mode: str):
        if mode in ("fit", "fill", "stretch"):
            with self._lock:
                self._fit_mode = mode
                self._update_cached_frame_locked()
            logger.info(f"图像适配模式已切换为: {mode}")
            self._notify_frame_changed()

    def cycle_fit_mode(self) -> str:
        """循环切换适配模式: fit -> fill -> stretch -> fit"""
        modes = ["fit", "fill", "stretch"]
        idx = modes.index(self._fit_mode) if self._fit_mode in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.fit_mode = next_mode
        return next_mode

    @property
    def flip_horizontal(self) -> bool:
        return self._flip_horizontal

    @flip_horizontal.setter
    def flip_horizontal(self, flip: bool):
        with self._lock:
            self._flip_horizontal = bool(flip)
            self._update_cached_frame_locked()
        logger.info(f"水平镜像翻转状态已设置为: {self._flip_horizontal}")
        self._notify_frame_changed()

    def toggle_flip(self) -> bool:
        """切换水平镜像翻转开关"""
        self.flip_horizontal = not self._flip_horizontal
        return self._flip_horizontal

    @property
    def auto_resolution(self) -> bool:
        return self._auto_resolution

    @auto_resolution.setter
    def auto_resolution(self, val: bool):
        self._auto_resolution = bool(val)
        logger.info(f"自动尺寸适配已设置为: {self._auto_resolution}")
        if self._auto_resolution and not self._running and self._image is not None:
            with self._lock:
                h, w = self._image.shape[:2]
                self._width, self._height = self.compute_safe_resolution(w, h)
                self._update_cached_frame_locked()
            self._notify_frame_changed()

    def get_processed_frame(self) -> np.ndarray | None:
        """获取当前处理完成的最终 RGB 帧（供 GUI 预览与外部调用）"""
        with self._lock:
            if self._cached_frame is not None:
                return self._cached_frame.copy()
            return None

    def _notify_frame_changed(self):
        """通知外部画面或参数发生改变"""
        if self.on_image_changed:
            with self._lock:
                img_copy = self._image.copy() if self._image is not None else None
            if img_copy is not None:
                try:
                    self.on_image_changed(img_copy)
                except Exception as e:
                    logger.warning(f"画面变更回调执行异常: {e}")

    @staticmethod
    def _process_frame(
        img: np.ndarray,
        target_w: int,
        target_h: int,
        fit_mode: str,
        flip_h: bool,
    ) -> np.ndarray:
        """
        处理单帧图像：等比/填充/拉伸适配 + 水平镜像翻转 + 色彩空间转换 (BGR -> RGB)
        """
        img_h, img_w = img.shape[:2]

        if fit_mode == "stretch" or (img_w == target_w and img_h == target_h):
            # 强制拉伸或尺寸恰好一致
            if img_w == target_w and img_h == target_h:
                frame = img.copy()
            else:
                interp = (
                    cv2.INTER_AREA
                    if (target_w < img_w and target_h < img_h)
                    else cv2.INTER_LINEAR
                )
                frame = cv2.resize(img, (target_w, target_h), interpolation=interp)

        elif fit_mode == "fill":
            # 填满裁切 (保持宽高比，放大直到填满全屏，超出部分居中裁剪)
            scale = max(target_w / img_w, target_h / img_h)
            new_w = max(target_w, int(math.ceil(img_w * scale)))
            new_h = max(target_h, int(math.ceil(img_h * scale)))

            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            resized = cv2.resize(img, (new_w, new_h), interpolation=interp)

            x_offset = max(0, (new_w - target_w) // 2)
            y_offset = max(0, (new_h - target_h) // 2)
            frame = resized[
                y_offset : y_offset + target_h, x_offset : x_offset + target_w
            ]

        else:
            # 默认 "fit": 等比完整包含 (保持原始比例缩放，居中黑边补全，画面 100% 完整不被裁剪拉伸)
            scale = min(target_w / img_w, target_h / img_h)
            new_w = min(target_w, max(1, int(round(img_w * scale))))
            new_h = min(target_h, max(1, int(round(img_h * scale))))

            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            resized = cv2.resize(img, (new_w, new_h), interpolation=interp)

            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            x_offset = max(0, (target_w - new_w) // 2)
            y_offset = max(0, (target_h - new_h) // 2)
            canvas[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = resized
            frame = canvas

        # 水平镜像翻转处理 (抵消浏览器/会议软件的前置镜像)
        if flip_h:
            frame = cv2.flip(frame, 1)

        # 转换为 pyvirtualcam 所需的 RGB 色彩空间
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb

    def _update_cached_frame_locked(self):
        """在 lock 保护下更新当前待输出的 RGB 帧缓存"""
        if self._image is None:
            self._cached_frame = None
            return

        target_w = self._cam.width if (self._cam and self._running) else self._width
        target_h = self._cam.height if (self._cam and self._running) else self._height

        self._cached_frame = self._process_frame(
            self._image,
            target_w,
            target_h,
            self._fit_mode,
            self._flip_horizontal,
        )

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
                logger.info(
                    f"已加载图片: {image_path_or_array} ({img.shape[1]}x{img.shape[0]})"
                )
            elif isinstance(image_path_or_array, np.ndarray):
                self._image = image_path_or_array
                img = image_path_or_array
                logger.info(f"已设置图片数据 ({img.shape[1]}x{img.shape[0]})")
            else:
                logger.error(f"不支持的图片类型: {type(image_path_or_array)}")
                return False

            # 自动适配分辨率 (若摄像头尚未启动，将输出分辨率直接设置为图片的合规比例)
            if self._auto_resolution and not self._running:
                h, w = img.shape[:2]
                self._width, self._height = self.compute_safe_resolution(w, h)
                logger.info(f"自动适配摄像头分辨率为: {self._width}x{self._height}")

            self._update_cached_frame_locked()

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
            width: 画面宽度 (None 使用当前或自动适配的值)
            height: 画面高度 (None 使用当前或自动适配的值)
            fps: 帧率 (None 使用当前值)
            device: 设备名称或路径
            backend: 后端类型

        Returns:
            (成功与否, 消息)
        """
        if self._running:
            return True, "已在运行"

        # 更新显式传入的参数
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

        # 确保有图片可输出，并计算好最新帧
        with self._lock:
            if self._image is None:
                self._create_placeholder()
            elif self._auto_resolution and width is None and height is None:
                # 再次确认自动分辨率
                h, w = self._image.shape[:2]
                self._width, self._height = self.compute_safe_resolution(w, h)

            self._update_cached_frame_locked()

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

            # 驱动创建成功后，重新根据驱动实际采用的分辨率校正一帧缓存
            with self._lock:
                self._update_cached_frame_locked()

            self._thread = threading.Thread(target=self._frame_loop, daemon=True)
            self._thread.start()

            msg = f"虚拟摄像头已启动: {self._device_name} ({self._width}x{self._height} @ {self._fps}fps)"
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
        self._update_cached_frame_locked()
        logger.info("已创建默认占位画面")

    def _frame_loop(self):
        """高效帧输出循环（使用预处理缓存帧，大幅节省 CPU 开销）"""
        frame_duration = 1.0 / self._fps

        while self._running and self._cam:
            try:
                with self._lock:
                    frame = self._cached_frame

                if frame is not None:
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
        with self._lock:
            img_size = (
                [self._image.shape[1], self._image.shape[0]]
                if self._image is not None
                else None
            )
            cur_w = self._cam.width if (self._cam and self._running) else self._width
            cur_h = self._cam.height if (self._cam and self._running) else self._height

        return {
            "running": self.is_running,
            "device": self._device_name,
            "has_image": self.has_image,
            "width": cur_w,
            "height": cur_h,
            "fps": self._fps,
            "platform": platform.system(),
            "fit_mode": self._fit_mode,
            "flip_horizontal": self._flip_horizontal,
            "auto_resolution": self._auto_resolution,
            "image_size": img_size,
        }
