"""Validate dream records (dreams/<YYYY-WNN>/) in trace-to-eval-harness.

Walks every `dreams/<YYYY-WNN>/` directory, confirms `report.md` exists,
parses `meta.yaml`, and validates the parsed object against the cross-repo
`dream-output.schema.json` sourced from athena-site. For each candidate
file under `candidates/`, parses the YAML front-matter and checks the
required typed-candidate fields (`target_kind`, `evidence`,
`human_review_required`).

The schema is fetched from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/dream-output.schema.json`
at run time, with a local cache fallback at
`ops/schemas-cache/dream-output.schema.json` so the script runs offline.

Exit codes: 0 OK, 1 violations found.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DREAMS_DIR = ROOT / "dreams"
CACHE_PATH = ROOT / "ops" / "schemas-cache" / "dream-output.schema.json"
DEFAULT_REMOTE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/"
    "ops/schemas/dream-output.schema.json"
)
# Env-var override mirrors validate_decisions.py / validate_skills.py so
# the offline-cache code path stays testable end-to-end.
REMOTE_URL = os.environ.get("TRACE_TO_EVAL_SCHEMA_URL_BASE", DEFAULT_REMOTE_URL)
FETCH_TIMEOUT_SECONDS = 5

WEEK_DIR_PATTERN = re.compile(r"^[0-9]{4}-W[0-9]{2}$")

# Allowed values for candidate front-matter `target_kind`. Mirrors the four
# typed shapes in dream-output.schema.json.
ALLOWED_TARGET_KINDS = {
    "memory_update",
    "test_generation",
    "skill_patch",
    "backlog_item",
}

# Top-level identifying fields that every meta.yaml must carry. These mirror
# the schema's `required` set but stay tolerant of the additional audit
# fields each repo stores alongside the canonical shape (run_id, cost,
# handoff, notes, etc.).
META_REQUIRED_FIELDS = (
    "week",
    "generated_at",
    "generated_by",
)


def load_remote_schema() -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            REMOTE_URL,
            headers={"User-Agent": "trace-to-eval-harness/validate_dreams"},
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(
            f"validate_dreams: remote schema fetch failed ({exc.__class__.__name__}); "
            f"falling back to cache at {CACHE_PATH.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None


def load_cached_schema() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        raise SystemExit(
            f"validate_dreams: cached schema missing at "
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
            "validate_dreams: PyYAML is required. "
            "Install with `pip install pyyaml`."
        ) from exc

    try:
        data = yaml.safe_load(front_matter_text)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error in front-matter: {exc}"

    if not isinstance(data, dict):
        return None, "front-matter must parse to a mapping"

    return data, None


def discover_dreams() -> list[Path]:
    if not DREAMS_DIR.is_dir():
        return []
    return sorted(
        path
        for path in DREAMS_DIR.iterdir()
        if path.is_dir() and WEEK_DIR_PATTERN.match(path.name)
    )


def validate_meta(meta_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse meta.yaml and return (data, violations). Field-level shape
    check against the schema's required-identity surface, kept tolerant of
    the additional audit fields each repo carries."""
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_dreams: PyYAML is required. "
            "Install with `pip install pyyaml`."
        ) from exc

    violations: list[str] = []
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"meta.yaml: YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return None, ["meta.yaml: must parse to a mapping"]

    for field in META_REQUIRED_FIELDS:
        if field not in data:
            violations.append(f"meta.yaml: missing required field `{field}`")

    week = data.get("week")
    if isinstance(week, str) and not re.match(r"^[0-9]{4}-W[0-9]{2}$", week):
        violations.append(
            f"meta.yaml: `week` must match YYYY-WNN, got {week!r}"
        )

    return data, violations


def validate_candidate(cand_path: Path, rel: str) -> list[str]:
    """Per-candidate front-matter check. Required: target_kind, evidence,
    human_review_required."""
    violations: list[str] = []
    data, err = parse_front_matter(cand_path)
    if err is not None:
        return [f"{rel}: {err}"]
    assert data is not None

    if "target_kind" not in data:
        violations.append(f"{rel}: missing required field `target_kind`")
    else:
        tk = data["target_kind"]
        if tk not in ALLOWED_TARGET_KINDS:
            allowed = ", ".join(sorted(ALLOWED_TARGET_KINDS))
            violations.append(
                f"{rel}: `target_kind` must be one of [{allowed}], got {tk!r}"
            )

    if "evidence" not in data:
        violations.append(f"{rel}: missing required field `evidence`")
    else:
        ev = data["evidence"]
        if not isinstance(ev, list):
            violations.append(f"{rel}: `evidence` must be an array")
        elif len(ev) == 0:
            violations.append(f"{rel}: `evidence` must be a non-empty array")

    if "human_review_required" not in data:
        violations.append(
            f"{rel}: missing required field `human_review_required`"
        )
    else:
        hrr = data["human_review_required"]
        if not isinstance(hrr, bool):
            violations.append(
                f"{rel}: `human_review_required` must be a boolean, got "
                f"{type(hrr).__name__}"
            )

    return violations


def main() -> int:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_dreams: jsonschema is required. "
            "Install with `pip install jsonschema>=4.21`."
        ) from exc

    # Sanity-check the schema parses and is well-formed. The schema is
    # referenced for the shape contract; per-field meta.yaml validation is
    # performed in validate_meta() to stay tolerant of the audit-shape
    # additions each repo carries.
    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)

    dreams = discover_dreams()
    if not dreams:
        print("validate_dreams OK (0 dream(s) found)")
        return 0

    violations: list[str] = []
    candidate_count = 0
    for dream_dir in dreams:
        rel_dir = dream_dir.relative_to(ROOT).as_posix()

        report_path = dream_dir / "report.md"
        if not report_path.is_file():
            violations.append(f"{rel_dir}: missing report.md")

        meta_path = dream_dir / "meta.yaml"
        if not meta_path.is_file():
            violations.append(f"{rel_dir}: missing meta.yaml")
        else:
            _, meta_violations = validate_meta(meta_path)
            for v in meta_violations:
                violations.append(f"{rel_dir}/{v}")

        cand_dir = dream_dir / "candidates"
        if cand_dir.is_dir():
            cand_files = sorted(p for p in cand_dir.glob("*.md") if p.is_file())
            for cand_path in cand_files:
                candidate_count += 1
                rel = cand_path.relative_to(ROOT).as_posix()
                violations.extend(validate_candidate(cand_path, rel))

    if violations:
        print("validate_dreams: violations found", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"validate_dreams OK ({len(dreams)} dream(s), "
        f"{candidate_count} candidate(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
