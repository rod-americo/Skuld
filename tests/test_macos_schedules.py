from __future__ import annotations

import datetime as dt
import plistlib
import tempfile
import unittest
from pathlib import Path

from skuld import skuld_macos_schedules as schedules


class MacScheduleTest(unittest.TestCase):
    def test_parse_supported_schedule_subset(self) -> None:
        self.assertEqual(schedules.parse_schedule("*-*-* *:00/15:00"), ("StartInterval", 900))
        self.assertEqual(schedules.parse_schedule("*-*-* 02:30:00"), ("StartCalendarInterval", {"Hour": 2, "Minute": 30}))
        self.assertEqual(schedules.parse_schedule("every 30 seconds"), ("StartInterval", 30))
        self.assertEqual(schedules.parse_schedule("every 2 minutes"), ("StartInterval", 120))
        self.assertEqual(
            schedules.parse_schedule("daily at 00:05, 07:05, 13:05, 19:05"),
            (
                "StartCalendarInterval",
                [
                    {"Hour": 0, "Minute": 5},
                    {"Hour": 7, "Minute": 5},
                    {"Hour": 13, "Minute": 5},
                    {"Hour": 19, "Minute": 5},
                ],
            ),
        )
        self.assertEqual(
            schedules.parse_schedule("Mon *-*-* 08:00:00"),
            ("StartCalendarInterval", {"Weekday": 1, "Hour": 8, "Minute": 0}),
        )
        self.assertEqual(
            schedules.parse_schedule("Mon-Fri *-*-* 08:00:00"),
            (
                "StartCalendarInterval",
                [
                    {"Weekday": 1, "Hour": 8, "Minute": 0},
                    {"Weekday": 2, "Hour": 8, "Minute": 0},
                    {"Weekday": 3, "Hour": 8, "Minute": 0},
                    {"Weekday": 4, "Hour": 8, "Minute": 0},
                    {"Weekday": 5, "Hour": 8, "Minute": 0},
                ],
            ),
        )

    def test_rejects_unsupported_seconds(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires :00 seconds"):
            schedules.parse_schedule("*-*-* 02:30:01")

    def test_humanize_schedule_for_display(self) -> None:
        self.assertEqual(schedules.humanize_schedule_for_display("every 30 seconds", True), "every 30 seconds")
        self.assertEqual(schedules.humanize_schedule_for_display("every 2 minutes", True), "every 2 minutes")
        self.assertEqual(
            schedules.humanize_schedule_for_display("daily at 00:05, 07:05, 13:05, 19:05", True),
            "daily at 00:05, 07:05, 13:05, 19:05",
        )
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-* *:00/15:00", True), "every 15 minutes")
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-* *:05:00", True), "hourly at :05")
        self.assertEqual(schedules.humanize_schedule_for_display("*-*-01 00:01:00", True), "monthly on day 1 at 00:01")
        self.assertEqual(schedules.humanize_schedule_for_display("Mon-Fri *-*-* 08:00:00", True), "Mon-Fri at 08:00")

    def test_compute_next_run_for_daily_schedule(self) -> None:
        now = dt.datetime(2026, 4, 25, 1, 10, tzinfo=dt.timezone.utc)

        self.assertEqual(schedules.compute_next_run("*-*-* 02:30:00", now=now), "2026-04-25 02:30")

    def test_compute_next_run_for_weekday_range_schedule(self) -> None:
        now = dt.datetime(2026, 4, 24, 20, 0, tzinfo=dt.timezone.utc)

        self.assertEqual(
            schedules.compute_next_run("Mon-Fri *-*-* 08:00:00", now=now),
            "2026-04-27 08:00",
        )

    def test_compute_next_run_for_multi_daily_schedule(self) -> None:
        now = dt.datetime(2026, 5, 1, 7, 6, tzinfo=dt.timezone.utc)

        self.assertEqual(
            schedules.compute_next_run("daily at 00:05, 07:05, 13:05, 19:05", now=now),
            "2026-05-01 13:05",
        )

    def test_schedule_from_plist_reads_short_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "worker.plist"
            path.write_bytes(plistlib.dumps({"StartInterval": 30}))

            self.assertEqual(schedules.schedule_from_plist(path), "every 30 seconds")

    def test_schedule_from_plist_reads_minute_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "worker.plist"
            path.write_bytes(plistlib.dumps({"StartInterval": 120}))

            self.assertEqual(schedules.schedule_from_plist(path), "every 2 minutes")

    def test_schedule_from_plist_reads_daily_calendar_item(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "worker.plist"
            path.write_bytes(
                plistlib.dumps({"StartCalendarInterval": {"Hour": 4, "Minute": 0}})
            )

            self.assertEqual(schedules.schedule_from_plist(path), "daily at 04:00")

    def test_schedule_from_plist_reads_multi_daily_times(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "worker.plist"
            path.write_bytes(
                plistlib.dumps(
                    {
                        "StartCalendarInterval": [
                            {"Hour": 0, "Minute": 5},
                            {"Hour": 7, "Minute": 5},
                            {"Hour": 13, "Minute": 5},
                            {"Hour": 19, "Minute": 5},
                        ]
                    }
                )
            )

            self.assertEqual(
                schedules.schedule_from_plist(path),
                "daily at 00:05, 07:05, 13:05, 19:05",
            )

    def test_schedule_from_plist_reads_weekday_range(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "worker.plist"
            path.write_bytes(
                plistlib.dumps(
                    {
                        "StartCalendarInterval": [
                            {"Weekday": 1, "Hour": 8, "Minute": 0},
                            {"Weekday": 2, "Hour": 8, "Minute": 0},
                            {"Weekday": 3, "Hour": 8, "Minute": 0},
                            {"Weekday": 4, "Hour": 8, "Minute": 0},
                            {"Weekday": 5, "Hour": 8, "Minute": 0},
                        ]
                    }
                )
            )

            self.assertEqual(
                schedules.schedule_from_plist(path),
                "Mon-Fri at 08:00",
            )


if __name__ == "__main__":
    unittest.main()
