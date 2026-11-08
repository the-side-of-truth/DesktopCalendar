# -*- coding: utf-8 -*-
"""提醒设置对话框（针对普通工作事件）"""

from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QComboBox,
                             QCheckBox, QSpinBox, QVBoxLayout, QHBoxLayout,
                             QMessageBox)


class ReminderDialog(QDialog):
    def __init__(self, parent, db, event):
        super().__init__(parent)
        self.db = db
        self.event = event
        self.setWindowTitle("提醒设置")
        self.setMinimumWidth(400)
        self._build()
        self._load()

    def _build(self):
        lay = QVBoxLayout(self)

        # 第一行：事件名
        row = QHBoxLayout()
        row.addWidget(QLabel("事件名称:"))
        self.name_edit = QLineEdit()
        row.addWidget(self.name_edit, 1)
        lay.addLayout(row)

        # 第二行：完成勾选
        row = QHBoxLayout()
        self.ck_done = QCheckBox("将事件更改为完成状态")
        row.addWidget(self.ck_done)
        row.addStretch(1)
        lay.addLayout(row)

        # 第三行：提醒时间（即事件开始时间）
        row = QHBoxLayout()
        self.ck_enable = QCheckBox("启用提醒")
        row.addWidget(self.ck_enable)
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

        # 第四行：提醒日期（最多提前3天）
        row = QHBoxLayout()
        row.addWidget(QLabel("提醒日期:"))
        self.advance_combo = QComboBox()
        self.advance_combo.addItems(["当天", "提前1天", "提前2天", "提前3天"])
        row.addWidget(self.advance_combo)
        row.addStretch(1)
        lay.addLayout(row)

        # 第五行：提醒重复周期（仅当天内重复）
        row = QHBoxLayout()
        row.addWidget(QLabel("提醒重复:"))
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["不重复", "每N分钟", "每N小时"])
        self.repeat_combo.currentIndexChanged.connect(self._on_repeat_changed)
        row.addWidget(self.repeat_combo)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 720)
        self.interval_spin.setValue(30)
        self.interval_spin.setVisible(False)
        row.addWidget(self.interval_spin)
        row.addWidget(QLabel("最多"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 100)
        self.max_spin.setValue(3)
        self.max_spin.setVisible(False)
        row.addWidget(self.max_spin)
        self.max_label = QLabel("次")
        self.max_label.setVisible(False)
        row.addWidget(self.max_label)
        row.addStretch(1)
        lay.addLayout(row)

        # 按钮
        row = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)
        row.addStretch(1)
        row.addWidget(btn_cancel)
        row.addWidget(btn_save)
        lay.addLayout(row)

    def _on_repeat_changed(self, idx):
        self.interval_spin.setVisible(idx > 0)
        self.max_spin.setVisible(idx > 0)
        self.max_label.setVisible(idx > 0)

    def _load(self):
        ev = self.event
        self.name_edit.setText(ev["content"])
        self.ck_done.setChecked(bool(ev["completed"]))
        t = ev.get("start_time") or "09:00"
        self.hour_combo.setCurrentIndex(int(t[0:2]))
        self.min_combo.setCurrentIndex(int(t[3:5]))
        adv = ev.get("remind_advance")
        self.ck_enable.setChecked(adv is not None)
        self.advance_combo.setCurrentIndex(int(adv or 0))
        ri = ev.get("remind_rinterval")
        if ri:
            if ri % 60 == 0:
                self.repeat_combo.setCurrentIndex(2)
                self.interval_spin.setValue(ri // 60)
            else:
                self.repeat_combo.setCurrentIndex(1)
                self.interval_spin.setValue(ri)
            self.max_spin.setValue(int(ev.get("remind_rmax") or 1))
            self._on_repeat_changed(self.repeat_combo.currentIndex())

    def save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入事件名称")
            return
        fields = {"content": name,
                  "completed": 1 if self.ck_done.isChecked() else 0}
        if self.ck_enable.isChecked():
            fields["start_time"] = "%s:%s" % (self.hour_combo.currentText(),
                                              self.min_combo.currentText())
            fields["remind_advance"] = self.advance_combo.currentIndex()
            idx = self.repeat_combo.currentIndex()
            if idx == 0:
                fields["remind_rinterval"] = None
                fields["remind_rmax"] = None
            else:
                v = self.interval_spin.value()
                fields["remind_rinterval"] = v * 60 if idx == 2 else v
                fields["remind_rmax"] = self.max_spin.value()
            fields["remind_fired"] = "[]"
        else:
            fields["remind_advance"] = None
            fields["remind_rinterval"] = None
            fields["remind_rmax"] = None
            fields["remind_fired"] = "[]"
        self.db.update_event(self.event["id"], **fields)
        if self.ck_done.isChecked():
            ev = self.db.get_event(self.event["id"])
            if ev.get("postponed_from"):
                self.db.update_event(ev["postponed_from"], completed=1)
        self.accept()
