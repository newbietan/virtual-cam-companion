"""
VirtualCam Companion - GUI 界面模块
基于 tkinter 的深色现代视觉设计，遵循跨平台规范并减少 emoji 装饰
"""

from __future__ import annotations

import os
import platform
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog
from typing import Any

import numpy as np  # type: ignore
from PIL import Image, ImageTk  # type: ignore

from api_server import APIServer, start_api_server
from cam_manager import VirtualCamManager
from config import AppConfig
from driver_helper import show_driver_setup_dialog
from utils import get_log_file, setup_logger

logger = setup_logger("GUI", get_log_file())

# 现代专业深色高对比度主题调色盘
COLOR_BG = "#0f1118"  # 根窗口底色
COLOR_CARD = "#171a24"  # 卡片面板底色
COLOR_CARD_BORDER = "#282e40"  # 卡片描边色 (清晰对比度)
COLOR_WELL = "#0a0c12"  # 预览凹槽深色底
COLOR_WELL_BORDER = "#1f2434"  # 预览凹槽描边
COLOR_FG_PRIMARY = "#ffffff"  # 主文字纯白色 (高对比清晰)
COLOR_FG_SECONDARY = "#cbd5e1"  # 次级文字亮色 (Slate-300，清晰不发灰)
COLOR_FG_MUTED = "#94a3b8"  # 弱化文字提示 (Slate-400)
COLOR_FG_SUBTLE = "#64748b"  # 超弱文字说明 (Slate-500)

COLOR_BTN_SECONDARY = "#222738"  # 次要按钮背景 (深色实体底，绝不发白)
COLOR_BTN_SECONDARY_HOVER = "#2e354c"  # 次要按钮悬停
COLOR_BTN_SECONDARY_BORDER = "#353d57"  # 次要按钮描边
COLOR_BTN_CHIP_ACTIVE = "#2d3f6d"  # 激活选项高亮底色
COLOR_BTN_CHIP_ACTIVE_FG = "#ffffff"  # 激活选项文字色
COLOR_BTN_CHIP_ACTIVE_BORDER = "#4f6cb5"  # 激活选项高亮描边
COLOR_BTN_SUCCESS = "#10b981"  # 成功/就绪绿 (Emerald-500)
COLOR_BTN_PRIMARY = "#2563eb"  # 主要行动按钮亮蓝 (Blue-600)
COLOR_BTN_PRIMARY_HOVER = "#3b82f6"  # 主要行动按钮悬停 (Blue-500)
COLOR_BTN_DANGER = "#dc2626"  # 危险/停止按钮鲜红 (Red-600)
COLOR_BTN_DANGER_HOVER = "#ef4444"  # 停止按钮悬停 (Red-500)


def get_ui_font(size: int = 10, weight: str = "normal") -> tuple[str, int, str]:
    """获取跨平台的精美排版字体"""
    sys_name = platform.system()
    if sys_name == "Darwin":
        family = "PingFang SC"
    elif sys_name == "Windows":
        family = "Microsoft YaHei UI"
    else:
        family = "DejaVu Sans"
    return (family, size, weight)


def get_mono_font(size: int = 9) -> tuple[str, int, str]:
    """获取等宽字体"""
    sys_name = platform.system()
    if sys_name == "Darwin":
        family = "Menlo"
    elif sys_name == "Windows":
        family = "Consolas"
    else:
        family = "Monospace"
    return (family, size, "normal")


