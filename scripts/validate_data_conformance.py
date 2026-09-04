#!/usr/bin/env python3
"""Validate repository data files against the JSON Schemas that describe them.

`validate_schemas.py` checks that schema *files* parse and declare a
recognized dialect. It does not open a single document those schemas
describe, so a schema can be green while every record it governs has
drifted off it. That gap was found in ai-field-brief (172 enum violations
across eight published files, unnoticed for eleven weeks) and the same
`validate_schemas.py` ships in 32 sibling repos.

This gate closes it. It reads `schemas/conformance.yaml`, which maps each
schema to the files it governs, and validates every record against it.

    # schemas/conformance.yaml
    version: 1
    mappings:
      - schema: card.schema.json
        files: ["cards/**/*.yaml"]
        records: self          # the document is one record (default)
      - schema: score.schema.json
        files: ["reports/**/*.md"]
        records: frontmatter   # YAML front-matter block is the record
      - schema: cell.schema.json
        files: ["briefs/*/matrix/*.yaml"]
        records: "list:cells"  # document[key] is a list of records

`records` modes:
  self         the parsed document is the record
  frontmatter  the leading `---` YAML block is the record (Markdown)
  each         the document is a bare list; each item is a record
  list:<key>   document[<key>] is a list of records

A repo with no `schemas/conformance.yaml` exits 0 with a note, so the gate is
safe to add before the mapping is authored. Once mappings are declared, a
missing `jsonschema` or `pyyaml` is a failure rather than a skip: a gate that
no-ops when its dependency is absent is the same class of defect it exists to
catch.

Exit codes: 0 OK, 1 violations found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
CONFIG_PATH = SCHEMA_DIR / "conformance.yaml"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)
MAX_REPORTED = 40

try:  # optional: only needed when a schema uses a relative $ref
    from referencing.jsonschema import DRAFT202012  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - resolver is skipped without it
    DRAFT202012 = None  # type: ignore[assignment]


def need_yaml() -> Any:
    try:
        import yaml  # type: ignore[import-not-found]

        return yaml
    except ImportError:
        print(
            "validate_data_conformance FAILED: pyyaml is not installed, but "
            "schemas/conformance.yaml exists and declares what to check. Add "
            "'pyyaml' to this repo's dependencies."
        )
        raise SystemExit(1)


def load_document(path: Path, yaml_mod: Any) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix in (".yaml", ".yml"):
        return yaml_mod.safe_load(text)
    if path.suffix in (".md", ".markdown"):
        match = FRONTMATTER_RE.match(text)
        if not match:
            return None
        return yaml_mod.safe_load(match.group(1))
    return None


def jsonify(value: Any) -> Any:
    """Normalize a YAML-parsed value to its JSON equivalent.

    YAML resolves an unquoted `2025-07-30` to a date object; JSON Schema is a
    JSON contract, so a consumer reading the same record through JSON sees the
    ISO string. Validating the raw YAML object would report a type error that
    no consumer can observe, so normalize first.
    """
    import datetime as _dt

    if isinstance(value, dict):
        return {str(k): jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(v) for v in value]
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    return value


def extract_records(doc: Any, mode: str, path: Path) -> Iterator[tuple[str, Any]]:
    if doc is None:
        return
    if mode == "self" or mode == "frontmatter":
        yield ("", doc)
        return
    if mode == "each":
        if not isinstance(doc, list):
            return
        for index, item in enumerate(doc):
            label = item.get("id") or item.get("slug") if isinstance(item, dict) else None
            yield (f"[{label or index}]", item)
        return
    if mode.startswith("list:"):
        key = mode.split(":", 1)[1]
        items = doc.get(key) if isinstance(doc, dict) else None
        if items is None:
            return
        if not isinstance(items, list):
            return
        for index, item in enumerate(items):
            label = item.get("id") if isinstance(item, dict) and "id" in item else f"#{index}"
            yield (f"{key}[{label}]", item)
        return
    raise SystemExit(f"validate_data_conformance: unknown records mode '{mode}' for {path}")


def local_schema_registry() -> Any:
    """Resolve sibling `$ref`s against schemas/ instead of over the network.

    A schema that says `"$ref": "coupling_row.schema.json"` means the file
    next to it. Without a local registry, jsonschema tries to fetch the
    reference over HTTP and the gate fails on a network error rather than on
    the data.
    """
    try:
        from referencing import Registry, Resource  # type: ignore[import-not-found]
    except ImportError:
        return None

    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            contents = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((path.name, resource))
        schema_id = contents.get("$id")
        if schema_id:
            resources.append((schema_id, resource))
    if not resources:
        return None
    return Registry().with_resources(resources)


def main() -> int:
    if not CONFIG_PATH.is_file():
        print(
            "validate_data_conformance: no schemas/conformance.yaml; "
            "nothing declared to validate (see the module docstring to add one)"
        )
        return 0

    yaml_mod = need_yaml()
    config = yaml_mod.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    mappings = config.get("mappings") or []
    if not mappings:
        print("validate_data_conformance: schemas/conformance.yaml declares no mappings")
        return 0

    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-not-found]
    except ImportError:
        print(
            "validate_data_conformance FAILED: jsonschema is not installed, but "
            "schemas/conformance.yaml declares mappings to check. A gate that "
            "skips silently is the defect this gate exists to catch. Add "
            "'jsonschema' to this repo's dependencies."
        )
        return 1

    registry = local_schema_registry()

    violations: list[str] = []
    files_checked = 0
    records_checked = 0

    for mapping in mappings:
        schema_name = mapping.get("schema")
        globs = mapping.get("files") or []
        mode = mapping.get("records", "self")
        if not schema_name or not globs:
            violations.append(f"conformance.yaml: mapping missing 'schema' or 'files': {mapping}")
            continue

        schema_path = SCHEMA_DIR / schema_name
        if not schema_path.is_file():
            violations.append(f"conformance.yaml: schema '{schema_name}' does not exist")
            continue

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(f"{schema_name}: does not parse as JSON ({exc})")
            continue
        validator = (
            Draft202012Validator(schema, registry=registry)
            if registry is not None
            else Draft202012Validator(schema)
        )

        matched: list[Path] = []
        for pattern in globs:
            matched.extend(p for p in ROOT.glob(pattern) if p.is_file())
        if not matched:
            violations.append(
                f"conformance.yaml: '{schema_name}' matches no files "
                f"(globs: {', '.join(globs)}); fix the glob or drop the mapping"
            )
            continue

        for path in sorted(set(matched)):
            rel = path.relative_to(ROOT).as_posix()
            files_checked += 1
            try:
                doc = load_document(path, yaml_mod)
            except Exception as exc:  # noqa: BLE001 - report, do not crash the gate
                violations.append(f"{rel}: does not parse ({type(exc).__name__}: {exc})")
                continue
            if doc is None:
                violations.append(f"{rel}: no record found (expected {mode})")
                continue
            for label, record in extract_records(doc, mode, path):
                record = jsonify(record)
                records_checked += 1
                where = f"{rel}:{label}" if label else rel
                if not isinstance(record, dict):
                    violations.append(f"{where}: record is not a mapping")
                    continue
                for error in validator.iter_errors(record):
                    loc = ".".join(str(x) for x in error.path) or "(root)"
                    violations.append(f"{where}: {loc}: {error.message}")

    if violations:
        shown = violations[:MAX_REPORTED]
        print(f"validate_data_conformance FAILED ({len(violations)} violation(s)):")
        for line in shown:
            print(f"  - {line}")
        if len(violations) > len(shown):
            print(f"  ... and {len(violations) - len(shown)} more")
        return 1

    print(
        f"validate_data_conformance OK ({records_checked} record(s) in "
        f"{files_checked} file(s) across {len(mappings)} mapping(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
