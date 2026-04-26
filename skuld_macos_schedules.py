from __future__ import annotations

import datetime as dt
import re
from typing import Optional, Tuple

import skuld_common as common


WEEKDAY_MAP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


def parse_schedule(schedule: str) -> Tuple[Optional[str], object]:
    value = (schedule or "").strip()
    if not value:
        return None, None
    match = re.match(r"^\*-\*-\* \*:00/(\d{1,2}):00$", value)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0 or minutes > 59:
            raise RuntimeError("Unsupported --schedule interval. Use minutes between 1 and 59.")
        return "StartInterval", minutes * 60
    match = re.match(r"^\*-\*-\* \*:(\d{2}):(\d{2})$", value)
    if match:
        minute = int(match.group(1))
        second = int(match.group(2))
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Minute": minute}
    match = re.match(r"^\*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        hour, minute, second = map(int, match.groups())
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Hour": hour, "Minute": minute}
    match = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        weekday, hour, minute, second = match.groups()
        if int(second) != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Weekday": WEEKDAY_MAP[weekday.lower()], "Hour": int(hour), "Minute": int(minute)}
    match = re.match(r"^\*-\*-(\d{2}) (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        day, hour, minute, second = map(int, match.groups())
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Day": day, "Hour": hour, "Minute": minute}
    raise RuntimeError(
        "Unsupported --schedule for macOS. Supported subset: "
        "'*-*-* *:00/15:00', '*-*-* *:05:00', '*-*-* 02:30:00', "
        "'Mon *-*-* 08:00:00', '*-*-01 00:01:00'."
    )


def humanize_schedule_for_display(schedule: str, timer_persistent: bool, max_width: int = 48) -> str:
    value = (schedule or "").strip()
    if not value:
        return "-"

    match = re.match(r"^\*-\*-\* \*:00/(\d{1,2}):00$", value)
    if match:
        minutes = int(match.group(1))
        summary = f"every {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        match = re.match(r"^\*-\*-\* \*:(\d{2}):00$", value)
        if match:
            summary = f"hourly at :{match.group(1)}"
        else:
            match = re.match(r"^\*-\*-\* (\d{2}):(\d{2}):00$", value)
            if match:
                summary = f"daily at {match.group(1)}:{match.group(2)}"
            else:
                match = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \*-\*-\* (\d{2}):(\d{2}):00$", value)
                if match:
                    summary = f"{match.group(1)} at {match.group(2)}:{match.group(3)}"
                else:
                    match = re.match(r"^\*-\*-(\d{2}) (\d{2}):(\d{2}):00$", value)
                    if match:
                        summary = f"monthly on day {int(match.group(1))} at {match.group(2)}:{match.group(3)}"
                    else:
                        summary = value

    return common.clip_text(summary, max_width)


def compute_next_run(schedule: str, now: Optional[dt.datetime] = None) -> str:
    if not schedule:
        return "-"
    now = now or dt.datetime.now().astimezone()
    sched_type, data = parse_schedule(schedule)
    if sched_type == "StartInterval":
        seconds = int(data)
        epoch = int(now.timestamp())
        next_epoch = ((epoch // seconds) + 1) * seconds
        return dt.datetime.fromtimestamp(next_epoch, tz=now.tzinfo).strftime("%Y-%m-%d %H:%M")
    if sched_type != "StartCalendarInterval":
        return "-"
    info = dict(data)
    for offset in range(1, 366 * 2):
        candidate_date = now.date() + dt.timedelta(days=offset // 1440)
        for minute_of_day in range(1440):
            candidate = dt.datetime.combine(
                candidate_date,
                dt.time(hour=minute_of_day // 60, minute=minute_of_day % 60, tzinfo=now.tzinfo),
            )
            if candidate <= now:
                continue
            if "Minute" in info and candidate.minute != info["Minute"]:
                continue
            if "Hour" in info and candidate.hour != info["Hour"]:
                continue
            if "Day" in info and candidate.day != info["Day"]:
                continue
            if "Weekday" in info:
                candidate_weekday = (candidate.weekday() + 1) % 7
                if candidate_weekday != info["Weekday"]:
                    continue
            if "Month" in info and candidate.month != info["Month"]:
                continue
            return candidate.strftime("%Y-%m-%d %H:%M")
    return "-"
