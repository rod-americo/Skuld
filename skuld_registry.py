from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Generic, Hashable, Iterable, List, Sequence, TypeVar

import skuld_observability as observability


ServiceT = TypeVar("ServiceT")


class RegistryStore(Generic[ServiceT]):
    def __init__(
        self,
        *,
        home: Path,
        registry_file: Path,
        normalize_item: Callable[[dict[str, object]], ServiceT],
        validate_service: Callable[[ServiceT, int], None],
        sort_key: Callable[[ServiceT], object],
        service_key: Callable[[ServiceT], Hashable],
        required_fields: Sequence[str],
    ) -> None:
        self.home = home
        self.registry_file = registry_file
        self.normalize_item = normalize_item
        self.validate_service = validate_service
        self.sort_key = sort_key
        self.service_key = service_key
        self.required_fields = tuple(required_fields)

    def ensure_storage(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self.registry_file.write_text("[]", encoding="utf-8")

    def load(self, *, write_back: bool = False) -> List[ServiceT]:
        self.ensure_storage()
        raw_text = self.registry_file.read_text(encoding="utf-8")
        services, changed, canonical_text = self.normalize_text(raw_text)
        if write_back and (changed or raw_text != canonical_text):
            observability.debug("registry_write", path=self.registry_file)
            self.registry_file.write_text(canonical_text, encoding="utf-8")
        return services

    def normalize_text(self, raw_text: str) -> tuple[List[ServiceT], bool, str]:
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid registry JSON at {self.registry_file}: {exc}") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"Invalid registry format at {self.registry_file}: root must be an array.")
        return self.normalize_data(data)

    def normalize_data(self, data: list[object]) -> tuple[List[ServiceT], bool, str]:
        services: List[ServiceT] = []
        changed = False
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(f"Invalid registry entry #{index}: expected object.")
            service = self.normalize_item(item)
            self._validate_required(service, index)
            self.validate_service(service, index)
            services.append(service)
            if self._item_changed(service, item):
                changed = True

        if self._assign_missing_or_duplicate_ids(services):
            changed = True

        self._validate_unique_display_names(services)
        ordered = sorted(services, key=self.sort_key)
        if ordered != services:
            changed = True

        canonical_text = self._encode(ordered)
        return ordered, changed, canonical_text

    def save(self, services: Iterable[ServiceT]) -> None:
        self.ensure_storage()
        ordered = sorted(list(services), key=self.sort_key)
        self.registry_file.write_text(self._encode(ordered), encoding="utf-8")

    def upsert(self, service: ServiceT) -> None:
        services = self.load()
        target_key = self.service_key(service)
        for existing in services:
            if getattr(existing, "display_name") != getattr(service, "display_name"):
                continue
            if getattr(existing, "id") == getattr(service, "id") or self.service_key(existing) == target_key:
                continue
            raise RuntimeError(f"Display name '{getattr(service, 'display_name')}' is already in use.")

        by_key = {self.service_key(item): item for item in services}
        existing = by_key.get(target_key)
        if getattr(service, "id") <= 0 and existing:
            setattr(service, "id", getattr(existing, "id"))
        if getattr(service, "id") <= 0:
            max_id = max((getattr(item, "id") for item in services), default=0)
            setattr(service, "id", max_id + 1)
        by_key[target_key] = service
        self.save(by_key.values())

    def remove(self, key: Hashable) -> None:
        self.save([service for service in self.load() if self.service_key(service) != key])

    def _validate_required(self, service: ServiceT, index: int) -> None:
        missing = [field for field in self.required_fields if not getattr(service, field)]
        if missing:
            fields = "', '".join(self.required_fields)
            raise RuntimeError(f"Invalid registry entry #{index}: fields '{fields}' are required.")

    def _item_changed(self, service: ServiceT, item: dict[str, object]) -> bool:
        normalized = asdict(service)  # type: ignore[arg-type]
        known_keys = set(normalized)
        if set(item) - known_keys:
            return True
        existing = {key: item.get(key) for key in known_keys if key in item}
        return normalized != existing

    def _assign_missing_or_duplicate_ids(self, services: List[ServiceT]) -> bool:
        changed = False
        used_ids = set()
        next_id = 1
        for service in services:
            service_id = int(getattr(service, "id"))
            if service_id <= 0 or service_id in used_ids:
                while next_id in used_ids:
                    next_id += 1
                setattr(service, "id", next_id)
                service_id = next_id
                changed = True
            used_ids.add(service_id)
        return changed

    def _validate_unique_display_names(self, services: List[ServiceT]) -> None:
        display_names = set()
        for service in services:
            display_name = getattr(service, "display_name")
            if display_name in display_names:
                raise RuntimeError(f"Duplicate display name in registry: '{display_name}'.")
            display_names.add(display_name)

    def _encode(self, services: List[ServiceT]) -> str:
        return json.dumps([asdict(service) for service in services], indent=2, ensure_ascii=False) + "\n"
