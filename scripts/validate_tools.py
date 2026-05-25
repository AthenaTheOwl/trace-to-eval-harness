"""Validate tool registry entries in trace-to-eval-harness.

Reads `.agents/tools.yaml`, which holds a top-level `tools` list, and
validates each entry against the cross-repo `tool.schema.json` sourced
from athena-site. The schema is fetched from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/tool.schema.json`
at run time, with a local cache fallback at
`ops/schemas-cache/tool.schema.json` so the script runs offline.

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
TOOLS_FILE = ROOT / ".agents" / "tools.yaml"
CACHE_PATH = ROOT / "ops" / "schemas-cache" / "tool.schema.json"
REMOTE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/"
    "ops/schemas/tool.schema.json"
)
FETCH_TIMEOUT_SECONDS = 5


def load_remote_schema() -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            REMOTE_URL, headers={"User-Agent": "trace-to-eval-harness/validate_tools"}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(
            f"validate_tools: remote schema fetch failed ({exc.__class__.__name__}); "
            f"falling back to cache at {CACHE_PATH.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None


def load_cached_schema() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        raise SystemExit(
            f"validate_tools: cached schema missing at "
            f"{CACHE_PATH.relative_to(ROOT).as_posix()}. Re-cache from "
            f"{REMOTE_URL} or restore the file."
        )
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def load_schema() -> dict[str, Any]:
    remote = load_remote_schema()
    if remote is not None:
        return remote
    return load_cached_schema()


def main() -> int:
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_tools: jsonschema is required. "
            "Install with `pip install jsonschema>=4.21`."
        ) from exc
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "validate_tools: PyYAML is required. Install with `pip install pyyaml`."
        ) from exc

    if not TOOLS_FILE.is_file():
        print("validate_tools OK (0 tools; no .agents/tools.yaml present)")
        return 0

    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    try:
        data = yaml.safe_load(TOOLS_FILE.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"validate_tools: YAML parse error in .agents/tools.yaml: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict) or "tools" not in data:
        print(
            "validate_tools: .agents/tools.yaml must be a mapping with a top-level `tools` list",
            file=sys.stderr,
        )
        return 1

    tools = data["tools"]
    if not isinstance(tools, list):
        print("validate_tools: top-level `tools` must be a list", file=sys.stderr)
        return 1

    violations: list[str] = []
    for idx, entry in enumerate(tools):
        tool_id = entry.get("id", f"<index {idx}>") if isinstance(entry, dict) else f"<index {idx}>"
        if not isinstance(entry, dict):
            violations.append(f"tools[{idx}]: entry must be a mapping")
            continue
        for err_obj in validator.iter_errors(entry):
            location = "/".join(str(part) for part in err_obj.absolute_path) or "<root>"
            violations.append(f"tools[{tool_id}]: {location}: {err_obj.message}")

    if violations:
        print("validate_tools: violations found", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"validate_tools OK ({len(tools)} tool(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
