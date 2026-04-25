#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR_CONFIG_PATH = ROOT / "config" / "doctor.json"
REQUIRED_FILES = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "PROJECT_GATE.md",
    ROOT / "START_CHECKLIST.md",
    ROOT / "CHANGELOG.md",
    DOCTOR_CONFIG_PATH,
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "CONTRACTS.md",
    ROOT / "docs" / "OPERATIONS.md",
    ROOT / "docs" / "DECISIONS.md",
    ROOT / "scripts" / "check_project_gate.py",
]
KEY_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "PROJECT_GATE.md",
    ROOT / "START_CHECKLIST.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "CONTRACTS.md",
    ROOT / "docs" / "OPERATIONS.md",
    ROOT / "docs" / "DECISIONS.md",
]
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "available",
    "before",
    "between",
    "current",
    "default",
    "during",
    "existing",
    "local",
    "project",
    "repository",
    "service",
    "services",
    "should",
    "system",
    "through",
    "where",
    "which",
    "without",
}
KNOWN_WARNING_CODES = {
    "scope_negative_mismatch",
    "objective_mismatch",
    "scope_architecture_mismatch",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def add_warning(warnings: list[dict[str, str]], code: str, message: str) -> None:
    warnings.append({"code": code, "message": message})


def extract_section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue

        level = len(line) - len(line.lstrip("#"))
        section: list[str] = []
        for candidate in lines[index + 1 :]:
            stripped = candidate.strip()
            if stripped.startswith("#"):
                candidate_level = len(stripped) - len(stripped.lstrip("#"))
                if candidate_level <= level:
                    break
            section.append(candidate)
        return "\n".join(section).strip()
    return None


def extract_first_code_block(section: str | None) -> str | None:
    if not section:
        return None
    match = re.search(r"```(?:bash|text)?\n(.*?)```", section, flags=re.S)
    if not match:
        return None
    return match.group(1).strip()


def normalize_block(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_bullets(section: str | None) -> list[str]:
    if not section:
        return []
    bullets: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def extract_readme_entrypoints(text: str) -> list[str]:
    section = extract_section(text, "## Entrypoints") or ""
    return re.findall(r"`([^`]+)`", section)


def normalize_token(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", token.lower())
    return cleaned.strip("_-")


def significant_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[A-Za-z0-9_-]+", text.lower()):
        if len(token) < 5:
            continue
        if token in STOPWORDS:
            continue
        normalized = normalize_token(token)
        if normalized:
            tokens.add(normalized)
    return tokens


def compare_token_sets(
    left_text: str,
    right_text: str,
    alias_groups: list[set[str]],
) -> dict[str, object]:
    left_tokens = significant_tokens(left_text)
    right_tokens = significant_tokens(right_text)
    shared_tokens = left_tokens & right_tokens
    matched_alias_indexes: list[int] = []

    if not shared_tokens:
        for index, group in enumerate(alias_groups):
            if left_tokens & group and right_tokens & group:
                matched_alias_indexes.append(index)

    return {
        "shared_tokens": shared_tokens,
        "matched_alias_indexes": matched_alias_indexes,
    }


def load_doctor_config(errors: list[str]) -> dict[str, object]:
    default = {
        "version": 1,
        "ignored_warnings": [],
        "token_alias_groups": [],
    }
    if not DOCTOR_CONFIG_PATH.exists():
        return default

    try:
        raw = json.loads(read_text(DOCTOR_CONFIG_PATH))
    except json.JSONDecodeError as exc:
        add_error(errors, f"config/doctor.json is invalid JSON: {exc}")
        return default

    if not isinstance(raw, dict):
        add_error(errors, "config/doctor.json must be a JSON object")
        return default

    if raw.get("version", 1) != 1:
        add_error(errors, "config/doctor.json uses an unsupported version")

    ignored_raw = raw.get("ignored_warnings", [])
    normalized_ignored: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    if not isinstance(ignored_raw, list):
        add_error(errors, "config/doctor.json: ignored_warnings must be a list")
    else:
        for index, item in enumerate(ignored_raw):
            if not isinstance(item, dict):
                add_error(errors, f"config/doctor.json: ignored_warnings[{index}] must be an object")
                continue
            code = str(item.get("code", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if code not in KNOWN_WARNING_CODES:
                add_error(errors, f"config/doctor.json: unknown warning code in ignored_warnings[{index}]")
                continue
            if code in seen_codes:
                add_error(errors, f"config/doctor.json: duplicate ignored warning code {code}")
                continue
            if len(reason) < 12:
                add_error(errors, f"config/doctor.json: reason too short for ignored_warnings[{index}]")
                continue
            seen_codes.add(code)
            normalized_ignored.append({"code": code, "reason": reason})

    alias_groups_raw = raw.get("token_alias_groups", [])
    normalized_alias_groups: list[set[str]] = []
    if not isinstance(alias_groups_raw, list):
        add_error(errors, "config/doctor.json: token_alias_groups must be a list")
    else:
        for index, item in enumerate(alias_groups_raw):
            if not isinstance(item, list):
                add_error(errors, f"config/doctor.json: token_alias_groups[{index}] must be a list")
                continue
            tokens = {normalize_token(str(value)) for value in item if normalize_token(str(value))}
            if len(tokens) < 2:
                add_error(errors, f"config/doctor.json: token_alias_groups[{index}] needs at least two valid terms")
                continue
            normalized_alias_groups.append(tokens)

    return {
        "version": 1,
        "ignored_warnings": normalized_ignored,
        "token_alias_groups": normalized_alias_groups,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Skuld structural documentation and gate consistency.")
    parser.add_argument("--strict", action="store_true", help="Treat semantic warnings as failures.")
    parser.add_argument("--audit-config", action="store_true", help="Audit config/doctor.json overrides.")
    return parser.parse_args()


def print_warning_list(title: str, warnings: list[dict[str, str]], stream: object) -> None:
    if not warnings:
        return
    print(title, file=stream)
    for warning in warnings:
        print(f"- [{warning['code']}] {warning['message']}", file=stream)


def run_config_audit(
    doctor_config: dict[str, object],
    raw_warnings: list[dict[str, str]],
    comparison_reports: list[dict[str, object]],
) -> int:
    ignored_entries = list(doctor_config["ignored_warnings"])
    alias_groups = list(doctor_config["token_alias_groups"])
    ignored_reason_by_code = {
        item["code"]: item["reason"]
        for item in ignored_entries
        if isinstance(item, dict) and "code" in item and "reason" in item
    }
    raw_codes = {item["code"] for item in raw_warnings}
    stale_ignored_codes = sorted(set(ignored_reason_by_code) - raw_codes)
    suppressed_warnings = [item for item in raw_warnings if item.get("code") in ignored_reason_by_code]

    alias_usage: dict[int, list[str]] = {}
    for report in comparison_reports:
        for alias_index in report["matched_alias_indexes"]:
            alias_usage.setdefault(alias_index, []).append(str(report["code"]))

    print("Doctor config audit:")
    print(f"- ignored_warnings: {len(ignored_entries)}")
    print(f"- token_alias_groups: {len(alias_groups)}")

    if not ignored_entries and not alias_groups:
        print("- no overrides configured")

    if suppressed_warnings:
        print("")
        print("Currently suppressed warnings:")
        for warning in suppressed_warnings:
            code = str(warning["code"])
            reason = ignored_reason_by_code.get(code, "no reason registered")
            print(f"- [{code}] {warning['message']}")
            print(f"  reason: {reason}")

    if stale_ignored_codes:
        print("")
        print("Ignored warnings with no current effect:", file=sys.stderr)
        for code in stale_ignored_codes:
            print(f"- [{code}] {ignored_reason_by_code[code]}", file=sys.stderr)

    if alias_usage:
        print("")
        print("Alias groups in use:")
        for index in sorted(alias_usage):
            tokens = ", ".join(sorted(alias_groups[index]))
            codes = ", ".join(sorted(set(alias_usage[index])))
            print(f"- group {index}: {tokens} -> {codes}")

    unused_alias_indexes = [index for index in range(len(alias_groups)) if index not in alias_usage]
    if unused_alias_indexes:
        print("")
        print("Alias groups with no observed use right now:")
        for index in unused_alias_indexes:
            tokens = ", ".join(sorted(alias_groups[index]))
            print(f"- group {index}: {tokens}")

    if stale_ignored_codes:
        return 1

    print("")
    print("Doctor config audit passed.")
    return 0


def check_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            add_error(errors, f"required file is missing: {path.relative_to(ROOT)}")


def check_placeholders(errors: list[str], docs: dict[Path, str]) -> None:
    for path, text in docs.items():
        if "{{" in text or "}}" in text:
            add_error(errors, f"unresolved placeholder in {path.relative_to(ROOT)}")
        if re.search(r"\bTODO:", text):
            add_error(errors, f"remaining TODO marker in {path.relative_to(ROOT)}")


def check_required_sections(errors: list[str]) -> None:
    required_sections = {
        ROOT / "README.md": [
            "## What This Repository Is",
            "## What This Repository Is Not",
            "### 4. Run",
        ],
        ROOT / "AGENTS.md": [
            "## Minimum Reading Order",
            "## Minimum Validation",
            "## Hotspots",
        ],
        ROOT / "PROJECT_GATE.md": [
            "## 1. Why does this project exist?",
            "## 4. What must this project not carry?",
        ],
        ROOT / "START_CHECKLIST.md": [
            "## 1. Baseline Added Or Recovered",
            "## 3. What Is Intentionally Not Done Yet",
        ],
        ROOT / "docs" / "ARCHITECTURE.md": [
            "## 2. Scope",
            "## 5. Main Flow",
        ],
        ROOT / "docs" / "CONTRACTS.md": [
            "## 2. Canonical Inputs",
            "## 3. Canonical Outputs",
        ],
        ROOT / "docs" / "OPERATIONS.md": [
            "### Primary Run",
            "## 5. Minimum Validation",
        ],
        ROOT / "docs" / "DECISIONS.md": [
            "## 2026-04-25 - Recover The Existing Repository Instead Of Rescaffolding",
        ],
    }
    for path, headings in required_sections.items():
        text = read_text(path)
        for heading in headings:
            if extract_section(text, heading) is None:
                add_error(errors, f"missing section in {path.relative_to(ROOT)}: {heading}")


def check_consistency(errors: list[str]) -> None:
    readme_text = read_text(ROOT / "README.md")
    agents_text = read_text(ROOT / "AGENTS.md")
    operations_text = read_text(ROOT / "docs" / "OPERATIONS.md")

    readme_run = normalize_block(extract_first_code_block(extract_section(readme_text, "### 4. Run")))
    ops_run = normalize_block(extract_first_code_block(extract_section(operations_text, "### Primary Run")))
    if readme_run and ops_run and readme_run != ops_run:
        add_error(errors, "README.md and docs/OPERATIONS.md disagree on the primary run command")

    readme_entrypoints = [normalize_block(item) for item in extract_readme_entrypoints(readme_text)]
    readme_entrypoints = [item for item in readme_entrypoints if item]
    if readme_entrypoints and ops_run and ops_run not in readme_entrypoints:
        add_error(errors, "README.md does not list the primary run command in entrypoints")

    agents_validation = normalize_block(
        extract_first_code_block(extract_section(agents_text, "## Minimum Validation"))
    )
    ops_validation = normalize_block(
        extract_first_code_block(extract_section(operations_text, "## 5. Minimum Validation"))
    )
    if agents_validation and ops_validation and agents_validation != ops_validation:
        add_error(errors, "AGENTS.md and docs/OPERATIONS.md disagree on minimum validation")


def check_gate(errors: list[str]) -> None:
    gate_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_project_gate.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if gate_check.returncode != 0:
        add_error(errors, "PROJECT_GATE.md failed scripts/check_project_gate.py")


def collect_semantic_warnings(
    warnings: list[dict[str, str]],
    comparison_reports: list[dict[str, object]],
    alias_groups: list[set[str]],
) -> None:
    readme_text = read_text(ROOT / "README.md")
    gate_text = read_text(ROOT / "PROJECT_GATE.md")
    architecture_text = read_text(ROOT / "docs" / "ARCHITECTURE.md")

    negative_scope_readme = " ".join(extract_bullets(extract_section(readme_text, "## What This Repository Is Not")))
    negative_scope_gate = " ".join(extract_bullets(extract_section(gate_text, "## 4. What must this project not carry?")))
    if negative_scope_readme and negative_scope_gate:
        comparison = compare_token_sets(negative_scope_readme, negative_scope_gate, alias_groups)
        comparison_reports.append(
            {
                "code": "scope_negative_mismatch",
                "matched_alias_indexes": list(comparison["matched_alias_indexes"]),
            }
        )
        if not comparison["shared_tokens"] and not comparison["matched_alias_indexes"]:
            add_warning(
                warnings,
                "scope_negative_mismatch",
                "README.md and PROJECT_GATE.md appear disconnected in out-of-scope language",
            )

    positive_scope_readme = " ".join(extract_bullets(extract_section(readme_text, "## What This Repository Is")))
    positive_scope_gate = " ".join(extract_bullets(extract_section(gate_text, "## 1. Why does this project exist?")))
    if positive_scope_readme and positive_scope_gate:
        comparison = compare_token_sets(positive_scope_readme, positive_scope_gate, alias_groups)
        comparison_reports.append(
            {
                "code": "objective_mismatch",
                "matched_alias_indexes": list(comparison["matched_alias_indexes"]),
            }
        )
        if not comparison["shared_tokens"] and not comparison["matched_alias_indexes"]:
            add_warning(
                warnings,
                "objective_mismatch",
                "README.md and PROJECT_GATE.md appear disconnected in project objective language",
            )

    architecture_scope = " ".join(extract_bullets(extract_section(architecture_text, "## 2. Scope")))
    if architecture_scope and negative_scope_readme:
        comparison = compare_token_sets(architecture_scope, negative_scope_readme, alias_groups)
        comparison_reports.append(
            {
                "code": "scope_architecture_mismatch",
                "matched_alias_indexes": list(comparison["matched_alias_indexes"]),
            }
        )
        if not comparison["shared_tokens"] and not comparison["matched_alias_indexes"]:
            add_warning(
                warnings,
                "scope_architecture_mismatch",
                "README.md and docs/ARCHITECTURE.md use disconnected scope vocabulary",
            )


def check_contract_tables(errors: list[str]) -> None:
    contracts_text = read_text(ROOT / "docs" / "CONTRACTS.md")
    inputs = extract_section(contracts_text, "## 2. Canonical Inputs") or ""
    outputs = extract_section(contracts_text, "## 3. Canonical Outputs") or ""
    if inputs.count("|") < 10:
        add_error(errors, "docs/CONTRACTS.md appears to have too few canonical input table entries")
    if outputs.count("|") < 8:
        add_error(errors, "docs/CONTRACTS.md appears to have too few canonical output table entries")


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    warnings: list[dict[str, str]] = []
    comparison_reports: list[dict[str, object]] = []

    check_required_files(errors)
    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 1

    doctor_config = load_doctor_config(errors)
    if errors:
        print("Project doctor found errors:", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        return 1

    docs = {path: read_text(path) for path in KEY_DOCS}
    check_placeholders(errors, docs)
    check_required_sections(errors)
    check_consistency(errors)
    check_gate(errors)
    check_contract_tables(errors)

    alias_groups = list(doctor_config["token_alias_groups"])
    collect_semantic_warnings(warnings, comparison_reports, alias_groups)

    ignored_codes = {
        item["code"]
        for item in doctor_config["ignored_warnings"]
        if isinstance(item, dict) and "code" in item
    }
    active_warnings = [item for item in warnings if item.get("code") not in ignored_codes]

    if errors:
        print("Project doctor found errors:", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        if active_warnings:
            print("", file=sys.stderr)
            print_warning_list("Warnings:", active_warnings, sys.stderr)
        return 1

    if args.audit_config:
        return run_config_audit(doctor_config, warnings, comparison_reports)

    if args.strict and active_warnings:
        print("Project doctor found warnings in strict mode:", file=sys.stderr)
        for warning in active_warnings:
            print(f"- [{warning['code']}] {warning['message']}", file=sys.stderr)
        return 1

    if active_warnings:
        print("Project doctor passed with warnings:")
        for warning in active_warnings:
            print(f"- [{warning['code']}] {warning['message']}")
        return 0

    print("Project doctor passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
