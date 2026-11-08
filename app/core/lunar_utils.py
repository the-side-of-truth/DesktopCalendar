# -*- coding: utf-8 -*-
"""农历、节气与星期相关的文本工具"""
import datetime

from lunarcalendar import Converter, Solar
from lunarcalendar.solarterm import specified_solar_term, zh_hans_terms

WEEKDAYS_FULL = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期天"]
LUNAR_MONTH_NAMES = ["正月", "二月", "三月", "四月", "五月", "六月",
                     "七月", "八月", "九月", "十月", "冬月", "腊月"]
LUNAR_DAY_NAMES = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
                   "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
                   "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]

_term_cache = {}


def _terms_of_year(year):
    """返回 {date: 节气名}，结果按年缓存"""
    if year not in _term_cache:
        mapping = {}
        for i in range(24):
            try:
                dt = specified_solar_term(year, i).date()
                mapping[dt] = zh_hans_terms[i]
            except Exception:
                pass
        if len(_term_cache) > 8:
            _term_cache.pop(next(iter(_term_cache)))
        _term_cache[year] = mapping
    return _term_cache[year]


def solar_term(d):
    """某公历日的节气名，无则 None（小寒/大寒落在次年1月，需要查前一年）"""
    t = _terms_of_year(d.year).get(d)
    if t:
        return t
    return _terms_of_year(d.year - 1).get(d)


def lunar_date(d):
    return Converter.Solar2Lunar(Solar(d.year, d.month, d.day))


def cell_lunar_text(d):
    """日单元格左上角日期旁的农历/节气名：节气优先，初一显示月名"""
    t = solar_term(d)
    if t:
        return t
    l = lunar_date(d)
    if l.day == 1:
        return ("闰" if l.isleap else "") + LUNAR_MONTH_NAMES[l.month - 1]
    return LUNAR_DAY_NAMES[l.day - 1]


def full_lunar_text(d):
    """顶栏使用的完整农历日期，如 九月廿九"""
    l = lunar_date(d)
    return LUNAR_MONTH_NAMES[l.month - 1] + LUNAR_DAY_NAMES[l.day - 1]


def title_text(d):
    """xxxx年xx月xx日 星期x 农历日期"""
    return "%d年%d月%d日 %s %s" % (
        d.year, d.month, d.day, WEEKDAYS_FULL[d.weekday()], full_lunar_text(d))


def month_text(d):
    return "%d年%d月" % (d.year, d.month)


def week_start_of(d, week_start):
    """d 所在周的起始日期(按设置的周起始日)"""
    return d - datetime.timedelta(days=(d.weekday() - week_start) % 7)


def week_number(d, week_start):
    """d 所在周是一年中的第几周(第一周为包含1月1日的周)"""
    jan1 = datetime.date(d.year, 1, 1)
    first_ws = week_start_of(jan1, week_start)
    ws = week_start_of(d, week_start)
    return (ws - first_ws).days // 7 + 1
