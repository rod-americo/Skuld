from __future__ import annotations

import argparse
import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import skuld_linux as linux
from tests.helpers import IsolatedLinuxState


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class LinuxRegistryTest(unittest.TestCase):
    def test_load_registry_normalizes_ids_scope_order_and_unknown_fields(self) -> None:
        with IsolatedLinuxState(linux) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            state.registry.write_text(
                json.dumps(
                    [
                        {
                            "name": "beta",
                            "scope": "root",
                            "exec_cmd": "/bin/beta",
                            "description": "Beta service",
                            "display_name": "beta-alias",
                            "timer_persistent": "false",
                            "id": 0,
                            "ignored": "removed",
                        },
                        {
                            "name": "alpha",
                            "scope": "user",
                            "exec_cmd": "/bin/alpha",
                            "description": "Alpha service",
                            "display_name": "alpha-alias",
                            "id": 4,
                        },
                    ]
                ),
                encoding="utf-8",
            )

            services = linux.load_registry(write_back=True)
            self.assertEqual([svc.name for svc in services], ["alpha", "beta"])
            self.assertEqual(services[0].scope, "user")
            self.assertEqual(services[1].scope, "system")
            self.assertEqual(services[1].id, 1)
            self.assertFalse(services[1].timer_persistent)

            canonical = json.loads(state.registry.read_text(encoding="utf-8"))
            self.assertNotIn("ignored", canonical[1])
            self.assertEqual(canonical[1]["scope"], "system")
            self.assertTrue(state.registry.read_text(encoding="utf-8").endswith("\n"))

    def test_load_registry_does_not_write_by_default(self) -> None:
        with IsolatedLinuxState(linux) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(
                [
                    {
                        "name": "beta",
                        "scope": "root",
                        "exec_cmd": "/bin/beta",
                        "description": "Beta service",
                        "display_name": "beta-alias",
                        "id": 0,
                        "ignored": "left-alone",
                    }
                ]
            )
            state.registry.write_text(raw, encoding="utf-8")

            [service] = linux.load_registry()

            self.assertEqual(service.scope, "system")
            self.assertEqual(service.id, 1)
            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_duplicate_display_name_is_rejected(self) -> None:
        with IsolatedLinuxState(linux) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            state.registry.write_text(
                json.dumps(
                    [
                        {
                            "name": "one",
                            "scope": "system",
                            "exec_cmd": "/bin/one",
                            "description": "One",
                            "display_name": "same",
                        },
                        {
                            "name": "two",
                            "scope": "user",
                            "exec_cmd": "/bin/two",
                            "description": "Two",
                            "display_name": "same",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Duplicate display name"):
                linux.load_registry()


class LinuxTargetResolutionTest(unittest.TestCase):
    def test_resolves_ambiguous_backend_name_only_with_scope_or_id(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry(
                [
                    linux.ManagedService("nginx", "system", "/bin/nginx", "System nginx", "edge", id=1),
                    linux.ManagedService("nginx", "user", "/bin/nginx", "User nginx", "dev-edge", id=2),
                ]
            )

            with self.assertRaisesRegex(RuntimeError, "ambiguous across scopes"):
                linux.resolve_managed_from_token("nginx")

            self.assertEqual(linux.resolve_managed_from_token("system:nginx").display_name, "edge")
            self.assertEqual(linux.resolve_managed_from_token("2").scope, "user")


class LinuxCatalogScopeTest(unittest.TestCase):
    def test_normalizes_catalog_scope(self) -> None:
        self.assertEqual(linux.normalize_discoverable_scope(None), "all")
        self.assertEqual(linux.normalize_discoverable_scope(" USER "), "user")
        with self.assertRaisesRegex(ValueError, "Invalid catalog scope"):
            linux.normalize_discoverable_scope("daemon")

    def test_scope_filter_preserves_global_catalog_ids(self) -> None:
        system_entry = linux.DiscoverableService(0, "system", "alpha", "enabled", "n/a")
        user_entry = linux.DiscoverableService(0, "user", "alpha", "enabled", "enabled")
        beta_entry = linux.DiscoverableService(0, "system", "beta", "enabled", "n/a")

        def list_scope(scope: str) -> list[linux.DiscoverableService]:
            if scope == "system":
                return [system_entry, beta_entry]
            if scope == "user":
                return [user_entry]
            return []

        with patch.object(linux, "require_systemctl"), patch.object(
            linux, "list_discoverable_services_for_scope", side_effect=list_scope
        ):
            all_entries = linux.list_discoverable_services()
            user_entries = linux.list_discoverable_services("user")

        self.assertEqual([(item.index, item.scope, item.name) for item in all_entries], [
            (1, "system", "alpha"),
            (2, "user", "alpha"),
            (3, "system", "beta"),
        ])
        self.assertEqual([(item.index, item.scope, item.name) for item in user_entries], [
            (2, "user", "alpha"),
        ])

    def test_catalog_scope_filters_rendered_entries(self) -> None:
        entries = [
            linux.DiscoverableService(1, "system", "alpha", "enabled", "n/a"),
            linux.DiscoverableService(2, "user", "beta", "enabled", "enabled"),
        ]
        with patch.object(linux, "list_discoverable_services", return_value=[entries[1]]):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                linux.catalog(argparse.Namespace(scope="user"))

        output = stdout.getvalue()
        self.assertIn("Available systemd services (user only):", output)
        self.assertIn("2. [user] beta", output)
        self.assertNotIn("[system] alpha", output)


class LinuxCommandBehaviorTest(unittest.TestCase):
    def test_list_does_not_persist_registry_normalization(self) -> None:
        with IsolatedLinuxState(linux) as state:
            state.registry.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(
                [
                    {
                        "name": "api",
                        "scope": "root",
                        "exec_cmd": "/bin/api",
                        "description": "API",
                        "display_name": "api",
                        "id": 0,
                        "ignored": "left-alone",
                    }
                ]
            )
            state.registry.write_text(raw, encoding="utf-8")

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "read_gpu_memory_by_pid", return_value={}
            ), patch.object(
                linux, "load_runtime_stats", return_value={}
            ), patch.object(
                linux, "render_host_panel"
            ), patch.object(
                linux, "unit_exists", return_value=False
            ), patch.object(
                linux, "read_unit_usage", return_value={"cpu": "-", "memory": "-"}
            ), patch.object(
                linux, "read_unit_ports", return_value="-"
            ), patch.object(
                linux, "timer_triggers_for_display", return_value="-"
            ), patch.object(
                linux, "render_table"
            ), redirect_stdout(io.StringIO()):
                linux.list_services_compact()

            self.assertEqual(state.registry.read_text(encoding="utf-8"), raw)

    def test_track_captures_systemd_metadata_into_registry(self) -> None:
        with IsolatedLinuxState(linux):
            entry = linux.DiscoverableService(1, "user", "demo", "enabled", "enabled")

            def unit_exists(unit: str, scope: str = "system") -> bool:
                self.assertEqual(scope, "user")
                return unit in {"demo.service", "demo.timer"}

            def systemctl_show(unit: str, props: list[str], scope: str = "system") -> dict[str, str]:
                self.assertEqual(scope, "user")
                if unit == "demo.service":
                    return {
                        "Description": "Demo unit",
                        "WorkingDirectory": "/tmp",
                        "User": "",
                        "Restart": "on-failure",
                    }
                if unit == "demo.timer":
                    return {"OnCalendar": "daily", "Persistent": "true"}
                return {}

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "list_discoverable_services", return_value=[entry]
            ), patch.object(
                linux, "unit_exists", side_effect=unit_exists
            ), patch.object(
                linux, "systemctl_cat", return_value="[Service]\nExecStart=/usr/bin/demo --flag\n"
            ), patch.object(
                linux, "systemctl_show", side_effect=systemctl_show
            ), redirect_stdout(io.StringIO()):
                linux.track(argparse.Namespace(targets=["1"], alias="demo-alias"))

            [service] = linux.load_registry()
            self.assertEqual(service.name, "demo")
            self.assertEqual(service.scope, "user")
            self.assertEqual(service.display_name, "demo-alias")
            self.assertEqual(service.exec_cmd, "/usr/bin/demo --flag")
            self.assertEqual(service.schedule, "daily")
            self.assertEqual(service.working_dir, "/tmp")

    def test_start_routes_scheduled_services_to_timer(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry(
                [linux.ManagedService("job", "user", "/bin/job", "Job", "job", schedule="daily", id=1)]
            )
            calls: list[tuple[str, list[str]]] = []

            def unit_exists(unit: str, scope: str = "system") -> bool:
                return unit == "job.timer"

            def run_action(scope: str, args: list[str], check: bool = True, capture: bool = False):
                calls.append((scope, args))
                return completed()

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "unit_exists", side_effect=unit_exists
            ), patch.object(
                linux, "run_systemctl_action", side_effect=run_action
            ), redirect_stdout(io.StringIO()):
                linux.start_stop(argparse.Namespace(targets=["job"], name_flag=None, id_flag=None), "start")

            self.assertEqual(calls, [("user", ["start", "job.timer"])])

    def test_start_routes_unscheduled_services_to_service(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry([linux.ManagedService("api", "system", "/bin/api", "API", "api", id=1)])
            calls: list[tuple[str, list[str]]] = []

            def run_action(scope: str, args: list[str], check: bool = True, capture: bool = False):
                calls.append((scope, args))
                return completed()

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "unit_exists", return_value=False
            ), patch.object(
                linux, "run_systemctl_action", side_effect=run_action
            ), redirect_stdout(io.StringIO()):
                linux.start_stop(argparse.Namespace(targets=["api"], name_flag=None, id_flag=None), "restart")

            self.assertEqual(calls, [("system", ["restart", "api.service"])])

    def test_exec_always_starts_service_unit(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry(
                [linux.ManagedService("job", "user", "/bin/job", "Job", "job", schedule="daily", id=1)]
            )
            calls: list[tuple[str, list[str]]] = []

            def run_action(scope: str, args: list[str], check: bool = True, capture: bool = False):
                calls.append((scope, args))
                return completed()

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "run_systemctl_action", side_effect=run_action
            ), redirect_stdout(io.StringIO()):
                linux.exec_now(argparse.Namespace(name="job", name_flag=None, id_flag=None))

            self.assertEqual(calls, [("user", ["start", "job.service"])])

    def test_logs_fall_back_to_sudo_on_journal_permission_hint(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry([linux.ManagedService("api", "system", "/bin/api", "API", "api", id=1)])
            sudo_calls: list[list[str]] = []

            def fake_run(cmd, check=True, capture=False, input_text=None, env=None):
                return completed(
                    stderr="Hint: You are currently not seeing messages from other users and the system."
                )

            def fake_sudo(cmd, check=True, capture=False):
                sudo_calls.append(cmd)
                return completed(stdout="sudo log line\n")

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "run", side_effect=fake_run
            ), patch.object(
                linux, "run_sudo", side_effect=fake_sudo
            ), redirect_stdout(io.StringIO()) as stdout:
                linux.logs(
                    argparse.Namespace(
                        name="api",
                        name_flag=None,
                        id_flag=None,
                        lines_pos=None,
                        lines=100,
                        follow=False,
                        since=None,
                        timer=False,
                        output="short",
                        plain=False,
                    )
                )

            self.assertIn("sudo log line", stdout.getvalue())
            self.assertEqual(sudo_calls[0][:3], ["journalctl", "-u", "api.service"])

    def test_stats_reports_execution_and_restart_counts(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry([linux.ManagedService("api", "system", "/bin/api", "API", "api", id=1)])
            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "sync_registry_from_systemd", return_value=0
            ), patch.object(
                linux, "count_unit_starts", return_value=7
            ), patch.object(
                linux, "read_restart_count", return_value="2"
            ), redirect_stdout(io.StringIO()) as stdout:
                linux.stats(argparse.Namespace(name="api", name_flag=None, id_flag=None, since="24 hours ago", boot=False))

            output = stdout.getvalue()
            self.assertIn("window: since 24 hours ago", output)
            self.assertIn("executions: 7", output)
            self.assertIn("restarts: 2", output)

    def test_doctor_reports_missing_expected_timer(self) -> None:
        with IsolatedLinuxState(linux):
            linux.save_registry(
                [linux.ManagedService("job", "user", "/bin/job", "Job", "job", schedule="daily", id=1)]
            )

            def unit_exists(unit: str, scope: str = "system") -> bool:
                return unit == "job.service"

            with patch.object(linux, "require_systemctl"), patch.object(
                linux, "sync_registry_from_systemd", return_value=0
            ), patch.object(
                linux, "unit_exists", side_effect=unit_exists
            ), patch.object(
                linux, "unit_active", return_value="active"
            ), patch.object(
                linux, "read_timer_schedule", return_value=""
            ), patch.object(
                linux, "systemctl_cat", return_value="ExecStart=/bin/job\n"
            ), redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                linux.doctor(argparse.Namespace())

            self.assertIn("ERROR expected timer is missing", stdout.getvalue())
            self.assertIn("doctor: found 1 issue", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
