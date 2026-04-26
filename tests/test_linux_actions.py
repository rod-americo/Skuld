from __future__ import annotations

import types
import unittest

import skuld_linux_actions as actions


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def service(schedule: str = ""):
    return types.SimpleNamespace(
        name="api",
        scope="user",
        display_name="api",
        schedule=schedule,
    )


class LinuxActionsTest(unittest.TestCase):
    def test_execute_now_always_starts_service_unit(self) -> None:
        calls = []
        messages = []

        actions.execute_now(
            service(schedule="daily"),
            run_systemctl_action=lambda scope, args: calls.append((scope, args)),
            ok=messages.append,
        )

        self.assertEqual(calls, [("user", ["start", "api.service"])])
        self.assertEqual(
            messages,
            ["Execution started: api.service (api, scope=user)"],
        )

    def test_lifecycle_routes_scheduled_service_to_existing_timer(self) -> None:
        calls = []
        messages = []

        actions.apply_lifecycle_action(
            service(schedule="daily"),
            "start",
            unit_exists=lambda unit, **kwargs: unit == "api.timer",
            run_systemctl_action=lambda scope, args, **kwargs: (
                calls.append((scope, args, kwargs)) or completed()
            ),
            ok=messages.append,
        )

        self.assertEqual(
            calls,
            [("user", ["start", "api.timer"], {"check": False, "capture": True})],
        )
        self.assertEqual(messages, ["start -> api.timer (user)"])

    def test_lifecycle_routes_unscheduled_service_to_service_unit(self) -> None:
        calls = []

        actions.apply_lifecycle_action(
            service(),
            "restart",
            unit_exists=lambda unit, **kwargs: False,
            run_systemctl_action=lambda scope, args, **kwargs: (
                calls.append((scope, args)) or completed()
            ),
            ok=lambda message: None,
        )

        self.assertEqual(calls, [("user", ["restart", "api.service"])])

    def test_lifecycle_surfaces_action_failure_details(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Failed to stop api.service. no"):
            actions.apply_lifecycle_action(
                service(),
                "stop",
                unit_exists=lambda unit, **kwargs: False,
                run_systemctl_action=lambda scope, args, **kwargs: completed(
                    stderr="no",
                    returncode=1,
                ),
                ok=lambda message: None,
            )


if __name__ == "__main__":
    unittest.main()
