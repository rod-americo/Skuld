from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import skuld_macos_runtime as runtime


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class MacOSRuntimeStatsTest(unittest.TestCase):
    def test_reads_event_stats_and_restart_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "worker.jsonl"
            event_path.write_text(
                "\n".join(
                    [
                        json.dumps({"event": "start", "ts": "2026-04-26T08:00:00Z", "pid": 10}),
                        "not json",
                        json.dumps({"event": "end", "exit_status": 0}),
                        json.dumps({"event": "start", "ts": "2026-04-26T09:00:00Z", "pid": 11}),
                    ]
                ),
                encoding="utf-8",
            )

            stats = runtime.read_event_stats(event_path, schedule="", restart="on-failure")

        self.assertEqual(stats["executions"], 2)
        self.assertEqual(stats["restarts"], 1)
        self.assertEqual(stats["last_exit_status"], "0")
        self.assertRegex(str(stats["last_run"]), r"2026-04-26")

    def test_scheduled_or_no_restart_policy_reports_zero_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "job.jsonl"
            event_path.write_text(
                json.dumps({"event": "start", "ts": "2026-04-26T08:00:00Z"}) + "\n"
                + json.dumps({"event": "start", "ts": "2026-04-26T09:00:00Z"}) + "\n",
                encoding="utf-8",
            )

            scheduled = runtime.read_event_stats(event_path, schedule="daily", restart="on-failure")
            no_restart = runtime.read_event_stats(event_path, schedule="", restart="no")

        self.assertEqual(scheduled["restarts"], 0)
        self.assertEqual(no_restart["restarts"], 0)

    def test_updates_runtime_stats_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "runtime_stats.json"
            calls = []

            services = runtime.update_runtime_stats(
                runtime_file,
                lambda: calls.append("ensure"),
                "worker",
                {"executions": 3, "restarts": 1},
            )

            payload = json.loads(runtime_file.read_text(encoding="utf-8"))

        self.assertEqual(calls, ["ensure"])
        self.assertEqual(services["worker"]["executions"], 3)
        self.assertEqual(payload["services"]["worker"]["restarts"], 1)

    def test_reads_recent_run_root_pids_from_events(self) -> None:
        events = [
            {"event": "start", "pid": 1},
            {"event": "end", "pid": 1},
            {"event": "start", "child_pid": 2},
            {"event": "start", "pid": "bad"},
            {"event": "start", "pid": 3},
        ]

        self.assertEqual(runtime.read_recent_run_root_pids(events, limit=2), [3, 2])


class MacOSRuntimeLogsTest(unittest.TestCase):
    def test_tail_file_uses_tail_command(self) -> None:
        calls = []

        def run_cmd(cmd, check=True, capture=False):
            calls.append((cmd, check, capture))
            return completed()

        runtime.tail_file(run_cmd, Path("/tmp/out.log"), 20, True)

        self.assertEqual(calls, [(["tail", "-n", "20", "-f", "/tmp/out.log"], False, False)])

    def test_log_paths_for_managed_service_uses_log_dir(self) -> None:
        stdout_path, stderr_path = runtime.log_paths_for_service(
            managed_by_skuld=True,
            log_dir="/tmp/skuld/logs/worker",
            plist_path=Path("/missing.plist"),
        )

        self.assertEqual(stdout_path, Path("/tmp/skuld/logs/worker/stdout.log"))
        self.assertEqual(stderr_path, Path("/tmp/skuld/logs/worker/stderr.log"))

    def test_log_paths_for_external_service_reads_plist_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = Path(tmp) / "worker.out"
            stderr = Path(tmp) / "worker.err"
            plist = Path(tmp) / "worker.plist"
            plist.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>StandardOutPath</key>
  <string>{stdout}</string>
  <key>StandardErrorPath</key>
  <string>{stderr}</string>
</dict>
</plist>
""",
                encoding="utf-8",
            )

            paths = runtime.log_paths_for_service(
                managed_by_skuld=False,
                log_dir="",
                plist_path=plist,
            )

        self.assertEqual(paths, (stdout, stderr))


if __name__ == "__main__":
    unittest.main()
