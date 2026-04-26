import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import skuld_common as common


def format_cpu_nsec(value: str) -> str:
    raw = (value or "").strip()
    if not raw or raw in ("[not set]", "n/a"):
        return "-"
    try:
        nsec = int(raw)
    except ValueError:
        return "-"
    if nsec < 0:
        return "-"
    seconds = nsec / 1_000_000_000
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rem = seconds - (minutes * 60)
    if minutes < 60:
        return f"{minutes}m{rem:.0f}s"
    hours = int(minutes // 60)
    rem_min = minutes % 60
    return f"{hours}h{rem_min}m"


def read_host_overview() -> Dict[str, str]:
    uptime = "-"
    try:
        raw = Path("/proc/uptime").read_text(encoding="utf-8").split()[0]
        uptime = common.format_duration_human(int(float(raw)))
    except Exception:
        pass

    cpu = "-"
    try:
        load1, load5, load15 = os.getloadavg()
        cores = max(1, os.cpu_count() or 1)
        load_pct = int((load1 / cores) * 100)
        cpu = f"{load1:.2f} {load5:.2f} {load15:.2f} ({load_pct}%)"
    except Exception:
        pass

    memory = "-"
    try:
        meminfo: Dict[str, int] = {}
        for raw in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in raw:
                continue
            key, val = raw.split(":", 1)
            tokens = val.strip().split()
            if not tokens:
                continue
            meminfo[key.strip()] = int(tokens[0]) * 1024
        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = max(0, total - available)
        if total > 0:
            pct = int((used / total) * 100)
            memory = f"{common.format_bytes(str(used))}/{common.format_bytes(str(total))} ({pct}%)"
    except Exception:
        pass

    return {
        "uptime": uptime,
        "cpu(load1/5/15)": cpu,
        "memory": memory,
    }


def read_proc_cpu_nsec(pid: int) -> Optional[int]:
    if pid <= 0:
        return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").strip()
        end = stat.rfind(")")
        if end < 0:
            return None
        fields = stat[end + 2 :].split()
        if len(fields) < 13:
            return None
        utime_ticks = int(fields[11])
        stime_ticks = int(fields[12])
        clk_tck = int(os.sysconf("SC_CLK_TCK"))
        if clk_tck <= 0:
            return None
        total_nsec = int(((utime_ticks + stime_ticks) / clk_tck) * 1_000_000_000)
        return total_nsec if total_nsec >= 0 else None
    except Exception:
        return None


def read_proc_memory_bytes(pid: int) -> Optional[int]:
    if pid <= 0:
        return None
    try:
        for raw in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if not raw.startswith("VmRSS:"):
                continue
            tokens = raw.split()
            if len(tokens) < 2:
                return None
            value_kb = int(tokens[1])
            if value_kb < 0:
                return None
            return value_kb * 1024
    except Exception:
        return None
    return None


def format_gpu_mib(value: int) -> str:
    if value <= 0:
        return "0MB"
    if value < 1024:
        return f"{value}MB"
    gib = value / 1024
    text = f"{gib:.1f}".rstrip("0").rstrip(".")
    return f"{text}GB"


def read_gpu_memory_by_pid(run_cmd: Callable[..., object]) -> Optional[Dict[int, int]]:
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=pid,used_gpu_memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = run_cmd(cmd, check=False, capture=True)
    except FileNotFoundError:
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None

    by_pid: Dict[int, int] = {}
    output = (getattr(proc, "stdout", "") or "").strip()
    if not output:
        return by_pid

    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",", 1)]
        if len(parts) != 2:
            continue
        pid = common.parse_int(parts[0])
        if pid <= 0:
            continue
        try:
            used_mib = int(parts[1])
        except ValueError:
            continue
        if used_mib < 0:
            continue
        by_pid[pid] = by_pid.get(pid, 0) + used_mib
    return by_pid


def read_unit_usage(
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., Dict[str, str]],
    service_unit: str,
    scope: str = "system",
    gpu_memory_by_pid: Optional[Dict[int, int]] = None,
) -> Dict[str, str]:
    if not unit_exists(service_unit, scope=scope):
        return {"cpu": "-", "memory": "-", "gpu": "-"}
    show = systemctl_show(service_unit, ["CPUUsageNSec", "MemoryCurrent", "MainPID"], scope=scope)
    pid = common.parse_int(show.get("MainPID", ""))
    gpu_usage = "-"
    if gpu_memory_by_pid is not None:
        gpu_usage = format_gpu_mib(gpu_memory_by_pid.get(pid, 0) if pid > 0 else 0)
    cpu_usage = format_cpu_nsec(show.get("CPUUsageNSec", ""))
    if cpu_usage == "-" and pid > 0:
        proc_cpu_nsec = read_proc_cpu_nsec(pid)
        if proc_cpu_nsec is not None:
            cpu_usage = format_cpu_nsec(str(proc_cpu_nsec))
    memory_usage = common.format_bytes(show.get("MemoryCurrent", ""))
    if memory_usage == "-" and pid > 0:
        proc_memory = read_proc_memory_bytes(pid)
        if proc_memory is not None:
            memory_usage = common.format_bytes(str(proc_memory))
    return {
        "cpu": cpu_usage,
        "memory": memory_usage,
        "gpu": gpu_usage,
    }


def get_main_pid(
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., Dict[str, str]],
    service_unit: str,
    scope: str = "system",
) -> int:
    if not unit_exists(service_unit, scope=scope):
        return 0
    show = systemctl_show(service_unit, ["MainPID"], scope=scope)
    return common.parse_int(show.get("MainPID", ""))


