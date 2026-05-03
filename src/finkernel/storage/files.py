from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def append_json_line(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def read_json_lines(path: Path) -> list[Any]:
    if not path.exists():
        return []
    items: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            items.append(json.loads(cleaned))
    return items
