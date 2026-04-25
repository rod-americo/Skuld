from __future__ import annotations

import argparse
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import skuld_macos as macos
from tests.helpers import IsolatedMacState


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class MacRegistryTest(unittest.TestCase):
    def test_load_registry_normalizes_defaults_and_runtime_files(self) -> None:
        with IsolatedMacState(macos) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            state.registry.write_text(
                json.dumps(
                    [
                        {
                            "name": "com.example.worker",
                            "exec_cmd": "/bin/worker",
                            "description": "Worker",
                            "display_name": "worker",
                            "id": 0,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            [service] = macos.load_registry(write_back=True)
            self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
            self.assertEqual(service.scope, "daemon")
            self.assertEqual(service.backend, "launchd")
            self.assertEqual(service.id, 1)
            self.assertTrue(state.stats.exists())
            self.assertTrue(state.registry.read_text(encoding="utf-8").endswith("\n"))

    def test_load_registry_does_not_write_by_default(self) -> None:
        with IsolatedMacState(macos) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(
                [
                    {
                        "name": "com.example.worker",
                        "exec_cmd": "/bin/worker",
                        "description": "Worker",
                        "display_name": "worker",
                        "id": 0,
                        "ignored": "left-alone",
                    }
                ]
            )
            state.registry.write_text(raw, encoding="utf-8")

            [service] = macos.load_registry()

            self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
            self.assertEqual(service.id, 1)
            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_agent_registry_entry_cannot_store_user(self) -> None:
        with IsolatedMacState(macos) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            state.registry.write_text(
                json.dumps(
                    [
                        {
                            "name": "agent",
                            "exec_cmd": "/bin/agent",
                            "description": "Agent",
                            "display_name": "agent",
                            "scope": "agent",
                            "user": "someone",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "'user' is only valid for daemon scope"):
                macos.load_registry()


class MacCommandBehaviorTest(unittest.TestCase):
    def test_list_does_not_persist_registry_normalization(self) -> None:
        with IsolatedMacState(macos) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(
                [
                    {
                        "name": "com.example.Worker",
                        "exec_cmd": "/usr/bin/worker",
                        "description": "Worker",
                        "display_name": "worker",
                        "id": 0,
                        "ignored": "left-alone",
                    }
                ]
            )
            state.registry.write_text(raw, encoding="utf-8")

            with patch.object(macos, "read_event_stats", return_value={}), patch.object(
                macos, "read_pid", return_value=0
            ), patch.object(
                macos, "read_cpu_memory", return_value={"cpu": "-", "memory": "-"}
            ), patch.object(
                macos, "service_loaded", return_value=False
            ), patch.object(
                macos, "read_ports", return_value="-"
            ), patch.object(
                macos, "render_host_panel"
            ), patch.object(
                macos, "render_table"
            ), redirect_stdout(io.StringIO()):
                macos.list_services_compact()

            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_track_captures_launchd_metadata_as_external_job(self) -> None:
        with IsolatedMacState(macos):
            entry = macos.DiscoverableService(1, "com.example.Worker", "-", "0")
            raw = """
            path = /Users/me/Library/LaunchAgents/com.example.Worker.plist
            program = /usr/bin/worker
            state = running
            """
            with patch.object(macos, "discover_launchd_services", return_value=[entry]), patch.object(
                macos, "launchctl_print_service_raw", return_value=raw
            ), redirect_stdout(io.StringIO()):
                macos.track(argparse.Namespace(targets=["1"], alias="worker"))

            [service] = macos.load_registry()
            self.assertEqual(service.name, "com.example.Worker")
            self.assertEqual(service.display_name, "worker")
            self.assertEqual(service.exec_cmd, "/usr/bin/worker")
            self.assertEqual(service.plist_path_hint, "/Users/me/Library/LaunchAgents/com.example.Worker.plist")
            self.assertFalse(service.managed_by_skuld)
            self.assertEqual(service.scope, "agent")

    def test_start_unscheduled_job_bootstraps_and_kickstarts(self) -> None:
        with IsolatedMacState(macos):
            service = macos.ManagedService("worker", "/bin/worker", "Worker", display_name="worker", scope="agent", id=1)
            macos.save_registry([service])
            calls: list[str] = []

            def fake_kickstart(service, kill_existing=False):
                calls.append(f"kickstart:{kill_existing}")
                return completed()

            with patch.object(macos, "bootstrap_service", side_effect=lambda _svc: calls.append("bootstrap")), patch.object(
                macos, "kickstart_service", side_effect=fake_kickstart
            ), redirect_stdout(io.StringIO()):
                macos.start_stop(argparse.Namespace(targets=["worker"], name_flag=None, id_flag=None), "start")

            self.assertEqual(calls, ["bootstrap", "kickstart:False"])

    def test_start_scheduled_job_does_not_kickstart_immediately(self) -> None:
        with IsolatedMacState(macos):
            service = macos.ManagedService(
                "scheduled",
                "/bin/scheduled",
                "Scheduled",
                display_name="scheduled",
                scope="agent",
                schedule="daily",
                id=1,
            )
            macos.save_registry([service])
            with patch.object(macos, "bootstrap_service") as bootstrap, patch.object(
                macos, "kickstart_service"
            ) as kickstart, redirect_stdout(io.StringIO()):
                macos.start_stop(argparse.Namespace(targets=["scheduled"], name_flag=None, id_flag=None), "start")

            bootstrap.assert_called_once()
            kickstart.assert_not_called()

    def test_restart_boots_out_terminates_and_kickstarts_with_kill(self) -> None:
        with IsolatedMacState(macos):
            service = macos.ManagedService("worker", "/bin/worker", "Worker", display_name="worker", scope="agent", id=1)
            macos.save_registry([service])
            calls: list[tuple[str, object]] = []

            def fake_kickstart(service, kill_existing=False):
                calls.append(("kickstart", kill_existing))
                return completed()

            with patch.object(macos, "read_pid", return_value=42), patch.object(
                macos, "read_recent_run_root_pids", return_value=[43]
            ), patch.object(
                macos, "bootout_service", side_effect=lambda _svc: calls.append(("bootout", None))
            ), patch.object(
                macos, "terminate_process_tree", side_effect=lambda pid: calls.append(("terminate", pid))
            ), patch.object(
                macos, "bootstrap_service", side_effect=lambda _svc: calls.append(("bootstrap", None))
            ), patch.object(
                macos, "kickstart_service", side_effect=fake_kickstart
            ), redirect_stdout(io.StringIO()):
                macos.restart(argparse.Namespace(targets=["worker"], name_flag=None, id_flag=None))

            self.assertEqual(
                calls,
                [
                    ("bootout", None),
                    ("terminate", 42),
                    ("terminate", 43),
                    ("bootstrap", None),
                    ("kickstart", True),
                ],
            )

    def test_logs_reject_external_tracked_jobs(self) -> None:
        with IsolatedMacState(macos):
            service = macos.ManagedService(
                "com.example.Worker",
                "/usr/bin/worker",
                "Worker",
                display_name="worker",
                managed_by_skuld=False,
                scope="agent",
                id=1,
            )
            macos.save_registry([service])

            with self.assertRaisesRegex(RuntimeError, "only available for jobs created by skuld"):
                macos.logs(
                    argparse.Namespace(
                        name="worker",
                        name_flag=None,
                        id_flag=None,
                        lines_pos=None,
                        lines=50,
                        follow=False,
                        since=None,
                        timer=False,
                        output="short",
                        plain=False,
                    )
                )

    def test_logs_tail_stdout_and_stderr_for_managed_jobs(self) -> None:
        with IsolatedMacState(macos) as state:
            log_dir = state.root / "logs" / "worker"
            log_dir.mkdir(parents=True)
            (log_dir / "stdout.log").write_text("out\n", encoding="utf-8")
            (log_dir / "stderr.log").write_text("err\n", encoding="utf-8")
            service = macos.ManagedService(
                "worker",
                "/bin/worker",
                "Worker",
                display_name="worker",
                managed_by_skuld=True,
                scope="agent",
                log_dir=str(log_dir),
                id=1,
            )
            macos.save_registry([service])
            tailed: list[tuple[str, int, bool]] = []

            def fake_tail(path, lines, follow):
                tailed.append((path.name, lines, follow))

            with patch.object(macos, "tail_file", side_effect=fake_tail), redirect_stdout(io.StringIO()):
                macos.logs(
                    argparse.Namespace(
                        name="worker",
                        name_flag=None,
                        id_flag=None,
                        lines_pos=None,
                        lines=20,
                        follow=False,
                        since=None,
                        timer=False,
                        output="short",
                        plain=False,
                    )
                )

            self.assertEqual(tailed, [("stdout.log", 20, False), ("stderr.log", 20, False)])


if __name__ == "__main__":
    unittest.main()