class FlatButton(tk.Label):
    """
    跨平台高对比度自定义扁平按钮组件
    解决 macOS 系统下 Tkinter 原生 tk.Button 强制渲染为浅白底色导致文字发白看不清的问题，
    在所有平台上呈现一致、清晰、高对比的深色卡片质感与悬停动效。
    """

    def __init__(
        self,
        parent,
        text: str = "",
        command: Callable[[], None] | None = None,
        bg: str = COLOR_BTN_SECONDARY,
        fg: str = COLOR_FG_PRIMARY,
        hover_bg: str | None = None,
        active_bg: str | None = None,
        font: tuple | None = None,
        padx: int = 12,
        pady: int = 8,
        border_color: str | None = None,
        **kwargs,
    ):
        self._command = command
        self._normal_bg = bg
        self._normal_fg = fg
        self._hover_bg = hover_bg or bg
        self._active_bg = active_bg or hover_bg or bg
        self._enabled = True

        kwargs.pop("activebackground", None)
        kwargs.pop("activeforeground", None)

        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font or get_ui_font(10, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
            bd=0,
            highlightthickness=1,
            highlightbackground=border_color or bg,
            anchor="center",
            justify="center",
            **kwargs,
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, _e):
        if self._enabled and self._hover_bg:
            super().configure(bg=self._hover_bg)

    def _on_leave(self, _e):
        if self._enabled:
            super().configure(bg=self._normal_bg)

    def _on_press(self, _e):
        if self._enabled and self._active_bg:
            super().configure(bg=self._active_bg)

    def _on_release(self, e):
        if self._enabled:
            super().configure(bg=self._normal_bg)
            if (
                0 <= e.x <= self.winfo_width()
                and 0 <= e.y <= self.winfo_height()
                and self._command
            ):
                self._command()

    def configure(self, cnf=None, **kwargs) -> Any:
        if cnf:
            kwargs.update(cnf)
        if "bg" in kwargs:
            self._normal_bg = kwargs["bg"]
            if "activebackground" not in kwargs:
                self._hover_bg = kwargs["bg"]
        if "fg" in kwargs:
            self._normal_fg = kwargs["fg"]
        if "activebackground" in kwargs:
            self._hover_bg = kwargs.pop("activebackground")
        if "activeforeground" in kwargs:
            kwargs.pop("activeforeground")
        return super().configure(**kwargs)

    config = configure


