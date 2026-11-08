#!/bin/bash
# 将 dist/DesktopCalendar 打包为 Debian 安装包（.deb）
# 用法：先 bash build_linux.sh 生成二进制，再 bash build_deb.sh
#       VERSION=1.2.0 bash build_deb.sh   # 自定义版本号
# 安装：sudo dpkg -i dist/desktopcalendar_*.deb
#       缺少依赖时：sudo apt-get -f install
# 卸载：sudo apt-get remove desktopcalendar
set -e

APP=DesktopCalendar
PKG=desktopcalendar
VERSION=${VERSION:-1.0.0}
ARCH=$(dpkg --print-architecture)
BIN=dist/DesktopCalendar

if [ ! -f "$BIN" ]; then
    echo "未找到 $BIN，请先执行：bash build_linux.sh"
    exit 1
fi

ROOT=build/deb/${PKG}_${VERSION}_${ARCH}
rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" \
         "$ROOT/opt/$PKG" \
         "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/doc/$PKG"

# 主程序放到 /opt，权限 755（安装后即可直接运行，无需 chmod）
cp "$BIN" "$ROOT/opt/$PKG/$APP"
chmod 755 "$ROOT/opt/$PKG/$APP"

# 命令行入口
printf '%s\n' '#!/bin/sh' "exec /opt/$PKG/$APP \"\$@\"" > "$ROOT/usr/bin/$PKG"
chmod 755 "$ROOT/usr/bin/$PKG"

# 桌面菜单项（应用列表里可直接点击启动）
cat > "$ROOT/usr/share/applications/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=桌面日历
Comment=桌面日历与待办提醒
Exec=/opt/$PKG/$APP
Terminal=false
Categories=Utility;Calendar;
StartupNotify=false
EOF

# 版权/说明文件
cat > "$ROOT/usr/share/doc/$PKG/README.md" <<'EOF'
桌面日历（DesktopCalendar）

启动方式：
  1) 在应用菜单中搜索“桌面日历”；
  2) 或在终端执行 desktopcalendar。

数据位置：~/.local/share/DesktopCalendar/DesktopCalendar/
  calendar.db    事件与重复规则
  settings.json  界面设置
卸载：sudo apt-get remove desktopcalendar
EOF

SIZE=$(du -sk "$ROOT" | cut -f1)

# 依赖：PyQt5 运行所需系统库（不含 Python，二进制已自带解释器）
cat > "$ROOT/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Depends: libgl1, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0,
 libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0,
 libxcb-xkb1, libxcb-xinerama0, libdbus-1-3, fontconfig
Maintainer: DesktopCalendar <noreply@example.com>
Description: 桌面日历与待办提醒
 无边框半透明桌面日历，支持农历节气、重复事件、提醒、
 搜索与导入导出，数据全部保存在本机。
EOF

# 生成 deb（--root-owner-group 保证文件属主为 root）
mkdir -p dist
DEB="dist/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$ROOT" "$DEB"

echo ""
echo "============================================"
echo "打包完成：$DEB"
echo "安装：sudo dpkg -i $DEB"
echo "      （若提示缺少依赖，执行 sudo apt-get -f install）"
echo "============================================"
