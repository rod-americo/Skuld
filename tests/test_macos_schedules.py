from __future__ import annotations

import datetime as dt
import unittest

import skuld_macos_schedules as schedules


class MacScheduleTest(unittest.TestCase):
    def test_parse_supported_schedule_subset(self) -> None:
        self.assertEqual(schedules.parse_schedule("*-*-* *:00/15:00"), ("StartInterval", 900))
        self.assertEqual(schedules.parse_schedule("*-*-* 02:30:00"), ("StartCalendarInterval", {"Hour": 2, "Minute": 30}))
        self.assertEqual(
            schedules.parse_schedule("Mon *-*-* 08:00:00"),
            ("StartCalendarInterval", {"Weekday": 1, "Hour": 8, "Minute": 0}),
        )

    def test_rejects_unsupported_seconds(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires :00 seconds"):
            schedules.parse_schedule("*-*-* 02:30:01")

    def test_humanize_schedule_for_display(self) -> None:
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-* *:00/15:00", True), "every 15 minutes")
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-* *:05:00", True), "hourly at :05")
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-01 00:01:00", True), "monthly on day 1 at 00:01")

    def test_compute_next_run_for_daily_schedule(self) -> None:
        now = dt.datetime(2026, 4, 25, 1, 10, tzinfo=dt.timezone.utc)

        self.assertEqual(schedules.compute_next_run("*-*-* 02:30:00", now=now), "2026-04-25 02:30")


if __name__ == "__main__":
    unittest.main()
