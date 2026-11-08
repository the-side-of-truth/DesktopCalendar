# 桌面日历（DesktopCalendar）

一个基于 PyQt5 的桌面日历/待办小工具：无边框半透明窗口贴在桌面上，按日展示待办事件，
支持农历、节气、重复事件、提醒、搜索、导入导出。数据全部保存在本机，不联网。

## 主要功能

- **日视图日历**：顶部显示年月（当天所在页额外显示完整日期、星期、农历、节气），
  ◀ ▶ 翻页；左侧周号栏；星期表头起始星期可配置。
- **日单元格待办**：双击单元格打开编辑面板，逐条录入事件，回车自动新增一条。
  - 序号 + 内容 + 状态颜色（未开始 / 进行中 / 已完成 / 超期未完成），已完成显示删除线。
  - 设置提醒的事件**排在前面、序号前带 🔔**，并与未设置提醒的事件用分隔线分开展示。
- **单元格编辑面板**：新增事件 / 删除事件 / 确认完成 / 重复事件设置 / 提醒设置 / 保存。
  - 删除为**延迟生效**：点删除只是从面板移除，点“保存”才写库；关闭时选“否”则改动全部丢弃。
- **重复事件**：每天 / 每周 / 每月 / 每年 / 自定义周期，可设置重复限制（结束日期、重复次数）。
  - **单日编辑**：在某天的单元格里直接改文字，只覆盖当天。
  - **单日删除**：单元格里删除或清空文字，只删当天，其他日期不受影响。
  - **全量删除**：在“重复事件设置”里删除任务，规则及所有派生事件一并删除。
- **提醒**：可设提醒时间（最多提前 3 天），当天内可按 N 分钟/N 小时重复提醒并限次数；
  重复事件的提醒在重复规则里统一配置。
- **总设置菜单**（☰）：隐藏日历、调整位置和大小、切换色调、历史搜索、导出、导入、
  选择日期、设置、功能介绍、退出。
- **其他**：单实例运行（重复双击只会唤起已运行的窗口）、跨月周自动扩展行、未完成事件可自动顺延。

## 运行环境

- Python 3.9+
- 依赖见 `requirements.txt`：PyQt5、lunarcalendar、openpyxl、pyinstaller

## 源码运行

```bash
python -m pip install -r requirements.txt
python main.py
```

## 打包

### Windows

在项目根目录执行（或直接双击 `build_windows.bat`，先把里面的 `PYTHON` 改成你的解释器路径）：

```bat
build_windows.bat
```

产物：`dist\DesktopCalendar.exe`（单文件，约 40MB）。

### Linux（Ubuntu / 麒麟 / 统信）

PyInstaller **不能跨平台、不能跨 CPU 架构**打包，必须在与目标设备相同架构的 Linux 机器上执行：

```bash
pip install -r requirements.txt
bash build_linux.sh
```

产物：`dist/DesktopCalendar`（单文件）。

### Linux 安装包（.deb）

在上述产物基础上，生成 Debian 安装包（Ubuntu / 麒麟 / 统信 / 深度均可用）：

```bash
bash build_deb.sh                 # 版本号默认 1.0.0
VERSION=1.2.0 bash build_deb.sh   # 自定义版本号
```

产物：`dist/desktopcalendar_<版本>_<架构>.deb`

安装与卸载：

```bash
sudo dpkg -i dist/desktopcalendar_1.0.0_amd64.deb
sudo apt-get -f install        # 若提示缺少依赖
sudo apt-get remove desktopcalendar   # 卸载
```

装好后可直接在应用菜单搜索“桌面日历”，或终端执行 `desktopcalendar`；
文件权限由包内元数据（755）决定，**无需再 chmod**。注意 `dpkg` 安装本身需要 root。

## 分发到其他设备

- **Windows**：直接把 `dist\DesktopCalendar.exe` 拷贝过去双击运行，目标机不需要安装 Python 或任何依赖。
- **Linux**：拷贝 `dist/DesktopCalendar`，`chmod +x DesktopCalendar` 后运行；
  注意 x86 架构打的包不能用于 ARM 版系统，需在对应架构上重新打包。
- 每台设备的数据各自独立；迁移数据请用菜单中的 **导出 → CalendarTask数据库**，
  在目标设备用 **导入** 还原。

## 数据存储位置

程序按 Qt 的应用数据目录规则存放数据（`QStandardPaths.AppDataLocation`），文件名固定：

| 文件 | 说明 |
| --- | --- |
| `calendar.db` | SQLite 数据库：普通事件、重复事件规则、完成状态、提醒配置 |
| `settings.json` | 界面设置：主题/背景色、字体大小、起始星期、休息日、窗口位置尺寸等 |

具体路径：

- **Windows**：`C:\Users\<用户名>\AppData\Roaming\DesktopCalendar\DesktopCalendar\`
  （可直接在资源管理器地址栏输入 `%APPDATA%\DesktopCalendar\DesktopCalendar` 打开）
- **Linux**：`~/.local/share/DesktopCalendar/DesktopCalendar/`

> 注意：路径取决于打包时设置的应用名/组织名（均为 `DesktopCalendar`），与 exe 放在哪个目录无关。
> 想换电脑使用，拷贝 `calendar.db` 和 `settings.json` 到目标机同名目录即可，或直接用菜单里的导入导出。

## 项目结构

```
DesktopCalendar/
├── main.py                  # 入口：单实例控制、创建主窗口、启动提醒服务
├── app/
│   ├── core/
│   │   ├── database.py      # SQLite 读写（事件、重复规则、单日覆盖/删除、旧库自动迁移）
│   │   ├── settings.py      # JSON 设置读写 + 数据目录定位
│   │   └── lunar_utils.py   # 农历、节气、干支等文字
│   └── ui/
│       ├── main_window.py   # 主窗口：布局、翻页、菜单、事件展示分组
│       ├── day_cell.py      # 单个日单元格（日期、农历、事件列表、铃铛分组）
│       ├── cell_editor.py   # 单元格编辑面板
│       ├── repeat_dialog.py # 重复事件设置
│       ├── reminder_dialog.py # 提醒设置
│       ├── reminder_service.py # 定时检查与提醒弹窗
│       ├── settings_dialog.py  # 设置窗口（日历/单元格/高级）
│       ├── transfer_dialog.py  # 导入导出（txt / xlsx / db）
│       └── search_dialog.py    # 历史搜索、日期选择
├── help.html                # “功能介绍”打开的本地帮助页
├── DesktopCalendar.spec     # PyInstaller 打包配置
├── build_windows.bat        # Windows 一键打包
├── build_linux.sh           # Linux 一键打包
├── build_deb.sh             # 将 Linux 产物打包为 .deb 安装包
└── requirements.txt
```

## 常见问题

- **点“隐藏日历”后程序还在运行？** 是设计如此，提醒继续生效。再双击程序图标会唤起窗口；
  彻底退出请用菜单里的“退出”。
- **误删了事件？** 编辑面板的删除在点“保存”前不写库，关闭时选“否”即可放弃；
  若是重复事件误删单日，重新编辑该规则或导入备份即可恢复。
- **启动没反应？** 程序是单实例的，若已有一个实例在后台运行，双击只会让已有窗口显示出来。
