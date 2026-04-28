from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import skuld_common as common


NGINX_PROVIDER = "nginx"
NGINX_PROVIDER_TOKEN = "provider:nginx"
NGINX_ROUTE_TABLE_COLUMNS = (
    {"key": "id", "header": "id", "min_width": 2, "shrink": False},
    {"key": "server", "header": "server", "min_width": 12, "shrink": True},
    {"key": "listen", "header": "listen", "min_width": 6, "shrink": True},
    {"key": "target", "header": "target", "min_width": 12, "shrink": True},
)
NGINX_ROUTE_SHRINK_ORDER = ("server", "target", "listen")
NGINX_ROUTE_HIDE_ORDER: Tuple[str, ...] = ()

CONFIG_FILE_RE = re.compile(r"^# configuration file (?P<path>.+?)(?::\d*)?\s*$")
TARGET_PORT_RE = re.compile(r":(?P<port>\d+)(?:$|[\s/;])")
PORT_VALUE_RE = re.compile(r"(?P<port>\d+)/(?:tcp|udp)")
UPSTREAM_HTTP_RE = re.compile(r"^https?://(?P<name>[A-Za-z0-9_.-]+)$")


@dataclass
class NginxRoute:
    index: int
    server: str
    listen: str
    target: str
    source: str


def is_provider_target(token: str) -> bool:
    return (token or "").strip().lower() in {NGINX_PROVIDER, NGINX_PROVIDER_TOKEN}


def _clean_config_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""
    hash_index = line.find("#")
    if hash_index >= 0:
        line = line[:hash_index].rstrip()
    return line


def _normalize_target(value: str, upstreams: Dict[str, List[str]]) -> str:
    target = value.strip()
    if not target:
        return "-"
    match = UPSTREAM_HTTP_RE.match(target)
    if match:
        name = match.group("name")
        members = upstreams.get(name)
        if members:
            return ", ".join(members)
    return target


def _simplify_listen_value(value: str) -> str:
    raw = value.strip()
    if not raw:
        return "-"
    match = re.search(r"(?::|\b)(\d+)\b", raw)
    if match:
        return match.group(1)
    return raw.split()[0]


def _simplify_target_value(value: str) -> str:
    raw = value.strip()
    if not raw or raw == "-":
        return "-"
    if raw == "static":
        return "static"
    if raw.startswith("unix:"):
        return raw[5:]
    match = TARGET_PORT_RE.search(raw)
    if match:
        return match.group("port")
    if raw.startswith("/"):
        return raw
    return raw


def parse_nginx_dump(text: str) -> List[NginxRoute]:
    routes: List[NginxRoute] = []
    upstreams: Dict[str, List[str]] = {}
    source = ""
    block_stack: List[Tuple[str, Optional[str], Optional[dict[str, object]]]] = []

    def current_server_block() -> Optional[dict[str, object]]:
        for kind, _name, data in reversed(block_stack):
            if kind == "server":
                return data
        return None

    def current_upstream_name() -> Optional[str]:
        for kind, name, _data in reversed(block_stack):
            if kind == "upstream":
                return name
        return None

    def finalize_server(server_data: dict[str, object]) -> None:
        names = [item for item in server_data.get("server_names", []) if item]
        listens = [item for item in server_data.get("listens", []) if item]
        targets = [item for item in server_data.get("targets", []) if item]
        static_paths = [item for item in server_data.get("static_paths", []) if item]
        server_name = ", ".join(names) if names else "_"
        listen = ", ".join(listens) if listens else "-"
        normalized_targets = [
            _normalize_target(str(item), upstreams)
            for item in targets
        ]
        if not normalized_targets:
            normalized_targets = list(dict.fromkeys(static_paths)) or ["static"]
        for target in normalized_targets:
            routes.append(
                NginxRoute(
                    index=0,
                    server=server_name,
                    listen=listen,
                    target=target,
                    source=str(server_data.get("source", "") or "-"),
                )
            )

    for raw in (text or "").splitlines():
        marker_match = CONFIG_FILE_RE.match(raw.strip())
        if marker_match:
            source = marker_match.group("path")
            continue

        line = _clean_config_line(raw)
        if not line:
            continue

        if line.endswith("{"):
            prefix = line[:-1].strip()
            if prefix == "server":
                block_stack.append(
                    (
                        "server",
                        None,
                        {
                            "source": source,
                            "server_names": [],
                            "listens": [],
                            "targets": [],
                            "static_paths": [],
                        },
                    )
                )
                continue
            if prefix.startswith("upstream "):
                block_stack.append(("upstream", prefix.split(None, 1)[1].strip(), None))
                continue
            block_stack.append(("other", None, None))
            continue

        if line == "}":
            if not block_stack:
                continue
            kind, _name, data = block_stack.pop()
            if kind == "server" and data is not None:
                finalize_server(data)
            continue

        if not line.endswith(";"):
            continue

        directive = line[:-1].strip()
        if not directive:
            continue
        if " " in directive:
            key, value = directive.split(None, 1)
        else:
            key, value = directive, ""

        current_server = current_server_block()
        if current_server is not None:
            if key == "listen":
                current_server["listens"].append(value.strip())
                continue
            if key == "server_name":
                current_server["server_names"].extend(
                    token
                    for token in value.split()
                    if token and not token.startswith("$")
                )
                continue
            if key in {"root", "alias"}:
                current_server["static_paths"].append(value.strip())
                continue
            if key in {"proxy_pass", "fastcgi_pass", "uwsgi_pass", "scgi_pass", "grpc_pass"}:
                current_server["targets"].append(value.strip())
                continue

        upstream_name = current_upstream_name()
        if upstream_name and key == "server":
            upstreams.setdefault(upstream_name, []).append(value.strip())

    routes.sort(key=lambda item: (item.server.lower(), item.listen.lower(), item.target.lower(), item.source.lower()))
    for index, route in enumerate(routes, start=1):
        route.index = index
    return routes


