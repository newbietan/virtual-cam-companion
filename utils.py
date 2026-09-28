"""
VirtualCam Companion - 工具模块
提供日志、验证等通用功能
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_app_data_dir() -> str:
    """
    获取跨平台的用户配置与数据目录
    - Windows: %APPDATA%/VirtualCamCompanion
    - macOS: ~/Library/Application Support/VirtualCamCompanion
    - Linux: $XDG_CONFIG_HOME/virtual-cam-companion (~/.config/virtual-cam-companion)
    """
    # 检查是否便携模式 (Windows 便携版或同目录已有配置且可写)
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            is_macos_bundle = (
                "Contents/MacOS" in exe_dir or "Contents/Frameworks" in exe_dir
            )
            is_appimage = bool(os.environ.get("APPDIR") or os.environ.get("APPIMAGE"))
            is_readonly_system = exe_dir.startswith("/usr") or is_appimage
            if not is_macos_bundle and not is_readonly_system:
                config_target = os.path.join(exe_dir, "config.json")
                if os.path.exists(config_target) or os.access(exe_dir, os.W_OK):
                    return exe_dir
        else:
            src_dir = os.path.dirname(os.path.abspath(__file__))
            config_target = os.path.join(src_dir, "config.json")
            if os.path.exists(config_target):
                return src_dir
    except (OSError, Exception) as err:
        logging.getLogger("Utils").debug("检查便携配置路径失败: %s", err)

    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        app_dir = (
            Path(base) / "VirtualCamCompanion"
            if base
            else Path.home() / ".config" / "VirtualCamCompanion"
        )
    elif system == "Darwin":
        app_dir = (
            Path.home() / "Library" / "Application Support" / "VirtualCamCompanion"
        )
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        app_dir = (
            Path(xdg) / "virtual-cam-companion"
            if xdg
            else Path.home() / ".config" / "virtual-cam-companion"
        )

    try:
        os.makedirs(app_dir, exist_ok=True)
    except OSError as err:
        logging.getLogger("Utils").debug("创建配置目录失败 %s: %s", app_dir, err)
    return str(app_dir)


def get_log_dir() -> str:
    """
    获取跨平台的日志目录
    - Windows: %LOCALAPPDATA%/VirtualCamCompanion/logs 或 AppData/VirtualCamCompanion/logs
    - macOS: ~/Library/Logs/VirtualCamCompanion
    - Linux: $XDG_STATE_HOME/virtual-cam-companion/logs (~/.local/state/virtual-cam-companion/logs)
    """
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            is_macos_bundle = (
                "Contents/MacOS" in exe_dir or "Contents/Frameworks" in exe_dir
            )
            is_appimage = bool(os.environ.get("APPDIR") or os.environ.get("APPIMAGE"))
            is_readonly_system = exe_dir.startswith("/usr") or is_appimage
            if not is_macos_bundle and not is_readonly_system:
                local_logs = os.path.join(exe_dir, "logs")
                if os.path.exists(local_logs) or (
                    os.access(exe_dir, os.W_OK) and not os.path.exists(local_logs)
                ):
                    os.makedirs(local_logs, exist_ok=True)
                    return local_logs
    except (OSError, Exception) as err:
        logging.getLogger("Utils").debug("检查便携日志路径失败: %s", err)

    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        log_dir = (
            Path(base) / "VirtualCamCompanion" / "logs"
            if base
            else Path.home() / ".config" / "VirtualCamCompanion" / "logs"
        )
    elif system == "Darwin":
        log_dir = Path.home() / "Library" / "Logs" / "VirtualCamCompanion"
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        log_dir = (
            Path(xdg) / "virtual-cam-companion" / "logs"
            if xdg
            else Path.home() / ".local" / "state" / "virtual-cam-companion" / "logs"
        )

    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as err:
        logging.getLogger("Utils").debug("创建日志目录失败 %s: %s", log_dir, err)
    return str(log_dir)


def get_log_file() -> str:
    """获取日志文件路径"""
    log_dir = get_log_dir()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(log_dir, f"virtualcam_{date_str}.log")


def setup_logger(
    name: str, log_file: str | None = None, level: int = logging.INFO
) -> logging.Logger:
    """
    创建并配置日志记录器（带滚动文件 Handler）

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径 (可选)
        level: 日志级别

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出 (带回滚)
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"无法创建日志文件 {log_file}: {e}")

    return logger


def validate_image_data(data: bytes, max_size_mb: int = 10) -> tuple[bool, str]:
    """
    验证图片数据是否有效

    Args:
        data: 图片二进制数据
        max_size_mb: 最大文件大小 (MB)

    Returns:
        (是否有效, 错误信息)
    """
    if not data:
        return False, "图片数据为空"

    # 检查大小限制
    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"图片大小 {size_mb:.1f}MB 超过限制 {max_size_mb}MB"

    # 检查最小大小 (至少应该有一些数据)
    if len(data) < 32:
        return False, "图片数据过小，可能已损坏"

    # 验证常见图片文件头魔数 (JPEG, PNG, GIF, BMP, WEBP)
    is_jpeg = data.startswith(b"\xff\xd8\xff")
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    is_bmp = data.startswith(b"BM")
    is_gif = data.startswith((b"GIF87a", b"GIF89a"))
    is_webp = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_bmp or is_gif or is_webp):
        return False, "不支持的图片格式或文件头已损坏 (支持 JPG/PNG/BMP/GIF/WEBP)"

    return True, ""


def validate_base64_image(
    base64_str: str, max_size_mb: int = 10
) -> tuple[bool, bytes, str]:
    """
    验证并解码 base64 图片数据

    Args:
        base64_str: base64 编码的图片字符串
        max_size_mb: 最大文件大小 (MB)

    Returns:
        (是否有效, 解码后的数据, 错误信息)
    """
    import base64

    if not base64_str:
        return False, b"", "图片数据为空"

    # 处理 data:image/xxx;base64, 前缀
    if "," in base64_str and ";base64" in base64_str:
        base64_str = base64_str.split(",", 1)[1]

    try:
        data = base64.b64decode(base64_str)
    except Exception as e:
        return False, b"", f"Base64 解码失败: {e!s}"

    valid, error = validate_image_data(data, max_size_mb)
    if not valid:
        return False, b"", error

    return True, data, ""
