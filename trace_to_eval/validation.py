from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_DIR = ROOT / "schemas"

SCHEMA_FILES = {
    "trace": "trace.schema.json",
    "eval": "eval-case.schema.json",
    "report": "run-report.schema.json",
    "evidence": "run-evidence.schema.json",
    "run-bundle": "run-bundle.schema.json",
    "reliability": "reliability-report.schema.json",
}


@dataclass(frozen=True)
class ValidationIssue:
    location: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    kind: str
    path: Path
    schema_id: str
    issues: list[ValidationIssue]

    @property
    def passed(self) -> bool:
        return not self.issues


def schema_kinds() -> tuple[str, ...]:
    return tuple(SCHEMA_FILES)


def load_schema(kind: str, schema_dir: Path | None = None) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:
        known = ", ".join(schema_kinds())
        raise ValueError(f"unknown schema kind {kind!r}; expected one of: {known}") from exc
    root = schema_dir or DEFAULT_SCHEMA_DIR
    return json.loads((root / filename).read_text(encoding="utf-8"))


def schema_id(kind: str, schema_dir: Path | None = None) -> str:
    schema = load_schema(kind, schema_dir)
    value = schema.get("$id")
    if not isinstance(value, str) or not value:
        raise ValueError(f"{kind} schema is missing a non-empty $id")
    return value


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_document(kind: str, path: Path) -> Any:
    if kind == "eval":
        return _load_yaml(path)
    if kind in {"trace", "report", "evidence", "run-bundle", "reliability"}:
        return _load_json(path)
    known = ", ".join(schema_kinds())
    raise ValueError(f"unknown schema kind {kind!r}; expected one of: {known}")


def _location(error: ValidationError) -> str:
    if not error.absolute_path:
        return "<root>"
    return "/" + "/".join(str(part) for part in error.absolute_path)


def validate_document(
    kind: str,
    path: Path,
    *,
    schema_dir: Path | None = None,
) -> ValidationResult:
    schema = load_schema(kind, schema_dir)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    payload = load_document(kind, path)
    issues = [
        ValidationIssue(_location(error), error.message)
        for error in sorted(validator.iter_errors(payload), key=str)
    ]
    raw_schema_id = schema.get("$id", "")
    return ValidationResult(
        kind=kind,
        path=path,
        schema_id=str(raw_schema_id),
        issues=issues,
    )