def discover_routes(
    *,
    run: Callable[..., object],
    run_sudo: Callable[..., object],
) -> List[NginxRoute]:
    proc = run(["nginx", "-T"], check=False, capture=True)
    if proc.returncode != 0:
        proc = run_sudo(["nginx", "-T"], check=False, capture=True)
    if proc.returncode != 0:
        return []
    return parse_nginx_dump((proc.stdout or "") + "\n" + (proc.stderr or ""))


def read_unit_ports_map(
    services: Sequence[object],
    *,
    read_unit_ports: Callable[..., str],
) -> Dict[str, List[str]]:
    port_map: Dict[str, List[str]] = {}
    for service in services:
        unit = f"{service.name}.service"
        port_text = read_unit_ports(unit, scope=service.scope)
        for match in PORT_VALUE_RE.finditer(port_text or ""):
            port_map.setdefault(match.group("port"), []).append(service.display_name)
    return port_map


def service_names_for_target(target: str, port_map: Dict[str, List[str]]) -> str:
    match = TARGET_PORT_RE.search(target)
    if not match:
        return "-"
    names = port_map.get(match.group("port"), [])
    if not names:
        return "-"
    ordered = sorted(dict.fromkeys(names), key=str.lower)
    return ", ".join(ordered)


def _join_unique(values: Sequence[str]) -> str:
    items = [item for item in values if item and item != "-"]
    if not items:
        return "-"
    return ", ".join(dict.fromkeys(items))


def build_route_rows(
    routes: Sequence[NginxRoute],
) -> List[Dict[str, object]]:
    grouped: Dict[str, Dict[str, object]] = {}
    order: List[str] = []
    for route in routes:
        item = grouped.get(route.server)
        if item is None:
            item = {
                "server": route.server,
                "listens": [],
                "targets": [],
                "index": route.index,
            }
            grouped[route.server] = item
            order.append(route.server)
        item["listens"].append(route.listen)
        item["targets"].append(route.target)

    rows: List[Dict[str, object]] = []
    for server in order:
        item = grouped[server]
        simplified_listens = [
            _simplify_listen_value(str(value))
            for value in item["listens"]
            for value in str(value).split(",")
        ]
        simplified_targets = [
            _simplify_target_value(str(value))
            for value in item["targets"]
        ]
        non_static_targets = [value for value in simplified_targets if value not in {"-", "static"}]
        if non_static_targets:
            rendered_target = _join_unique(non_static_targets)
        else:
            rendered_target = "static"
        rows.append(
            {
                "id": item["index"],
                "server": item["server"],
                "listen": _join_unique(simplified_listens),
                "target": rendered_target,
            }
        )
    return rows


def fit_nginx_route_table(
    rows: List[Dict[str, object]],
    max_width: Optional[int] = None,
) -> Tuple[List[str], List[List[str]]]:
    return common.fit_table(
        rows,
        service_columns=NGINX_ROUTE_TABLE_COLUMNS,
        shrink_order=NGINX_ROUTE_SHRINK_ORDER,
        hide_order=NGINX_ROUTE_HIDE_ORDER,
        max_width=max_width,
    )


def render_routes_table(
    routes: Sequence[NginxRoute],
    *,
    render_table: Callable[[List[str], List[List[str]]], None],
    emit_blank: Callable[[], None] = print,
    emit: Callable[[str], None] = print,
) -> None:
    emit_blank()
    emit("nginx routes")
    emit("")
    if not routes:
        emit("No visible nginx routes were discovered.")
        return
    rows = build_route_rows(routes)
    headers, fitted_rows = fit_nginx_route_table(rows)
    render_table(headers, fitted_rows)


def describe_route_lines(
    service: object,
    *,
    routes: Sequence[NginxRoute],
    read_unit_ports: Callable[..., str],
) -> List[str]:
    port_map = read_unit_ports_map([service], read_unit_ports=read_unit_ports)
    matched = [
        route
        for route in routes
        if service_names_for_target(route.target, port_map) != "-"
    ]
    if not matched:
        return []
    lines = ["---", "nginx routes:"]
    for route in matched:
        lines.extend(
            [
                f"- server: {route.server}",
                f"  listen: {route.listen}",
                f"  target: {route.target}",
                f"  source: {route.source}",
            ]
        )
    return lines
