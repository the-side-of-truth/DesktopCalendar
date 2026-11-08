# -*- coding: utf-8 -*-
"""导入 / 导出对话框：文本、Excel、CalendarTask数据库"""
import datetime
import os
import shutil

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QRadioButton,
                             QPushButton, QLabel, QFileDialog, QMessageBox,
                             QButtonGroup)

from app.core.database import event_status


def _fmt_time(t):
    return t if t else ""


REPEAT_TYPE_NAMES = {
    "daily": "每天", "weekly": "每周", "monthly": "每月", "yearly": "每年",
    "custom_day": "自定义-日", "custom_week": "自定义-周",
    "custom_month": "自定义-月", "custom_year": "自定义-年",
}

REPEAT_HEADER = ("事件名称", "开始日期", "重复类型", "间隔", "每周星期", "每月几号",
                 "限制类型", "限制日期", "限制次数", "开始时间", "结束时间",
                 "提醒时间", "已完成日期", "单日删除日期")


def _repeat_row(r):
    limit_names = {"none": "无限制", "end_date": "结束日期", "count": "重复次数"}
    weekdays = ""
    if r.get("weekdays"):
        names = ["一", "二", "三", "四", "五", "六", "日"]
        weekdays = "/".join(names[int(i)] for i in r["weekdays"])
    return (r["name"], r["start_date"],
            REPEAT_TYPE_NAMES.get(r["repeat_type"], r["repeat_type"]),
            r.get("interval") or 1, weekdays, r.get("month_day") or "",
            limit_names.get(r.get("limit_type") or "none", ""),
            r.get("limit_date") or "", r.get("limit_count") or "",
            _fmt_time(r.get("start_time")), _fmt_time(r.get("end_time")),
            r.get("remind_time") if r.get("remind_enabled") else "",
            ",".join(r.get("completed_dates") or []),
            ",".join(r.get("deleted_dates") or []))


def export_events(db, path, fmt):
    """导出全部普通事件与重复事件规则。fmt: txt / xlsx / db"""
    events = db.all_events()
    rules = db.all_repeats()
    if fmt == "db":
        db.conn.commit()
        shutil.copyfile(db.path, path)
        return len(events) + len(rules)
    rows = [("日期", "事件内容", "开始时间", "结束时间", "状态")]
    for ev in events:
        rows.append((ev["event_date"], ev["content"],
                     _fmt_time(ev.get("start_time")),
                     _fmt_time(ev.get("end_time")),
                     event_status(ev)))
    if fmt == "txt":
        with open(path, "w", encoding="utf-8-sig") as f:
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
            f.write("\n[重复事件]\n")
            f.write("\t".join(REPEAT_HEADER) + "\n")
            for rule in rules:
                f.write("\t".join(str(x) for x in _repeat_row(rule)) + "\n")
        return len(events) + len(rules)
    # xlsx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "CalendarTask"
    for r in rows:
        ws.append(list(r))
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    for col in "CDE":
        ws.column_dimensions[col].width = 12
    ws2 = wb.create_sheet("重复事件")
    ws2.append(list(REPEAT_HEADER))
    for rule in rules:
        ws2.append(list(_repeat_row(rule)))
    ws2.column_dimensions["A"].width = 30
    for col in ("B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"):
        ws2.column_dimensions[col].width = 14
    wb.save(path)
    return len(events) + len(rules)


def _parse_date(v):
    if v is None:
        return None
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.date().isoformat() if isinstance(v, datetime.datetime) \
            else v.isoformat()
    s = str(v).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _parse_time(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime.time):
        return "%02d:%02d" % (v.hour, v.minute)
    if isinstance(v, datetime.datetime):
        return "%02d:%02d" % (v.hour, v.minute)
    s = str(v).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.datetime.strptime(s, fmt)
            return "%02d:%02d" % (t.hour, t.minute)
        except ValueError:
            pass
    return "ERR"


