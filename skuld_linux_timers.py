from __future__ import annotations

import re
from typing import Dict, List, Optional, Set


SYSTEMD_DURATION_LABELS = {
    "us": ("microsecond", "microseconds"),
    "usec": ("microsecond", "microseconds"),
    "ms": ("millisecond", "milliseconds"),
    "msec": ("millisecond", "milliseconds"),
    "s": ("second", "seconds"),
    "sec": ("second", "seconds"),
    "secs": ("second", "seconds"),
    "second": ("second", "seconds"),
    "seconds": ("second", "seconds"),
    "m": ("minute", "minutes"),
    "min": ("minute", "minutes"),
    "mins": ("minute", "minutes"),
    "minute": ("minute", "minutes"),
    "minutes": ("minute", "minutes"),
    "h": ("hour", "hours"),
    "hr": ("hour", "hours"),
    "hrs": ("hour", "hours"),
    "hour": ("hour", "hours"),
    "hours": ("hour", "hours"),
    "d": ("day", "days"),
    "day": ("day", "days"),
    "days": ("day", "days"),
    "w": ("week", "weeks"),
    "week": ("week", "weeks"),
    "weeks": ("week", "weeks"),
    "month": ("month", "months"),
    "months": ("month", "months"),
    "y": ("year", "years"),
    "year": ("year", "years"),
    "years": ("year", "years"),
}

SYSTEMD_DURATION_SHORT = {
    "us": "us",
    "usec": "us",
    "ms": "ms",
    "msec": "ms",
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "m": "m",
    "min": "m",
    "mins": "m",
    "minute": "m",
    "minutes": "m",
    "h": "h",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
    "d": "d",
    "day": "d",
    "days": "d",
    "w": "w",
    "week": "w",
    "weeks": "w",
}


def parse_unit_directive_values(unit_text: str) -> Dict[str, List[str]]:
    directives: Dict[str, List[str]] = {}
    for raw in unit_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        directives.setdefault(key, []).append(value.strip())
    return directives


def humanize_count_and_unit(amount_text: str, singular: str, plural: str) -> str:
    try:
        amount = float(amount_text)
    except ValueError:
        return f"{amount_text} {plural}"
    if amount.is_integer():
        whole = int(amount)
        return f"{whole} {singular if whole == 1 else plural}"
    return f"{amount_text} {plural}"


def humanize_systemd_duration(value: str) -> str:
    raw = re.sub(r"\s+", " ", (value or "").strip())
    if not raw:
        return "-"
    if re.sub(r"\d+(?:\.\d+)?[A-Za-z]+\s*", "", raw).strip():
        return raw

    parts: List[str] = []
    for amount_text, unit in re.findall(r"(\d+(?:\.\d+)?)([A-Za-z]+)", raw):
        labels = SYSTEMD_DURATION_LABELS.get(unit.lower())
        if not labels:
            return raw
        singular, plural = labels
        parts.append(humanize_count_and_unit(amount_text, singular, plural))
    return " ".join(parts) if parts else raw


def compact_systemd_duration(value: str) -> str:
    raw = re.sub(r"\s+", "", (value or "").strip().lower())
    if not raw:
        return "-"

    parts: List[str] = []
    cursor = 0
    for match in re.finditer(r"(\d+(?:\.\d+)?)([a-z]+)", raw):
        if match.start() != cursor:
            return humanize_systemd_duration(value)
        amount_text, unit = match.groups()
        suffix = SYSTEMD_DURATION_SHORT.get(unit)
        if not suffix:
            return humanize_systemd_duration(value)
        try:
            amount = float(amount_text)
        except ValueError:
            return humanize_systemd_duration(value)
        if amount.is_integer():
            amount_text = str(int(amount))
        parts.append(f"{amount_text}{suffix}")
        cursor = match.end()

    if cursor != len(raw) or not parts:
        return humanize_systemd_duration(value)
    return "".join(parts)


def humanize_calendar_prefix(value: str) -> Optional[str]:
    raw = re.sub(r"\s+", " ", (value or "").strip())
    if not raw or raw == "*-*-*":
        return ""

    match = re.fullmatch(r"([A-Za-z]{3}(?:\.\.[A-Za-z]{3})?(?:,[A-Za-z]{3})*) \*-\*-\*", raw)
    if match:
        return re.sub(r",\s*", ", ", match.group(1).replace("..", "-"))

    match = re.fullmatch(r"\*-\*-(\d{2})", raw)
    if match:
        return f"monthly on day {int(match.group(1))}"

    return None


def with_calendar_prefix(prefix: str, phrase: str) -> str:
    cleaned_prefix = (prefix or "").strip()
    if not cleaned_prefix:
        return phrase
    if phrase.startswith("every "):
        return f"{cleaned_prefix} {phrase}"
    return f"{cleaned_prefix} {phrase}"


def evenly_spaced(values: List[int], cycle: int) -> Optional[int]:
    if len(values) < 2:
        return None
    ordered = sorted(dict.fromkeys(values))
    if len(ordered) < 2:
        return None
    steps = [(ordered[(idx + 1) % len(ordered)] - ordered[idx]) % cycle for idx in range(len(ordered))]
    first = steps[0]
    if first <= 0:
        return None
    if all(step == first for step in steps):
        return first
    return None


