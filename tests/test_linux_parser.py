from __future__ import annotations

import unittest
from typing import Optional

import skuld_linux_parser as linux_parser


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


class LinuxParserTest(unittest.TestCase):
    def build_parser(self, calls: Optional[list[tuple[str, object]]] = None):
        def start_stop(args, action):
            if calls is not None:
                calls.append((action, list(args.targets)))

        return linux_parser.build_parser(
            sort_choices=("id", "name", "cpu", "memory"),
            discoverable_scope_choices=("all", "system", "user"),
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

    def test_catalog_keeps_scope_filter_contract(self) -> None:
        args = self.build_parser().parse_args(["catalog", "--scope", "user"])

        self.assertEqual(args.scope, "user")
        self.assertIs(args.func, _noop)

    def test_logs_keep_journal_options_and_folow_compatibility(self) -> None:
        args = self.build_parser().parse_args(
            ["logs", "api", "25", "--folow", "--timer", "--output", "cat"]
        )

        self.assertEqual(args.name, "api")
        self.assertEqual(args.lines_pos, 25)
        self.assertTrue(args.follow)
        self.assertTrue(args.timer)
        self.assertEqual(args.output, "cat")

    def test_start_dispatches_to_shared_action_handler(self) -> None:
        calls: list[tuple[str, object]] = []
        args = self.build_parser(calls).parse_args(["start", "api", "worker"])

        args.func(args)

        self.assertEqual(calls, [("start", ["api", "worker"])])

    def test_sync_keeps_target_forms(self) -> None:
        args = self.build_parser().parse_args(["sync", "--id", "7"])

        self.assertIsNone(args.name)
        self.assertEqual(args.id_flag, 7)


if __name__ == "__main__":
    unittest.main()
