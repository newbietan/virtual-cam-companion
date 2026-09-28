"""
VirtualCam Companion - 虚拟摄像头驱动与环境自动配置助手
支持自动检测、一键拉起 OBS 激活驱动、一键直达系统设置与自动安装
"""

from __future__ import annotations

from collections.abc import Callable
import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
import webbrowser

from utils import get_log_file, setup_logger

logger = setup_logger("DriverHelper", get_log_file())


def is_obs_installed() -> bool:
    """检测本地是否已安装 OBS Studio"""
    if platform.system() == "Darwin":
        return os.path.exists("/Applications/OBS.app")
    elif platform.system() == "Windows":
        prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        obs_64 = os.path.join(prog_files, "obs-studio", "bin", "64bit", "obs64.exe")
        obs_32 = os.path.join(prog_files_x86, "obs-studio", "bin", "32bit", "obs32.exe")
        return os.path.exists(obs_64) or os.path.exists(obs_32)
    return shutil.which("obs") is not None


def get_brew_path() -> str | None:
    """检测 Homebrew 路径 (macOS)"""
    return shutil.which("brew")


def launch_obs_with_virtualcam() -> bool:
    """尝试以带虚拟摄像机参数启动 OBS"""
    sys_name = platform.system()
    try:
        if sys_name == "Darwin":
            if os.path.exists("/Applications/OBS.app"):
                subprocess.Popen(["open", "-a", "/Applications/OBS.app", "--args", "--startvirtualcam"])
                logger.info("已通过 open 调起 OBS 并请求启动虚拟相机")
                return True
        elif sys_name == "Windows":
            prog_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            obs_exe = os.path.join(prog_files, "obs-studio", "bin", "64bit", "obs64.exe")
            if os.path.exists(obs_exe):
                subprocess.Popen([obs_exe, "--startvirtualcam"], cwd=os.path.dirname(obs_exe))
                return True
        elif sys_name == "Linux":
            obs_bin = shutil.which("obs")
            if obs_bin:
                subprocess.Popen([obs_bin, "--startvirtualcam"])
                return True
    except Exception as e:
        logger.error(f"调起 OBS 失败: {e}")
    return False


def open_system_security_settings():
    """打开 macOS 系统设置中的安全与隐私面板"""
    if platform.system() == "Darwin":
        try:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security"])
        except Exception as e:
            logger.error(f"打开系统偏好设置失败: {e}")


def open_obs_website():
    """打开 OBS 官方下载页面"""
    webbrowser.open("https://obsproject.com/download")


