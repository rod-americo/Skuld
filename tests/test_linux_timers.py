from __future__ import annotations

from dataclasses import dataclass
import unittest

import skuld_linux_timers as timers


@dataclass
class TimerService:
    name: str
    scope: str = "system"
    schedule: str = ""


class LinuxTimerFormattingTest(unittest.TestCase):
    def test_parse_unit_directive_values_keeps_repeated_keys(self) -> None:
        directives = timers.parse_unit_directive_values(
            """
            # ignored
            OnCalendar=*-*-* 08:00:00
            OnCalendar=*-*-* 17:00:00
            OnBootSec=5min
            """
        )

        self.assertEqual(directives["OnCalendar"], ["*-*-* 08:00:00", "*-*-* 17:00:00"])
        self.assertEqual(directives["OnBootSec"], ["5min"])

    def test_duration_formatting(self) -> None:
        self.assertEqual(timers.humanize_systemd_duration("1h 30min"), "1 hour 30 minutes")
        self.assertEqual(timers.compact_systemd_duration("1hour 30minutes"), "1h30m")
        self.assertEqual(timers.compact_systemd_duration("bad value"), "bad value")

    def test_calendar_humanization(self) -> None:
        self.assertEqual(timers.humanize_timer_calendar("*-*-* 02:30:00"), "daily at 02:30")
        self.assertEqual(timers.humanize_timer_calendar("*-*-* *:00/15:00"), "every 15m")
        self.assertEqual(timers.humanize_timer_calendar("Mon..Fri *-*-* 08:00:00"), "Mon-Fri at 08:00")
        self.assertEqual(timers.humanize_timer_calendar("*-*-01 00:01:00"), "monthly on day 1 at 00:01")

    def test_summarize_calendar_phrases_merges_matching_prefixes(self) -> None:
        self.assertEqual(
            timers.summarize_calendar_phrases(["daily at 08:00", "daily at 12:00", "daily at 18:00", "daily at 22:00"]),
            "daily at 08:00, 12:00, 18:00, +1",
        )

    def test_timer_triggers_read_live_timer_directives(self) -> None:
        service = TimerService("api", scope="user")

        def systemctl_cat(unit: str, scope: str = "system") -> str:
            self.assertEqual((unit, scope), ("api.timer", "user"))
            return "OnCalendar=*-*-* 08:00:00\nOnCalendar=*-*-* 12:00:00\n"

        result = timers.timer_triggers_for_display(
            service,
            unit_exists=lambda unit, scope="system": unit == "api.timer" and scope == "user",
            systemctl_cat=systemctl_cat,
            schedule_for_display=lambda _service: "",
            clip_text=lambda text, _width: text,
        )

        self.assertEqual(result, "daily at 08:00, 12:00")

    def test_timer_triggers_fall_back_to_registry_schedule(self) -> None:
        service = TimerService("api", schedule="*-*-* 02:30:00")

        result = timers.timer_triggers_for_display(
            service,
            unit_exists=lambda _unit, scope="system": False,
            systemctl_cat=lambda _unit, scope="system": "",
            schedule_for_display=lambda item: item.schedule,
            clip_text=lambda text, _width: text,
        )

        self.assertEqual(result, "daily at 02:30")

    def test_read_timer_persistent_uses_unit_file_fallback(self) -> None:
        result = timers.read_timer_persistent(
            "api",
            unit_exists=lambda unit, scope="system": unit == "api.timer",
            systemctl_show=lambda _unit, _props, scope="system": {},
            systemctl_cat=lambda _unit, scope="system": "Persistent=false\n",
            parse_bool=lambda value, default=True: value == "true",
        )

        self.assertFalse(result)

    def test_read_timer_next_and_last_run_normalize_empty_values(self) -> None:
        self.assertEqual(
            timers.read_timer_next_run(
                "api",
                systemctl_show=lambda _unit, _props, scope="system": {"NextElapseUSecRealtime": "n/a"},
            ),
            "-",
        )
        self.assertEqual(
            timers.read_timer_last_run(
                "api",
                systemctl_show=lambda _unit, _props, scope="system": {"LastTriggerUSec": "2026-04-26 10:00:00"},
            ),
            "2026-04-26 10:00:00",
        )


if __name__ == "__main__":
    unittest.main()
