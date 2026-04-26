from __future__ import annotations

import types
import unittest

import skuld_macos_actions as actions


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def service(schedule: str = ""):
    return types.SimpleNamespace(
        name="worker",
        display_name="worker",
        schedule=schedule,
    )


class MacosActionsTest(unittest.TestCase):
    def test_start_unscheduled_job_bootstraps_and_kickstarts(self) -> None:
        calls = []
        messages = []

        actions.apply_lifecycle_action(
            service(),
            "start",
            bootstrap_service=lambda service: calls.append("bootstrap"),
            bootout_service=lambda service: calls.append("bootout"),
            kickstart_service=lambda service, kill_existing=False: (
                calls.append(f"kickstart:{kill_existing}") or completed()
            ),
            read_pid=lambda service: 0,
            read_recent_run_root_pids=lambda service: [],
            terminate_process_tree=lambda pid: calls.append(f"terminate:{pid}"),
            ok=messages.append,
        )

        self.assertEqual(calls, ["bootstrap", "kickstart:False"])
        self.assertEqual(messages, ["start -> worker"])

    def test_start_scheduled_job_does_not_kickstart(self) -> None:
        calls = []

        actions.apply_lifecycle_action(
            service(schedule="daily"),
            "start",
            bootstrap_service=lambda service: calls.append("bootstrap"),
            bootout_service=lambda service: calls.append("bootout"),
            kickstart_service=lambda service, kill_existing=False: (
                calls.append(f"kickstart:{kill_existing}") or completed()
            ),
            read_pid=lambda service: 0,
            read_recent_run_root_pids=lambda service: [],
            terminate_process_tree=lambda pid: calls.append(f"terminate:{pid}"),
            ok=lambda message: None,
        )

        self.assertEqual(calls, ["bootstrap"])

    def test_restart_boots_out_terminates_and_kickstarts_with_kill(self) -> None:
        calls = []

        actions.apply_lifecycle_action(
            service(),
            "restart",
            bootstrap_service=lambda service: calls.append("bootstrap"),
            bootout_service=lambda service: calls.append("bootout"),
            kickstart_service=lambda service, kill_existing=False: (
                calls.append(f"kickstart:{kill_existing}") or completed()
            ),
            read_pid=lambda service: 42,
            read_recent_run_root_pids=lambda service: [43],
            terminate_process_tree=lambda pid: calls.append(f"terminate:{pid}"),
            ok=lambda message: calls.append(message),
        )

        self.assertEqual(
            calls,
            [
                "bootout",
                "terminate:42",
                "terminate:43",
                "bootstrap",
                "kickstart:True",
                "restart -> worker",
            ],
        )

    def test_execute_now_surfaces_kickstart_failure_details(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Failed to execute worker. denied"):
            actions.execute_now(
                service(),
                bootstrap_service=lambda service: None,
                kickstart_service=lambda service, kill_existing=False: completed(
                    stderr="denied",
                    returncode=1,
                ),
                ok=lambda message: None,
            )


if __name__ == "__main__":
    unittest.main()
