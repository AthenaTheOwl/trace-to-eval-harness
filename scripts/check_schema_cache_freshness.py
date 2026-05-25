"""Check that cached cross-repo schemas match athena-site.

Every product repo keeps local copies under `ops/schemas-cache/` so
validators can run when the network is down. This gate compares each
cached schema with `athena-site/ops/schemas/` from a sibling checkout,
or with the GitHub raw copy when the sibling checkout is unavailable.

Exit codes: 0 OK, 1 stale or missing cache entries.
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
CACHE_DIR = ROOT / "ops" / "schemas-cache"
DEFAULT_SOURCE_DIR = ROOT.parent / "athena-site" / "ops" / "schemas"
SOURCE_DIR = Path(os.environ.get("ATHENA_SITE_SCHEMA_ROOT", DEFAULT_SOURCE_DIR))
RAW_BASE_URL = (
    "https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas"
)
FETCH_TIMEOUT_SECONDS = 5


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_remote(name: str) -> Any:
    url = f"{RAW_BASE_URL}/{name}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "cdcp/check_schema_cache_freshness"}
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_source(name: str) -> Any:
    local = SOURCE_DIR / name
    if local.is_file():
        return load_json(local)
    return load_remote(name)


def main() -> int:
    if not CACHE_DIR.is_dir():
        print("check_schema_cache_freshness: ops/schemas-cache missing", file=sys.stderr)
        return 1

    cached = sorted(CACHE_DIR.glob("*.schema.json"))
    if not cached:
        print("check_schema_cache_freshness: no cached schemas found", file=sys.stderr)
        return 1

    violations: list[str] = []
    for cached_path in cached:
        rel = cached_path.relative_to(ROOT).as_posix()
        try:
            cached_schema = load_json(cached_path)
        except json.JSONDecodeError as exc:
            violations.append(f"{rel}: invalid cached JSON ({exc})")
            continue

        try:
            source_schema = load_source(cached_path.name)
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as exc:
            violations.append(
                f"{rel}: could not read source schema {cached_path.name} "
                f"({exc.__class__.__name__})"
            )
            continue

        if cached_schema != source_schema:
            violations.append(
                f"{rel}: stale cache; refresh from athena-site/ops/schemas/"
                f"{cached_path.name}"
            )

    if violations:
        print("check_schema_cache_freshness: violations found", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print(f"check_schema_cache_freshness OK ({len(cached)} schema(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
