"""Validate skill records (SKILL.md) in trace-to-eval-harness.

Walks every `.agents/skills/<id>/SKILL.md`, parses the YAML front-matter,
and validates the parsed object against the cross-repo `skill.schema.json`
sourced from athena-site. The schema is fetched from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/skill.schema.json`
at run time, with a local cache fallback at
`ops/schemas-cache/skill.schema.json` so the script runs offline.

Exit codes: 0 OK, 1 violations found.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".agents" / "skills"
CACHE_PATH = ROOT / "ops" / "schemas-cache" / "skill.schema.json"
DEFAULT_REMOTE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/"
    "ops/schemas/skill.schema.json"
)
# Env-var override mirrors the validate_decisions.py pattern so the
# offline-cache code path stays testable end-to-end.
REMOTE_URL = os.environ.get("TRACE_TO_EVAL_SCHEMA_URL_BASE", DEFAULT_REMOTE_URL)
FETCH_TIMEOUT_SECONDS = 5


def load_remote_schema() -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            REMOTE_URL,
            headers={"User-Agent": "trace-to-eval-harness/validate_skills"},
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(
            f"validate_skills: remote schema fetch failed ({exc.__class__.__name__}); "
            f"falling back to cache at {CACHE_PATH.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None


def load_cached_schema() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        raise SystemExit(
            f"validate_skills: cached schema missing at "
            f"{CACHE_PATH.relative_to(ROOT).as_posix()}. Re-cache from "
            f"{REMOTE_URL} or restore the file."
        )
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict[str, Any]:
    remote = load_remote_schema()
    if remote is not None:
        return remote
    return load_cached_schema()


def parse_front_matter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a markdown file, parse YAML front-matter, return (data, error)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, "missing opening `---` front-matter delimiter on line 1"

    lines = text.splitlines()
    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None, "missing closing `---` front-matter delimiter"

    front_matter_text = "\n".join(lines[1:end_index])

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_skills: PyYAML is required. "
            "Install with `pip install pyyaml`."
        ) from exc

    try:
        data = yaml.safe_load(front_matter_text)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error in front-matter: {exc}"

    if not isinstance(data, dict):
        return None, "front-matter must parse to a mapping"

    return data, None


def discover_skills() -> list[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        path
        for path in SKILLS_DIR.glob("*/SKILL.md")
        if path.is_file()
    )


def main() -> int:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_skills: jsonschema is required. "
            "Install with `pip install jsonschema>=4.21`."
        ) from exc

    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    skills = discover_skills()
    if not skills:
        print("validate_skills OK (0 skills)")
        return 0

    violations: list[str] = []
    for skill_path in skills:
        rel = skill_path.relative_to(ROOT).as_posix()
        data, err = parse_front_matter(skill_path)
        if err is not None:
            violations.append(f"{rel}: {err}")
            continue
        assert data is not None
        errors = list(validator.iter_errors(data))
        for err_obj in errors:
            location = "/".join(str(part) for part in err_obj.absolute_path) or "<root>"
            violations.append(f"{rel}: {location}: {err_obj.message}")

    if violations:
        print("validate_skills: violations found", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"validate_skills OK ({len(skills)} skill(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
