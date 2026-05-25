"""Validate role contracts (.agents/roles/*/role.yaml) in trace-to-eval-harness.

Walks every `.agents/roles/<role-id>/role.yaml`, parses the YAML, and
validates the parsed object against the cross-repo `role.schema.json`
sourced from athena-site. The schema is fetched from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/role.schema.json`
at run time, with a local cache fallback at
`ops/schemas-cache/role.schema.json` so the script runs offline.

Exit codes: 0 OK, 1 violations found.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROLES_DIR = ROOT / ".agents" / "roles"
CACHE_PATH = ROOT / "ops" / "schemas-cache" / "role.schema.json"
REMOTE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/"
    "ops/schemas/role.schema.json"
)
FETCH_TIMEOUT_SECONDS = 5


def load_remote_schema() -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            REMOTE_URL, headers={"User-Agent": "trace-to-eval-harness/validate_roles"}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(
            f"validate_roles: remote schema fetch failed ({exc.__class__.__name__}); "
            f"falling back to cache at {CACHE_PATH.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None


def load_cached_schema() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        raise SystemExit(
            f"validate_roles: cached schema missing at "
            f"{CACHE_PATH.relative_to(ROOT).as_posix()}. Re-cache from "
            f"{REMOTE_URL} or restore the file."
        )
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict[str, Any]:
    remote = load_remote_schema()
    if remote is not None:
        return remote
    return load_cached_schema()


def discover_roles() -> list[Path]:
    if not ROLES_DIR.is_dir():
        return []
    return sorted(ROLES_DIR.glob("*/role.yaml"))


def main() -> int:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_roles: jsonschema is required. "
            "Install with `pip install jsonschema>=4.21`."
        ) from exc
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_roles: PyYAML is required. Install with `pip install pyyaml`."
        ) from exc

    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    roles = discover_roles()
    if not roles:
        print("validate_roles OK (0 roles)")
        return 0

    violations: list[str] = []
    for role_path in roles:
        rel = role_path.relative_to(ROOT).as_posix()
        try:
            data = yaml.safe_load(role_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            violations.append(f"{rel}: YAML parse error: {exc}")
            continue
        if not isinstance(data, dict):
            violations.append(f"{rel}: top-level must be a mapping")
            continue
        for err_obj in validator.iter_errors(data):
            location = "/".join(str(part) for part in err_obj.absolute_path) or "<root>"
            violations.append(f"{rel}: {location}: {err_obj.message}")

    if violations:
        print("validate_roles: violations found", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"validate_roles OK ({len(roles)} role(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
