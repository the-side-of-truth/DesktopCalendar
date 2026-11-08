# -*- coding: utf-8 -*-
"""提醒服务：定时检查事件提醒并弹出提醒窗口"""
import datetime
import json

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QFrame, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QDesktopWidget)

from app.core.recurrence import expand_repeat


class ReminderPopup(QFrame):
    """单个提醒弹窗（无边框、置顶）"""
    _open = []

    def __init__(self, title, sub):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            "QFrame#pop { background: rgba(23,43,77,245); border: 1px solid #6fb3ff;"
            " border-radius: 10px; }"
            "QLabel { color: #fff; background: transparent; }"
            "QPushButton { background: #2b6cb0; color: #fff; border-radius: 4px;"
            " padding: 4px 16px; }")
        body = QFrame()
        body.setObjectName("pop")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(body)
        inner = QVBoxLayout(body)
        inner.setContentsMargins(14, 10, 14, 10)
        t = QLabel("⏰ 日历提醒")
        t.setStyleSheet("font-weight:bold; font-size:12pt;")
        inner.addWidget(t)
        msg = QLabel(title)
        msg.setStyleSheet("font-size:11pt;")
        msg.setWordWrap(True)
        inner.addWidget(msg)
        if sub:
            s = QLabel(sub)
            s.setStyleSheet("color:#9fc5ff;")
            inner.addWidget(s)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("知道了")
        btn.clicked.connect(self.close)
        row.addWidget(btn)
        inner.addLayout(row)
        self.setMinimumWidth(300)
        self.adjustSize()
        screen = QDesktopWidget().availableGeometry()
        idx = len(ReminderPopup._open)
        self.move(screen.right() - self.width() - 20,
                  screen.bottom() - (self.height() + 12) * (idx + 1) - 12)
        ReminderPopup._open.append(self)
        QApplication.beep()

    def closeEvent(self, e):
        if self in ReminderPopup._open:
            ReminderPopup._open.remove(self)
        super().closeEvent(e)


class ReminderService:
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    def check(self):
        now = datetime.datetime.now()
        today = now.date()
        self._check_events(now, today)
        self._check_repeats(now, today)

    def _check_events(self, now, today):
        end = today + datetime.timedelta(days=3)
        for ev in self.db.events_between(today.isoformat(), end.isoformat()):
            adv = ev.get("remind_advance")
            if adv is None or not ev.get("start_time"):
                continue
            d = datetime.date.fromisoformat(ev["event_date"])
            if d - datetime.timedelta(days=int(adv)) != today:
                continue
            try:
                base = datetime.datetime.combine(
                    today, datetime.time(int(ev["start_time"][0:2]),
                                         int(ev["start_time"][3:5])))
            except Exception:
                continue
            times = [base]
            ri = ev.get("remind_rinterval")
            rmax = ev.get("remind_rmax")
            if ri and rmax:
                for k in range(1, int(rmax)):
                    t = base + datetime.timedelta(minutes=int(ri) * k)
                    if t.date() != today:
                        break
                    times.append(t)
            try:
                fired = json.loads(ev.get("remind_fired") or "[]")
            except Exception:
                fired = []
            changed = False
            for ft in times:
                key = ft.strftime("%H:%M")
                if ft <= now and key not in fired:
                    fired.append(key)
                    changed = True
                    ReminderPopup(ev["content"],
                                  "%s %s" % (ev["event_date"], ev["start_time"])).show()
            if changed:
                self.db.update_event(ev["id"],
                                     remind_fired=json.dumps(fired, ensure_ascii=False))

    def _check_repeats(self, now, today):
        ws = self.settings.get("week_start")
        for rule in self.db.all_repeats():
            if not rule.get("remind_enabled") or not rule.get("remind_time"):
                continue
            try:
                dates = expand_repeat(rule, today, today, ws)
            except Exception:
                continue
            if today not in dates:
                continue
            if today.isoformat() in (rule.get("deleted_dates") or []):
                continue
            try:
                ft = datetime.datetime.combine(
                    today, datetime.time(int(rule["remind_time"][0:2]),
                                         int(rule["remind_time"][3:5])))
            except Exception:
                continue
            fired = rule.get("remind_fired") or {}
            key = today.isoformat()
            if ft <= now and not fired.get(key):
                fired[key] = True
                self.db.update_repeat(rule["id"],
                                      remind_fired=json.dumps(fired, ensure_ascii=False))
                name = (rule.get("overrides") or {}).get(key, rule["name"])
                ReminderPopup(name,
                              "重复事件 %s" % rule["remind_time"]).show()
