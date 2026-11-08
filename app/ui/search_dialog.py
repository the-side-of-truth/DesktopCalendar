# -*- coding: utf-8 -*-
"""历史搜索窗口"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QLineEdit, QTableWidget, QVBoxLayout,
                             QTableWidgetItem, QLabel, QHBoxLayout,
                             QAbstractItemView, QHeaderView)

from app.core.database import event_status


class SearchDialog(QDialog):
    jumpTo = pyqtSignal(str)   # 日期字符串 yyyy-MM-dd

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("历史搜索")
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键字搜索每个日单元格中的工作事件")
        self.input.textChanged.connect(self.do_search)
        row.addWidget(QLabel("关键字:"))
        row.addWidget(self.input, 1)
        lay.addLayout(row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["日期", "事件内容", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double)
        lay.addWidget(self.table, 1)

        self.empty_label = QLabel("无相关记录")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        lay.addWidget(self.empty_label)
        self.input.setFocus()

    def do_search(self, text):
        text = text.strip()
        self.table.setRowCount(0)
        if not text:
            self.empty_label.setVisible(False)
            self.table.setVisible(True)
            return
        rows = []
        for ev in self.db.search_events(text):
            rows.append((ev["event_date"], ev["content"],
                         event_status(ev), ev["event_date"]))
        for rule in self.db.search_repeats(text):
            rows.append((rule["start_date"], "↻ " + rule["name"],
                         "重复事件", rule["start_date"]))
        rows.sort(key=lambda r: r[0], reverse=True)
        for r, (d, content, status, jump) in enumerate(rows):
            self.table.insertRow(r)
            item0 = QTableWidgetItem(d)
            item0.setData(Qt.UserRole, jump)
            self.table.setItem(r, 0, item0)
            self.table.setItem(r, 1, QTableWidgetItem(content))
            self.table.setItem(r, 2, QTableWidgetItem(status))
        has = bool(rows)
        self.table.setVisible(has)
        self.empty_label.setVisible(not has)

    def _on_double(self, index):
        item = self.table.item(index.row(), 0)
        if item:
            self.jumpTo.emit(item.data(Qt.UserRole))
            self.accept()
