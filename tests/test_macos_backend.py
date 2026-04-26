from __future__ import annotations

import argparse
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from skuld_macos_handlers import MacOSCommandHandlers
from skuld_macos_model import DiscoverableService, ManagedService
from tests.helpers import IsolatedMacContext


def completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["fake"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class MacRegistryTest(unittest.TestCase):
    def test_load_registry_normalizes_defaults_and_runtime_files(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
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

            [service] = ctx.load_registry(write_back=True)
            self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
            self.assertEqual(service.scope, "daemon")
            self.assertEqual(service.backend, "launchd")
            self.assertEqual(service.id, 1)
            self.assertTrue(state.stats.exists())
            self.assertTrue(state.registry.read_text(encoding="utf-8").endswith("\n"))

    def test_load_registry_does_not_write_by_default(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
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

            [service] = ctx.load_registry()

            self.assertEqual(service.launchd_label, "io.skuld.com.example.worker")
            self.assertEqual(service.id, 1)
            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_agent_registry_entry_cannot_store_user(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
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

            with self.assertRaisesRegex(RuntimeError, "'user' is only valid"):
                ctx.load_registry()


class MacCommandBehaviorTest(unittest.TestCase):
    def test_list_does_not_persist_registry_normalization(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
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

            with patch.object(ctx, "read_event_stats", return_value={}), patch.object(
                ctx,
                "read_pid",
                return_value=0,
            ), patch.object(
                ctx,
                "read_cpu_memory",
                return_value={"cpu": "-", "memory": "-"},
            ), patch.object(
                ctx,
                "service_loaded",
                return_value=False,
            ), patch.object(
                ctx,
                "read_ports",
                return_value="-",
            ), patch.object(
                ctx,
                "render_host_panel",
            ), patch.object(
                ctx,
                "render_table",
            ), redirect_stdout(io.StringIO()):
                handlers.list_services_compact()

            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_track_captures_launchd_metadata_as_external_job(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            entry = DiscoverableService(1, "com.example.Worker", "-", "0")
            raw = """
            path = /Users/me/Library/LaunchAgents/com.example.Worker.plist
            program = /usr/bin/worker
            state = running
            """
            with patch.object(
                ctx,
                "discover_launchd_services",
                return_value=[entry],
            ), patch.object(
                ctx,
                "launchctl_print_service_raw",
                return_value=raw,
            ), redirect_stdout(io.StringIO()):
                handlers.track(argparse.Namespace(targets=["1"], alias="worker"))

            [service] = ctx.load_registry()
            self.assertEqual(service.name, "com.example.Worker")
            self.assertEqual(service.display_name, "worker")
            self.assertEqual(service.exec_cmd, "/usr/bin/worker")
            self.assertEqual(
                service.plist_path_hint,
                "/Users/me/Library/LaunchAgents/com.example.Worker.plist",
            )
            self.assertFalse(service.managed_by_skuld)
            self.assertEqual(service.scope, "agent")

    def test_start_unscheduled_job_bootstraps_and_kickstarts(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            service = ManagedService(
                "worker",
                "/bin/worker",
                "Worker",
                display_name="worker",
                scope="agent",
                id=1,
            )
            ctx.save_registry([service])
            calls: list[str] = []

            def fake_kickstart(service, kill_existing=False):
                calls.append(f"kickstart:{kill_existing}")
                return completed()

            with patch.object(
                ctx,
                "bootstrap_service",
                side_effect=lambda _svc: calls.append("bootstrap"),
            ), patch.object(
                ctx,
                "kickstart_service",
                side_effect=fake_kickstart,
            ), redirect_stdout(io.StringIO()):
                handlers.start_stop(
                    argparse.Namespace(
                        targets=["worker"],
                        name_flag=None,
                        id_flag=None,
                    ),
                    "start",
                )

            self.assertEqual(calls, ["bootstrap", "kickstart:False"])

    def test_start_scheduled_job_does_not_kickstart_immediately(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            service = ManagedService(
                "scheduled",
                "/bin/scheduled",
                "Scheduled",
                display_name="scheduled",
                scope="agent",
                schedule="daily",
                id=1,
            )
            ctx.save_registry([service])
            with patch.object(ctx, "bootstrap_service") as bootstrap, patch.object(
                ctx,
                "kickstart_service",
            ) as kickstart, redirect_stdout(io.StringIO()):
                handlers.start_stop(
                    argparse.Namespace(
                        targets=["scheduled"],
                        name_flag=None,
                        id_flag=None,
                    ),
                    "start",
                )

            bootstrap.assert_called_once()
            kickstart.assert_not_called()

    def test_restart_boots_out_terminates_and_kickstarts_with_kill(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            service = ManagedService(
                "worker",
                "/bin/worker",
                "Worker",
                display_name="worker",
                scope="agent",
                id=1,
            )
            ctx.save_registry([service])
            calls: list[tuple[str, object]] = []

            def fake_kickstart(service, kill_existing=False):
                calls.append(("kickstart", kill_existing))
                return completed()

            with patch.object(ctx, "read_pid", return_value=42), patch.object(
                ctx,
                "read_recent_run_root_pids",
                return_value=[43],
            ), patch.object(
                ctx,
                "bootout_service",
                side_effect=lambda _svc: calls.append(("bootout", None)),
            ), patch.object(
                ctx,
                "terminate_process_tree",
                side_effect=lambda pid: calls.append(("terminate", pid)),
            ), patch.object(
                ctx,
                "bootstrap_service",
                side_effect=lambda _svc: calls.append(("bootstrap", None)),
            ), patch.object(
                ctx,
                "kickstart_service",
                side_effect=fake_kickstart,
            ), redirect_stdout(io.StringIO()):
                handlers.restart(
                    argparse.Namespace(
                        targets=["worker"],
                        name_flag=None,
                        id_flag=None,
                    )
                )

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

    def test_logs_reject_external_tracked_jobs_without_plist_log_paths(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            service = ManagedService(
                "com.example.Worker",
                "/usr/bin/worker",
                "Worker",
                display_name="worker",
                managed_by_skuld=False,
                scope="agent",
                id=1,
            )
            ctx.save_registry([service])

            with self.assertRaisesRegex(RuntimeError, "compatible log_dir"):
                handlers.logs(
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

    def test_logs_tail_external_launchd_paths_when_plist_declares_them(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            stdout_path = state.root / "external.out"
            stderr_path = state.root / "external.err"
            stdout_path.write_text("out\n", encoding="utf-8")
            stderr_path.write_text("err\n", encoding="utf-8")
            plist_path = state.root / "com.example.Worker.plist"
            plist_path.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.Worker</string>
  <key>StandardOutPath</key>
  <string>{stdout_path}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_path}</string>
</dict>
</plist>
""",
                encoding="utf-8",
            )
            service = ManagedService(
                "com.example.Worker",
                "/usr/bin/worker",
                "Worker",
                display_name="worker",
                plist_path_hint=str(plist_path),
                managed_by_skuld=False,
                scope="agent",
                id=1,
            )
            ctx.save_registry([service])
            tailed: list[tuple[str, int, bool]] = []

            def fake_tail(path, lines, follow):
                tailed.append((path.name, lines, follow))

            with patch.object(
                ctx,
                "tail_file",
                side_effect=fake_tail,
            ), redirect_stdout(io.StringIO()):
                handlers.logs(
                    argparse.Namespace(
                        name="worker",
                        name_flag=None,
                        id_flag=None,
                        lines_pos=None,
                        lines=30,
                        follow=False,
                        since=None,
                        timer=False,
                        output="short",
                        plain=False,
                    )
                )

            self.assertEqual(
                tailed,
                [("external.out", 30, False), ("external.err", 30, False)],
            )

    def test_logs_tail_stdout_and_stderr_for_managed_jobs(self) -> None:
        with IsolatedMacContext() as state:
            ctx = state.context
            handlers = MacOSCommandHandlers(ctx)
            log_dir = state.root / "logs" / "worker"
            log_dir.mkdir(parents=True)
            (log_dir / "stdout.log").write_text("out\n", encoding="utf-8")
            (log_dir / "stderr.log").write_text("err\n", encoding="utf-8")
            service = ManagedService(
                "worker",
                "/bin/worker",
                "Worker",
                display_name="worker",
                managed_by_skuld=True,
                scope="agent",
                log_dir=str(log_dir),
                id=1,
            )
            ctx.save_registry([service])
            tailed: list[tuple[str, int, bool]] = []

            def fake_tail(path, lines, follow):
                tailed.append((path.name, lines, follow))

            with patch.object(
                ctx,
                "tail_file",
                side_effect=fake_tail,
            ), redirect_stdout(io.StringIO()):
                handlers.logs(
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
