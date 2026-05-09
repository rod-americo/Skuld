from __future__ import annotations

import plistlib
import tempfile
import types
import unittest
from pathlib import Path

from skuld import skuld_macos_managed as managed


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class MacOSManagedServicesTest(unittest.TestCase):
    def test_create_agent_service_writes_wrapper_plist_registers_and_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = []
            messages = []
            calls = []

            service = managed.create_agent_service(
                name="api",
                command=["python", "app.py"],
                working_dir=str(root),
                service_factory=types.SimpleNamespace,
                validate_name=lambda name: calls.append(("validate", name)),
                ensure_display_name_available=lambda name: calls.append(("display", name)),
                get_managed=lambda name: None,
                service_label=lambda name: f"io.skuld.{name}",
                plist_path_for_service=lambda service: root / f"{service.name}.plist",
                wrapper_script_for_service=lambda name, scope: root / f"{name}.sh",
                log_dir_for_service=lambda name, scope: root / "logs" / name,
                event_file_for_service=lambda name, scope: root / "events" / f"{name}.jsonl",
                bootstrap_service=lambda service: calls.append(("bootstrap", service.name)),
                kickstart_service=lambda service, kill_existing=False: (
                    calls.append(("kickstart", service.name, kill_existing)) or completed()
                ),
                upsert_registry=saved.append,
                ok=messages.append,
            )

            plist = plistlib.loads((root / "api.plist").read_bytes())
            wrapper = (root / "api.sh").read_text(encoding="utf-8")

        self.assertEqual(service.name, "api")
        self.assertTrue(service.managed_by_skuld)
        self.assertEqual(saved[0].launchd_label, "io.skuld.api")
        self.assertEqual(plist["ProgramArguments"], [str(root / "api.sh")])
        self.assertEqual(plist["StandardOutPath"], str(root / "logs/api/stdout.log"))
        self.assertIn("python app.py", wrapper)
        self.assertIn(("bootstrap", "api"), calls)
        self.assertIn(("kickstart", "api", False), calls)
        self.assertEqual(messages, ["Created and started Skuld-managed LaunchAgent 'api'."])

    def test_create_agent_service_refuses_existing_plist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "api.plist").write_text("exists", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                managed.create_agent_service(
                    name="api",
                    command=["python", "app.py"],
                    working_dir=str(root),
                    service_factory=types.SimpleNamespace,
                    validate_name=lambda name: None,
                    ensure_display_name_available=lambda name: None,
                    get_managed=lambda name: None,
                    service_label=lambda name: f"io.skuld.{name}",
                    plist_path_for_service=lambda service: root / f"{service.name}.plist",
                    wrapper_script_for_service=lambda name, scope: root / f"{name}.sh",
                    log_dir_for_service=lambda name, scope: root / "logs" / name,
                    event_file_for_service=lambda name, scope: root / "events" / f"{name}.jsonl",
                    bootstrap_service=lambda service: None,
                    kickstart_service=lambda service, kill_existing=False: completed(),
                    upsert_registry=lambda service: None,
                    ok=lambda message: None,
                )

    def test_delete_agent_service_requires_skuld_managed_agent(self) -> None:
        external = types.SimpleNamespace(
            name="api",
            scope="agent",
            display_name="api",
            managed_by_skuld=False,
        )

        with self.assertRaisesRegex(RuntimeError, "externally tracked"):
            managed.delete_agent_service(
                external,
                bootout_service=lambda service: None,
                remove_registry=lambda name: None,
                plist_path_for_service=lambda service: Path("/tmp/missing.plist"),
                wrapper_script_for_service=lambda name, scope: Path("/tmp/missing.sh"),
                ok=lambda message: None,
            )

    def test_delete_agent_service_removes_definition_files_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plist = root / "api.plist"
            wrapper = root / "api.sh"
            plist.write_text("plist", encoding="utf-8")
            wrapper.write_text("wrapper", encoding="utf-8")
            calls = []
            removed = []
            messages = []
            service = types.SimpleNamespace(
                name="api",
                scope="agent",
                display_name="api",
                managed_by_skuld=True,
            )

            managed.delete_agent_service(
                service,
                bootout_service=lambda service: calls.append(("bootout", service.name)),
                remove_registry=removed.append,
                plist_path_for_service=lambda service: plist,
                wrapper_script_for_service=lambda name, scope: wrapper,
                ok=messages.append,
            )

            self.assertFalse(plist.exists())
            self.assertFalse(wrapper.exists())

        self.assertEqual(calls, [("bootout", "api")])
        self.assertEqual(removed, ["api"])
        self.assertEqual(messages, ["Deleted Skuld-managed LaunchAgent 'api'."])


if __name__ == "__main__":
    unittest.main()