class VirtualCamApp:
    """跨平台现代虚拟摄像头 GUI 应用"""

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
            fit_mode=config.fit_mode,
            auto_resolution=config.auto_resolution,
            flip_horizontal=config.flip_horizontal,
        )
        self._api_server: APIServer | None = None
        self._current_image_path: str | None = config.last_image
        self._photo_ref: ImageTk.PhotoImage | None = None

        # 监听摄像头状态与画面变更事件
        self._cam_manager.on_image_changed = self._on_cam_image_changed
        self._cam_manager.on_status_changed = self._on_cam_status_changed

        # 创建主窗口
        self._root = tk.Tk()
        self._root.title("VirtualCam Companion")
        self._root.geometry(f"{config.window_width}x{config.window_height}")
        self._root.resizable(False, False)
        self._root.configure(bg=COLOR_BG)

        # 设置跨平台图标
        self._setup_icon()

        # 构建现代化布局
        self._build_ui()

        # 启动本地 REST API 服务
        self._start_api()

        # 加载上次的图片或占位
        if self._current_image_path:
            safe_path = os.path.abspath(self._current_image_path)
            if os.path.isfile(safe_path):
                self._load_image(safe_path)
            else:
                self._update_preview()
        else:
            self._update_preview()

        # 注册窗口关闭事件
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_icon(self):
        """设置窗口图标"""
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
        """构建专业、紧凑、现代化的用户界面"""
        # ==================== 1. 顶部 Header 栏 ====================
        header_frame = tk.Frame(self._root, bg=COLOR_BG)
        header_frame.pack(fill=tk.X, padx=24, pady=(20, 14))

        # 标题与副标题区
        title_box = tk.Frame(header_frame, bg=COLOR_BG)
        title_box.pack(side=tk.LEFT)

        app_title = tk.Label(
            title_box,
            text="VirtualCam Companion",
            font=get_ui_font(15, "bold"),
            fg=COLOR_FG_PRIMARY,
            bg=COLOR_BG,
        )
        app_title.pack(anchor="w")

        app_subtitle = tk.Label(
            title_box,
            text="系统级虚拟摄像头推流管理",
            font=get_ui_font(9),
            fg=COLOR_FG_MUTED,
            bg=COLOR_BG,
        )
        app_subtitle.pack(anchor="w", pady=(2, 0))

        # 状态指示胶囊 (Status Badge)
        self._status_var = tk.StringVar(value="○ 离线")
        self._status_badge = tk.Label(
            header_frame,
            textvariable=self._status_var,
            font=get_ui_font(9, "bold"),
            fg=COLOR_FG_SECONDARY,
            bg=COLOR_CARD,
            padx=12,
            pady=6,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=1,
            bd=0,
        )
        self._status_badge.pack(side=tk.RIGHT)

        # ==================== 2. 预览区卡片 ====================
        preview_card = tk.Frame(
            self._root,
            bg=COLOR_CARD,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=1,
            bd=0,
        )
        preview_card.pack(fill=tk.X, padx=24, pady=(0, 14))

        # 视频预览槽 (深色 Well)
        preview_well = tk.Frame(
            preview_card,
            bg=COLOR_WELL,
            highlightbackground=COLOR_WELL_BORDER,
            highlightthickness=1,
            bd=0,
        )
        preview_well.pack(fill=tk.X, padx=12, pady=12)

        self._preview_label = tk.Label(
            preview_well,
            bg=COLOR_WELL,
            text="暂无推流画面\n\n点击下方「选择图片」加载本地文件\n或通过 Chrome 扩展直接推送",
            fg=COLOR_FG_MUTED,
            font=get_ui_font(10),
            width=50,
            height=12,
        )
        self._preview_label.pack(padx=2, pady=2)

        # 预览下方的信息条 (Metadata Strip)
        self._meta_var = tk.StringVar(value="等待选择图片")
        self._meta_label = tk.Label(
            preview_card,
            textvariable=self._meta_var,
            font=get_mono_font(9),
            fg=COLOR_FG_SECONDARY,
            bg=COLOR_CARD,
        )
        self._meta_label.pack(anchor="w", padx=14, pady=(0, 10))

        # ==================== 3. 画面调节卡片 ====================
        controls_card = tk.Frame(
            self._root,
            bg=COLOR_CARD,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=1,
            bd=0,
        )
        controls_card.pack(fill=tk.X, padx=24, pady=(0, 14))

        control_header = tk.Frame(controls_card, bg=COLOR_CARD)
        control_header.pack(fill=tk.X, padx=14, pady=(10, 8))

        lbl_section = tk.Label(
            control_header,
            text="画面输出调节",
            font=get_ui_font(10, "bold"),
            fg=COLOR_FG_SECONDARY,
            bg=COLOR_CARD,
        )
        lbl_section.pack(side=tk.LEFT)

        # 三个紧凑参数按钮排成一行
        chips_frame = tk.Frame(controls_card, bg=COLOR_CARD)
        chips_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        # 设置 3 列均分权重
        chips_frame.columnconfigure(0, weight=1)
        chips_frame.columnconfigure(1, weight=1)
        chips_frame.columnconfigure(2, weight=1)

        style_chip = {
            "font": get_ui_font(9, "bold"),
            "padx": 6,
            "pady": 7,
            "border_color": COLOR_BTN_SECONDARY_BORDER,
            "hover_bg": COLOR_BTN_SECONDARY_HOVER,
        }

        self._btn_flip = FlatButton(
            chips_frame,
            text="镜像: 关",
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_FG_PRIMARY,
            command=self._toggle_flip,
            **style_chip,
        )
        self._btn_flip.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._btn_fit = FlatButton(
            chips_frame,
            text="适配: 完整",
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_FG_PRIMARY,
            command=self._cycle_fit_mode,
            **style_chip,
        )
        self._btn_fit.grid(row=0, column=1, sticky="ew", padx=4)

        self._btn_auto_res = FlatButton(
            chips_frame,
            text="尺寸: 固定 720P",
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_FG_PRIMARY,
            command=self._toggle_auto_resolution,
            **style_chip,
        )
        self._btn_auto_res.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self._update_control_buttons_ui()

        # ==================== 4. 主操作按钮行 ====================
        action_frame = tk.Frame(self._root, bg=COLOR_BG)
        action_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)

        style_action = {
            "font": get_ui_font(11, "bold"),
            "pady": 10,
        }

        self._btn_select = FlatButton(
            action_frame,
            text="选择图片",
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_FG_PRIMARY,
            hover_bg=COLOR_BTN_SECONDARY_HOVER,
            border_color=COLOR_BTN_SECONDARY_BORDER,
            command=self._select_image,
            **style_action,
        )
        self._btn_select.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._btn_start = FlatButton(
            action_frame,
            text="启动摄像头",
            bg=COLOR_BTN_PRIMARY,
            fg="#ffffff",
            hover_bg=COLOR_BTN_PRIMARY_HOVER,
            border_color=COLOR_BTN_PRIMARY,
            command=self._toggle_camera,
            **style_action,
        )
        self._btn_start.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # ==================== 5. 底部状态与提示栏 ====================
        footer_frame = tk.Frame(self._root, bg=COLOR_BG)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=(0, 16))

        # 提示文字
        self._tip_label = tk.Label(
            footer_frame,
            text="提示: 浏览器或会议软件画面左右颠倒时，开启「镜像」即可纠正",
            font=get_ui_font(8),
            fg=COLOR_FG_SUBTLE,
            bg=COLOR_BG,
        )
        self._tip_label.pack(anchor="w", pady=(0, 4))

        # API 状态
        api_label = tk.Label(
            footer_frame,
            text=f"API 运行于 {self._config.api_address} · 支持 Chrome 扩展自动连接",
            font=get_mono_font(8),
            fg=COLOR_FG_MUTED,
            bg=COLOR_BG,
        )
        api_label.pack(anchor="w")

    def _update_control_buttons_ui(self):
        """刷新参数微调按钮的状态样式与文字"""
        # 1. 镜像按钮
        is_flip = self._cam_manager.flip_horizontal
        if is_flip:
            self._btn_flip.configure(
                text="镜像: 开启 (已翻转)",
                bg=COLOR_BTN_CHIP_ACTIVE,
                fg=COLOR_BTN_CHIP_ACTIVE_FG,
                activebackground=COLOR_BTN_CHIP_ACTIVE,
                highlightbackground=COLOR_BTN_CHIP_ACTIVE_BORDER,
            )
        else:
            self._btn_flip.configure(
                text="镜像: 关闭 (正常)",
                bg=COLOR_BTN_SECONDARY,
                fg=COLOR_FG_PRIMARY,
                activebackground=COLOR_BTN_SECONDARY_HOVER,
                highlightbackground=COLOR_BTN_SECONDARY_BORDER,
            )

        # 2. 适配模式按钮
        fit_mode = self._cam_manager.fit_mode
        mode_text_map = {
            "fit": "适配: 完整 (等比黑边)",
            "fill": "适配: 裁切 (填满全屏)",
            "stretch": "适配: 拉伸 (强制满屏)",
        }
        self._btn_fit.configure(
            text=mode_text_map.get(fit_mode, "适配: 完整"),
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_FG_PRIMARY,
            highlightbackground=COLOR_BTN_SECONDARY_BORDER,
        )

        # 3. 自动分辨率按钮
        auto_res = self._cam_manager.auto_resolution
        if auto_res:
            self._btn_auto_res.configure(
                text="尺寸: 自动契合",
                bg="#1a2e26",
                fg="#6ee7b7",
                activebackground="#1a2e26",
                highlightbackground="#2a5a46",
            )
        else:
            self._btn_auto_res.configure(
                text="尺寸: 固定 720P",
                bg=COLOR_BTN_SECONDARY,
                fg=COLOR_FG_PRIMARY,
                activebackground=COLOR_BTN_SECONDARY_HOVER,
                highlightbackground=COLOR_BTN_SECONDARY_BORDER,
            )

    def _toggle_flip(self):
        """切换水平镜像翻转"""
        new_state = self._cam_manager.toggle_flip()
        self._config.flip_horizontal = new_state
        self._config.save()
        self._update_control_buttons_ui()
        self._update_preview()

    def _cycle_fit_mode(self):
        """循环切换适配模式"""
        new_mode = self._cam_manager.cycle_fit_mode()
        self._config.fit_mode = new_mode
        self._config.save()
        self._update_control_buttons_ui()
        self._update_preview()

    def _toggle_auto_resolution(self):
        """切换自动尺寸模式"""
        self._cam_manager.auto_resolution = not self._cam_manager.auto_resolution
        self._config.auto_resolution = self._cam_manager.auto_resolution
        self._config.save()
        self._update_control_buttons_ui()
        self._update_preview()

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
        """加载图片"""
        if not os.path.exists(path):
            logger.warning(f"图片文件不存在: {path}")
            return

        self._current_image_path = path

        # 保存配置
        self._config.last_image = path
        self._config.save()

        # 加载到摄像头管理器 (触发 on_image_changed)
        self._cam_manager.set_image(path)
        self._btn_select.configure(text="更换图片")
        self._update_preview()

    def _update_info_label(self):
        """更新预览卡片底部的元数据文字"""
        status = self._cam_manager.get_status()
        raw_size = status.get("image_size")
        cam_w = status.get("width")
        cam_h = status.get("height")
        fps = status.get("fps", 30)

        source_name = (
            os.path.basename(self._current_image_path)
            if self._current_image_path
            else "内存图像"
        )

        if raw_size:
            self._meta_var.set(
                f"{source_name} ({raw_size[0]}×{raw_size[1]})  →  输出 {cam_w}×{cam_h} @ {fps}fps"
            )
        else:
            self._meta_var.set(f"输出分辨率: {cam_w}×{cam_h} @ {fps}fps")

    def _update_preview(self):
        """从摄像头管理器获取处理后的最新帧刷新预览"""
        try:
            frame_rgb = self._cam_manager.get_processed_frame()
            if frame_rgb is None:
                return

            pil_img = Image.fromarray(frame_rgb)
            # 缩略图自适应 420x240 的预览槽
            pil_img.thumbnail((420, 240))
            self._photo_ref = ImageTk.PhotoImage(pil_img)
            self._preview_label.configure(image=self._photo_ref, text="")  # type: ignore

            self._update_info_label()
            self._update_control_buttons_ui()
        except Exception as e:
            logger.error(f"更新画面预览失败: {e}")
            self._preview_label.configure(image="", text="预览渲染失败")

    def _update_status_ui(self, running: bool, msg: str):
        """更新顶部状态标签与行动按钮状态"""
        if running:
            self._status_var.set("● 正在推流")
            self._status_badge.configure(
                fg=COLOR_BTN_SUCCESS,
                bg="#13241e",
                highlightbackground="#1e3a30",
            )
            self._btn_start.configure(
                text="停止推流",
                bg=COLOR_BTN_DANGER,
                fg="#ffffff",
                activebackground=COLOR_BTN_DANGER_HOVER,
                highlightbackground=COLOR_BTN_DANGER,
            )
        else:
            self._status_var.set("○ 已停止")
            self._status_badge.configure(
                fg=COLOR_FG_SECONDARY,
                bg=COLOR_CARD,
                highlightbackground=COLOR_CARD_BORDER,
            )
            self._btn_start.configure(
                text="启动摄像头",
                bg=COLOR_BTN_PRIMARY,
                fg="#ffffff",
                activebackground=COLOR_BTN_PRIMARY_HOVER,
                highlightbackground=COLOR_BTN_PRIMARY,
            )

    def _on_cam_image_changed(self, _img_array: np.ndarray):
        """API 或本地图片更新时由后台线程回调"""
        self._root.after(0, self._update_preview)

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
                show_driver_setup_dialog(self._root, msg, on_retry=self._toggle_camera)

    def _on_close(self):
        """窗口关闭清理处理"""
        logger.info("正在关闭应用...")

        # 停止摄像头
        self._cam_manager.stop()

        # 停止 API 服务
        if self._api_server:
            self._api_server.stop()

        # 销毁窗口
        try:
            if self._root.winfo_exists():
                self._root.destroy()
        except Exception as e:
            logger.debug(f"销毁窗口异常: {e}")
        logger.info("应用已关闭")

    def run(self):
        """运行应用主循环"""
        logger.info("应用启动")
        self._root.mainloop()
