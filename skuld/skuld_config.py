from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple


CONFIG_COLUMNS_KEY = "columns"
CONFIG_PROVIDERS_KEY = "providers"


def load_config(config_file: Path) -> Dict[str, Any]:
    if not config_file.exists():
        return {}
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid Skuld config JSON: {config_file}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid Skuld config: {config_file} must contain an object.")
    return data


def save_config(config_file: Path, config: Dict[str, Any]) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def columns_value_as_text(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        items = []
        for item in value:
            if not isinstance(item, str):
                raise RuntimeError("Skuld config columns must be strings.")
            items.append(item)
        return ",".join(items)
    raise RuntimeError("Skuld config columns must be a list of strings.")


def load_columns_text(config_file: Path) -> Optional[str]:
    return columns_value_as_text(load_config(config_file).get(CONFIG_COLUMNS_KEY))


def save_columns(config_file: Path, columns: Optional[Sequence[str]]) -> None:
    try:
        config = load_config(config_file)
    except RuntimeError:
        config = {}
    if columns is None:
        config.pop(CONFIG_COLUMNS_KEY, None)
    else:
        config[CONFIG_COLUMNS_KEY] = list(columns)
    save_config(config_file, config)


def enabled_providers(config_file: Path) -> Tuple[str, ...]:
    raw = load_config(config_file).get(CONFIG_PROVIDERS_KEY)
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise RuntimeError("Skuld config providers must be an object.")
    enabled: list[str] = []
    for name, value in sorted(raw.items()):
        if not isinstance(name, str):
            raise RuntimeError("Skuld config provider names must be strings.")
        if not isinstance(value, dict):
            raise RuntimeError("Skuld config providers must map to objects.")
        enabled_flag = value.get("enabled", False)
        if not isinstance(enabled_flag, bool):
            raise RuntimeError("Skuld config provider enabled flags must be booleans.")
        if enabled_flag:
            enabled.append(name)
    return tuple(enabled)


def provider_enabled(config_file: Path, provider: str) -> bool:
    return provider in enabled_providers(config_file)


def save_provider_enabled(config_file: Path, provider: str, enabled: bool) -> None:
    normalized = (provider or "").strip().lower()
    if not normalized:
        raise RuntimeError("Provider name is required.")
    try:
        config = load_config(config_file)
    except RuntimeError:
        config = {}
    providers = config.get(CONFIG_PROVIDERS_KEY)
    if providers is None or not isinstance(providers, dict):
        providers = {}
    if enabled:
        providers[normalized] = {"enabled": True}
        config[CONFIG_PROVIDERS_KEY] = providers
    else:
        providers.pop(normalized, None)
        if providers:
            config[CONFIG_PROVIDERS_KEY] = providers
        else:
            config.pop(CONFIG_PROVIDERS_KEY, None)
    save_config(config_file, config)


def config_lines(
    config_file: Path,
    columns: Optional[Tuple[str, ...]],
    *,
    providers: Sequence[str] = (),
) -> list[str]:
    rendered = ",".join(columns) if columns else "default"
    exists = "yes" if config_file.exists() else "no"
    providers_text = ",".join(providers) if providers else "-"
    return [
        f"path: {config_file}",
        f"exists: {exists}",
        f"columns: {rendered}",
        f"providers: {providers_text}",
    ]
