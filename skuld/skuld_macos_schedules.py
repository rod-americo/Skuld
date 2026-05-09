from __future__ import annotations

import datetime as dt
import plistlib
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from . import skuld_common as common


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


def _compact_interval(seconds: int) -> str:
    if seconds <= 0:
        return ""
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"every {hours} hour{'s' if hours != 1 else ''}"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"every {minutes} minute{'s' if minutes != 1 else ''}"
    return f"every {seconds} second{'s' if seconds != 1 else ''}"


def _parse_hhmm_list(text: str) -> List[tuple[int, int]]:
    result: List[tuple[int, int]] = []
    for raw_part in text.split(","):
        part = raw_part.strip()
        match = re.match(r"^(\d{2}):(\d{2})$", part)
        if not match:
            return []
        value = (int(match.group(1)), int(match.group(2)))
        if value not in result:
            result.append(value)
    return result


def _hhmm_list_text(times: Iterable[tuple[int, int]]) -> str:
    return ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in times)


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


def _calendar_item_signature(item: Dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(item.items()))


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
        return f"{WEEKDAY_NAMES[weekday]} at {hour:02d}:{minute:02d}"
    if "Month" in item:
        month = item["Month"]
        if "Day" in item:
            return f"yearly on {month:02d}-{item['Day']:02d} at {hour:02d}:{minute:02d}"
        return f"yearly in month {month:02d} at {hour:02d}:{minute:02d}"
    if "Day" in item:
        return f"monthly on day {item['Day']} at {hour:02d}:{minute:02d}"
    if "Hour" in item:
        return f"daily at {hour:02d}:{minute:02d}"
    return f"hourly at :{minute:02d}"


