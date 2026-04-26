from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

import skuld_macos_processes as processes


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class MacOSProcessTreeTest(unittest.TestCase):
    def test_reads_process_tree_from_ps_output(self) -> None:
        def run_cmd(cmd, check=True, capture=False):
            return completed(stdout="10 1\n11 10\n12 11\n99 1\n")

        self.assertEqual(processes.read_process_tree_pids(10, run_cmd), [10, 11, 12])

    def test_terminates_process_tree_children_first(self) -> None:
        calls: list[tuple[int, int]] = []

        def fake_kill(pid: int, sig: int) -> None:
            calls.append((pid, sig))
            if sig == 0:
                raise ProcessLookupError()

        with patch.object(processes.os, "kill", side_effect=fake_kill):
            processes.terminate_process_tree(10, lambda pid: [10, 11], grace_seconds=0.1)

        self.assertEqual(calls[:2], [(11, processes.signal.SIGTERM), (10, processes.signal.SIGTERM)])


class MacOSProcessStatsTest(unittest.TestCase):
    def test_reads_cpu_and_memory(self) -> None:
        def run_cmd(cmd, check=True, capture=False):
            return completed(stdout="12,5 1048576\n")

        self.assertEqual(processes.read_cpu_memory(42, run_cmd), {"cpu": "12.5%", "memory": "1.00GB"})

    def test_parse_lsof_listen_ports(self) -> None:
        output = "\n".join(
            [
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME",
                "python 42 user 3u IPv4 0x0 0t0 TCP *:8000 (LISTEN)",
                "python 42 user 4u IPv4 0x0 0t0 UDP *:5353",
                "python 42 user 5u IPv4 0x0 0t0 TCP *:9000 (ESTABLISHED)",
            ]
        )

        self.assertEqual(processes.parse_lsof_listen_ports(output), ["5353/udp", "8000/tcp"])

    def test_read_ports_uses_process_tree(self) -> None:
        def run_cmd(cmd, check=True, capture=False):
            self.assertIn("42,43", cmd)
            return completed(stdout="H\napi 42 u 3 IPv4 0 0 TCP *:8000 (LISTEN)\n")

        self.assertEqual(processes.read_ports(42, lambda pid: [42, 43], run_cmd), "8000/tcp")

    def test_parses_vm_stat_counts(self) -> None:
        self.assertEqual(processes.parse_vm_stat_count("1,234."), 1234)
        self.assertEqual(processes.parse_vm_stat_count("."), 0)

    def test_reads_host_overview_memory(self) -> None:
        def run_cmd(cmd, check=True, capture=False):
            if cmd[:3] == ["sysctl", "-n", "kern.boottime"]:
                return completed(stdout="{ sec = 1777200000, usec = 0 }")
            if cmd[:3] == ["sysctl", "-n", "hw.memsize"]:
                return completed(stdout=str(8 * 1024 * 1024 * 1024))
            if cmd == ["vm_stat"]:
                return completed(
                    stdout="\n".join(
                        [
                            "Mach Virtual Memory Statistics: (page size of 4096 bytes)",
                            "Pages free: 1000.",
                            "Pages inactive: 1000.",
                            "Pages speculative: 0.",
                        ]
                    )
                )
            return completed()

        overview = processes.read_host_overview(run_cmd)

        self.assertIn("uptime", overview)
        self.assertIn("cpu(load1/5/15)", overview)
        self.assertEqual(overview["memory"], "7.99GB/8.00GB (99%)")


if __name__ == "__main__":
    unittest.main()
