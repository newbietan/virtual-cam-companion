"""
VirtualCam Companion - GUI 界面模块
基于 tkinter 的可视化界面，支持跨平台 (Windows/macOS/Linux)
"""

from __future__ import annotations

import os
import platform
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2  # type: ignore
import numpy as np  # type: ignore
from PIL import Image, ImageTk  # type: ignore

from api_server import APIServer, start_api_server
from cam_manager import VirtualCamManager
from config import AppConfig
from utils import get_log_file, setup_logger

logger = setup_logger("GUI", get_log_file())


def get_ui_font(size: int = 10, weight: str = "normal") -> tuple[str, int, str]:
    """获取跨平台的系统首选字体"""
    sys_name = platform.system()
    if sys_name == "Darwin":
        family = "Helvetica Neue"
    elif sys_name == "Windows":
        family = "Segoe UI"
    else:
        family = "DejaVu Sans"
    return (family, size, weight)


class VirtualCamApp:
    """跨平台虚拟摄像头 GUI 应用"""

    def __init__(self, config: AppConfig):
        """
        初始化 GUI 应用

        Args:
            config: 应用配置
        """
        self._config = config
        self._cam_manager = VirtualCamManager(
            width=config.cam_width,
            height=config.cam_height,
            fps=config.cam_fps,
            device=config.cam_device,
            backend=config.cam_backend,
        )
        self._api_server: APIServer | None = None
        self._current_image_path: str | None = config.last_image
        self._photo_ref: ImageTk.PhotoImage | None = None

        # 监听摄像头状态与画面变更事件 (用于响应 API 远程调用同步)
        self._cam_manager.on_image_changed = self._on_cam_image_changed
        self._cam_manager.on_status_changed = self._on_cam_status_changed

        # 创建主窗口
        self._root = tk.Tk()
        self._root.title("📷 VirtualCam Companion")
        self._root.geometry(f"{config.window_width}x{config.window_height}")
        self._root.resizable(False, False)
        self._root.configure(bg="#1a1a2e")

        # 设置跨平台图标
        self._setup_icon()

        # 构建界面
        self._build_ui()

        # 启动 API 服务
        self._start_api()

        # 加载上次的图片
        if self._current_image_path and os.path.exists(self._current_image_path):
            self._load_image(self._current_image_path)

        # 注册关闭事件
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_icon(self):
        """设置跨平台窗口图标"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "app.png"),
            os.path.join(base_dir, "app.ico"),
            "app.png",
            "app.ico",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    if platform.system() == "Windows" and p.endswith(".ico"):
                        self._root.iconbitmap(default=p)
                    else:
                        img = Image.open(p)
                        self._icon_photo = ImageTk.PhotoImage(img)
                        self._root.iconphoto(True, self._icon_photo)  # type: ignore
                    break
                except Exception as e:
                    logger.debug(f"加载图标 {p} 失败: {e}")

    def _build_ui(self):
        """构建用户界面"""
        # 标题
        title = tk.Label(
            self._root,
            text="📷 虚拟摄像头",
            font=get_ui_font(18, "bold"),
            fg="#fff",
            bg="#1a1a2e",
        )
        title.pack(pady=(16, 8))

        # 状态标签
        self._status_var = tk.StringVar(value="⚠️ 未启动")
        self._status_label = tk.Label(
            self._root,
            textvariable=self._status_var,
            font=get_ui_font(12),
            fg="#e8a0a0",
            bg="#3d1f1f",
            padx=16,
            pady=6,
        )
        self._status_label.pack(pady=(0, 12))

        # 图片预览区域
        preview_frame = tk.Frame(
            self._root,
            bg="#2a2a3e",
            bd=0,
            highlightbackground="#444",
            highlightthickness=1,
        )
        preview_frame.pack(padx=24, pady=(0, 12))

        self._preview_label = tk.Label(
            preview_frame,
            bg="#2a2a3e",
            text="点击下方按钮选择图片\n或通过 Chrome 扩展推送",
            fg="#666",
            font=get_ui_font(11),
            width=48,
            height=12,
        )
        self._preview_label.pack(padx=2, pady=2)

        # 图片信息标签
        self._info_var = tk.StringVar(value="")
        self._info_label = tk.Label(
            self._root,
            textvariable=self._info_var,
            font=get_ui_font(10),
            fg="#999",
            bg="#1a1a2e",
        )
        self._info_label.pack()

        # 按钮行
        btn_frame = tk.Frame(self._root, bg="#1a1a2e")
        btn_frame.pack(pady=12)

        style_btn = {
            "font": get_ui_font(11, "bold"),
            "bd": 0,
            "padx": 20,
            "pady": 8,
            "cursor": "hand2",
        }

        self._btn_select = tk.Button(
            btn_frame,
            text="📁 选择图片",
            bg="#6c63ff",
            fg="#fff",
            activebackground="#5a52d5",
            command=self._select_image,
            **style_btn,
        )
        self._btn_select.pack(side=tk.LEFT, padx=6)

        self._btn_start = tk.Button(
            btn_frame,
            text="🚀 启动摄像头",
            bg="#2d6a4f",
            fg="#fff",
            activebackground="#1b4332",
            command=self._toggle_camera,
            **style_btn,
        )
        self._btn_start.pack(side=tk.LEFT, padx=6)

        # API 信息
        api_frame = tk.Frame(self._root, bg="#1a1a2e")
        api_frame.pack(pady=(12, 4))

        api_label = tk.Label(
            api_frame,
            text=f"HTTP API: {self._config.api_address}",
            font=("Courier" if platform.system() == "Darwin" else "Consolas", 9),
            fg="#555",
            bg="#1a1a2e",
        )
        api_label.pack()

        hint = tk.Label(
            api_frame,
            text="Chrome 扩展通过此 API 发送图片到虚拟摄像头",
            font=get_ui_font(9),
            fg="#444",
            bg="#1a1a2e",
        )
        hint.pack()

    def _start_api(self):
        """启动 API 服务"""
        self._api_server = start_api_server(self._cam_manager, self._config)
        if not self._api_server:
            logger.error("API 服务启动失败")

    def _select_image(self):
        """选择图片文件"""
        path = filedialog.askopenfilename(
            title="选择图片", filetypes=self._config.get_file_types()
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str):
        """
        加载图片

        Args:
            path: 图片文件路径
        """
        if not os.path.exists(path):
            logger.warning(f"图片文件不存在: {path}")
            return

        self._current_image_path = path

        # 保存配置
        self._config.last_image = path
        self._config.save()

        # 加载到摄像头管理器 (触发 on_image_changed)
        self._cam_manager.set_image(path)

    def _update_preview_from_array(self, img_array: np.ndarray):
        """从 numpy BGR 图片更新预览界面"""
        try:
            rgb_img = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            h, w = img_array.shape[:2]

            pil_img.thumbnail((400, 280))
            self._photo_ref = ImageTk.PhotoImage(pil_img)
            self._preview_label.configure(image=self._photo_ref, text="")  # type: ignore

            source_label = (
                os.path.basename(self._current_image_path)
                if self._current_image_path
                else "API 推送"
            )
            self._info_var.set(f"{source_label}  {w}×{h}")
        except Exception as e:
            logger.error(f"更新画面预览失败: {e}")
            self._preview_label.configure(image="", text="预览失败")

    def _update_status_ui(self, running: bool, msg: str):
        """更新状态栏与按钮显示"""
        if running:
            self._status_var.set(f"✅ {msg}")
            self._status_label.configure(fg="#95d5b2", bg="#1b4332")
            self._btn_start.configure(text="⏹ 停止", bg="#6a1a1a")
        else:
            self._status_var.set("⚠️ 已停止")
            self._status_label.configure(fg="#e8a0a0", bg="#3d1f1f")
            self._btn_start.configure(text="🚀 启动摄像头", bg="#2d6a4f")

    def _on_cam_image_changed(self, img_array: np.ndarray):
        """API 或本地图片更新时由后台线程回调"""
        self._root.after(0, lambda: self._update_preview_from_array(img_array))

    def _on_cam_status_changed(self, running: bool, msg: str):
        """摄像头启停时由后台线程回调"""
        self._root.after(0, lambda: self._update_status_ui(running, msg))

    def _toggle_camera(self):
        """切换摄像头状态"""
        if self._cam_manager.is_running:
            self._cam_manager.stop()
        else:
            ok, msg = self._cam_manager.start()
            if not ok:
                messagebox.showerror("启动失败", msg)

    def _on_close(self):
        """窗口关闭处理"""
        logger.info("正在关闭应用...")

        # 停止摄像头
        self._cam_manager.stop()

        # 停止 API 服务
        if self._api_server:
            self._api_server.stop()

        # 销毁窗口
        self._root.destroy()
        logger.info("应用已关闭")

    def run(self):
        """运行应用主循环"""
        logger.info("应用启动")
        self._root.mainloop()

