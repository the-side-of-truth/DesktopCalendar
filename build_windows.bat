@echo off
REM 在 Windows 上打包桌面日历（生成 dist\DesktopCalendar.exe 单文件）
REM 使用前先把下面的 PYTHON 改成目标环境的 python.exe
set PYTHON=E:\ProgramFile\MiniConda\envs\calendar\python.exe

"%PYTHON%" -m pip install -r requirements.txt
"%PYTHON%" -m PyInstaller --clean --noconfirm DesktopCalendar.spec

echo.
echo ============================================
echo 打包完成：dist\DesktopCalendar.exe
echo 直接把该 exe 拷贝到其他 Windows 设备即可运行
echo ============================================
pause
