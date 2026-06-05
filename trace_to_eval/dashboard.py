"""Portfolio packet dashboard.

Walks one or more directories of `*.packet.json` files and renders a
per-producer-repo summary: packet count, most recent generation date, gate
results breakdown, and artifact-coverage stats.

The packet shape is the DEC-CDCP-015 Run Evidence packet (see
schemas/run_evidence.schema.json). Producer repos are extracted from
artifact_refs / artifact_hashes by parsing repo://<name>@<sha>/... URIs.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


REPO_URI_RE = re.compile(r"^repo://([^@]+)@")


@dataclass
class RepoSummary:
    name: str
    packet_count: int = 0
    latest_generated_at: str | None = None
    latest_run_id: str | None = None
    latest_packet_path: Path | None = None
    gate_results: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    artifact_count: int = 0
    runtime_providers: set[str] = field(default_factory=set)


def _producer_repos(packet: dict) -> set[str]:
    """Extract repo names referenced by a packet's artifact + run record refs."""
    names: set[str] = set()
    for entry in packet.get("artifact_hashes", []):
        ref = entry.get("ref", "")
        m = REPO_URI_RE.match(ref)
        if m:
            names.add(m.group(1))
    for entry in packet.get("artifact_refs", []):
        ref = entry.get("ref", "") if isinstance(entry, dict) else str(entry)
        m = REPO_URI_RE.match(ref)
        if m:
            names.add(m.group(1))
    rr_ref = packet.get("run_record_ref") or ""
    m = REPO_URI_RE.match(rr_ref)
    if m:
        names.add(m.group(1))
    return names


def collect(paths: Iterable[Path]) -> dict[str, RepoSummary]:
    """Walk each path (file or directory) for packet.json files and aggregate."""
    summaries: dict[str, RepoSummary] = {}
    for path in paths:
        if path.is_dir():
            files = sorted(path.glob("*.packet.json"))
        elif path.is_file():
            files = [path]
        else:
            continue
        for f in files:
            try:
                packet = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            producers = _producer_repos(packet) or {"(unattributed)"}
            generated_at = packet.get("generated_at") or ""
            run_id = packet.get("producer_run_id") or packet.get("run_id") or ""
            runtime = packet.get("runtime_provider") or "(unknown)"
            gates = packet.get("gate_results", []) or []
            artifact_count = len(packet.get("artifact_hashes", []) or [])
            for name in producers:
                s = summaries.setdefault(name, RepoSummary(name=name))
                s.packet_count += 1
                s.artifact_count += artifact_count
                s.runtime_providers.add(runtime)
                for gate in gates:
                    status = gate.get("status", "unknown") if isinstance(gate, dict) else "unknown"
                    s.gate_results[status] += 1
                if generated_at > (s.latest_generated_at or ""):
                    s.latest_generated_at = generated_at
                    s.latest_run_id = run_id
                    s.latest_packet_path = f
    return summaries


def render_markdown(summaries: dict[str, RepoSummary], paths: list[Path]) -> str:
    """Render a portfolio packet dashboard as Markdown."""
    out: list[str] = []
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out.append(f"# Run-evidence packet dashboard — {today}")
    out.append("")
    out.append("Walked paths:")
    for p in paths:
        out.append(f"- `{p}`")
    out.append("")

    if not summaries:
        out.append("No packets found.")
        return "\n".join(out) + "\n"

    out.append("## Per-repo summary")
    out.append("")
    out.append("| Repo | Packets | Artifacts | Runtime | Latest run | Latest at |")
    out.append("|---|---|---|---|---|---|")
    for name in sorted(summaries):
        s = summaries[name]
        runtimes = ", ".join(sorted(s.runtime_providers)) or "—"
        latest_run = s.latest_run_id or "—"
        latest_at = s.latest_generated_at or "—"
        out.append(
            f"| {name} | {s.packet_count} | {s.artifact_count} | "
            f"{runtimes} | `{latest_run}` | {latest_at} |"
        )

    any_gates = any(s.gate_results for s in summaries.values())
    if any_gates:
        out.append("")
        out.append("## Gate-result breakdown")
        out.append("")
        out.append("| Repo | Pass | Fail | Other |")
        out.append("|---|---|---|---|")
        for name in sorted(summaries):
            s = summaries[name]
            if not s.gate_results:
                continue
            passes = s.gate_results.get("pass", 0) + s.gate_results.get("ok", 0)
            fails = s.gate_results.get("fail", 0) + s.gate_results.get("error", 0)
            other = sum(s.gate_results.values()) - passes - fails
            out.append(f"| {name} | {passes} | {fails} | {other} |")

    return "\n".join(out) + "\n"


def run_dashboard(
    paths: list[Path],
    output: Path | None = None,
    portfolio_root: Path | None = None,
) -> str:
    """Walk paths + (optionally) sibling repos under portfolio_root for packets.

    portfolio_root looks for `<root>/<repo>/examples/run_evidence/` directories.
    """
    walk_paths = list(paths)
    if portfolio_root is not None and portfolio_root.is_dir():
        for child in sorted(portfolio_root.iterdir()):
            candidate = child / "examples" / "run_evidence"
            if candidate.is_dir():
                walk_paths.append(candidate)

    seen: set[Path] = set()
    deduped: list[Path] = []
    for p in walk_paths:
        try:
            resolved = p.resolve()
        except OSError:
            resolved = p
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(p)
    walk_paths = deduped

    summaries = collect(walk_paths)
    rendered = render_markdown(summaries, walk_paths)
    if output is not None:
        output.write_text(rendered, encoding="utf-8")
    return rendered