def read_unit_pids(
    unit_exists: Callable[..., bool],
    systemctl_show: Callable[..., Dict[str, str]],
    service_unit: str,
    scope: str = "system",
) -> List[int]:
    if not unit_exists(service_unit, scope=scope):
        return []
    show = systemctl_show(service_unit, ["MainPID", "ControlGroup"], scope=scope)
    pids: Set[int] = set()
    main_pid = common.parse_int(show.get("MainPID", ""))
    if main_pid > 0:
        pids.add(main_pid)

    control_group = (show.get("ControlGroup", "") or "").strip()
    if not control_group or control_group == "/":
        return sorted(pids)

    cg_rel = control_group[1:] if control_group.startswith("/") else control_group
    candidates = [
        Path("/sys/fs/cgroup") / cg_rel / "cgroup.procs",
        Path("/sys/fs/cgroup/systemd") / cg_rel / "cgroup.procs",
        Path("/sys/fs/cgroup") / cg_rel / "tasks",
        Path("/sys/fs/cgroup/systemd") / cg_rel / "tasks",
    ]
    for candidate in candidates:
        try:
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                pid = common.parse_int(raw)
                if pid > 0:
                    pids.add(pid)
            if pids:
                break
        except Exception:
            continue
    return sorted(pids)


def parse_listen_ports_from_ss(output: str, pids: Set[int]) -> List[str]:
    ports: List[str] = []
    seen = set()
    if not pids:
        return ports
    for line in output.splitlines():
        match = re.search(r"pid=(\d+),", line)
        if not match:
            continue
        pid = common.parse_int(match.group(1))
        if pid not in pids:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        local = parts[4]
        proto = parts[0].lower()
        if proto not in ("tcp", "tcp6", "udp", "udp6"):
            continue
        port = ""
        if "[" in local and "]:" in local:
            port = local.rsplit("]:", 1)[-1]
        elif ":" in local:
            port = local.rsplit(":", 1)[-1]
        if not port or not port.isdigit():
            continue
        proto_tag = "tcp" if "tcp" in proto else "udp"
        tag = f"{port}/{proto_tag}"
        if tag not in seen:
            seen.add(tag)
            ports.append(tag)
    return sorted(ports)


def summarize_ports(ports: List[str], max_items: int = 2) -> str:
    if not ports:
        return "-"
    if len(ports) <= max_items:
        return ",".join(ports)
    shown = ",".join(ports[:max_items])
    return f"{shown}+{len(ports) - max_items}"


def read_socket_inodes_for_pid(pid: int) -> Set[str]:
    inodes: Set[str] = set()
    if pid <= 0:
        return inodes
    fd_dir = Path(f"/proc/{pid}/fd")
    try:
        for fd in fd_dir.iterdir():
            try:
                target = os.readlink(fd)
            except Exception:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                inodes.add(target[8:-1])
    except Exception:
        return set()
    return inodes


def parse_proc_net_ports(path: Path, proto: str, socket_inodes: Set[str]) -> Set[str]:
    tags: Set[str] = set()
    if not socket_inodes:
        return tags
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return tags
    for raw in lines[1:]:
        parts = raw.split()
        if len(parts) < 10:
            continue
        local = parts[1]
        state = parts[3]
        inode = parts[9]
        if inode not in socket_inodes:
            continue
        if proto == "tcp" and state != "0A":
            continue
        if ":" not in local:
            continue
        _, port_hex = local.split(":", 1)
        try:
            port = int(port_hex, 16)
        except ValueError:
            continue
        if port <= 0:
            continue
        tags.add(f"{port}/{proto}")
    return tags


def read_unit_ports_from_proc(pid: int) -> List[str]:
    inodes = read_socket_inodes_for_pid(pid)
    if not inodes:
        return []
    tags: Set[str] = set()
    tags.update(parse_proc_net_ports(Path(f"/proc/{pid}/net/tcp"), "tcp", inodes))
    tags.update(parse_proc_net_ports(Path(f"/proc/{pid}/net/tcp6"), "tcp", inodes))
    tags.update(parse_proc_net_ports(Path(f"/proc/{pid}/net/udp"), "udp", inodes))
    tags.update(parse_proc_net_ports(Path(f"/proc/{pid}/net/udp6"), "udp", inodes))
    return sorted(tags)


def read_unit_ports_from_proc_pids(pids: List[int]) -> List[str]:
    tags: Set[str] = set()
    for pid in pids:
        tags.update(read_unit_ports_from_proc(pid))
    return sorted(tags)


def read_unit_ports(
    read_unit_pids: Callable[..., List[int]],
    run_cmd: Callable[..., object],
    run_sudo_cmd: Callable[..., object],
    service_unit: str,
    scope: str = "system",
) -> str:
    pids = read_unit_pids(service_unit, scope=scope)
    if not pids:
        return "-"

    cmd = ["ss", "-ltnup"]
    output = ""
    try:
        proc = run_cmd(cmd, check=False, capture=True)
        output = getattr(proc, "stdout", "") or ""
    except FileNotFoundError:
        output = ""
    ports = parse_listen_ports_from_ss(output, set(pids))
    if not ports:
        ports = read_unit_ports_from_proc_pids(pids)

    if not ports:
        try:
            proc = run_sudo_cmd(cmd, check=False, capture=True)
            output = getattr(proc, "stdout", "") or ""
            ports = parse_listen_ports_from_ss(output, set(pids))
        except Exception:
            ports = []

    return summarize_ports(ports)
