from __future__ import annotations

import unittest
from typing import Optional

import skuld_macos_parser as macos_parser


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


class MacParserTest(unittest.TestCase):
    def build_parser(self, calls: Optional[list[tuple[str, object]]] = None):
        def start_stop(args, action):
            if calls is not None:
                calls.append((action, list(args.targets)))

        return macos_parser.build_parser(
            sort_choices=("id", "name", "cpu", "memory"),
            version="9.9.9",
            list_services=_noop,
            catalog=_noop,
            track=_noop,
            rename=_noop,
            untrack=_noop,
            exec_now=_noop,
            start_stop=start_stop,
            restart=_noop,
            status=_noop,
            logs=_noop,
            stats=_noop,
            doctor=_noop,
            describe=_noop,
            sync=_noop,
            sudo_check=_noop,
            sudo_run_command=_noop,
        )

    def test_track_keeps_launchd_target_and_alias_contract(self) -> None:
        args = self.build_parser().parse_args(["track", "1", "com.example.Worker", "--alias", "worker"])

        self.assertEqual(args.targets, ["1", "com.example.Worker"])
        self.assertEqual(args.alias, "worker")
        self.assertIs(args.func, _noop)

    def test_logs_keep_compatibility_options(self) -> None:
        args = self.build_parser().parse_args(["logs", "api", "--folow", "--timer", "--plain"])

        self.assertEqual(args.name, "api")
        self.assertTrue(args.follow)
        self.assertTrue(args.timer)
        self.assertTrue(args.plain)

    def test_stop_dispatches_to_shared_action_handler(self) -> None:
        calls: list[tuple[str, object]] = []
        args = self.build_parser(calls).parse_args(["stop", "api", "worker"])

        args.func(args)

        self.assertEqual(calls, [("stop", ["api", "worker"])])

    def test_sync_keeps_target_forms(self) -> None:
        args = self.build_parser().parse_args(["sync", "--name", "api"])

        self.assertIsNone(args.name)
        self.assertEqual(args.name_flag, "api")


if __name__ == "__main__":
    unittest.main()
