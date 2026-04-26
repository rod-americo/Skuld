from __future__ import annotations

import unittest

import skuld_linux_timers as timers


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


if __name__ == "__main__":
    unittest.main()
