# -*- coding: utf-8 -*-
"""桌面日历主窗口：无边框透明、菜单栏、日展示栏、周号栏、日单元格展板"""
import datetime
import os
import sys
import webbrowser

from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QMenu, QApplication,
                             QMessageBox, QDesktopWidget)

from app.core.database import event_status, STATUS_DONE
from app.core.lunar_utils import (WEEKDAYS_FULL, week_start_of, week_number,
                                  title_text, month_text)
from app.core.recurrence import expand_repeat
from app.core.settings import THEME_COLORS
from app.ui.day_cell import DayCell
from app.ui.cell_editor import CellEditor
from app.ui.reminder_service import ReminderService
from app.ui.settings_dialog import SettingsDialog
from app.ui.search_dialog import SearchDialog
from app.ui.transfer_dialog import ExportDialog, ImportDialog
from app.ui.date_picker import DatePickerDialog

WEEK_COL_W = 34
EDGE = 8


def resource_path(name):
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.dirname(os.path.dirname(
                       os.path.abspath(__file__)))))
    return os.path.join(base, name)


class MainWindow(QWidget):
    def __init__(self, settings, db):
        super().__init__()
        self.settings = settings
        self.db = db
        self.page_offset = 0      # 浮动模式：以 max_rows 周为一页
        self.month_offset = 0     # 完整月份模式
        self.sub_page = 0         # 完整月份模式下的页内分块
        self.cells = {}           # date -> DayCell
        self.editor = None
        self._adjust = False
        self._orig_geo = None
        self._drag = None
        self._today = datetime.date.today()
        self._last_minute = None

        self.setWindowTitle("桌面日历")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window
                            | Qt.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(520, 260)
        self._build_ui()
        self._restore_geometry()

        self.reminders = ReminderService(db, settings)
        if settings.get("auto_postpone"):
            self.db.postpone_overdue(
                self._today, week_start_of(self._today,
                                           settings.get("week_start")))
        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(15000)

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(8, 6, 8, 8)
        self.root.setSpacing(4)

        # 顶部菜单栏
        self.menubar = QWidget()
        mb = QHBoxLayout(self.menubar)
        mb.setContentsMargins(4, 0, 4, 0)
        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        mb.addWidget(self.date_label)
        mb.addStretch(1)
        self.btn_prev = self._mk_btn("◀", "上一页", lambda: self.flip_page(-1))
        self.btn_next = self._mk_btn("▶", "下一页", lambda: self.flip_page(1))
        self.btn_menu = self._mk_btn("☰", "总设置", self.show_menu)
        mb.addWidget(self.btn_prev)
        mb.addWidget(self.btn_next)
        mb.addWidget(self.btn_menu)
        self.root.addWidget(self.menubar)

        # 调整模式栏（仅 ✓ / ✕）
        self.adjustbar = QWidget()
        ab = QHBoxLayout(self.adjustbar)
        ab.setContentsMargins(4, 0, 4, 0)
        tip = QLabel("拖动边缘缩放，拖动内部移动")
        tip.setObjectName("adjustTip")
        ab.addWidget(tip)
        ab.addStretch(1)
        btn_ok = self._mk_btn("✓", "保存更改", self.adjust_confirm)
        btn_no = self._mk_btn("✕", "取消更改", self.adjust_cancel)
        ab.addWidget(btn_ok)
        ab.addWidget(btn_no)
        self.adjustbar.setVisible(False)
        self.root.addWidget(self.adjustbar)

        # 日展示栏（星期表头）
        self.header = QWidget()
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_labels = []
        corner = QLabel()
        corner.setFixedWidth(WEEK_COL_W)
        self.header_layout.addWidget(corner)
        for _i in range(7):
            lb = QLabel()
            lb.setAlignment(Qt.AlignCenter)
            lb.setObjectName("weekHeader")
            self.header_layout.addWidget(lb, 1)
            self.header_labels.append(lb)
        self.root.addWidget(self.header)

        # 日单元格展板 + 周号栏（同一网格，0 列为周号）
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.root.addWidget(self.grid_widget, 1)
        self._apply_fonts()

    def _mk_btn(self, text, tip, slot):
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setFixedSize(30, 24)
        b.setObjectName("menuBtn")
        b.clicked.connect(slot)
        return b

    def _apply_fonts(self):
        fs = self.settings.get("title_font_size")
        self.setStyleSheet("""
            #dateLabel { color: #ffffff; font-size: %(fs)dpt; font-weight: bold; }
            #weekHeader { font-size: %(fs)dpt; font-weight: bold; }
            #weekNum { color: #ffffff; font-size: %(fs)dpt; }
            #adjustTip { color: #ffe08a; }
            #menuBtn {
                background: rgba(255,255,255,50); color: #ffffff;
                border: 1px solid rgba(255,255,255,90); border-radius: 4px;
                font-size: %(fs)dpt;
            }
            #menuBtn:hover { background: rgba(255,255,255,100); }
        """ % {"fs": int(fs)})
        self.grid.setSpacing(self.settings.get("cell_gap"))
        self.header_layout.setSpacing(self.settings.get("cell_gap"))

    def _restore_geometry(self):
        geo = self.settings.get("geometry")
        if geo:
            self.setGeometry(*geo)
        else:
            screen = QDesktopWidget().availableGeometry()
            w = min(1100, int(screen.width() * 0.8))
            h = max(300, int(screen.height() * 0.32))
            self.setGeometry((screen.width() - w) // 2, 30, w, h)

    # ---------------- 布局计算 ----------------
    def _visible_weeks(self):
        """返回 [(week_start_date, ...)]，按当前模式与页码"""
        s = self.settings
        ws = s.get("week_start")
        max_rows = s.get("max_rows")
        today = datetime.date.today()
        if s.get("display_mode") == "floating":
            cur = week_start_of(today, ws)
            first = cur + datetime.timedelta(
                weeks=self.page_offset * max_rows - s.get("past_weeks"))
            return [first + datetime.timedelta(weeks=i) for i in range(max_rows)]
        # 完整的月份
        month = self._shown_month()
        chunks = self._month_chunks(month)
        self.sub_page = max(0, min(self.sub_page, len(chunks) - 1))
        return chunks[self.sub_page]

    def _shown_month(self):
        today = datetime.date.today()
        total = (today.year * 12 + today.month - 1) + self.month_offset
        y, m = divmod(total, 12)
        return datetime.date(y, m + 1, 1)

    def _month_chunks(self, month):
        s = self.settings
        ws = s.get("week_start")
        if month.month == 12:
            nxt = datetime.date(month.year + 1, 1, 1)
        else:
            nxt = datetime.date(month.year, month.month + 1, 1)
        last = nxt - datetime.timedelta(days=1)
        first_ws = week_start_of(month, ws)
        weeks = []
        wk = first_ws
        while wk <= last:
            weeks.append(wk)
            wk += datetime.timedelta(weeks=1)
        max_rows = s.get("max_rows")
        return [weeks[i:i + max_rows] for i in range(0, len(weeks), max_rows)]

    def _build_rows(self, weeks):
        """把周拆成行：浮动模式下不同月份的日不在同一行"""
        s = self.settings
        rows = []
        if s.get("display_mode") == "floating":
            for wk in weeks:
                seg = None
                cur_key = None
                for i in range(7):
                    d = wk + datetime.timedelta(days=i)
                    key = (d.year, d.month)
                    if key != cur_key:
                        seg = {"week_key": wk, "cells": [None] * 7}
                        rows.append(seg)
                        cur_key = key
                    seg["cells"][i] = d
        else:
            month = self._shown_month()
            for wk in weeks:
                cells = []
                for i in range(7):
                    d = wk + datetime.timedelta(days=i)
                    cells.append(d if (d.year, d.month) ==
                                 (month.year, month.month) else None)
                rows.append({"week_key": wk, "cells": cells})
        return rows

    # ---------------- 刷新 ----------------
    def refresh(self):
        s = self.settings
        weeks = self._visible_weeks()
        rows = self._build_rows(weeks)
        ws = s.get("week_start")

        # 清空网格（先隐藏再延迟删除，避免控件短暂成为顶层窗口造成闪窗）
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()
        self.cells = {}

        # 表头（按开始星期旋转）
        rest = s.get("rest_days") or []
        for i in range(7):
            wd = (ws + i) % 7
            lb = self.header_labels[i]
            lb.setText(WEEKDAYS_FULL[wd])
            color = "#ffd27f" if wd in rest else "#ffffff"
            lb.setStyleSheet("color:%s; font-weight:bold; font-size:%dpt;"
                             % (color, int(s.get("title_font_size"))))

        # 可见日期范围，用于重复规则展开
        alld = [d for row in rows for d in row["cells"] if d]
        derived_map = {}
        if alld:
            lo, hi = min(alld), max(alld)
            for rule in self.db.all_repeats():
                try:
                    for d in expand_repeat(rule, lo, hi, ws):
                        derived_map.setdefault(d, []).append(rule)
                except Exception:
                    continue

        # 网格：第0列周号（跨行），1-7列日单元格
        r = 0
        while r < len(rows):
            row = rows[r]
            # 计算同一周的行跨度
            span = 1
            while r + span < len(rows) and \
                    rows[r + span]["week_key"] == row["week_key"]:
                span += 1
            wn = QLabel("第%d\n周" % week_number(row["week_key"], ws))
            wn.setObjectName("weekNum")
            wn.setAlignment(Qt.AlignCenter)
            wn.setFixedWidth(WEEK_COL_W)
            self.grid.addWidget(wn, r, 0, span, 1)
            r += span

        for ri, row in enumerate(rows):
            for ci, d in enumerate(row["cells"]):
                if d is None:
                    ph = QWidget()
                    ph.setStyleSheet("background:transparent;")
                    self.grid.addWidget(ph, ri, ci + 1)
                else:
                    cell = DayCell(d, self.settings)
                    cell.doubleClicked.connect(self.open_editor)
                    cell.set_events(self._events_for_display(d, derived_map))
                    self.grid.addWidget(cell, ri, ci + 1)
                    self.cells[d] = cell
        for ri in range(len(rows)):
            self.grid.setRowStretch(ri, 1)
        for ci in range(1, 8):
            self.grid.setColumnStretch(ci, 1)

        # 顶栏日期
        if self._today in self.cells:
            self.date_label.setText(title_text(self._today))
        else:
            if s.get("display_mode") == "floating":
                base = alld[0] if alld else self._today
            else:
                base = self._shown_month()
            self.date_label.setText(month_text(base))

        for cell in self.cells.values():
            cell.apply_style()
        self._apply_fonts()
        if self.editor:
            self.editor.raise_()
        self.update()

    def _events_for_display(self, d, derived_map=None):
        reminded, normal = [], []
        now = datetime.datetime.now()
        for ev in self.db.events_of(d.isoformat()):
            item = {"content": ev["content"], "status": event_status(ev, now)}
            (reminded if ev.get("remind_advance") is not None
             else normal).append(item)
        for dev in self.repeat_events_of(d, derived_map):
            item = {"content": dev["content"], "status": dev["status"]}
            (reminded if dev.get("remind") else normal).append(item)
        # 设置提醒的事件带铃铛并排在前面，与未设置提醒的分开展示
        for x in reminded:
            x["bell"] = True
        return reminded + normal

    def repeat_events_of(self, day, derived_map=None):
        """某天由重复规则派生的事件"""
        out = []
        now = datetime.datetime.now()
        if derived_map is None:
            rules = self.db.all_repeats()
            derived_map = {}
            for rule in rules:
                try:
                    for d in expand_repeat(rule, day, day,
                                           self.settings.get("week_start")):
                        derived_map.setdefault(d, []).append(rule)
                except Exception:
                    continue
        for rule in derived_map.get(day, []):
            ds = day.isoformat()
            if ds in (rule.get("deleted_dates") or []):
                continue
            overrides = rule.get("overrides") or {}
            content = overrides.get(ds, rule["name"])
            done = ds in (rule.get("completed_dates") or [])
            ev = {"event_date": ds,
                  "start_time": rule.get("start_time"),
                  "end_time": rule.get("end_time"),
                  "completed": done}
            out.append({"rule_id": rule["id"], "content": content,
                        "orig_content": rule["name"],
                        "remind": bool(rule.get("remind_enabled")
                                       and rule.get("remind_time")),
                        "completed": done, "status": event_status(ev, now)})
        return out

    # ---------------- 翻页 ----------------
    def flip_page(self, delta):
        self.close_editor()
        s = self.settings
        if s.get("display_mode") == "floating":
            self.page_offset += delta
        else:
            chunks = self._month_chunks(self._shown_month())
            nxt = self.sub_page + delta
            if nxt < 0:
                self.month_offset -= 1
                self.sub_page = len(self._month_chunks(self._shown_month())) - 1
            elif nxt >= len(chunks):
                self.month_offset += 1
                self.sub_page = 0
            else:
                self.sub_page = nxt
        self.refresh()

    def goto_date(self, d):
        """跳转到包含某天的一页"""
        s = self.settings
        today = datetime.date.today()
        if s.get("display_mode") == "floating":
            ws = s.get("week_start")
            diff = (week_start_of(d, ws) - week_start_of(today, ws)).days // 7
            self.page_offset = (diff + s.get("past_weeks")) // s.get("max_rows")
        else:
            self.month_offset = (d.year - today.year) * 12 + d.month - today.month
            month = self._shown_month()
            chunks = self._month_chunks(month)
            ws = s.get("week_start")
            target = week_start_of(d, ws)
            self.sub_page = 0
            for i, ch in enumerate(chunks):
                if target in ch:
                    self.sub_page = i
                    break
        self.refresh()

    # ---------------- 单元格编辑 ----------------
    def open_editor(self, day):
        self.close_editor()
        cell = self.cells.get(day)
        self.editor = CellEditor(self, day, self.db, self.settings)
        self.editor.saved.connect(self.refresh)
        self.editor.closed.connect(self._editor_closed)
        w = max(360, cell.width() if cell else 360)
        h = min(300, max(220, self.height() - 60))
        self.editor.resize(w, h)
        if cell:
            p = cell.mapTo(self, QPoint(0, 0))
            x = p.x()
            y = p.y() + cell.height() + 2
            if y + h > self.height():
                y = max(4, p.y() - h - 2)
            if x + w > self.width():
                x = self.width() - w - 4
            self.editor.move(max(4, x), max(4, y))
        else:
            self.editor.move((self.width() - w) // 2, (self.height() - h) // 2)
        self.editor.show()
        self.editor.raise_()
        self.editor.setFocus()

    def _editor_closed(self):
        self.editor = None
        self.refresh()

    def close_editor(self):
        if self.editor:
            self.editor.closed.disconnect()
            self.editor.close()
            self.editor = None

    # ---------------- 总设置菜单 ----------------
    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(25,42,70,245); color: #fff;"
            " border: 1px solid #6fb3ff; }"
            "QMenu::item:selected { background: #2b6cb0; }")
        acts = [
            ("隐藏日历", self.hide_calendar),
            ("调整位置和大小", self.enter_adjust),
            ("切换色调", self.toggle_theme),
            ("历史搜索", self.open_search),
            ("导出", self.open_export),
            ("导入", self.open_import),
            ("选择日期", self.open_date_picker),
            ("设置", self.open_settings),
            ("功能介绍", self.open_help),
            ("退出", QApplication.instance().quit),
        ]
        for text, slot in acts:
            menu.addAction(text, slot)
        menu.exec_(self.btn_menu.mapToGlobal(
            QPoint(0, self.btn_menu.height())))

    def hide_calendar(self):
        self.hide()

    def toggle_theme(self):
        cur = self.settings.get("theme")
        nxt = "dark" if cur == "light" else "light"
        self.settings.set("theme", nxt)
        self.settings.set("bg_color", THEME_COLORS[nxt])
        self.refresh()

    def open_search(self):
        dlg = SearchDialog(self, self.db)
        dlg.jumpTo.connect(self._jump_to)
        dlg.exec_()

    def _jump_to(self, date_str):
        try:
            d = datetime.date.fromisoformat(date_str)
        except ValueError:
            return
        self.goto_date(d)

    def open_export(self):
        ExportDialog(self, self.db).exec_()

    def open_import(self):
        dlg = ImportDialog(self, self.db)
        if dlg.exec_() == ImportDialog.Accepted and dlg.imported:
            self.refresh()

    def open_date_picker(self):
        dlg = DatePickerDialog(self, datetime.date.today())
        if dlg.exec_() == DatePickerDialog.Accepted and dlg.selected:
            d = datetime.date(*dlg.selected)
            self.goto_date(d)
            self.open_editor(d)

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.changed.connect(self._on_settings_changed)
        dlg.exec_()

    def _on_settings_changed(self):
        self.page_offset = 0
        self.sub_page = 0
        self.refresh()

    def open_help(self):
        path = resource_path("help.html")
        if os.path.exists(path):
            webbrowser.open("file:///" + path.replace("\\", "/"))
        else:
            QMessageBox.information(self, "功能介绍", "未找到帮助文件 help.html")

    # ---------------- 调整位置和大小 ----------------
    def enter_adjust(self):
        self.close_editor()
        self._adjust = True
        self._orig_geo = self.geometry()
        self.menubar.setVisible(False)
        self.adjustbar.setVisible(True)
        self.update()

    def _exit_adjust(self, save):
        if save:
            g = self.geometry()
            self.settings.set("geometry", [g.x(), g.y(), g.width(), g.height()])
        elif self._orig_geo:
            self.setGeometry(self._orig_geo)
        self._adjust = False
        self._drag = None
        self.setCursor(Qt.ArrowCursor)
        self.menubar.setVisible(True)
        self.adjustbar.setVisible(False)
        self.update()

    def adjust_confirm(self):
        self._exit_adjust(True)

    def adjust_cancel(self):
        self._exit_adjust(False)

    def _edges_at(self, pos):
        r = self.rect()
        edges = set()
        if pos.x() <= EDGE:
            edges.add("l")
        if pos.x() >= r.width() - EDGE:
            edges.add("r")
        if pos.y() <= EDGE:
            edges.add("t")
        if pos.y() >= r.height() - EDGE:
            edges.add("b")
        return edges

    def _cursor_for(self, edges):
        if edges in ({"t", "l"}, {"b", "r"}):
            return Qt.SizeFDiagCursor
        if edges in ({"t", "r"}, {"b", "l"}):
            return Qt.SizeBDiagCursor
        if edges & {"l", "r"}:
            return Qt.SizeHorCursor
        if edges & {"t", "b"}:
            return Qt.SizeVerCursor
        return Qt.SizeAllCursor

    def mousePressEvent(self, e):
        if self._adjust and e.button() == Qt.LeftButton:
            edges = self._edges_at(e.pos())
            self._drag = (edges, e.globalPos(), QRect(self.geometry()))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._adjust:
            if self._drag is None:
                self.setCursor(self._cursor_for(self._edges_at(e.pos())))
                return
            edges, start_pos, start_geo = self._drag
            delta = e.globalPos() - start_pos
            geo = QRect(start_geo)
            if not edges:  # 内部拖动 -> 移动
                geo.moveTopLeft(start_geo.topLeft() + delta)
            else:
                if "l" in edges:
                    geo.setLeft(min(start_geo.left() + delta.x(),
                                    start_geo.right() - self.minimumWidth()))
                if "r" in edges:
                    geo.setRight(max(start_geo.right() + delta.x(),
                                     start_geo.left() + self.minimumWidth()))
                if "t" in edges:
                    geo.setTop(min(start_geo.top() + delta.y(),
                                   start_geo.bottom() - self.minimumHeight()))
                if "b" in edges:
                    geo.setBottom(max(start_geo.bottom() + delta.y(),
                                      start_geo.top() + self.minimumHeight()))
            self.setGeometry(geo)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._adjust:
            self._drag = None
            e.accept()
            return
        super().mouseReleaseEvent(e)

    # ---------------- 绘制 ----------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(self.settings.get("bg_color"))
        bg.setAlpha(150)
        p.setBrush(bg)
        if self._adjust:
            pen = QPen(QColor("#ffffff"), 2, Qt.DashLine)
        else:
            pen = QPen(QColor(255, 255, 255, 70), 1)
        p.setPen(pen)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        p.end()

    # ---------------- 定时 ----------------
    def _tick(self):
        now = datetime.datetime.now()
        if now.date() != self._today:
            self._today = now.date()
            if self.settings.get("auto_postpone"):
                self.db.postpone_overdue(
                    self._today,
                    week_start_of(self._today, self.settings.get("week_start")))
            self.refresh()
        elif self._last_minute != now.minute:
            self.refresh()
        self._last_minute = now.minute
        self.reminders.check()

    # ---------------- 关闭 ----------------
    def closeEvent(self, e):
        g = self.geometry()
        self.settings.set("geometry", [g.x(), g.y(), g.width(), g.height()])
        super().closeEvent(e)
