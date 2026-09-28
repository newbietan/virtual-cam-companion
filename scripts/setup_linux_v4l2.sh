#!/usr/bin/env bash
# VirtualCam Companion - Linux v4l2loopback 驱动一键配置脚本
set -e

echo "=== VirtualCam Companion - Linux 环境配置 ==="

# 1. 检查 root / sudo 权限
if [ "$EUID" -ne 0 ]; then
  echo "提示: 请使用 sudo 权限运行此脚本，例如:"
  echo "  sudo bash scripts/setup_linux_v4l2.sh"
  exit 1
fi

# 2. 安装 v4l2loopback-dkms
echo "[1/3] 正在检测并安装 v4l2loopback-dkms..."
if command -v apt-get &> /dev/null; then
  apt-get update -y
  apt-get install -y v4l2loopback-dkms python3-tk v4l-utils
elif command -v dnf &> /dev/null; then
  dnf install -y v4l2loopback python3-tkinter v4l-utils
elif command -v pacman &> /dev/null; then
  pacman -Sy --noconfirm v4l2loopback-dkms tk v4l-utils
else
  echo "⚠️ 未知包管理器，请手动安装: v4l2loopback-dkms, python3-tk"
fi

# 3. 加载内核模块
echo "[2/3] 正在加载 v4l2loopback 内核模块..."
modprobe -r v4l2loopback 2>/dev/null || true
modprobe v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1

# 4. 配置开机自启动模块
echo "[3/3] 配置开机自动加载模块..."
if [ -d "/etc/modules-load.d" ]; then
  echo "v4l2loopback" > /etc/modules-load.d/virtualcam.conf
  cat << 'EOF' > /etc/modprobe.d/virtualcam.conf
options v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1
EOF
  echo "✅ 已写入 /etc/modules-load.d/virtualcam.conf"
elif [ -f "/etc/modules" ]; then
  if ! grep -q "v4l2loopback" /etc/modules; then
    echo "v4l2loopback" >> /etc/modules
  fi
fi

echo ""
echo "=== 配置完成! ==="
echo "虚拟设备已创建: /dev/video10"
v4l2-ctl --list-devices 2>/dev/null || ls -l /dev/video*
