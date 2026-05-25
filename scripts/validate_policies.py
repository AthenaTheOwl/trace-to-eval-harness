"""Validate policy files in trace-to-eval-harness.

Walks every `.agents/policies/*.yaml`, parses the YAML, and validates
the parsed object against the cross-repo `policy.schema.json` sourced
from athena-site. The schema is fetched from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/policy.schema.json`
at run time, with a local cache fallback at
`ops/schemas-cache/policy.schema.json` so the script runs offline.

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
POLICIES_DIR = ROOT / ".agents" / "policies"
CACHE_PATH = ROOT / "ops" / "schemas-cache" / "policy.schema.json"
REMOTE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/"
    "ops/schemas/policy.schema.json"
)
FETCH_TIMEOUT_SECONDS = 5


def load_remote_schema() -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            REMOTE_URL, headers={"User-Agent": "trace-to-eval-harness/validate_policies"}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(
            f"validate_policies: remote schema fetch failed ({exc.__class__.__name__}); "
            f"falling back to cache at {CACHE_PATH.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None


def load_cached_schema() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        raise SystemExit(
            f"validate_policies: cached schema missing at "
            f"{CACHE_PATH.relative_to(ROOT).as_posix()}. Re-cache from "
            f"{REMOTE_URL} or restore the file."
        )
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict[str, Any]:
    remote = load_remote_schema()
    if remote is not None:
        return remote
    return load_cached_schema()


def discover_policies() -> list[Path]:
    if not POLICIES_DIR.is_dir():
        return []
    return sorted(POLICIES_DIR.glob("*.yaml"))


def main() -> int:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_policies: jsonschema is required. "
            "Install with `pip install jsonschema>=4.21`."
        ) from exc
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_policies: PyYAML is required. Install with `pip install pyyaml`."
        ) from exc

    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    policies = discover_policies()
    if not policies:
        print("validate_policies OK (0 policies)")
        return 0

    violations: list[str] = []
    for policy_path in policies:
        rel = policy_path.relative_to(ROOT).as_posix()
        try:
            data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
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
        print("validate_policies: violations found", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"validate_policies OK ({len(policies)} policy(ies))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