class DriverSetupDialog(tk.Toplevel):
    """跨平台驱动与环境自动化配置向导对话框"""

    def __init__(self, parent: tk.Tk | tk.Toplevel, error_msg: str, on_retry: Callable[[], None]):
        super().__init__(parent)
        self.title("🛠️ 虚拟摄像头环境配置向导")
        self.geometry("540x520")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self.transient(parent)
        self.grab_set()

        self._parent_window = parent
        self._error_msg = error_msg
        self._on_retry = on_retry
        self._sys_name = platform.system()
        self._is_installing = False

        self._build_ui()
        self._center_window(parent)

    def _center_window(self, parent: tk.Tk | tk.Toplevel):
        """让对话框居中于父窗口"""
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build_ui(self):
        """构建向导界面"""
        # 头部标题
        header_frame = tk.Frame(self, bg="#1a1a2e")
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))

        icon_label = tk.Label(header_frame, text="📷", font=("Segoe UI", 24), bg="#1a1a2e", fg="#6c63ff")
        icon_label.pack(side=tk.LEFT, padx=(0, 10))

        title_box = tk.Frame(header_frame, bg="#1a1a2e")
        title_box.pack(side=tk.LEFT, fill=tk.BOTH)

        tk.Label(
            title_box,
            text="未检测到虚拟摄像头环境",
            font=("Segoe UI", 14, "bold"),
            fg="#fff",
            bg="#1a1a2e",
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text=f"当前系统: {self._sys_name}，需要完成一次性驱动扩展激活",
            font=("Segoe UI", 9),
            fg="#888",
            bg="#1a1a2e",
        ).pack(anchor="w")

        # 详细引导内容区域
        content_frame = tk.Frame(self, bg="#24243a", bd=0, padx=16, pady=16)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        if self._sys_name == "Darwin":
            self._build_macos_wizard(content_frame)
        elif self._sys_name == "Linux":
            self._build_linux_wizard(content_frame)
        else:
            self._build_windows_wizard(content_frame)

        # 底部按钮栏
        bottom_frame = tk.Frame(self, bg="#1a1a2e")
        bottom_frame.pack(fill=tk.X, padx=20, pady=(10, 20))

        tk.Button(
            bottom_frame,
            text="❌ 取消",
            bg="#3a3a4e",
            fg="#bbb",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.destroy,
        ).pack(side=tk.LEFT)

        self._btn_retry = tk.Button(
            bottom_frame,
            text="🔄 我已授权，重新启动摄像头",
            bg="#2d6a4f",
            fg="#fff",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._handle_retry,
        )
        self._btn_retry.pack(side=tk.RIGHT)

    def _build_macos_wizard(self, container: tk.Frame):
        """macOS 自动化配置指引"""
        obs_ok = is_obs_installed()
        brew_ok = get_brew_path() is not None

        # 步骤 1: OBS 安装状态
        step1_box = tk.Frame(container, bg="#24243a")
        step1_box.pack(fill=tk.X, pady=(0, 12))

        status_icon = "✅" if obs_ok else "⚠️"
        status_text = "已检测到 OBS Studio 安装于 /Applications" if obs_ok else "未在系统应用程序中检测到 OBS Studio"
        status_color = "#95d5b2" if obs_ok else "#e8a0a0"

        tk.Label(
            step1_box,
            text=f"步骤 1: OBS 基础环境 ({status_icon} {status_text})",
            font=("Segoe UI", 10, "bold"),
            fg=status_color,
            bg="#24243a",
        ).pack(anchor="w", pady=(0, 6))

        if not obs_ok:
            btn_row = tk.Frame(step1_box, bg="#24243a")
            btn_row.pack(fill=tk.X)

            if brew_ok:
                self._btn_brew = tk.Button(
                    btn_row,
                    text="⚡ 一键通过 Homebrew 安装 OBS",
                    bg="#6c63ff",
                    fg="#fff",
                    bd=0,
                    padx=10,
                    pady=4,
                    cursor="hand2",
                    command=self._start_brew_install,
                )
                self._btn_brew.pack(side=tk.LEFT, padx=(0, 8))

            tk.Button(
                btn_row,
                text="🌐 打开 OBS 官网下载",
                bg="#3d3d5c",
                fg="#ddd",
                bd=0,
                padx=10,
                pady=4,
                cursor="hand2",
                command=open_obs_website,
            ).pack(side=tk.LEFT)

        # 步骤 2: 激活系统级虚拟相机扩展
        step2_box = tk.Frame(container, bg="#24243a")
        step2_box.pack(fill=tk.X, pady=6)

        tk.Label(
            step2_box,
            text="步骤 2: 激活系统虚拟相机扩展 (CoreMediaIO)",
            font=("Segoe UI", 10, "bold"),
            fg="#fff",
            bg="#24243a",
        ).pack(anchor="w")

        tk.Label(
            step2_box,
            text="由于 macOS 13+ 内核安全机制，必须拉起一次系统扩展授权：",
            font=("Segoe UI", 9),
            fg="#999",
            bg="#24243a",
        ).pack(anchor="w", pady=(2, 6))

        action_row = tk.Frame(step2_box, bg="#24243a")
        action_row.pack(fill=tk.X)

        tk.Button(
            action_row,
            text="🚀 一键拉起 OBS 激活虚拟相机",
            bg="#2d6a4f" if obs_ok else "#444",
            fg="#fff",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2" if obs_ok else "arrow",
            command=launch_obs_with_virtualcam if obs_ok else open_obs_website,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            action_row,
            text="⚙️ 一键直达「系统设置-隐私」",
            bg="#3d3d5c",
            fg="#ddd",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=open_system_security_settings,
        ).pack(side=tk.LEFT)

        # 日志/进度提示区域
        self._log_var = tk.StringVar(
            value="提示: 点击『一键拉起 OBS』后，请在弹出的系统设置中点击『允许』系统扩展。"
        )
        self._log_label = tk.Label(
            container,
            textvariable=self._log_var,
            font=("Segoe UI", 9),
            fg="#bbb",
            bg="#1d1d2f",
            wraplength=460,
            justify=tk.LEFT,
            padx=10,
            pady=8,
        )
        self._log_label.pack(fill=tk.X, pady=(12, 0))

    def _build_linux_wizard(self, container: tk.Frame):
        """Linux 配置指引"""
        tk.Label(
            container,
            text="Linux 需要加载 v4l2loopback 内核模块",
            font=("Segoe UI", 10, "bold"),
            fg="#fff",
            bg="#24243a",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            container,
            text="请在终端执行项目自带的配置脚本：\nsudo bash scripts/setup_linux_v4l2.sh",
            font=("Courier", 10),
            fg="#95d5b2",
            bg="#1d1d2f",
            padx=10,
            pady=10,
        ).pack(fill=tk.X, pady=(0, 10))

    def _build_windows_wizard(self, container: tk.Frame):
        """Windows 配置指引"""
        tk.Label(
            container,
            text="未检测到 Windows DirectShow 虚拟摄像头驱动",
            font=("Segoe UI", 10, "bold"),
            fg="#fff",
            bg="#24243a",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            container,
            text="建议直接重新运行 VirtualCamCompanion-Setup 安装包自动注册驱动，\n或安装 OBS Studio 并在其内点击一次启动虚拟摄像头。",
            font=("Segoe UI", 9),
            fg="#ccc",
            bg="#24243a",
        ).pack(anchor="w", pady=(0, 10))

    def _start_brew_install(self):
        """后台执行 Homebrew 安装 OBS"""
        if self._is_installing:
            return
        self._is_installing = True
        self._btn_brew.configure(state=tk.DISABLED, text="⏳ 正在下载并安装 OBS (请稍候)...")
        self._log_var.set("正在执行: brew install --cask obs\n后台下载安装中，这通常需要 1~2 分钟...")

        def _worker():
            try:
                proc = subprocess.Popen(
                    ["brew", "install", "--cask", "obs"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if proc.stdout is not None:
                    for line in iter(proc.stdout.readline, ""):
                        if line:
                            line_str = line.strip()
                            self.after(0, lambda msg=line_str: self._log_var.set(f"进度: {msg}"))
                proc.wait()
                if proc.returncode == 0:
                    self.after(0, self._on_install_success)
                else:
                    self.after(0, lambda: self._log_var.set("❌ Homebrew 安装遇到问题，建议前往官网下载安装。"))
            except Exception as e:
                self.after(0, lambda err=e: self._log_var.set(f"❌ 安装出错: {err}"))
            finally:
                self._is_installing = False

        threading.Thread(target=_worker, daemon=True).start()

    def _on_install_success(self):
        """安装成功后的 UI 刷新"""
        self._log_var.set("✅ OBS 安装成功！点击上方『一键拉起 OBS 激活虚拟相机』继续。")
        self.destroy()
        # 重新调出向导刷新状态
        DriverSetupDialog(self._parent_window, "", self._on_retry)

    def _handle_retry(self):
        """用户点击重试"""
        self.destroy()
        if self._on_retry:
            self._on_retry()


def show_driver_setup_dialog(parent: tk.Tk | tk.Toplevel, error_msg: str, on_retry: Callable[[], None]):
    """调起环境配置向导对话框"""
    DriverSetupDialog(parent, error_msg, on_retry)