def import_events_from_file(db, path):
    """从 Excel / CalendarTask数据库 导入，返回(成功条数, [错误信息])"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".db", ".sqlite", ".sqlite3"):
        try:
            ne, nr = db.import_from_db(path)
            return ne + nr, []
        except Exception as e:
            return 0, ["数据库文件无法读取: %s" % e]
    if ext in (".xlsx", ".xlsm", ".xls"):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
        except Exception as e:
            return 0, ["Excel 文件无法读取: %s" % e]
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            return 0, ["文件为空"]
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        try:
            c_date = header.index("日期")
            c_content = header.index("事件内容")
        except ValueError:
            return 0, ["缺少必需表头“日期”“事件内容”"]
        c_start = header.index("开始时间") if "开始时间" in header else None
        c_end = header.index("结束时间") if "结束时间" in header else None
        c_status = header.index("状态") if "状态" in header else None
        events = []
        errors = []
        for i, row in enumerate(rows[1:], start=2):
            if all(c is None or str(c).strip() == "" for c in row):
                continue
            d = _parse_date(row[c_date] if c_date < len(row) else None)
            content = str(row[c_content]).strip() \
                if c_content < len(row) and row[c_content] is not None else ""
            if not d:
                errors.append("第%d行：日期无效" % i)
                continue
            if not content:
                errors.append("第%d行：事件内容为空" % i)
                continue
            start = _parse_time(row[c_start]) if c_start is not None else None
            end = _parse_time(row[c_end]) if c_end is not None else None
            if start == "ERR":
                errors.append("第%d行：开始时间格式无效" % i)
                continue
            if end == "ERR":
                errors.append("第%d行：结束时间格式无效" % i)
                continue
            status = str(row[c_status]).strip() \
                if c_status is not None and row[c_status] is not None else ""
            events.append({"event_date": d, "content": content,
                           "start_time": start, "end_time": end or "23:59",
                           "completed": 1 if status == "已完成" else 0})
        n = db.import_events(events)
        return n, errors
    return 0, ["不支持的文件格式: %s" % ext]


class ExportDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("导出")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("请选择导出格式:"))
        self.group = QButtonGroup(self)
        self.rb_txt = QRadioButton("文本 (txt)")
        self.rb_xlsx = QRadioButton("Excel (xlsx)")
        self.rb_db = QRadioButton("CalendarTask 数据库 (db)")
        self.rb_xlsx.setChecked(True)
        for i, rb in enumerate((self.rb_txt, self.rb_xlsx, self.rb_db)):
            self.group.addButton(rb, i)
            lay.addWidget(rb)
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("导出")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.do_export)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        lay.addLayout(row)

    def do_export(self):
        if self.rb_txt.isChecked():
            fmt, filt, suffix = "txt", "文本文件 (*.txt)", ".txt"
        elif self.rb_xlsx.isChecked():
            fmt, filt, suffix = "xlsx", "Excel 文件 (*.xlsx)", ".xlsx"
        else:
            fmt, filt, suffix = "db", "CalendarTask 数据库 (*.db)", ".db"
        default = "CalendarTask_%s%s" % (
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S"), suffix)
        path, _ = QFileDialog.getSaveFileName(self, "选择保存路径", default, filt)
        if not path:
            return
        try:
            n = export_events(self.db, path, fmt)
            QMessageBox.information(self, "导出完成",
                                    "已导出 %d 条记录到:\n%s" % (n, path))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))


class ImportDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("导入")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("支持 Excel(xlsx) 与 CalendarTask 数据库(db) 格式。\n"
                             "Excel 需包含表头：日期、事件内容、开始时间、结束时间、状态。"))
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("导入")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.do_import)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        lay.addLayout(row)
        self.imported = 0

    def do_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择导入文件", "",
            "可导入文件 (*.xlsx *.xlsm *.xls *.db *.sqlite *.sqlite3)")
        if not path:
            return
        try:
            n, errors = import_events_from_file(self.db, path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return
        self.imported = n
        if errors:
            QMessageBox.warning(
                self, "导入完成(部分失败)",
                "成功导入 %d 条，%d 条失败:\n%s" % (
                    n, len(errors), "\n".join(errors[:10])))
        else:
            QMessageBox.information(self, "导入完成", "成功导入 %d 条记录" % n)
        if n > 0:
            self.accept()
