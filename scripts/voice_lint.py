#!/usr/bin/env python3
"""Voice lint for public project copy."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]


class Rule(NamedTuple):
    severity: str
    label: str
    pattern: re.Pattern[str]


def phrase_rule(phrase: str) -> Rule:
    return Rule("FAIL", f"banned-{phrase}", re.compile(rf"\b{re.escape(phrase)}\b", re.I))


BANNED_PHRASES = [
    "leverage",
    "leverages",
    "leveraging",
    "comprehensive",
    "robust",
    "seamless",
    "seamlessly",
    "powerful",
    "elegant",
    "thoughtful",
    "innovative",
    "transformative",
    "revolutionary",
    "the point is",
    "in conclusion",
    "ultimately",
    "importantly",
    "notably",
    "moreover",
    "furthermore",
]

STRUCTURAL = [
    Rule("FAIL", "not-just-but", re.compile(r"\bnot\s+(?:just|only|merely|simply)\b[^.\n]{1,120}\bbut\b", re.I)),
    Rule("FAIL", "more-than-just", re.compile(r"\bmore\s+than\s+just\b", re.I)),
    Rule("FAIL", "not-because-because", re.compile(r"\bnot\s+because\b[^.\n]{1,120}\bbecause\b", re.I)),
]

TARGETS = [
    "README.md",
    "specs/**/*.md",
    "decisions/*.md",
]

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
ALLOWLIST_RE = re.compile(r"voice_lint:allow\s+([A-Za-z0-9\-_ ]+)")


def iter_files(root: Path, targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        for path in root.glob(target):
            if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
                files.append(path)
    return sorted(set(files))


def line_allowlist(line: str) -> set[str]:
    match = ALLOWLIST_RE.search(line)
    if not match:
        return set()
    return {label.strip() for label in match.group(1).split() if label.strip()}


def rules() -> list[Rule]:
    return [phrase_rule(phrase) for phrase in BANNED_PHRASES] + STRUCTURAL


def scan(path: Path, active_rules: list[Rule]) -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    for line_no, line in enumerate(text.splitlines(), start=1):
        allowed = line_allowlist(line)
        if "all" in allowed:
            continue
        for severity, label, pattern in active_rules:
            if label in allowed:
                continue
            if pattern.search(line):
                findings.append((severity, line_no, label, line.strip()))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check project copy for banned voice markers")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--target", action="append", default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    files = iter_files(root, args.target or TARGETS)
    findings: list[tuple[Path, str, int, str, str]] = []
    active_rules = rules()
    for path in files:
        for severity, line_no, label, text in scan(path, active_rules):
            findings.append((path, severity, line_no, label, text))

    for path, severity, line_no, label, text in findings:
        rel = path.relative_to(root).as_posix()
        snippet = text if len(text) <= 180 else text[:180] + "..."
        print(f"{rel}:{line_no}: {severity}: {label} -> {snippet}")

    if findings:
        print(f"voice_lint: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print(f"voice_lint: clean. {len(files)} file(s) scanned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