def format_short_list(items: List[str], max_items: int = 3) -> str:
    if len(items) <= max_items:
        return ", ".join(items)
    visible = ", ".join(items[:max_items])
    return f"{visible}, +{len(items) - max_items}"


def humanize_timer_calendar(value: str) -> str:
    raw = re.sub(r"\s+", " ", (value or "").strip())
    if not raw:
        return "-"
    normalized = re.sub(r",\s+", ",", raw)
    parts = normalized.split(" ")
    if len(parts) < 2:
        cleaned = raw.replace("..", "-")
        cleaned = re.sub(r",\s*", ", ", cleaned)
        cleaned = re.sub(r"(\d{2}:\d{2}):00\b", r"\1", cleaned)
        return cleaned

    time_expr = parts[-1]
    prefix = humanize_calendar_prefix(" ".join(parts[:-1]))
    if prefix is not None:
        if time_expr == "*:*:00":
            return with_calendar_prefix(prefix, "every minute")

        match = re.fullmatch(r"\*:((?:\d{1,2})(?:,\d{1,2})+):00", time_expr)
        if match:
            minutes = [int(item) for item in match.group(1).split(",")]
            interval = evenly_spaced(minutes, 60)
            if interval is not None:
                start_minute = min(minutes)
                phrase = f"every {interval}m"
                if start_minute != 0:
                    phrase = f"{phrase} from :{start_minute:02d}"
                return with_calendar_prefix(prefix, phrase)
            clock_points = [f":{minute:02d}" for minute in sorted(dict.fromkeys(minutes))]
            return with_calendar_prefix(prefix, f"hourly at {format_short_list(clock_points)}")

        match = re.fullmatch(r"\*:(\d{1,2})/(\d{1,2}):00", time_expr)
        if match:
            start_minute = int(match.group(1))
            every_minutes = int(match.group(2))
            phrase = f"every {every_minutes}m"
            if start_minute != 0:
                phrase = f"{phrase} from :{start_minute:02d}"
            return with_calendar_prefix(prefix, phrase)

        match = re.fullmatch(r"((?:\d{2}:\d{2}:\d{2})(?:,\d{2}:\d{2}:\d{2})+)", time_expr)
        if match:
            times = [item[:5] for item in match.group(1).split(",")]
            base = "daily" if not prefix else prefix
            return f"{base} at {format_short_list(times)}"

        match = re.fullmatch(r"(\d{1,2})/(\d{1,2}):(\d{2}):00", time_expr)
        if match:
            start_hour = int(match.group(1))
            every_hours = int(match.group(2))
            minute = int(match.group(3))
            phrase = f"every {every_hours}h"
            if start_hour != 0 or minute != 0:
                phrase = f"{phrase} from {start_hour:02d}:{minute:02d}"
            return with_calendar_prefix(prefix, phrase)

        match = re.fullmatch(r"\*:(\d{1,2}):00", time_expr)
        if match:
            return with_calendar_prefix(prefix, f"hourly at :{int(match.group(1)):02d}")

        match = re.fullmatch(r"(\d{2}):(\d{2}):00", time_expr)
        if match:
            if not prefix:
                return f"daily at {match.group(1)}:{match.group(2)}"
            if prefix.startswith("monthly on day "):
                return f"{prefix} at {match.group(1)}:{match.group(2)}"
            return f"{prefix} at {match.group(1)}:{match.group(2)}"

    cleaned = raw.replace("..", "-")
    cleaned = re.sub(r",\s*", ", ", cleaned)
    cleaned = re.sub(r"(\d{2}:\d{2}):00\b", r"\1", cleaned)
    return cleaned


def summarize_calendar_phrases(phrases: List[str]) -> str:
    cleaned: List[str] = []
    for phrase in phrases:
        text = (phrase or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]

    grouped: Dict[str, List[str]] = {}
    remainder: List[str] = []
    for phrase in cleaned:
        match = re.fullmatch(r"(.+?) at ((?::\d{2}|\d{2}:\d{2})(?:, (?::\d{2}|\d{2}:\d{2}))*?)", phrase)
        if not match:
            remainder.append(phrase)
            continue
        prefix = match.group(1)
        times = [item.strip() for item in match.group(2).split(",") if item.strip()]
        bucket = grouped.setdefault(prefix, [])
        for time_text in times:
            if time_text not in bucket:
                bucket.append(time_text)

    merged: List[str] = []
    used_prefixes: Set[str] = set()
    for phrase in cleaned:
        match = re.fullmatch(r"(.+?) at ((?::\d{2}|\d{2}:\d{2})(?:, (?::\d{2}|\d{2}:\d{2}))*?)", phrase)
        if not match:
            continue
        prefix = match.group(1)
        if prefix in used_prefixes:
            continue
        used_prefixes.add(prefix)
        merged.append(f"{prefix} at {format_short_list(grouped.get(prefix, []))}")

    merged.extend(remainder)
    if len(merged) == 1:
        return merged[0]
    return f"{merged[0]}; +{len(merged) - 1} more"