def _schedule_from_calendar_items(items: List[Dict[str, int]]) -> str:
    entries = [item for item in items if item]
    if not entries:
        return ""
    if len(entries) == 1:
        return _schedule_from_calendar_item(entries[0])
    if all(set(item.keys()) <= {"Hour", "Minute"} for item in entries):
        times = sorted({(item.get("Hour", 0), item.get("Minute", 0)) for item in entries})
        return f"daily at {_hhmm_list_text(times)}"
    if all(set(item.keys()) <= {"Weekday", "Hour", "Minute"} and "Weekday" in item for item in entries):
        grouped_by_weekdays: Dict[str, List[tuple[int, int]]] = {}
        by_time: Dict[tuple[int, int], List[int]] = {}
        for item in entries:
            time_key = (item.get("Hour", 0), item.get("Minute", 0))
            by_time.setdefault(time_key, []).append(item["Weekday"])
        for time_key, weekdays in by_time.items():
            spec = _weekday_spec_for_display(weekdays)
            if not spec:
                return ""
            grouped_by_weekdays.setdefault(spec, []).append(time_key)
        summaries = []
        for spec, times in grouped_by_weekdays.items():
            summaries.append(f"{spec} at {_hhmm_list_text(sorted(set(times)))}")
        return "; ".join(sorted(summaries))

    grouped: Dict[tuple[tuple[str, int], ...], List[tuple[int, int]]] = {}
    for item in entries:
        base = dict(item)
        base.pop("Hour", None)
        base.pop("Minute", None)
        key = _calendar_item_signature(base)
        grouped.setdefault(key, []).append((item.get("Hour", 0), item.get("Minute", 0)))

    summaries: List[str] = []
    for signature, times in grouped.items():
        base = dict(signature)
        weekday = base.pop("Weekday", None)
        if "Month" in base or ("Day" in base and weekday is None):
            return ""
        time_text = _hhmm_list_text(sorted(set(times)))
        if weekday is None and not base:
            summaries.append(f"daily at {time_text}")
            continue
        if weekday is None:
            return ""
        weekday_spec = _weekday_spec_for_display([weekday])
        if not weekday_spec:
            return ""
        summaries.append(f"{weekday_spec} at {time_text}")

    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]

    combined: Dict[str, List[str]] = {}
    for summary in summaries:
        if " at " not in summary:
            return "; ".join(summaries)
        prefix, time_text = summary.split(" at ", 1)
        combined.setdefault(prefix, []).append(time_text)
    if len(combined) == 1:
        prefix, groups = next(iter(combined.items()))
        times = _parse_hhmm_list(", ".join(groups))
        if times:
            return f"{prefix} at {_hhmm_list_text(times)}"
    return "; ".join(summaries)


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
        if seconds > 0:
            return _compact_interval(seconds)
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
    match = re.match(r"^every (\d+) second(?:s)?$", value, flags=re.IGNORECASE)
    if match:
        seconds = int(match.group(1))
        if seconds <= 0:
            raise RuntimeError("Unsupported --schedule interval. Use a positive interval.")
        return "StartInterval", seconds
    match = re.match(r"^every (\d+) minute(?:s)?$", value, flags=re.IGNORECASE)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0:
            raise RuntimeError("Unsupported --schedule interval. Use a positive interval.")
        return "StartInterval", minutes * 60
    match = re.match(r"^every (\d+) hour(?:s)?$", value, flags=re.IGNORECASE)
    if match:
        hours = int(match.group(1))
        if hours <= 0:
            raise RuntimeError("Unsupported --schedule interval. Use a positive interval.")
        return "StartInterval", hours * 3600
    match = re.match(r"^\*-\*-\* \*:00/(\d{1,2}):00$", value)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0 or minutes > 59:
            raise RuntimeError("Unsupported --schedule interval. Use minutes between 1 and 59.")
        return "StartInterval", minutes * 60
    match = re.match(r"^hourly at :(\d{2})$", value, flags=re.IGNORECASE)
    if match:
        return "StartCalendarInterval", {"Minute": int(match.group(1))}
    match = re.match(r"^\*-\*-\* \*:(\d{2}):(\d{2})$", value)
    if match:
        minute = int(match.group(1))
        second = int(match.group(2))
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Minute": minute}
    match = re.match(r"^daily at ((?:\d{2}:\d{2})(?:,\s*\d{2}:\d{2})*)$", value, flags=re.IGNORECASE)
    if match:
        times = _parse_hhmm_list(match.group(1))
        if not times:
            raise RuntimeError("Unsupported daily schedule format for macOS.")
        if len(times) == 1:
            hour, minute = times[0]
            return "StartCalendarInterval", {"Hour": hour, "Minute": minute}
        return "StartCalendarInterval", [
            {"Hour": hour, "Minute": minute}
            for hour, minute in times
        ]
    match = re.match(r"^\*-\*-\* (\d{2}):(\d{2}):(\d{2})$", value)
    if match:
        hour, minute, second = map(int, match.groups())
        if second != 0:
            raise RuntimeError("Unsupported --schedule seconds. macOS schedule subset requires :00 seconds.")
        return "StartCalendarInterval", {"Hour": hour, "Minute": minute}
    match = re.match(
        r"^([A-Za-z]{3}(?:-[A-Za-z]{3}|(?:,[A-Za-z]{3})*)) at ((?:\d{2}:\d{2})(?:,\s*\d{2}:\d{2})*)$",
        value,
        flags=re.IGNORECASE,
    )
    if match:
        weekdays = _parse_weekday_spec(match.group(1))
        times = _parse_hhmm_list(match.group(2))
        if not weekdays or not times:
            raise RuntimeError("Unsupported weekday schedule format for macOS.")
        if len(weekdays) == 1 and len(times) == 1:
            hour, minute = times[0]
            return "StartCalendarInterval", {"Weekday": weekdays[0], "Hour": hour, "Minute": minute}
        items = []
        for weekday in weekdays:
            for hour, minute in times:
                items.append({"Weekday": weekday, "Hour": hour, "Minute": minute})
        return "StartCalendarInterval", items
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
    match = re.match(r"^monthly on day (\d{1,2}) at (\d{2}):(\d{2})$", value, flags=re.IGNORECASE)
    if match:
        return "StartCalendarInterval", {
            "Day": int(match.group(1)),
            "Hour": int(match.group(2)),
            "Minute": int(match.group(3)),
        }
    raise RuntimeError(
        "Unsupported --schedule for macOS. Supported subset: "
        "'every 30 seconds', 'every 15 minutes', 'daily at 02:30', "
        "'daily at 00:05, 07:05', 'Mon-Fri at 08:00', '*-*-01 00:01:00'."
    )


def humanize_schedule_for_display(schedule: str, timer_persistent: bool, max_width: int = 48) -> str:
    value = (schedule or "").strip()
    if not value:
        return "-"
    match = re.match(
        r"^(every \d+ (?:second|seconds|minute|minutes|hour|hours)|hourly at :\d{2}|daily at (?:\d{2}:\d{2})(?:,\s*\d{2}:\d{2})*|[A-Za-z]{3}(?:-[A-Za-z]{3}|(?:,[A-Za-z]{3})*) at (?:\d{2}:\d{2})(?:,\s*\d{2}:\d{2})*|monthly on day \d{1,2} at \d{2}:\d{2}|yearly on \d{2}-\d{2} at \d{2}:\d{2}|yearly in month \d{2} at \d{2}:\d{2})$",
        value,
        flags=re.IGNORECASE,
    )
    if match:
        return common.clip_text(value, max_width)

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
