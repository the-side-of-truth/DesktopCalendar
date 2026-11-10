# -*- coding: utf-8 -*-
"""日单元格：左上角日期+农历/节气，下方为工作事件列表"""
import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget

from app.core.database import (STATUS_TODO, STATUS_DOING, STATUS_DONE,
                               STATUS_OVERDUE)
from app.core.lunar_utils import cell_lunar_text

STATUS_COLORS = {
    STATUS_TODO: "#f5f5f5",
    STATUS_DOING: "#7fd4ff",
    STATUS_DONE: "#7be495",
    STATUS_OVERDUE: "#ff8a80",
}


class DayCell(QFrame):
    def __init__(self, day, settings, parent=None):
        super().__init__(parent)
        self.day = day
        self.settings = settings
        self.events = []
        self._labels = []
        self._build()
        self.apply_style()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.num_label = QLabel()
        self.num_label.setStyleSheet("background:transparent; font-weight:bold;")
        self.lunar_label = QLabel()
        self.lunar_label.setStyleSheet("background:transparent;")
        self.lunar_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.num_label)
        top.addStretch(1)
        top.addWidget(self.lunar_label)
        lay.addLayout(top)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 1, 0, 0)
        self.body.setSpacing(0)
        lay.addLayout(self.body)
        lay.addStretch(1)

    def apply_style(self):
        s = self.settings
        bg = QColor(s.get("bg_color"))
        alpha = s.get("cell_opacity") / 100.0
        today = self.day == datetime.date.today()
        border = "2px solid %s" % s.get("today_border_color") if today \
            else "1px solid rgba(255,255,255,60)"
        self.setStyleSheet(
            "DayCell { background-color: rgba(%d,%d,%d,%d); border: %s;"
            " border-radius: 6px; }" % (
                bg.red(), bg.green(), bg.blue(), int(alpha * 255), border))
        fs = s.get("cell_font_size")
        self.num_label.setStyleSheet(
            "background:transparent; font-weight:bold; color:#ffffff; font-size:%dpt;" % fs)
        self.lunar_label.setStyleSheet(
            "background:transparent; color:#e8e8e8; font-size:%dpt;" % max(6, fs - 1))
        if self.day.day == 1:
            self.num_label.setText("%d月%d日" % (self.day.month, self.day.day))
        else:
            self.num_label.setText(str(self.day.day))
        self.lunar_label.setText(cell_lunar_text(self.day))
        self._rebuild_lines()

    def set_events(self, events):
        """events: [dict(content, status)]"""
        self.events = events
        self._rebuild_lines()

    def _clear_lines(self):
        for lb in self._labels:
            lb.hide()
            lb.deleteLater()
        self._labels = []

    def _rebuild_lines(self):
        if not hasattr(self, "body"):
            return
        self._clear_lines()
        fs = self.settings.get("cell_font_size")
        prev_bell = None
        for i, ev in enumerate(self._visible_slice()):
            bell = bool(ev.get("bell"))
            if prev_bell and not bell:
                # 提醒组与普通组之间的分隔线
                sep = QWidget()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: rgba(255,255,255,130);")
                self.body.addWidget(sep)
                self._labels.append(sep)
            prev_bell = bell
            lb = QLabel()
            color = STATUS_COLORS.get(ev.get("status"), "#f5f5f5")
            strike = "text-decoration: line-through;" \
                if ev.get("status") == STATUS_DONE else ""
            lb.setStyleSheet("background:transparent; color:%s; font-size:%dpt; %s"
                             % (color, fs, strike))
            lb.setText("%s%d. %s" % ("🔔" if bell else "",
                                     i + 1, ev.get("content", "")))
            lb.setWordWrap(False)
            self.body.addWidget(lb)
            self._labels.append(lb)
        self._last_max_lines = self._max_lines()

    def _visible_slice(self):
        """按单元格可用高度裁剪可见行数，超出以 +n 提示"""
        max_lines = self._max_lines()
        if len(self.events) <= max_lines:
            return self.events
        cut = max(1, max_lines - 1)
        shown = self.events[:cut]
        rest = len(self.events) - cut
        shown = list(shown) + [{"content": "…… 还有%d条" % rest, "status": STATUS_TODO}]
        return shown

    def _max_lines(self):
        line_h = self.fontMetrics().lineSpacing() + 1
        header_h = self.num_label.sizeHint().height() + 6
        avail = self.height() - header_h - 6
        return max(1, avail // max(1, line_h))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 仅在可用行数变化时重建，避免拖动/缩放时每帧增删控件造成跳动
        max_lines = self._max_lines()
        if max_lines != getattr(self, "_last_max_lines", None):
            self._rebuild_lines()
