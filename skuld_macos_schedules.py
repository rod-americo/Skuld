from __future__ import annotations

import datetime as dt
import plistlib
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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
WEEKDAY_NAMES = {
    0: "Sun",
    1: "Mon",
    2: "Tue",
    3: "Wed",
    4: "Thu",
    5: "Fri",
    6: "Sat",
}


def _parse_weekday_spec(spec: str) -> List[int]:
    value = spec.strip()
    if not value:
        return []
    if "-" in value and "," not in value:
        start_name, end_name = value.split("-", 1)
        start = WEEKDAY_MAP.get(start_name.strip().lower())
        end = WEEKDAY_MAP.get(end_name.strip().lower())
        if start is None or end is None:
            return []
        if start <= end:
            return list(range(start, end + 1))
        return list(range(start, 7)) + list(range(0, end + 1))
    result: List[int] = []
    for part in value.split(","):
        weekday = WEEKDAY_MAP.get(part.strip().lower())
        if weekday is None or weekday in result:
            continue
        result.append(weekday)
    return result


def _weekday_spec_for_display(weekdays: Iterable[int]) -> str:
    values = sorted(set(weekdays))
    if not values:
        return ""
    if values == [0, 1, 2, 3, 4, 5, 6]:
        return "daily"
    if len(values) > 1 and values == list(range(values[0], values[-1] + 1)):
        return f"{WEEKDAY_NAMES[values[0]]}-{WEEKDAY_NAMES[values[-1]]}"
    return ",".join(WEEKDAY_NAMES[value] for value in values)


def _normalize_calendar_item(item: object) -> Dict[str, int]:
    if not isinstance(item, dict):
        return {}
    result: Dict[str, int] = {}
    for key in ("Month", "Day", "Weekday", "Hour", "Minute"):
        raw_value = item.get(key)
        if raw_value in (None, ""):
            continue
        try:
            result[key] = int(raw_value)
        except (TypeError, ValueError):
            return {}
    weekday = result.get("Weekday")
    if weekday == 7:
        result["Weekday"] = 0
    return result


def _schedule_from_calendar_item(item: Dict[str, int]) -> str:
    hour = item.get("Hour", 0)
    minute = item.get("Minute", 0)
    if "Weekday" in item:
        weekday = item["Weekday"]
        if weekday not in WEEKDAY_NAMES:
            return ""
        return f"{WEEKDAY_NAMES[weekday]} *-*-* {hour:02d}:{minute:02d}:00"
    if "Day" in item:
        return f"*-*-{item['Day']:02d} {hour:02d}:{minute:02d}:00"
    if "Hour" in item:
        return f"*-*-* {hour:02d}:{minute:02d}:00"
    return f"*-*-* *:{minute:02d}:00"


def _schedule_from_calendar_items(items: List[Dict[str, int]]) -> str:
    entries = [item for item in items if item]
    if not entries:
        return ""
    if len(entries) == 1:
        return _schedule_from_calendar_item(entries[0])
    base_items = []
    weekdays: List[int] = []
    for item in entries:
        if "Weekday" not in item:
            return ""
        weekdays.append(item["Weekday"])
        base = dict(item)
        base.pop("Weekday", None)
        base_items.append(base)
    first = base_items[0]
    if any(base != first for base in base_items[1:]):
        return ""
    spec = _weekday_spec_for_display(weekdays)
    if spec == "daily":
        return _schedule_from_calendar_item(first)
    if not spec:
        return ""
    hour = first.get("Hour", 0)
    minute = first.get("Minute", 0)
    return f"{spec} *-*-* {hour:02d}:{minute:02d}:00"


def schedule_from_plist(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return ""
    start_interval = plist.get("StartInterval")
    if start_interval not in (None, ""):
        try:
            seconds = int(start_interval)
        except (TypeError, ValueError):
            seconds = 0
        if seconds > 0 and seconds % 60 == 0:
            minutes = seconds // 60
            if 1 <= minutes <= 59:
                return f"*-*-* *:00/{minutes}:00"
    start_calendar = plist.get("StartCalendarInterval")
    if isinstance(start_calendar, dict):
        return _schedule_from_calendar_item(_normalize_calendar_item(start_calendar))
    if isinstance(start_calendar, list):
        return _schedule_from_calendar_items(
            [_normalize_calendar_item(item) for item in start_calendar]
        )
    return ""


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
    match = re.match(r"^([A-Za-z]{3}(?:-[A-Za-z]{3}|(?:,[A-Za-z]{3})*)) \*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        weekdays = _parse_weekday_spec(match.group(1))
        if not weekdays:
            raise RuntimeError("Unsupported --schedule weekday spec for macOS.")
        if int(match.group(4)) != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        hour = int(match.group(2))
        minute = int(match.group(3))
        if len(weekdays) == 1:
            return "StartCalendarInterval", {"Weekday": weekdays[0], "Hour": hour, "Minute": minute}
        return "StartCalendarInterval", [
            {"Weekday": weekday, "Hour": hour, "Minute": minute}
            for weekday in weekdays
        ]
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
                match = re.match(r"^([A-Za-z]{3}(?:-[A-Za-z]{3}|(?:,[A-Za-z]{3})*)) \*-\*-\* (\d{2}):(\d{2}):00$", value)
                if match:
                    summary = f"{match.group(1)} at {match.group(2)}:{match.group(3)}"
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


def _calendar_items_for_compute(data: object) -> List[Dict[str, int]]:
    if isinstance(data, dict):
        return [dict(data)]
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, dict)]
    return []


def _candidate_matches(candidate: dt.datetime, info: Dict[str, int]) -> bool:
    if "Minute" in info and candidate.minute != info["Minute"]:
        return False
    if "Hour" in info and candidate.hour != info["Hour"]:
        return False
    if "Day" in info and candidate.day != info["Day"]:
        return False
    if "Weekday" in info:
        candidate_weekday = (candidate.weekday() + 1) % 7
        if candidate_weekday != info["Weekday"]:
            return False
    if "Month" in info and candidate.month != info["Month"]:
        return False
    return True


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
    items = _calendar_items_for_compute(data)
    if not items:
        return "-"
    for day_offset in range(0, 366 * 2):
        candidate_date = now.date() + dt.timedelta(days=day_offset)
        for minute_of_day in range(1440):
            candidate = dt.datetime.combine(
                candidate_date,
                dt.time(hour=minute_of_day // 60, minute=minute_of_day % 60, tzinfo=now.tzinfo),
            )
            if candidate <= now:
                continue
            if any(_candidate_matches(candidate, info) for info in items):
                return candidate.strftime("%Y-%m-%d %H:%M")
    return "-"
