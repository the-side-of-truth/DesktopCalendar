# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（Windows / Linux 通用，需在目标系统上分别执行打包）

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('help.html', '.')],
    hiddenimports=['lunarcalendar', 'ephem', 'openpyxl'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5.QtWebEngine', 'PyQt5.QtWebEngineWidgets',
              'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtBluetooth',
              'PyQt5.QtMultimedia', 'PyQt5.QtSql'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DesktopCalendar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
