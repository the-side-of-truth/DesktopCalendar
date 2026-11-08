# -*- coding: utf-8 -*-
"""设置窗口：日历 / 单元格 / 高级 三页 + 恢复默认设置"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QDialog, QListWidget, QStackedWidget, QWidget,
                             QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
                             QPushButton, QCheckBox, QLabel, QMessageBox,
                             QGridLayout, QDialogButtonBox)

# Word 常用字号
FONT_SIZES = [("初号", 42), ("小初", 36), ("一号", 26), ("小一", 24),
              ("二号", 22), ("小二", 18), ("三号", 16), ("小三", 15),
              ("四号", 14), ("小四", 12), ("五号", 10.5), ("小五", 9),
              ("六号", 7.5), ("小六", 6.5)]

PALETTE = ["#2b6cb0", "#3182ce", "#38a169", "#d69e2e", "#dd6b20",
           "#e53e3e", "#805ad5", "#319795", "#16233b", "#2d3748",
           "#4a5568", "#718096"]

WEEK_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期天"]


class ColorGridDialog(QDialog):
    """方格选色小弹窗"""
    def __init__(self, parent, current):
        super().__init__(parent)
        self.setWindowTitle("选择颜色")
        self.color = current
        grid = QGridLayout(self)
        for i, c in enumerate(PALETTE):
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setStyleSheet("background:%s; border:2px solid %s; border-radius:4px;"
                              % (c, "#ffffff" if c == current else "#666666"))
            btn.clicked.connect(lambda _=False, col=c: self._pick(col))
            grid.addWidget(btn, i // 4, i % 4)

    def _pick(self, color):
        self.color = color
        self.accept()


class SettingsDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumSize(560, 420)
        lay = QVBoxLayout(self)
        body = QHBoxLayout()
        self.sidebar = QListWidget()
        self.sidebar.addItems(["日历", "单元格", "高级"])
        self.sidebar.setFixedWidth(110)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_calendar())
        self.stack.addWidget(self._page_cell())
        self.stack.addWidget(self._page_advanced())
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)
        lay.addLayout(body, 1)

        bottom = QHBoxLayout()
        btn_reset = QPushButton("恢复默认设置")
        btn_reset.clicked.connect(self.reset_defaults)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        bottom.addStretch(1)
        bottom.addWidget(btn_reset)
        bottom.addWidget(btn_close)
        lay.addLayout(bottom)

    # ---------------- 日历页 ----------------
    def _page_calendar(self):
        s = self.settings
        w = QWidget()
        form = QFormLayout(w)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["浮动的月份", "完整的月份"])
        self.mode_combo.setCurrentIndex(0 if s.get("display_mode") == "floating" else 1)
        self.mode_combo.currentIndexChanged.connect(self._apply)
        form.addRow("显示:", self.mode_combo)

        self.rows_combo = QComboBox()
        self.rows_combo.addItems([str(i) for i in range(1, 11)])
        self.rows_combo.setCurrentIndex(s.get("max_rows") - 1)
        self.rows_combo.currentIndexChanged.connect(self._on_rows_changed)
        form.addRow("最大行数:", self.rows_combo)

        self.past_combo = QComboBox()
        self._fill_past()
        self.past_combo.currentIndexChanged.connect(self._apply)
        form.addRow("已过星期数:", self.past_combo)

        self.bg_btn = QPushButton()
        self._paint_btn(self.bg_btn, s.get("bg_color"))
        self.bg_btn.clicked.connect(lambda: self._pick_color(self.bg_btn, "bg_color"))
        form.addRow("日历背景颜色:", self.bg_btn)

        self.title_font_combo = QComboBox()
        for name, size in FONT_SIZES:
            self.title_font_combo.addItem(name, size)
        self._select_font(self.title_font_combo, s.get("title_font_size"))
        self.title_font_combo.currentIndexChanged.connect(self._apply)
        form.addRow("日历字体大小:", self.title_font_combo)

        form.addRow(QLabel("（颜色随深浅色调切换，此处即“切换色调”的底层设置）"))
        return w

    # ---------------- 单元格页 ----------------
    def _page_cell(self):
        s = self.settings
        w = QWidget()
        form = QFormLayout(w)

        self.opacity_combo = QComboBox()
        self.opacity_combo.addItems([str(i) for i in range(0, 101, 10)])
        self.opacity_combo.setCurrentIndex(s.get("cell_opacity") // 10)
        self.opacity_combo.currentIndexChanged.connect(self._apply)
        form.addRow("透明度:", self.opacity_combo)

        self.gap_combo = QComboBox()
        self.gap_combo.addItems([str(i) for i in range(0, 11)])
        self.gap_combo.setCurrentIndex(s.get("cell_gap"))
        self.gap_combo.currentIndexChanged.connect(self._apply)
        form.addRow("单元格间隙:", self.gap_combo)

        self.today_btn = QPushButton()
        self._paint_btn(self.today_btn, s.get("today_border_color"))
        self.today_btn.clicked.connect(
            lambda: self._pick_color(self.today_btn, "today_border_color"))
        form.addRow("今日边框颜色:", self.today_btn)

        self.cell_font_combo = QComboBox()
        for name, size in FONT_SIZES:
            self.cell_font_combo.addItem(name, size)
        self._select_font(self.cell_font_combo, s.get("cell_font_size"))
        self.cell_font_combo.currentIndexChanged.connect(self._apply)
        form.addRow("字体大小:", self.cell_font_combo)

        self.ck_append = QCheckBox("编辑完成后自动排到末尾")
        self.ck_append.setChecked(s.get("auto_append_end"))
        self.ck_append.toggled.connect(self._apply)
        form.addRow(self.ck_append)

        self.ck_postpone = QCheckBox("未完成一周内自动顺延")
        self.ck_postpone.setChecked(s.get("auto_postpone"))
        self.ck_postpone.toggled.connect(self._apply)
        form.addRow(self.ck_postpone)
        return w

    # ---------------- 高级页 ----------------
    def _page_advanced(self):
        s = self.settings
        w = QWidget()
        form = QFormLayout(w)

        self.weekstart_combo = QComboBox()
        self.weekstart_combo.addItems(WEEK_NAMES)
        self.weekstart_combo.setCurrentIndex(s.get("week_start"))
        self.weekstart_combo.currentIndexChanged.connect(self._apply)
        form.addRow("开始星期:", self.weekstart_combo)

        row = QHBoxLayout()
        self.rest_checks = []
        for i, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            ck = QCheckBox(name)
            ck.setChecked(i in (s.get("rest_days") or []))
            ck.toggled.connect(self._apply)
            self.rest_checks.append(ck)
            row.addWidget(ck)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow("每周休息日:", holder)
        return w

    # ---------------- 工具 ----------------
    def _fill_past(self):
        max_rows = self.settings.get("max_rows")
        self.past_combo.blockSignals(True)
        self.past_combo.clear()
        self.past_combo.addItems([str(i) for i in range(0, max_rows)])
        past = min(self.settings.get("past_weeks"), max_rows - 1)
        self.past_combo.setCurrentIndex(past)
        self.past_combo.blockSignals(False)

    def _on_rows_changed(self, _i):
        self.settings.set("max_rows", self.rows_combo.currentIndex() + 1)
        self._fill_past()
        self.settings.set("past_weeks", self.past_combo.currentIndex())
        self.changed.emit()

    def _select_font(self, combo, size):
        for i in range(combo.count()):
            if abs(float(combo.itemData(i)) - float(size)) < 0.01:
                combo.setCurrentIndex(i)
                return

    def _paint_btn(self, btn, color):
        btn.setFixedSize(48, 26)
        btn.setStyleSheet("background:%s; border:1px solid #888; border-radius:4px;"
                          % color)

    def _pick_color(self, btn, key):
        dlg = ColorGridDialog(self, self.settings.get(key))
        if dlg.exec_() == QDialog.Accepted:
            self.settings.set(key, dlg.color)
            # 背景颜色变化视为对应色调切换
            if key == "bg_color":
                self.settings.set("theme", "custom")
            self._paint_btn(btn, dlg.color)
            self.changed.emit()

    def _apply(self, *_):
        s = self.settings
        s.set("display_mode",
              "floating" if self.mode_combo.currentIndex() == 0 else "full_month")
        s.set("past_weeks", self.past_combo.currentIndex())
        s.set("title_font_size",
              float(self.title_font_combo.currentData()))
        s.set("cell_opacity", self.opacity_combo.currentIndex() * 10)
        s.set("cell_gap", self.gap_combo.currentIndex())
        s.set("cell_font_size", float(self.cell_font_combo.currentData()))
        s.set("auto_append_end", self.ck_append.isChecked())
        s.set("auto_postpone", self.ck_postpone.isChecked())
        s.set("week_start", self.weekstart_combo.currentIndex())
        s.set("rest_days", [i for i, ck in enumerate(self.rest_checks)
                            if ck.isChecked()])
        self.changed.emit()

    def reset_defaults(self):
        r = QMessageBox.question(self, "恢复默认设置", "确定恢复全部默认设置？",
                                 QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        self.settings.reset()
        # 重新加载界面值
        self.mode_combo.setCurrentIndex(0)
        self.rows_combo.setCurrentIndex(self.settings.get("max_rows") - 1)
        self._fill_past()
        self._paint_btn(self.bg_btn, self.settings.get("bg_color"))
        self._paint_btn(self.today_btn, self.settings.get("today_border_color"))
        self._select_font(self.title_font_combo, self.settings.get("title_font_size"))
        self._select_font(self.cell_font_combo, self.settings.get("cell_font_size"))
        self.opacity_combo.setCurrentIndex(self.settings.get("cell_opacity") // 10)
        self.gap_combo.setCurrentIndex(self.settings.get("cell_gap"))
        self.ck_append.setChecked(self.settings.get("auto_append_end"))
        self.ck_postpone.setChecked(self.settings.get("auto_postpone"))
        self.weekstart_combo.setCurrentIndex(self.settings.get("week_start"))
        for i, ck in enumerate(self.rest_checks):
            ck.setChecked(i in (self.settings.get("rest_days") or []))
        self.changed.emit()
