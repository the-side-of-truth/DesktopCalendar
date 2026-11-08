# -*- coding: utf-8 -*-
"""SQLite 数据层：工作事件、重复规则"""
import datetime
import json
import sqlite3

STATUS_TODO = "未开始"
STATUS_DOING = "进行中"
STATUS_DONE = "已完成"
STATUS_OVERDUE = "超期未完成"
STATUSES = (STATUS_TODO, STATUS_DOING, STATUS_DONE, STATUS_OVERDUE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,
    content TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT DEFAULT '23:59',
    completed INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    postponed_from INTEGER,
    remind_advance INTEGER,
    remind_rinterval INTEGER,
    remind_rmax INTEGER,
    remind_fired TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);

CREATE TABLE IF NOT EXISTS repeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT DEFAULT '23:59',
    repeat_type TEXT NOT NULL,
    interval INTEGER DEFAULT 1,
    weekdays TEXT,
    month_day INTEGER,
    limit_type TEXT DEFAULT 'none',
    limit_date TEXT,
    limit_count INTEGER,
    remind_enabled INTEGER DEFAULT 0,
    remind_time TEXT,
    completed_dates TEXT DEFAULT '[]',
    remind_fired TEXT DEFAULT '{}',
    deleted_dates TEXT DEFAULT '[]',
    overrides TEXT DEFAULT '{}'
);
"""

MIGRATIONS = (
    ("deleted_dates", "ALTER TABLE repeats ADD COLUMN deleted_dates TEXT DEFAULT '[]'"),
    ("overrides", "ALTER TABLE repeats ADD COLUMN overrides TEXT DEFAULT '{}'"),
)


def _parse_time(s):
    if not s:
        return None
    try:
        return datetime.time(int(s[0:2]), int(s[3:5]))
    except Exception:
        return None


def event_status(ev, now=None):
    """计算工作事件状态。已完成由用户标记，其余按时间推算"""
    if ev.get("completed"):
        return STATUS_DONE
    now = now or datetime.datetime.now()
    d = ev["event_date"]
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    end_t = _parse_time(ev.get("end_time")) or datetime.time(23, 59)
    end_dt = datetime.datetime.combine(d, end_t)
    if end_dt < now:
        return STATUS_OVERDUE
    start_t = _parse_time(ev.get("start_time"))
    if start_t is None or datetime.datetime.combine(d, start_t) <= now:
        return STATUS_DOING
    return STATUS_TODO


class Database:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(repeats)")]
        for name, sql in MIGRATIONS:
            if name not in cols:
                self.conn.execute(sql)
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    @staticmethod
    def _row(r):
        return dict(r) if r is not None else None

    # ---------------- 普通工作事件 ----------------
    def add_event(self, event_date, content, start_time=None, end_time="23:59",
                  position=0, completed=0, postponed_from=None):
        cur = self.conn.execute(
            "INSERT INTO events(event_date, content, start_time, end_time, position,"
            " completed, postponed_from) VALUES(?,?,?,?,?,?,?)",
            (event_date, content, start_time, end_time, position, completed, postponed_from))
        self.conn.commit()
        return cur.lastrowid

    def update_event(self, eid, **fields):
        if not fields:
            return
        keys = ", ".join("%s=?" % k for k in fields)
        self.conn.execute("UPDATE events SET %s WHERE id=?" % keys,
                          tuple(fields.values()) + (eid,))
        self.conn.commit()

    def delete_event(self, eid):
        self.conn.execute("DELETE FROM events WHERE id=?", (eid,))
        self.conn.commit()

    def get_event(self, eid):
        return self._row(self.conn.execute(
            "SELECT * FROM events WHERE id=?", (eid,)).fetchone())

    def events_of(self, date_str):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE event_date=? ORDER BY position, id",
            (date_str,)).fetchall()]

    def events_between(self, start_str, end_str):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE event_date BETWEEN ? AND ? ORDER BY event_date, position, id",
            (start_str, end_str)).fetchall()]

    def all_events(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM events ORDER BY event_date, position, id").fetchall()]

    def search_events(self, keyword):
        like = "%%%s%%" % keyword
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE content LIKE ? ORDER BY event_date DESC, position",
            (like,)).fetchall()]

    # ---------------- 重复规则 ----------------
    def add_repeat(self, name, start_date, repeat_type, interval=1, weekdays=None,
                   month_day=None, limit_type="none", limit_date=None, limit_count=None,
                   start_time=None, end_time="23:59", remind_enabled=0, remind_time=None):
        cur = self.conn.execute(
            "INSERT INTO repeats(name, start_date, start_time, end_time, repeat_type,"
            " interval, weekdays, month_day, limit_type, limit_date, limit_count,"
            " remind_enabled, remind_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, start_date, start_time, end_time, repeat_type, interval,
             json.dumps(weekdays) if weekdays else None, month_day,
             limit_type, limit_date, limit_count, remind_enabled, remind_time))
        self.conn.commit()
        return cur.lastrowid

    def update_repeat(self, rid, **fields):
        if "weekdays" in fields and fields["weekdays"] is not None \
                and not isinstance(fields["weekdays"], str):
            fields["weekdays"] = json.dumps(fields["weekdays"])
        keys = ", ".join("%s=?" % k for k in fields)
        self.conn.execute("UPDATE repeats SET %s WHERE id=?" % keys,
                          tuple(fields.values()) + (rid,))
        self.conn.commit()

    def delete_repeat(self, rid):
        self.conn.execute("DELETE FROM repeats WHERE id=?", (rid,))
        self.conn.commit()

    def get_repeat(self, rid):
        return self._row(self.conn.execute(
            "SELECT * FROM repeats WHERE id=?", (rid,)).fetchone())

    def all_repeats(self):
        rules = [dict(r) for r in self.conn.execute(
            "SELECT * FROM repeats ORDER BY id").fetchall()]
        for r in rules:
            try:
                r["weekdays"] = json.loads(r["weekdays"]) if r["weekdays"] else None
            except Exception:
                r["weekdays"] = None
            try:
                r["completed_dates"] = json.loads(r["completed_dates"] or "[]")
            except Exception:
                r["completed_dates"] = []
            try:
                r["remind_fired"] = json.loads(r["remind_fired"] or "{}")
            except Exception:
                r["remind_fired"] = {}
            try:
                r["deleted_dates"] = json.loads(r.get("deleted_dates") or "[]")
            except Exception:
                r["deleted_dates"] = []
            try:
                r["overrides"] = json.loads(r.get("overrides") or "{}")
            except Exception:
                r["overrides"] = {}
        return rules

    def set_repeat_deleted(self, rid, date_str, deleted):
        """单日删除/恢复某天派生事件"""
        rule = self.get_repeat(rid)
        if not rule:
            return
        dates = json.loads(rule.get("deleted_dates") or "[]")
        if deleted and date_str not in dates:
            dates.append(date_str)
        elif not deleted and date_str in dates:
            dates.remove(date_str)
        self.update_repeat(rid, deleted_dates=json.dumps(dates, ensure_ascii=False))

    def set_repeat_override(self, rid, date_str, content):
        """单日修改某天派生事件内容；content 为 None 表示恢复默认"""
        rule = self.get_repeat(rid)
        if not rule:
            return
        ov = json.loads(rule.get("overrides") or "{}")
        if content is None or content == rule["name"]:
            ov.pop(date_str, None)
        else:
            ov[date_str] = content
        self.update_repeat(rid, overrides=json.dumps(ov, ensure_ascii=False))

    def search_repeats(self, keyword):
        like = "%%%s%%" % keyword
        return [r for r in self.all_repeats()
                if keyword in r["name"] or self.conn.execute(
                    "SELECT 1 FROM repeats WHERE name LIKE ? AND id=?",
                    (like, r["id"])).fetchone()]

    # ---------------- 自动顺延 ----------------
    def postpone_overdue(self, today, week_start_day):
        """把本周内(含今天所在周起)过去日期中未完成的事件复制到今天。
        仅复制原始事件(postponed_from 为空)，同一天不重复复制。"""
        start = week_start_day.isoformat()
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        if start > yesterday:
            return 0
        rows = self.conn.execute(
            "SELECT * FROM events WHERE event_date BETWEEN ? AND ?"
            " AND completed=0 AND postponed_from IS NULL",
            (start, yesterday)).fetchall()
        today_str = today.isoformat()
        max_pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM events WHERE event_date=?",
            (today_str,)).fetchone()[0]
        added = 0
        now = datetime.datetime.now()
        for r in rows:
            ev = dict(r)
            if event_status(ev, now) != STATUS_OVERDUE:
                continue
            dup = self.conn.execute(
                "SELECT 1 FROM events WHERE event_date=? AND postponed_from=?",
                (today_str, ev["id"])).fetchone()
            if dup:
                continue
            max_pos += 1
            self.conn.execute(
                "INSERT INTO events(event_date, content, start_time, end_time, position,"
                " completed, postponed_from) VALUES(?,?,?,?,?,0,?)",
                (today_str, ev["content"], ev["start_time"], ev["end_time"],
                 max_pos, ev["id"]))
            added += 1
        if added:
            self.conn.commit()
        return added

    def complete_event(self, eid, done):
        """标记完成/撤销完成；顺延副本联动原始事件"""
        self.update_event(eid, completed=1 if done else 0)
        ev = self.get_event(eid)
        if ev and ev.get("postponed_from") and done:
            self.update_event(ev["postponed_from"], completed=1)

    # ---------------- 导入 ----------------
    def import_events(self, events):
        """events: [dict(event_date, content, start_time, end_time, completed)]"""
        n = 0
        for ev in events:
            pos = self.conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM events WHERE event_date=?",
                (ev["event_date"],)).fetchone()[0]
            self.conn.execute(
                "INSERT INTO events(event_date, content, start_time, end_time, position,"
                " completed) VALUES(?,?,?,?,?,?)",
                (ev["event_date"], ev["content"], ev.get("start_time"),
                 ev.get("end_time") or "23:59", pos, int(ev.get("completed") or 0)))
            n += 1
        self.conn.commit()
        return n

    def import_from_db(self, other_path):
        """从另一个 CalendarTask 数据库合并导入，返回(事件数, 重复规则数)"""
        other = sqlite3.connect(other_path)
        other.row_factory = sqlite3.Row
        ne = nr = 0
        try:
            for r in other.execute(
                    "SELECT event_date, content, start_time, end_time, completed"
                    " FROM events"):
                pos = self.conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM events WHERE event_date=?",
                    (r["event_date"],)).fetchone()[0]
                self.conn.execute(
                    "INSERT INTO events(event_date, content, start_time, end_time,"
                    " position, completed) VALUES(?,?,?,?,?,?)",
                    (r["event_date"], r["content"], r["start_time"],
                     r["end_time"], pos, r["completed"]))
                ne += 1
            cols = [row[1] for row in other.execute("PRAGMA table_info(repeats)")]
            if cols:
                for r in other.execute("SELECT * FROM repeats"):
                    r = dict(r)
                    r.pop("id", None)
                    self.conn.execute(
                        "INSERT INTO repeats(%s) VALUES(%s)" % (
                            ",".join(r.keys()), ",".join("?" * len(r))),
                        tuple(r.values()))
                    nr += 1
            self.conn.commit()
        finally:
            other.close()
        return ne, nr
