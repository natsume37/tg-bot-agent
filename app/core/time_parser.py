from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def parse_spent_at(value: str | None, timezone_name: str) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass

    tz = ZoneInfo(timezone_name)
    now_local = datetime.now(tz)

    day_shift = 0
    if "前天" in text:
        day_shift = -2
    elif "昨天" in text:
        day_shift = -1
    elif "明天" in text:
        day_shift = 1
    elif "后天" in text:
        day_shift = 2

    target_date = (now_local + timedelta(days=day_shift)).date()

    hour = 12
    minute = 0

    if "凌晨" in text:
        hour = 2
    elif "早上" in text or "清晨" in text or "上午" in text:
        hour = 8
    elif "中午" in text:
        hour = 12
    elif "下午" in text:
        hour = 15
    elif "傍晚" in text:
        hour = 18
    elif "晚上" in text or "今晚" in text:
        hour = 20

    local_dt = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=hour,
        minute=minute,
        second=0,
        tzinfo=tz,
    )
    return local_dt.replace(tzinfo=None)
