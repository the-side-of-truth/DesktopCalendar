# -*- coding: utf-8 -*-
"""重复事件设置对话框"""
import json

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QComboBox,
                             QCheckBox, QSpinBox, QDateEdit, QVBoxLayout,
                             QHBoxLayout, QWidget, QMessageBox)

REPEAT_TYPES = [
    ("每天", "daily"), ("每周", "weekly"), ("每月", "monthly"), ("每年", "yearly"),
    ("自定义-日", "custom_day"), ("自定义-周", "custom_week"),
    ("自定义-月", "custom_month"), ("自定义-年", "custom_year"),
]
WEEK_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


class RepeatDialog(QDialog):
    def __init__(self, parent, db, settings, rule=None, day=None, default_name=""):
        super().__init__(parent)
        self.db = db
        self.rule = rule
        self.day = day
        self.created_rule_id = None
        self.setWindowTitle("重复事件设置")
        self.setMinimumWidth(430)
        self._build()
        self._load(default_name)

    def _build(self):
        lay = QVBoxLayout(self)

        # 第一行：事件名称
        row = QHBoxLayout()
        row.addWidget(QLabel("事件名称:"))
        self.name_edit = QLineEdit()
        row.addWidget(self.name_edit, 1)
        lay.addLayout(row)

        # 第二行：当天完成勾选框
        row = QHBoxLayout()
        self.ck_today_done = QCheckBox("将当天的重复事件标记为完成状态(不影响之后)")
        row.addWidget(self.ck_today_done)
        row.addStretch(1)
        lay.addLayout(row)

        # 第三行：重复周期
        row = QHBoxLayout()
        row.addWidget(QLabel("重复周期:"))
        self.type_combo = QComboBox()
        for text, _key in REPEAT_TYPES:
            self.type_combo.addItem(text)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        row.addWidget(self.type_combo)
        row.addStretch(1)
        lay.addLayout(row)

        # 自定义参数区
        self.param_widget = QWidget()
        self.param_layout = QHBoxLayout(self.param_widget)
        self.param_layout.setContentsMargins(20, 0, 0, 0)
        lay.addWidget(self.param_widget)
        self._build_param_widgets()

        # 第四行：重复限制
        row = QHBoxLayout()
        row.addWidget(QLabel("重复限制:"))
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["无限制", "结束日期", "重复次数"])
        self.limit_combo.currentIndexChanged.connect(self._on_limit_changed)
        row.addWidget(self.limit_combo)
        self.date_edit = QDateEdit(QDate.currentDate().addMonths(1))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setVisible(False)
        row.addWidget(self.date_edit)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10000)
        self.count_spin.setValue(10)
        self.count_spin.setSuffix(" 次")
        self.count_spin.setVisible(False)
        row.addWidget(self.count_spin)
        row.addStretch(1)
        lay.addLayout(row)

        # 第五行：提醒设置（派生的所有事件按该时间提醒）
        row = QHBoxLayout()
        self.ck_remind = QCheckBox("启用提醒")
        row.addWidget(self.ck_remind)
        row.addWidget(QLabel("提醒时间:"))
        self.hour_combo = QComboBox()
        self.hour_combo.addItems(["%02d" % h for h in range(24)])
        self.min_combo = QComboBox()
        self.min_combo.addItems(["%02d" % m for m in range(60)])
        row.addWidget(self.hour_combo)
        row.addWidget(QLabel("时"))
        row.addWidget(self.min_combo)
        row.addWidget(QLabel("分"))
        row.addStretch(1)
        lay.addLayout(row)

        # 底部按钮
        row = QHBoxLayout()
        self.btn_delete = QPushButton("删除任务")
        self.btn_delete.setStyleSheet("color:#c0392b;")
        self.btn_delete.clicked.connect(self.delete_rule)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)
        row.addWidget(self.btn_delete)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        lay.addLayout(row)

    def _build_param_widgets(self):
        # 自定义-日
        self.day_interval = QSpinBox()
        self.day_interval.setRange(1, 100)
        self.day_interval.setPrefix("每 ")
        self.day_interval.setSuffix(" 天")
        # 自定义-周
        self.week_interval = QSpinBox()
        self.week_interval.setRange(1, 100)
        self.week_interval.setPrefix("每 ")
        self.week_interval.setSuffix(" 周")
        self.weekday_checks = [QCheckBox(WEEK_NAMES[i]) for i in range(7)]
        # 自定义-月
        self.month_interval = QSpinBox()
        self.month_interval.setRange(1, 100)
        self.month_interval.setPrefix("每 ")
        self.month_interval.setSuffix(" 月")
        self.month_day = QSpinBox()
        self.month_day.setRange(1, 31)
        self.month_day.setPrefix("每月 ")
        self.month_day.setSuffix(" 日")
        # 自定义-年
        self.year_interval = QSpinBox()
        self.year_interval.setRange(1, 100)
        self.year_interval.setPrefix("每 ")
        self.year_interval.setSuffix(" 年")

    def _on_type_changed(self, idx):
        # 清空参数区
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().setVisible(False)
                item.widget().setParent(None)
        key = REPEAT_TYPES[idx][1]
        widgets = []
        if key == "custom_day":
            widgets = [self.day_interval]
        elif key == "custom_week":
            widgets = [self.week_interval] + self.weekday_checks
        elif key == "custom_month":
            widgets = [self.month_interval, self.month_day]
        elif key == "custom_year":
            widgets = [self.year_interval]
        for w in widgets:
            # 先加入布局再显示，避免控件短暂成为独立顶层窗口（闪窗）
            self.param_layout.addWidget(w)
            w.setVisible(True)
        self.param_layout.addStretch(1)
        self.param_widget.setVisible(bool(widgets))

    def _on_limit_changed(self, idx):
        self.date_edit.setVisible(idx == 1)
        self.count_spin.setVisible(idx == 2)

    def _load(self, default_name):
        r = self.rule
        if not r:
            self.name_edit.setText(default_name)
            self.btn_delete.setVisible(False)
            self._on_type_changed(0)
            return
        self.name_edit.setText(r["name"])
        keys = [k for _t, k in REPEAT_TYPES]
        idx = keys.index(r["repeat_type"]) if r["repeat_type"] in keys else 0
        self.type_combo.setCurrentIndex(idx)
        self._on_type_changed(idx)
        interval = int(r.get("interval") or 1)
        if r["repeat_type"] == "custom_day":
            self.day_interval.setValue(interval)
        elif r["repeat_type"] == "custom_week":
            self.week_interval.setValue(interval)
            wds = r.get("weekdays") or []
            for i, ck in enumerate(self.weekday_checks):
                ck.setChecked(i in wds)
        elif r["repeat_type"] == "custom_month":
            self.month_interval.setValue(interval)
            self.month_day.setValue(int(r.get("month_day") or 1))
        elif r["repeat_type"] == "custom_year":
            self.year_interval.setValue(interval)
        lt = r.get("limit_type") or "none"
        self.limit_combo.setCurrentIndex({"none": 0, "end_date": 1, "count": 2}.get(lt, 0))
        if r.get("limit_date"):
            self.date_edit.setDate(QDate.fromString(r["limit_date"], "yyyy-MM-dd"))
        if r.get("limit_count"):
            self.count_spin.setValue(int(r["limit_count"]))
        self._on_limit_changed(self.limit_combo.currentIndex())
        if r.get("remind_enabled"):
            self.ck_remind.setChecked(True)
            t = r.get("remind_time") or "09:00"
            self.hour_combo.setCurrentIndex(int(t[0:2]))
            self.min_combo.setCurrentIndex(int(t[3:5]))
        if self.day:
            dates = json.loads(r.get("completed_dates") or "[]")
            self.ck_today_done.setChecked(self.day.isoformat() in dates)

    def save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入事件名称")
            return
        key = REPEAT_TYPES[self.type_combo.currentIndex()][1]
        interval = 1
        weekdays = None
        month_day = None
        if key == "custom_day":
            interval = self.day_interval.value()
        elif key == "custom_week":
            interval = self.week_interval.value()
            weekdays = [i for i, ck in enumerate(self.weekday_checks) if ck.isChecked()]
            if not weekdays:
                QMessageBox.warning(self, "提示", "请至少选择一个星期")
                return
        elif key == "custom_month":
            interval = self.month_interval.value()
            month_day = self.month_day.value()
        elif key == "custom_year":
            interval = self.year_interval.value()
        li = self.limit_combo.currentIndex()
        limit_type = ["none", "end_date", "count"][li]
        limit_date = self.date_edit.date().toString("yyyy-MM-dd") if li == 1 else None
        limit_count = self.count_spin.value() if li == 2 else None
        remind_enabled = 1 if self.ck_remind.isChecked() else 0
        remind_time = "%s:%s" % (self.hour_combo.currentText(),
                                 self.min_combo.currentText())

        fields = dict(name=name, repeat_type=key, interval=interval,
                      weekdays=weekdays, month_day=month_day,
                      limit_type=limit_type, limit_date=limit_date,
                      limit_count=limit_count, remind_enabled=remind_enabled,
                      remind_time=remind_time)
        if self.rule:
            rid = self.rule["id"]
            self.db.update_repeat(rid, **fields)
            dates = json.loads(self.rule.get("completed_dates") or "[]")
            ds = self.day.isoformat() if self.day else None
            if ds:
                if self.ck_today_done.isChecked() and ds not in dates:
                    dates.append(ds)
                elif not self.ck_today_done.isChecked() and ds in dates:
                    dates.remove(ds)
                self.db.update_repeat(rid,
                                      completed_dates=json.dumps(dates, ensure_ascii=False))
            self.created_rule_id = rid
        else:
            start = (self.day or __import__("datetime").date.today()).isoformat()
            self.created_rule_id = self.db.add_repeat(
                name=name, start_date=start, repeat_type=key, interval=interval,
                weekdays=weekdays, month_day=month_day, limit_type=limit_type,
                limit_date=limit_date, limit_count=limit_count,
                remind_enabled=remind_enabled, remind_time=remind_time)
            if self.ck_today_done.isChecked():
                self.db.update_repeat(
                    self.created_rule_id,
                    completed_dates=json.dumps([start], ensure_ascii=False))
        self.accept()

    def delete_rule(self):
        if not self.rule:
            return
        r = QMessageBox.question(
            self, "删除任务", "将删除该任务派生的所有重复事件，确定删除？",
            QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            self.db.delete_repeat(self.rule["id"])
            self.rule = None
            self.accept()
