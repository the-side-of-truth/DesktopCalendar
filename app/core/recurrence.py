# -*- coding: utf-8 -*-
"""重复事件规则展开：把重复规则展开成指定区间内的日期列表"""
import calendar
import datetime

from app.core.lunar_utils import week_start_of

MAX_ITER = 50000  # 展开安全上限


def _add_months(d, months, day):
    total = d.year * 12 + (d.month - 1) + months
    y, m = divmod(total, 12)
    m += 1
    day = min(day, calendar.monthrange(y, m)[1])
    return datetime.date(y, m, day)


def expand_repeat(rule, range_start, range_end, week_start=0):
    """rule 为 dict，返回 [range_start, range_end] 内所有重复日期(升序)"""
    start = rule["start_date"]
    if isinstance(start, str):
        start = datetime.date.fromisoformat(start)
    rtype = rule.get("repeat_type", "daily")
    interval = max(1, int(rule.get("interval") or 1))
    limit_type = rule.get("limit_type", "none")
    limit_date = rule.get("limit_date") or None
    if isinstance(limit_date, str):
        limit_date = datetime.date.fromisoformat(limit_date)
    if limit_type != "end_date":
        limit_date = None
    limit_count = rule.get("limit_count") if limit_type == "count" else None
    if limit_count is not None:
        limit_count = max(1, int(limit_count))

    dates = []
    count = 0

    def accept(d):
        nonlocal count
        if limit_date and d > limit_date:
            return False
        count += 1
        if limit_count is not None and count > limit_count:
            return False
        if range_start <= d <= range_end:
            dates.append(d)
        return True

    it = 0

    def loop_ok(d):
        nonlocal it
        it += 1
        return it <= MAX_ITER and d <= range_end

    if rtype in ("daily", "custom_day"):
        step = 1 if rtype == "daily" else interval
        d = start
        while loop_ok(d):
            if not accept(d):
                break
            d += datetime.timedelta(days=step)

    elif rtype == "weekly":
        # 每周与起始日相同的星期几
        d = start
        while loop_ok(d):
            if not accept(d):
                break
            d += datetime.timedelta(days=7)

    elif rtype == "custom_week":
        # 每 interval 周，在一周内的指定星期几重复
        weekdays = rule.get("weekdays") or [start.weekday()]
        offsets = sorted((int(w) - week_start) % 7 for w in weekdays)
        ws = week_start_of(start, week_start)
        wk = ws
        while loop_ok(wk) and wk <= range_end:
            for off in offsets:
                d = wk + datetime.timedelta(days=off)
                if d < start:
                    continue
                if d > range_end:
                    break
                if not accept(d):
                    return dates
            wk += datetime.timedelta(weeks=interval)

    elif rtype in ("monthly", "custom_month"):
        step = 1 if rtype == "monthly" else interval
        day = int(rule.get("month_day") or start.day)
        k = 0
        d = _add_months(start, 0, day)
        if d < start:  # 起始月该日不存在(如2月30日)则顺推到下一个月
            k = step
            d = _add_months(start, k, day)
        while loop_ok(d):
            if not accept(d):
                break
            k += step
            d = _add_months(start, k, day)

    elif rtype in ("yearly", "custom_year"):
        step = 1 if rtype == "yearly" else interval
        k = 0
        while True:
            y = start.year + k
            try:
                d = datetime.date(y, start.month, start.day)
            except ValueError:  # 2月29日 -> 平年2月28日
                d = datetime.date(y, start.month, 28)
            it += 1
            if it > MAX_ITER or d > range_end:
                break
            if d >= start:
                if not accept(d):
                    break
            k += step

    return dates
