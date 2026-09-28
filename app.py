"""
VirtualCam Companion — 系统级虚拟摄像头
配合 Chrome 扩展使用，让任何网页都能检测到"摄像头设备"

入口文件 - 程序启动点
"""

import os
import sys

# 确保当前目录在模块搜索路径中
if getattr(sys, "frozen", False):
    # 打包后的 exe
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig
from gui import VirtualCamApp
from utils import get_log_file, setup_logger


def main():
    """主函数"""
    # 初始化日志
    logger = setup_logger("Main", get_log_file())
    logger.info("=" * 50)
    logger.info("VirtualCam Companion 启动中...")

    # Windows 高分屏 (DPI) 缩放适配
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as e:
            logger.debug(f"设置 DPI 缩放失败: {e}")

    # 检查依赖
    try:
        import pyvirtualcam  # type: ignore

        logger.info(f"pyvirtualcam 版本: {pyvirtualcam.__version__}")
    except ImportError:
        logger.error("pyvirtualcam 未安装")
        print(
            "错误: pyvirtualcam 未安装。请运行: pip install pyvirtualcam opencv-python Pillow"
        )
        sys.exit(1)

    try:
        import cv2  # type: ignore

        logger.info(f"OpenCV 已安装 (版本: {cv2.__version__})")
    except ImportError:
        logger.info("OpenCV 未安装，将使用 Pillow 图像处理引擎")

    try:
        import PIL  # type: ignore

        logger.info(
            f"Pillow 已安装 (版本: {getattr(PIL, '__version__', '未知')})"
        )
    except ImportError:
        logger.error("Pillow 未安装")
        print("错误: Pillow 未安装。请运行: pip install Pillow")
        sys.exit(1)

    # 加载配置
    config = AppConfig.load()
    logger.info(f"配置加载完成: API 地址 {config.api_address}")

    # 启动应用
    try:
        app = VirtualCamApp(config)
        app.run()
    except Exception as e:
        logger.exception(f"应用运行出错: {e}")
        raise


if __name__ == "__main__":
    main()
