from __future__ import annotations

import types
import unittest

import skuld_linux_nginx as nginx


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class LinuxNginxTest(unittest.TestCase):
    def test_parse_nginx_dump_extracts_routes_and_sources(self) -> None:
        dump = """
# configuration file /etc/nginx/nginx.conf:1
http {
# configuration file /etc/nginx/conf.d/upstreams.conf:1
upstream app_backend {
    server 127.0.0.1:5005;
}
# configuration file /etc/nginx/conf.d/api.conf
server {
    listen 443 ssl;
    server_name api.example.com www.api.example.com;
    location / {
        proxy_pass http://app_backend;
    }
}
# configuration file /etc/nginx/conf.d/static.conf:1
server {
    listen 80;
    server_name static.example.com;
}
}
        """

        routes = nginx.parse_nginx_dump(dump)

        self.assertEqual(
            [(route.server, route.listen, route.target, route.source) for route in routes],
            [
                (
                    "api.example.com, www.api.example.com",
                    "443 ssl",
                    "127.0.0.1:5005",
                    "/etc/nginx/conf.d/api.conf",
                ),
                (
                    "static.example.com",
                    "80",
                    "static",
                    "/etc/nginx/conf.d/static.conf",
                ),
            ],
        )

    def test_discover_routes_falls_back_to_sudo(self) -> None:
        calls: list[tuple[str, tuple[str, ...]]] = []

        def run(cmd, **_kwargs):
            calls.append(("run", tuple(cmd)))
            return completed(returncode=1)

        def run_sudo(cmd, **_kwargs):
            calls.append(("sudo", tuple(cmd)))
            return completed(
                stdout="""
# configuration file /etc/nginx/conf.d/api.conf:1
server {
    listen 443 ssl;
    server_name api.example.com;
    proxy_pass http://127.0.0.1:5005;
}
                """
            )

        routes = nginx.discover_routes(run=run, run_sudo=run_sudo)

        self.assertEqual(calls, [("run", ("nginx", "-T")), ("sudo", ("nginx", "-T"))])
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].server, "api.example.com")

    def test_describe_route_lines_match_service_by_port(self) -> None:
        service = types.SimpleNamespace(name="api", scope="system", display_name="api")
        routes = [
            nginx.NginxRoute(1, "api.example.com", "443 ssl", "http://127.0.0.1:5005", "/etc/nginx/conf.d/api.conf"),
            nginx.NginxRoute(2, "admin.example.com", "443 ssl", "http://127.0.0.1:6000", "/etc/nginx/conf.d/admin.conf"),
        ]

        lines = nginx.describe_route_lines(
            service,
            routes=routes,
            read_unit_ports=lambda unit, scope="system": "5005/tcp",
        )

        self.assertIn("nginx routes:", lines)
        self.assertIn("  source: /etc/nginx/conf.d/api.conf", lines)
        self.assertNotIn("admin.example.com", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
