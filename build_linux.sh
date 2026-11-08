#!/bin/bash
# 在 Linux(Ubuntu/麒麟/统信) 上打包桌面日历（生成 dist/DesktopCalendar 单文件）
# 注意：PyInstaller 不能跨平台/跨架构打包，必须在目标 CPU 架构的机器上执行
set -e

PYTHON=${PYTHON:-python3}

$PYTHON -m pip install -r requirements.txt
$PYTHON -m PyInstaller --clean --noconfirm DesktopCalendar.spec

echo ""
echo "============================================"
echo "打包完成：dist/DesktopCalendar"
echo "拷贝到其他同架构 Linux 设备，chmod +x 后即可运行"
echo "============================================"
