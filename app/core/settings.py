# -*- coding: utf-8 -*-
"""应用设置的读写与持久化(JSON)"""
import copy
import json
import os

from PyQt5.QtCore import QStandardPaths

DEFAULTS = {
    "theme": "light",            # light / dark
    "display_mode": "floating",  # floating=浮动的月份 / full_month=完整的月份
    "max_rows": 4,               # 日单元格展板最大行数(周数) 1-10
    "past_weeks": 1,             # 已过星期数 0 ~ max_rows-1
    "bg_color": "#2b6cb0",       # 日历背景颜色
    "title_font_size": 12,       # 顶部与日历字体大小(pt)
    "cell_opacity": 60,          # 单元格透明度 0-100
    "cell_gap": 2,               # 单元格间隙 0-10
    "today_border_color": "#ff7f50",
    "cell_font_size": 9,         # 单元格内部字体大小(pt)
    "auto_append_end": True,     # 编辑完成后自动排到末尾
    "auto_postpone": False,      # 未完成一周内自动顺延
    "week_start": 0,             # 开始星期 0=周一 ... 6=周日
    "rest_days": [5, 6],         # 每周休息日
    "geometry": None,            # [x, y, w, h]
}

THEME_COLORS = {
    "light": "#2b6cb0",
    "dark": "#16233b",
}


def data_dir():
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    os.makedirs(base, exist_ok=True)
    return base


class Settings:
    def __init__(self):
        self.dir = data_dir()
        self.path = os.path.join(self.dir, "settings.json")
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data.update(data)
        except Exception:
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def reset(self):
        geo = self._data.get("geometry")
        self._data = copy.deepcopy(DEFAULTS)
        self._data["geometry"] = geo
        self.save()
