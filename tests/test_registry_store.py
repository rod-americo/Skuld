from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from skuld_registry import RegistryStore


@dataclass
class DummyService:
    name: str
    exec_cmd: str
    description: str
    display_name: str = ""
    id: int = 0


def normalize(item: dict[str, object]) -> DummyService:
    name = str(item.get("name", "")).strip()
    return DummyService(
        name=name,
        exec_cmd=str(item.get("exec_cmd", "")).strip(),
        description=str(item.get("description", "")).strip(),
        display_name=str(item.get("display_name", name)).strip() or name,
        id=int(item.get("id", 0) or 0),
    )


class RegistryStoreTest(unittest.TestCase):
    def make_store(self, root: Path) -> RegistryStore[DummyService]:
        return RegistryStore(
            home=root,
            registry_file=root / "services.json",
            normalize_item=normalize,
            validate_service=lambda _service, _index: None,
            sort_key=lambda service: (service.name, service.id),
            service_key=lambda service: service.name,
            required_fields=("name", "exec_cmd", "description"),
        )

    def test_load_can_normalize_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self.make_store(root)
            raw = json.dumps(
                [
                    {"name": "b", "exec_cmd": "/b", "description": "B", "extra": "drop"},
                    {"name": "a", "exec_cmd": "/a", "description": "A", "id": 0},
                ]
            )
            store.registry_file.write_text(raw, encoding="utf-8")

            services = store.load(write_back=False)

            self.assertEqual([service.name for service in services], ["a", "b"])
            self.assertEqual({service.name: service.id for service in services}, {"a": 2, "b": 1})
            self.assertEqual(store.registry_file.read_text(encoding="utf-8"), raw)

    def test_upsert_preserves_existing_id_for_same_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self.make_store(root)
            store.save([DummyService("api", "/old", "API", "api", 9)])

            store.upsert(DummyService("api", "/new", "API new", "api"))

            [service] = store.load()
            self.assertEqual(service.id, 9)
            self.assertEqual(service.exec_cmd, "/new")


if __name__ == "__main__":
    unittest.main()
