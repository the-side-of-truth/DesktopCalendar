# -*- coding: utf-8 -*-
"""日单元格编辑器：逐条录入工作事件，带编号、完成、重复、提醒按钮"""
import datetime
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
                             QMessageBox)

from app.core import database as dbmod
from app.ui.repeat_dialog import RepeatDialog
from app.ui.reminder_dialog import ReminderDialog


class EventLineEdit(QLineEdit):
    focusedIn = pyqtSignal(object)

    def focusInEvent(self, e):
        self.focusedIn.emit(self)
        super().focusInEvent(e)


class CellEditor(QFrame):
    """覆盖在单元格上的编辑面板"""
    saved = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent, day, db, settings):
        super().__init__(parent)
        self.day = day
        self.db = db
        self.settings = settings
        self.rows = []          # [{kind,id,rule_id,text,completed}, edit, numlbl, dellbl]
        self.focus_row = None
        self._dirty = False
        self._pending_deletes = []   # [("event", eid) / ("repeat", rule_id)] 待保存时生效
        self._build()
        self.reload_rows()

    # ---------- UI ----------
    def _build(self):
        self.setObjectName("CellEditor")
        self.setStyleSheet(
            "#CellEditor { background-color: rgba(20,35,60,235);"
            " border: 1px solid #6fb3ff; border-radius: 8px; }"
            "QLabel { color: #ffffff; background: transparent; }"
            "QLineEdit { background: rgba(255,255,255,30); color: #ffffff;"
            " border: 1px solid rgba(255,255,255,80); border-radius: 3px;"
            " padding: 2px 4px; }"
            "QPushButton { background: rgba(255,255,255,40); color: #fff;"
            " border: 1px solid rgba(255,255,255,90); border-radius: 4px;"
            " padding: 3px 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,80); }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setStyleSheet("font-weight:bold;")
        head.addWidget(self.title)
        head.addStretch(1)
        btn_close = QPushButton("✕")
        btn_close.setFixedWidth(30)
        btn_close.clicked.connect(self.cancel)
        head.addWidget(btn_close)
        lay.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.rows_widget = QWidget()
        self.rows_widget.setStyleSheet("background:transparent;")
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(3)
        self.scroll.setWidget(self.rows_widget)
        lay.addWidget(self.scroll, 1)

        bar1 = QHBoxLayout()
        bar1.setSpacing(4)
        self.btn_done = QPushButton("确认完成")
        self.btn_done.clicked.connect(self.toggle_done)
        self.btn_repeat = QPushButton("重复事件设置")
        self.btn_repeat.clicked.connect(self.edit_repeat)
        self.btn_remind = QPushButton("提醒设置")
        self.btn_remind.clicked.connect(self.edit_reminder)
        for b in (self.btn_done, self.btn_repeat, self.btn_remind):
            bar1.addWidget(b)
        bar1.addStretch(1)
        lay.addLayout(bar1)

        bar2 = QHBoxLayout()
        bar2.setSpacing(4)
        self.btn_add = QPushButton("新增事件")
        self.btn_add.clicked.connect(self.add_event_row)
        self.btn_del = QPushButton("删除事件")
        self.btn_del.setToolTip("删除当前行；重复事件仅删除当天")
        self.btn_del.clicked.connect(self.delete_focused_row)
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_and_close)
        for b in (self.btn_add, self.btn_del, btn_save):
            bar2.addWidget(b)
        bar2.addStretch(1)
        lay.addLayout(bar2)

    # ---------- 数据 ----------
    def reload_rows(self):
        self.title.setText("%d月%d日 待办编辑" % (self.day.month, self.day.day))
        # 清空
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows = []
        self.focus_row = None
        self._pending_deletes = []

        for ev in self.db.events_of(self.day.isoformat()):
            self._append_row({"kind": "event", "id": ev["id"],
                              "text": ev["content"],
                              "completed": bool(ev["completed"]),
                              "start_time": ev.get("start_time")})
        main = self.parent()
        derived = getattr(main, "repeat_events_of", lambda d: [])(self.day)
        for dev in derived:
            self._append_row({"kind": "repeat", "rule_id": dev["rule_id"],
                              "text": dev["content"],
                              "orig_text": dev.get("orig_content", dev["content"]),
                              "completed": bool(dev["completed"])})
        if not self.rows:
            self._append_row({"kind": "event", "id": None, "text": "",
                              "completed": False})
        self._renumber()

    def _append_row(self, model, after_index=None):
        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        num = QLabel()
        num.setFixedWidth(22)
        num.setAlignment(Qt.AlignCenter)
        edit = EventLineEdit()
        edit.setText(model["text"])
        edit.setPlaceholderText("输入工作事件，回车新增一条")
        if model["kind"] == "repeat":
            edit.setToolTip("重复事件：修改/删除仅影响当天；整体修改请在“重复事件设置”中进行")
        edit.focusedIn.connect(lambda w, m=model: self._on_focus(m))
        edit.returnPressed.connect(lambda m=model: self._on_return(m))
        edit.textChanged.connect(self._mark_dirty)
        btn_del = QPushButton("×")
        btn_del.setFixedWidth(24)
        btn_del.setToolTip("删除该条（重复事件仅删除当天）")
        btn_del.clicked.connect(lambda _=None, m=model: self._delete_row(m))
        hl.addWidget(num)
        hl.addWidget(edit, 1)
        hl.addWidget(btn_del)
        idx = len(self.rows) if after_index is None else after_index + 1
        self.rows.insert(idx, [model, edit, num, row_widget])
        self.rows_layout.insertWidget(idx, row_widget)
        self._style_row(model, edit)
        return edit

    def _style_row(self, model, edit):
        if model.get("completed"):
            edit.setStyleSheet(
                "color:#7be495; text-decoration: line-through;"
                " background: rgba(255,255,255,20);")
        elif model["kind"] == "repeat":
            edit.setStyleSheet("color:#ffd27f; background: rgba(255,255,255,15);")
        else:
            edit.setStyleSheet("")

    def _renumber(self):
        n = 0
        for model, edit, num, _w in self.rows:
            if model["kind"] == "repeat":
                num.setText("↻")
            else:
                n += 1
                num.setText("%d." % n)

    def _mark_dirty(self, *_):
        self._dirty = True
        for model, edit, _n, _w in self.rows:
            if self.sender() is edit:
                model["text"] = edit.text()

    def _on_focus(self, model):
        self.focus_row = model

    def _on_return(self, model):
        """回车：新增一条（按设置插到当前行后或末尾）"""
        idx = self._row_index(model)
        if self.settings.get("auto_append_end") or idx is None:
            edit = self._append_row({"kind": "event", "id": None, "text": "",
                                     "completed": False})
        else:
            edit = self._append_row({"kind": "event", "id": None, "text": "",
                                     "completed": False}, after_index=idx)
        self._renumber()
        self._dirty = True
        edit.setFocus()

    def _row_index(self, model):
        for i, r in enumerate(self.rows):
            if r[0] is model:
                return i
        return None

    def add_event_row(self):
        """新增事件按钮：按设置插到当前行后或末尾"""
        model = self.focus_row
        idx = self._row_index(model) if model is not None else None
        if self.settings.get("auto_append_end") or idx is None:
            edit = self._append_row({"kind": "event", "id": None, "text": "",
                                     "completed": False})
        else:
            edit = self._append_row({"kind": "event", "id": None, "text": "",
                                     "completed": False}, after_index=idx)
        self._renumber()
        self._dirty = True
        edit.setFocus()

    def delete_focused_row(self):
        """删除事件按钮：删除当前光标所在行；重复事件默认只删当天"""
        model = self._focused_or_last()
        if model is not None:
            self._delete_row(model)

    def _delete_row(self, model):
        """仅从界面移除并记入待删清单，点保存时才真正写库（可取消）"""
        idx = self._row_index(model)
        if idx is None:
            return
        if model["kind"] == "repeat":
            # 仅删除当天的派生事件，不影响其他日期
            self._pending_deletes.append(("repeat", model["rule_id"]))
            self._dirty = True
        elif model.get("id"):
            self._pending_deletes.append(("event", model["id"]))
            self._dirty = True
        w = self.rows[idx][3]
        self.rows_layout.removeWidget(w)
        w.deleteLater()
        self.rows.pop(idx)
        if not self.rows:
            self._append_row({"kind": "event", "id": None, "text": "",
                              "completed": False})
        self._renumber()

    # ---------- 按钮动作 ----------
    def _focused_or_last(self):
        if self.focus_row is not None:
            return self.focus_row
        return self.rows[-1][0] if self.rows else None

    def _ensure_event(self, model):
        """未保存的行先落库，返回事件id"""
        if model["kind"] != "event":
            return None
        if model["id"]:
            return model["id"]
        if not model["text"].strip():
            return None
        eid = self.db.add_event(self.day.isoformat(), model["text"].strip(),
                                position=self._row_index(model) or 0)
        model["id"] = eid
        self._dirty = True
        self.saved.emit()
        return eid

    def toggle_done(self):
        model = self._focused_or_last()
        if model is None:
            return
        if model["kind"] == "repeat":
            rule = self.db.get_repeat(model["rule_id"])
            dates = json.loads(rule["completed_dates"] or "[]")
            ds = self.day.isoformat()
            if model["completed"]:
                if ds in dates:
                    dates.remove(ds)
            elif ds not in dates:
                dates.append(ds)
            self.db.update_repeat(rule["id"],
                                  completed_dates=json.dumps(dates, ensure_ascii=False))
            model["completed"] = not model["completed"]
        else:
            eid = self._ensure_event(model)
            if not eid:
                return
            model["completed"] = not model["completed"]
            self.db.complete_event(eid, model["completed"])
        self._style_row(model, self.rows[self._row_index(model)][1])
        self.saved.emit()

    def edit_repeat(self):
        model = self._focused_or_last()
        if model is None:
            return
        if model["kind"] == "repeat":
            rule = self.db.get_repeat(model["rule_id"])
            dlg = RepeatDialog(None, self.db, settings=self.settings,
                               rule=rule, day=self.day)
        else:
            eid = self._ensure_event(model)
            if not eid:
                QMessageBox.information(None, "提示", "请先输入事件内容")
                return
            dlg = RepeatDialog(None, self.db, settings=self.settings,
                               rule=None, day=self.day,
                               default_name=model["text"])
        if dlg.exec_() == RepeatDialog.Accepted:
            # 普通事件转为重复规则后删除原事件
            if model["kind"] == "event" and dlg.created_rule_id and model.get("id"):
                self.db.delete_event(model["id"])
            self.saved.emit()
            self.reload_rows()

    def edit_reminder(self):
        model = self._focused_or_last()
        if model is None:
            return
        if model["kind"] == "repeat":
            QMessageBox.information(
                None, "提示", "重复事件的提醒请在“重复事件设置”中配置")
            return
        eid = self._ensure_event(model)
        if not eid:
            QMessageBox.information(None, "提示", "请先输入事件内容")
            return
        ev = self.db.get_event(eid)
        dlg = ReminderDialog(None, self.db, ev)
        if dlg.exec_() == ReminderDialog.Accepted:
            model["text"] = self.db.get_event(eid)["content"]
            model["completed"] = bool(self.db.get_event(eid)["completed"])
            self.saved.emit()
            self.reload_rows()

    # ---------- 保存/关闭 ----------
    def save(self):
        # 先应用待删清单
        for kind, key in self._pending_deletes:
            if kind == "event":
                self.db.delete_event(key)
            else:
                self.db.set_repeat_deleted(key, self.day.isoformat(), True)
        self._pending_deletes = []
        # 以行的当前顺序重写事件与排序
        pos = 0
        for model, edit, _n, _w in self.rows:
            if model["kind"] == "repeat":
                # 修改文本仅覆盖当天；清空文本视为当天删除
                text = edit.text().strip()
                if not text:
                    self.db.set_repeat_deleted(model["rule_id"],
                                               self.day.isoformat(), True)
                elif text != model.get("orig_text"):
                    self.db.set_repeat_override(model["rule_id"],
                                                self.day.isoformat(), text)
                continue
            text = edit.text().strip()
            if model["id"] and not text:
                self.db.delete_event(model["id"])
                model["id"] = None
                continue
            if not text:
                continue
            if model["id"]:
                self.db.update_event(model["id"], content=text, position=pos)
            else:
                model["id"] = self.db.add_event(self.day.isoformat(), text,
                                                position=pos)
            pos += 1
        self._dirty = False
        self.saved.emit()

    def save_and_close(self):
        self.save()
        self.close()

    def cancel(self):
        if self._dirty:
            r = QMessageBox.question(None, "未保存", "有未保存的修改，是否保存？",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Yes:
                self.save()
        self.close()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)
