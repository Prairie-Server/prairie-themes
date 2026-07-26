#!/usr/bin/env python3
"""Validate catalog.json and themes/*.json for CI quality gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog.json"
THEMES_DIR = ROOT / "themes"
REQUIRED_DOWNLOAD_PREFIX = "raw.githubusercontent.com/prairie-server/prairie-themes/"
THEME_REQUIRED_KEYS = ("version", "name", "baseTheme", "vars")
CATALOG_REQUIRED_KEYS = ("version", "updatedAt", "themes")


def fail(message: str) -> None:
    print(message, file=sys.stderr)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def theme_paths_for_id(theme_id: str) -> list[Path]:
    return [
        THEMES_DIR / f"{theme_id}.json",
        THEMES_DIR / f"{theme_id}.prairie-theme.json",
    ]


def validate_theme_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load_json(path)
    except ValueError as exc:
        return [str(exc)]

    if not isinstance(data, dict):
        return [f"{path}: expected a JSON object"]

    for key in THEME_REQUIRED_KEYS:
        if key not in data:
            errors.append(f"{path}: missing required key '{key}'")

    if "vars" in data and not isinstance(data["vars"], dict):
        errors.append(f"{path}: 'vars' must be an object")

    return errors


def validate_download_url(theme_id: str, download_url: Any) -> list[str]:
    if not isinstance(download_url, str) or not download_url.strip():
        return [f"catalog entry '{theme_id}': downloadUrl must be a non-empty string"]

    parsed = urlparse(download_url)
    host_and_repo = f"{parsed.netloc}/{'/'.join(parsed.path.strip('/').split('/')[:2])}/"
    if host_and_repo != REQUIRED_DOWNLOAD_PREFIX:
        return [
            f"catalog entry '{theme_id}': downloadUrl host path must use "
            f"'{REQUIRED_DOWNLOAD_PREFIX}' (got {download_url!r})"
        ]
    return []


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in CATALOG_REQUIRED_KEYS:
        if key not in catalog:
            errors.append(f"catalog.json: missing required top-level key '{key}'")

    themes = catalog.get("themes")
    if "themes" in catalog and not isinstance(themes, list):
        errors.append("catalog.json: 'themes' must be an array")
        return errors

    if not isinstance(themes, list):
        return errors

    for index, entry in enumerate(themes):
        if not isinstance(entry, dict):
            errors.append(f"catalog.json: themes[{index}] must be an object")
            continue

        theme_id = entry.get("id")
        if not isinstance(theme_id, str) or not theme_id.strip():
            errors.append(f"catalog.json: themes[{index}] missing non-empty string 'id'")
            continue

        matches = [path for path in theme_paths_for_id(theme_id) if path.is_file()]
        if not matches:
            errors.append(
                f"catalog entry '{theme_id}': no matching theme file "
                f"(expected themes/{theme_id}.json or themes/{theme_id}.prairie-theme.json)"
            )

        errors.extend(validate_download_url(theme_id, entry.get("downloadUrl")))

    return errors


def main() -> int:
    errors: list[str] = []

    if not CATALOG_PATH.is_file():
        fail(f"missing {CATALOG_PATH}")
        return 1

    try:
        catalog_data = load_json(CATALOG_PATH)
    except ValueError as exc:
        fail(str(exc))
        return 1

    if not isinstance(catalog_data, dict):
        fail("catalog.json: expected a JSON object")
        return 1

    errors.extend(validate_catalog(catalog_data))

    if not THEMES_DIR.is_dir():
        errors.append(f"missing themes directory: {THEMES_DIR}")
    else:
        for path in sorted(THEMES_DIR.glob("*.json")):
            errors.extend(validate_theme_file(path))

    if errors:
        for message in errors:
            fail(message)
        fail(f"validation failed with {len(errors)} error(s)")
        return 1

    theme_count = len(list(THEMES_DIR.glob("*.json"))) if THEMES_DIR.is_dir() else 0
    catalog_count = len(catalog_data.get("themes", [])) if isinstance(catalog_data.get("themes"), list) else 0
    print(
        f"catalog and themes OK "
        f"({catalog_count} catalog entries, {theme_count} theme files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
