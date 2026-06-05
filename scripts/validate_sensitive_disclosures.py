"""Block committed secrets and over-detailed incident artifacts.

This gate is intentionally stricter than ordinary secret scanning. Provider
push-protection catches literal credentials; it does not catch a markdown
runbook that leaks key fragments, fingerprints, tails, or exact remediation
commands. This script blocks both classes.

The scanner prints category + path + line number only. It never prints the
matched text.

MIRRORED from AthenaTheOwl/mcp-security-lab :: scripts/validate_sensitive_disclosures.py.
Keep behavioral parity. Source repo is canonical — update there first, then
re-mirror. (The ALLOWLIST below is a no-op in this repo since no companion
test file exists; the scanner already self-excludes by relative path.)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

ALLOWLIST = {
    Path("scripts/validate_sensitive_disclosures.py"),
    Path("tests/test_validate_sensitive_disclosures.py"),
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("openai-api-key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{48,}")),
    ("anthropic-api-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    (
        "github-token",
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{20,}"),
    ),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
    ("stripe-live-key", re.compile(r"sk_live_[A-Za-z0-9]{20,}")),
    ("huggingface-token", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("sendgrid-token", re.compile(r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "literal-api-key-assignment",
        re.compile(
            r"(GNEWS_API_KEY|GOOGLE_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|RESEND_API_KEY|STRIPE_SECRET_KEY)"
            r"\s*=\s*(?!($|<|your-|placeholder|change-me|changeme|example|dummy|redacted))"
            r"[^#\s][^\r\n]+",
            re.IGNORECASE,
        ),
    ),
    (
        "contextual-32-hex-api-key",
        re.compile(r"(api[_ -]?key|gnews|secret).{0,48}\b[a-f0-9]{32}\b", re.IGNORECASE),
    ),
    (
        "filter-repo-literal-risk",
        re.compile(r"git\s+filter-repo.{0,120}(--replace-text|replace-text)", re.IGNORECASE),
    ),
    (
        "secret-fingerprint-disclosure",
        re.compile(
            r"((\bkey\b|\bsecret\b|\btoken\b|\bcredential\b).{0,32}"
            r"(\bfingerprint\b|\btail\b|\bending\b|starts? with|starting)|"
            r"(\bfingerprint\b|\btail\b|\bending\b).{0,32}"
            r"(\bkey\b|\bsecret\b|\btoken\b|\bcredential\b)).{0,96}"
            r"([a-f0-9]{8,64}|[A-Za-z0-9_-]{4,})",
            re.IGNORECASE,
        ),
    ),
    (
        "security-incident-source-artifact",
        re.compile(
            r"((secret[- ]?audit|security[- ]?audit).{0,80}"
            r"(finding|findings|verdict|credential|key|token|leak|runbook|scanner)|"
            r"remediation runbook|REAL_LEAK|leaked API key|linkedin.{0,40}(api key|secret|token))",
            re.IGNORECASE,
        ),
    ),
]


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    category: str


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def should_skip(path: Path, root: Path) -> bool:
    rel = _relative(path, root)
    if rel in ALLOWLIST:
        return True
    return any(part in SKIP_DIRS for part in rel.parts)


def iter_files(paths: Iterable[Path], root: Path) -> Iterable[Path]:
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            if not should_skip(path, root):
                yield path
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            current = Path(dirpath)
            dirnames[:] = [
                d for d in dirnames if d not in SKIP_DIRS and not should_skip(current / d, root)
            ]
            for filename in filenames:
                file_path = current / filename
                if not should_skip(file_path, root):
                    yield file_path


def scan_file(path: Path, root: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError:
        return []

    findings: list[Finding] = []
    rel = _relative(path, root)
    for line_no, line in enumerate(content.splitlines(), start=1):
        for category, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(Finding(rel, line_no, category))
    return findings


def scan(paths: Iterable[Path], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[Path] = set()
    for path in iter_files(paths, root):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        findings.extend(scan_file(path, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Block committed secrets and detailed secret-incident disclosures."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[ROOT],
        help="Files or directories to scan. Defaults to the current repo.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Root used for relative paths and allowlists.",
    )
    args = parser.parse_args(argv)

    findings = scan(args.paths, root=args.root)
    if findings:
        print("validate_sensitive_disclosures: blocked sensitive disclosure(s).", file=sys.stderr)
        for finding in findings:
            print(
                f"  {finding.path}:{finding.line}: {finding.category}",
                file=sys.stderr,
            )
        print(
            "Move detailed incident notes to a local gitignored location. "
            "Commit only sanitized placeholders.",
            file=sys.stderr,
        )
        return 1

    print("validate_sensitive_disclosures OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
