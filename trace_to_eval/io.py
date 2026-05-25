from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import Trace


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_trace(path: Path) -> Trace:
    return Trace.from_dict(load_json(path))


def load_eval_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{path} must contain a top-level cases list")
    return [case for case in cases if isinstance(case, dict)]


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

