<div align="center">

# VirtualCam Companion

**系统级虚拟摄像头工具 -- 让任何网页/软件都能检测到虚拟摄像头**

[![GitHub Stars](https://img.shields.io/github/stars/GreenhandTan/virtual-cam-companion?style=social)](https://github.com/GreenhandTan/virtual-cam-companion/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![GitHub Release](https://img.shields.io/github/v/release/GreenhandTan/virtual-cam-companion)](https://github.com/GreenhandTan/virtual-cam-companion/releases/latest)
[![GitHub Downloads](https://img.shields.io/github/downloads/GreenhandTan/virtual-cam-companion/total)](https://github.com/GreenhandTan/virtual-cam-companion/releases)

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-5C3EE8?logo=opencv&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?logo=linux&logoColor=white)

</div>

---

## 功能特性

- **跨平台系统级虚拟摄像头** -- 支持 **Windows** (DirectShow), **macOS** (CoreMediaIO Extension), **Linux** (v4l2loopback)，任何网页/会议软件都能识别
- **图片与流输出** -- 支持 JPG / PNG / BMP / WebP 格式图片作为摄像头画面，并保持 30fps 持续推流
- **HTTP API 联动** -- 内置 REST API（端口 5566），与 GUI 状态双向实时同步，可被 Chrome 扩展或自动化脚本远程调用
- **开箱即用与跨平台配置** -- Windows 包含一体化静默驱动安装；macOS/Linux 提供一键引导脚本；配置及日志遵循各操作系统规范
- **现代化可视化界面** -- 基于 tkinter 的深色现代化 GUI，支持实时缩略图预览、状态指示、自适应高分屏缩放

## 快速开始

### 下载安装

前往 [Releases](https://github.com/GreenhandTan/virtual-cam-companion/releases/latest) 下载对应平台的安装包：

#### 🪟 Windows
1. 下载 `VirtualCamCompanion-Setup.exe` 并安装（安装包已内置驱动并自动注册）。
2. 安装完成后直接启动即可。

#### 🍏 macOS
1. 下载 `VirtualCamCompanion-macOS.dmg`，将应用拖拽到 `Applications` 目录。
2. **一次性前置配置**：由于 macOS 13+ 的系统扩展权限要求，请确保已安装 [OBS Studio 30+](https://obsproject.com)（或 `brew install --cask obs`）。打开 OBS 点击一次『启动虚拟摄像机』后关闭即可激活驱动。

#### 🐧 Linux
1. 下载 `VirtualCamCompanion-Linux-x86_64.tar.gz` 并解压。
2. **内核模块准备**：执行解压目录中的一键脚本加载 `v4l2loopback` 驱动：
   ```bash
   sudo bash scripts/setup_linux_v4l2.sh
   ```
3. 运行 `./VirtualCamCompanion` 即可。

---

### 使用方法

1. 点击 **选择图片** 加载要显示的画面（或通过 Chrome 扩展推送）
2. 点击 **启动摄像头**
3. 打开浏览器 / Zoom / Teams / 腾讯会议，选择 **OBS Virtual Camera**（或对应的虚拟摄像头设备）
4. 网页/软件看到的就是你选择的实时画面

### 配合 Chrome 扩展使用

1. 启动本程序（HTTP API 自动在本地监听 `127.0.0.1:5566`）
2. 安装 [VirtualCam Extension](https://github.com/GreenhandTan/virtual-cam-extension)
3. 在扩展中选择图片，自动发送到本程序，虚拟摄像头输出该画面，桌面 GUI 同步刷新预览

---

## 工作原理

```mermaid
graph TB
    A[用户选择图片 / 外部脚本] --> B[VirtualCam Companion]
    C[Chrome 扩展] -->|HTTP REST API: 5566| B
    B -->|pyvirtualcam| D{多平台虚拟相机驱动}
    D -->|Windows| E[OBS Virtual Camera DLL / DirectShow]
    D -->|macOS| F[CoreMediaIO Camera Extension]
    D -->|Linux| G[v4l2loopback /dev/video10]
    E & F & G --> H[系统级摄像头输入设备]
    H --> I[浏览器 / Zoom / Teams / WebRTC]
```

```mermaid
graph LR
    subgraph 应用模块
        A[app.py<br>程序入口与 DPI 适配] --> B[gui.py<br>GUI 界面与双向同步]
        A --> C[config.py<br>跨平台配置管理]
        B --> D[cam_manager.py<br>多平台驱动控制与推流]
        B --> E[api_server.py<br>HTTP API 服务]
        D --> F[utils.py<br>跨平台路径/日志/校验]
        E --> F
    end
```

## HTTP API

程序启动后自动开启本地 HTTP 服务，供 Chrome 扩展或自动化调用：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/ping` | GET | 心跳检测，确认程序是否在后台运行 |
| `/api/status` | GET | 获取运行状态（平台、是否启动、设备名、是否有图片、镜像状态、适配模式、分辨率） |
| `/api/set_image` | POST | 发送图片（body: `{"image": "base64...", "flip": bool, "fit_mode": "fit/fill/stretch", "auto_resolution": bool}`） |
| `/api/flip` | POST | 切换或设置水平镜像翻转（body 可选: `{"flip": true/false}`，无 body 则切换） |
| `/api/fit_mode` | POST | 设置画面适配模式（body: `{"mode": "fit" / "fill" / "stretch"}`） |
| `/api/start` | POST | 启动虚拟摄像头推流，GUI 按钮联动更新 |
| `/api/stop` | POST | 停止虚拟摄像头推流，GUI 按钮联动更新 |

---

## 技术栈与平台适配

| 类别 | 技术 | 跨平台说明 |
|------|------|------|
| **编程语言** | Python 3.8+ | Windows / macOS / Linux 统一核心代码 |
| **GUI** | tkinter + Pillow | 自适应高分屏 (DPI)，跨平台字体与图标自适应 |
| **底层驱动** | pyvirtualcam | Windows (DirectShow) / macOS (CoreMediaIO) / Linux (V4L2) |
| **图像处理** | OpenCV, Pillow | 自动适应 16:9 (1280x720) 与色彩空间转换 |
| **网络通信** | HTTP Server | 内置单机 REST API，支持 CORS 跨域 |
| **打包分发** | PyInstaller, Inno Setup | Windows: Setup.exe / macOS: .dmg / Linux: tar.gz |
| **CI/CD** | GitHub Actions | 矩阵全自动多平台构建与发布 Release |

---

## 项目结构

```
virtual-cam-companion/
├── app.py                    # 程序入口 (Windows DPI 适配与初始化)
├── config.py                 # 跨平台配置管理模块 (AppData/Application Support/XDG)
├── cam_manager.py            # 跨平台虚拟摄像头核心模块 (Windows/macOS/Linux)
├── api_server.py             # HTTP API 服务模块 (CORS 支持、双向同步)
├── gui.py                    # 跨平台 GUI 界面模块 (高分屏、实时同步预览)
├── utils.py                  # 工具函数 (跨平台日志轮转、图片魔数校验、路径解析)
├── requirements.txt          # Python 依赖清单
├── setup.iss                 # Windows Inno Setup 安装包脚本
├── app.ico / app.png / app.icns # 各平台图标资产
├── LICENSE                   # MIT 开源协议
├── README.md                 # 本说明文档
├── scripts/
│   ├── setup_linux_v4l2.sh   # Linux v4l2loopback 驱动一键配置脚本
│   ├── setup_macos.sh        # macOS OBS 虚拟相机扩展检测脚本
│   ├── extract_obs_vcam.ps1  # Windows CI 提取 OBS 驱动脚本
│   └── extract_driver.py     # 从 pyvirtualcam 提取驱动（备用）
└── .github/workflows/
    └── build.yml             # GitHub Actions 跨平台矩阵自动构建流水线
```

---

## 开发与本地运行

```bash
# 1. 克隆项目
git clone https://github.com/GreenhandTan/virtual-cam-companion.git
cd virtual-cam-companion

# 2. 安装依赖
pip install pyvirtualcam opencv-python Pillow

# 3. 运行应用
python app.py
```

---

## 常见问题

**Q: 浏览器或会议软件中看不到虚拟摄像头？**
- **Windows**: 确保在程序中点击了『启动摄像头』，并刷新网页。如果未检测到设备，重启一次程序或重新运行安装包。
- **macOS**: macOS 13+ 需要在 OBS Studio 中启动一次虚拟摄像机以激活系统级 `CoreMediaIO` 扩展，如提示系统扩展被阻止，请至「系统设置 -> 隐私与安全性」中授权允许。
- **Linux**: 确保已执行 `sudo bash scripts/setup_linux_v4l2.sh` 加载了 `v4l2loopback` 模块生成 `/dev/video10`。

**Q: 为什么网页或会议软件看到的画面是镜像（左右颠倒）的？**
浏览器（WebRTC `<video>` 预览）和各大会议软件默认将虚拟摄像头视作「前置自拍镜头」，会自动进行水平镜像翻转。当推流带有文字、证件、二维码的图片时，文字就会变成反向的。
- **解决方法**：只需在 VirtualCam Companion 界面中点击**『🪞 镜像: 开』**（或通过 API 调用 `/api/flip`），程序会主动对画面进行水平翻转，前端再次镜像后「负负得正」，呈现完美的正向画面！

**Q: 为什么摄像头获取的图片不完整（被裁切）或被拉伸变形？**
- **原因**：常见网页或人脸核身框通常要求特定比例（如竖屏 3:4 / 9:16 或正方形 1:1），旧版虚拟摄像头如果固定输出 16:9 横屏流或者强行拉伸，网页端使用 `object-fit: cover` 就会切掉两侧大部分内容。
- **全新优化方案**：
  1. **智能尺寸自适应（Auto Resolution）**：默认开启，选择图片后程序会自动根据图片的实际尺寸与宽高比匹配虚拟摄像头分辨率（如 1080x1920 竖屏图将直接输出 1080x1920 原生竖屏流），避免网页端因比例不一致而发生二次裁剪！
  2. **等比完整包含（Fit / Letterbox）**：如果输出分辨率固定，程序会按原始比例等比缩放并以黑边居中补全，确保整张图片 100% 完整显示，绝不畸变、绝不丢失任何边缘！
  3. **多种适配模式切换**：支持在界面点击『📐 适配』自由切换『完整 (Fit)』、『裁切 (Fill)』与『拉伸 (Stretch)』模式。

**Q: 支持哪些操作系统？**
- Windows 10 / 11 (64位)
- macOS 13+ (Ventura, Sonoma, Sequoia / Intel & Apple Silicon)
- Linux (Ubuntu 20.04+, Debian 11+, Fedora, Arch Linux 等主流发行版)

---

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。
