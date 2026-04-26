from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import skuld_linux_stats as stats


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


class LinuxStatsFormattingTest(unittest.TestCase):
    def test_formats_cpu_nsec(self) -> None:
        self.assertEqual(stats.format_cpu_nsec("500000000"), "500ms")
        self.assertEqual(stats.format_cpu_nsec("1500000000"), "1.5s")
        self.assertEqual(stats.format_cpu_nsec("125000000000"), "2m5s")
        self.assertEqual(stats.format_cpu_nsec("bad"), "-")

    def test_formats_gpu_memory(self) -> None:
        self.assertEqual(stats.format_gpu_mib(0), "0MB")
        self.assertEqual(stats.format_gpu_mib(512), "512MB")
        self.assertEqual(stats.format_gpu_mib(1536), "1.5GB")

    def test_reads_gpu_memory_by_pid(self) -> None:
        def run_cmd(cmd, check=True, capture=False):
            return completed(stdout="42, 512\n42, 256\ninvalid, 99\n7, bad\n")

        self.assertEqual(stats.read_gpu_memory_by_pid(run_cmd), {42: 768})


class LinuxStatsUsageTest(unittest.TestCase):
    def test_unit_usage_prefers_systemd_values(self) -> None:
        def unit_exists(unit: str, scope: str = "system") -> bool:
            return True

        def systemctl_show(unit: str, props: list[str], scope: str = "system") -> dict[str, str]:
            return {"CPUUsageNSec": "2000000000", "MemoryCurrent": "1048576", "MainPID": "123"}

        usage = stats.read_unit_usage(unit_exists, systemctl_show, "api.service", gpu_memory_by_pid={123: 2048})

        self.assertEqual(usage, {"cpu": "2.0s", "memory": "0.00GB", "gpu": "2GB"})

    def test_unit_usage_returns_empty_when_unit_is_missing(self) -> None:
        usage = stats.read_unit_usage(lambda *args, **kwargs: False, lambda *args, **kwargs: {}, "api.service")
        self.assertEqual(usage, {"cpu": "-", "memory": "-", "gpu": "-"})

    def test_unit_usage_falls_back_to_proc_helpers(self) -> None:
        def unit_exists(unit: str, scope: str = "system") -> bool:
            return True

        def systemctl_show(unit: str, props: list[str], scope: str = "system") -> dict[str, str]:
            return {"CPUUsageNSec": "", "MemoryCurrent": "", "MainPID": "123"}

        with patch.object(stats, "read_proc_cpu_nsec", return_value=1_000_000_000), patch.object(
            stats, "read_proc_memory_bytes", return_value=2048
        ):
            usage = stats.read_unit_usage(unit_exists, systemctl_show, "api.service")

        self.assertEqual(usage["cpu"], "1.0s")
        self.assertEqual(usage["memory"], "0.00GB")


class LinuxPortsTest(unittest.TestCase):
    def test_parses_listen_ports_from_ss_for_matching_pids(self) -> None:
        output = "\n".join(
            [
                "Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process",
                'tcp LISTEN 0 4096 0.0.0.0:8000 0.0.0.0:* users:(("python",pid=123,fd=3))',
                'udp UNCONN 0 0 127.0.0.1:5353 0.0.0.0:* users:(("dns",pid=999,fd=4))',
                'tcp LISTEN 0 4096 [::]:9000 [::]:* users:(("python",pid=123,fd=4))',
            ]
        )

        self.assertEqual(stats.parse_listen_ports_from_ss(output, {123}), ["8000/tcp", "9000/tcp"])

    def test_parses_proc_net_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tcp"
            path.write_text(
                "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
                "0: 00000000:1F90 00000000:0000 0A 0 0 0 0 0 12345\n"
                "1: 00000000:1F91 00000000:0000 01 0 0 0 0 0 67890\n",
                encoding="utf-8",
            )

            self.assertEqual(stats.parse_proc_net_ports(path, "tcp", {"12345", "67890"}), {"8080/tcp"})

    def test_read_unit_ports_uses_sudo_when_regular_ss_has_no_pid_data(self) -> None:
        def read_pids(unit: str, scope: str = "system") -> list[int]:
            return [123]

        def run_cmd(cmd, check=True, capture=False):
            return completed(stdout="")

        def run_sudo_cmd(cmd, check=True, capture=False):
            return completed(stdout='tcp LISTEN 0 4096 0.0.0.0:8000 0.0.0.0:* users:(("api",pid=123,fd=3))\n')

        with patch.object(stats, "read_unit_ports_from_proc_pids", return_value=[]):
            self.assertEqual(stats.read_unit_ports(read_pids, run_cmd, run_sudo_cmd, "api.service"), "8000/tcp")


if __name__ == "__main__":
    unittest.main()
