#!/usr/bin/env bash
# VirtualCam Companion - macOS 驱动检测与配置助手
set -e

echo "=== VirtualCam Companion - macOS 环境检测 ==="

# 1. 检查是否安装 OBS Studio
OBS_APP="/Applications/OBS.app"
if [ -d "$OBS_APP" ]; then
  echo "✅ 已检测到 OBS Studio 安装于: $OBS_APP"
else
  echo "⚠️ 未在 /Applications 找到 OBS Studio"
  if command -v brew &> /dev/null; then
    echo "💡 检测到 Homebrew，可通过以下命令一键安装:"
    echo "   brew install --cask obs"
  else
    echo "💡 请前往 OBS 官方下载安装 OBS Studio 30+:"
    echo "   https://obsproject.com"
  fi
fi

# 2. 检查系统虚拟相机状态
echo ""
echo "=== 一次性激活步骤 ==="
echo "1. 打开 OBS Studio"
echo "2. 点击右下角的『启动虚拟摄像机』，然后点击『停止虚拟摄像机』"
echo "   (如果在 macOS 13+ 提示系统扩展被阻止，请打开『系统设置 -> 隐私与安全性』允许)"
echo "3. 启动 VirtualCam Companion 即可正常推流！"
