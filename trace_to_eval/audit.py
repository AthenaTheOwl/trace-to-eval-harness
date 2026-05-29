"""Append-only audit log for trace-to-eval CLI invocations.

Every successful run of a contract command (currently
``evidence from-cdcp-events`` and ``validate-chain``) appends a single
JSONL entry to ``ops/audit-log.jsonl``. The log is gitignored — it is
a per-machine usage trail, not a checked-in artifact — but the schema
is stable so a future operator can aggregate, archive, or replay it.

The ``audit summary`` CLI subcommand reads this file and prints
aggregate stats (total invocations, breakdown by command, success vs.
failure rate, top ledger paths).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

AUDIT_LOG_DEFAULT = Path("ops/audit-log.jsonl")


def append_audit_entry(
    command: str,
    ledger_path: str | None = None,
    run_id: str | None = None,
    result: str = "ok",
    packet_hash: str | None = None,
    log_path: Path = AUDIT_LOG_DEFAULT,
) -> Path:
    """Append a structured audit entry to ``ops/audit-log.jsonl``.

    Returns the resolved log path so the caller can surface where the
    entry landed. The log directory is created on demand.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "ledger_path": ledger_path,
        "run_id": run_id,
        "result": result,
        "packet_hash": packet_hash,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return log_path


@dataclass(frozen=True)
class AuditSummary:
    total: int
    by_command: dict[str, int]
    by_result: dict[str, int]
    top_ledger_paths: list[tuple[str, int]]
    first_seen: str | None
    last_seen: str | None


def _iter_entries(
    log_path: Path,
    since: str | None = None,
) -> Iterable[dict[str, Any]]:
    if not log_path.is_file():
        return
    for line in log_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            # Corrupted line: skip, do not break aggregation.
            continue
        if not isinstance(entry, dict):
            continue
        timestamp = entry.get("timestamp")
        if since is not None and isinstance(timestamp, str) and timestamp < since:
            continue
        yield entry


def summarize(
    log_path: Path = AUDIT_LOG_DEFAULT,
    since: str | None = None,
    top_n: int = 5,
) -> AuditSummary:
    """Aggregate the audit log into a summary structure.

    ``since`` filters entries with ``timestamp >= since`` (lexicographic
    comparison on RFC 3339 strings is correct for UTC). Pass
    ``YYYY-MM-DD`` and the comparison still works because RFC 3339
    timestamps sort lexicographically.
    """
    log_path = Path(log_path)
    total = 0
    by_command: Counter[str] = Counter()
    by_result: Counter[str] = Counter()
    ledger_counts: Counter[str] = Counter()
    timestamps: list[str] = []
    for entry in _iter_entries(log_path, since=since):
        total += 1
        command = str(entry.get("command") or "unknown")
        result = str(entry.get("result") or "unknown")
        by_command[command] += 1
        by_result[result] += 1
        ledger_path = entry.get("ledger_path")
        if isinstance(ledger_path, str) and ledger_path:
            ledger_counts[ledger_path] += 1
        timestamp = entry.get("timestamp")
        if isinstance(timestamp, str):
            timestamps.append(timestamp)
    timestamps.sort()
    return AuditSummary(
        total=total,
        by_command=dict(by_command),
        by_result=dict(by_result),
        top_ledger_paths=ledger_counts.most_common(top_n),
        first_seen=timestamps[0] if timestamps else None,
        last_seen=timestamps[-1] if timestamps else None,
    )


def format_summary(summary: AuditSummary) -> str:
    """Render an ``AuditSummary`` as a human-readable block."""
    lines = [
        f"audit-log summary: {summary.total} invocation(s)",
    ]
    if summary.first_seen and summary.last_seen:
        lines.append(f"  window: {summary.first_seen} -> {summary.last_seen}")
    if summary.by_command:
        lines.append("  by command:")
        for command, count in sorted(summary.by_command.items()):
            lines.append(f"    {command}: {count}")
    if summary.by_result:
        lines.append("  by result:")
        for result, count in sorted(summary.by_result.items()):
            lines.append(f"    {result}: {count}")
    if summary.top_ledger_paths:
        lines.append("  top ledger paths:")
        for path, count in summary.top_ledger_paths:
            lines.append(f"    {path}: {count}")
    return "\n".join(lines)
