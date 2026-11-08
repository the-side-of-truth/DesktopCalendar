# -*- coding: utf-8 -*-
"""选择日期：支持年/月/日多级选择的日历弹窗"""
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget


class DatePickerDialog(QDialog):
    def __init__(self, parent, day=None):
        super().__init__(parent)
        self.setWindowTitle("选择日期")
        lay = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        # 日历自带月/年导航，支持多级选择
        if day:
            self.calendar.setSelectedDate(
                QDate(day.year, day.month, day.day))
        self.calendar.activated.connect(lambda _d: self.accept())
        self.calendar.clicked.connect(lambda _d: self.accept())
        lay.addWidget(self.calendar)
        self.selected = None

    def accept(self):
        d = self.calendar.selectedDate()
        self.selected = (d.year(), d.month(), d.day())
        super().accept()
