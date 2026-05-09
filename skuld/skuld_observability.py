from __future__ import annotations

import os
import sys
from typing import Any


SECRET_MARKERS = ("password", "secret", "token", "key")


def debug_enabled() -> bool:
    value = (os.environ.get("SKULD_DEBUG") or "").strip().lower()
    return value in {"1", "true", "yes", "on", "debug"}


def redact_field(name: str, value: Any) -> str:
    lower_name = name.lower()
    if any(marker in lower_name for marker in SECRET_MARKERS):
        return "<redacted>"
    return str(value)


def debug(event: str, **fields: Any) -> None:
    if not debug_enabled():
        return
    parts = [f"event={event}"]
    for name in sorted(fields):
        parts.append(f"{name}={redact_field(name, fields[name])}")
    print("[debug] " + " ".join(parts), file=sys.stderr)
