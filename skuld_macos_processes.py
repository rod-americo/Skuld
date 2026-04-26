import datetime as dt
import os
import re
import signal
import time
from typing import Callable, Dict, List, Set

import skuld_common as common


def format_bytes_from_kib(kib: int) -> str:
    if kib <= 0:
        return "0.00GB"
    return common.format_bytes(str(kib * 1024))


def read_process_tree_pids(root_pid: int, run_cmd: Callable[..., object]) -> List[int]:
    if root_pid <= 0:
        return []
    proc = run_cmd(["ps", "-axo", "pid=,ppid="], check=False, capture=True)
    children_by_parent: Dict[int, Set[int]] = {}
    for raw in (getattr(proc, "stdout", "") or "").splitlines():
        parts = raw.split()
        if len(parts) != 2:
            continue
        pid = common.parse_int(parts[0])
        ppid = common.parse_int(parts[1])
        if pid <= 0 or ppid <= 0:
            continue
        children_by_parent.setdefault(ppid, set()).add(pid)
    seen: Set[int] = set()
    queue = [root_pid]
    while queue:
        current = queue.pop(0)
        if current in seen or current <= 0:
            continue
        seen.add(current)
        queue.extend(sorted(children_by_parent.get(current, set())))
    return sorted(seen)


def terminate_process_tree(
    root_pid: int,
    read_tree: Callable[[int], List[int]],
    grace_seconds: float = 2.0,
) -> None:
    pids = read_tree(root_pid)
    if not pids:
        return

    ordered = sorted(pids, reverse=True)

    for pid in ordered:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue

    deadline = time.time() + max(0.1, grace_seconds)
    while time.time() < deadline:
        alive = []
        for pid in ordered:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except ProcessLookupError:
                continue
            except PermissionError:
                alive.append(pid)
        if not alive:
            return
        time.sleep(0.1)

    for pid in ordered:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue


def read_cpu_memory(pid: int, run_cmd: Callable[..., object]) -> Dict[str, str]:
    if pid <= 0:
        return {"cpu": "-", "memory": "-"}
    proc = run_cmd(["ps", "-o", "%cpu=", "-o", "rss=", "-p", str(pid)], check=False, capture=True)
    output = (getattr(proc, "stdout", "") or "").strip()
    if not output:
        return {"cpu": "-", "memory": "-"}
    parts = output.split()
    if len(parts) < 2:
        return {"cpu": "-", "memory": "-"}
    cpu = parts[0].replace(",", ".")
    try:
        memory_kib = int(parts[1])
    except ValueError:
        memory_kib = 0
    return {"cpu": f"{cpu}%", "memory": format_bytes_from_kib(memory_kib)}


def parse_lsof_listen_ports(output: str) -> List[str]:
    tags: Set[str] = set()
    for raw in output.splitlines()[1:]:
        line = raw.strip()
        tcp_match = re.search(r"TCP .*:(\d+) \(LISTEN\)", line)
        if tcp_match:
            tags.add(f"{tcp_match.group(1)}/tcp")
        udp_match = re.search(r"UDP .*:(\d+)$", line)
        if udp_match:
            tags.add(f"{udp_match.group(1)}/udp")
    return sorted(tags)


def summarize_ports(ports: List[str], max_items: int = 2) -> str:
    if not ports:
        return "-"
    if len(ports) <= max_items:
        return ",".join(ports)
    return f"{','.join(ports[:max_items])}+{len(ports) - max_items}"


def read_ports(
    pid: int,
    read_tree: Callable[[int], List[int]],
    run_cmd: Callable[..., object],
) -> str:
    pids = read_tree(pid)
    if not pids:
        return "-"
    proc = run_cmd(
        ["lsof", "-Pan", "-p", ",".join(str(item) for item in pids), "-iTCP", "-sTCP:LISTEN", "-iUDP"],
        check=False,
        capture=True,
    )
    return summarize_ports(parse_lsof_listen_ports(getattr(proc, "stdout", "") or ""))


def parse_vm_stat_count(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    if not digits:
        return 0
    return int(digits)


def read_host_overview(run_cmd: Callable[..., object]) -> Dict[str, str]:
    uptime = "-"
    proc = run_cmd(["sysctl", "-n", "kern.boottime"], check=False, capture=True)
    match = re.search(r"sec = (\d+)", getattr(proc, "stdout", "") or "")
    if match:
        boot_time = int(match.group(1))
        uptime = common.format_duration_human(max(0, int(dt.datetime.now().timestamp()) - boot_time))
    cpu = "-"
    try:
        load1, load5, load15 = os.getloadavg()
        cores = max(1, os.cpu_count() or 1)
        pct = int((load1 / cores) * 100)
        cpu = f"{load1:.2f} {load5:.2f} {load15:.2f} ({pct}%)"
    except Exception:
        pass
    memory = "-"
    total_proc = run_cmd(["sysctl", "-n", "hw.memsize"], check=False, capture=True)
    vm_proc = run_cmd(["vm_stat"], check=False, capture=True)
    try:
        total = int((getattr(total_proc, "stdout", "") or "0").strip())
        page_size_match = re.search(r"page size of (\d+) bytes", getattr(vm_proc, "stdout", "") or "")
        page_size = int(page_size_match.group(1)) if page_size_match else 4096
        pages_free = 0
        pages_inactive = 0
        pages_speculative = 0
        for raw in (getattr(vm_proc, "stdout", "") or "").splitlines():
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            count = parse_vm_stat_count(value)
            if key.startswith("Pages free"):
                pages_free = count
            elif key.startswith("Pages inactive"):
                pages_inactive = count
            elif key.startswith("Pages speculative"):
                pages_speculative = count
        available = (pages_free + pages_inactive + pages_speculative) * page_size
        used = max(0, total - available)
        if total > 0:
            pct = int((used / total) * 100)
            memory = f"{common.format_bytes(str(used))}/{common.format_bytes(str(total))} ({pct}%)"
    except Exception:
        pass
    return {"uptime": uptime, "cpu(load1/5/15)": cpu, "memory": memory}
