from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import hashlib
import os

from .audit import AUDIT_LOG_DEFAULT, append_audit_entry, format_summary, summarize
from .cdcp_events import import_cdcp_events
from .dashboard import run_dashboard
from .ingest import ingest_trace
from .report import write_reports
from .run_evidence import OUTPUT_FILENAME as EVIDENCE_OUTPUT_FILENAME
from .run_evidence import write_run_evidence_from_cdcp_events
from .runner import run_eval_file
from .uri import resolve_ref
from .validate_chain import ChainValidationError, run_validate_chain
from .validation import schema_kinds, validate_document


def _sha256_file(path: Path) -> str | None:
    """Return the sha256 hex digest of a file, or None if it cannot be read."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _strict_rehash_packet(
    packet: dict, portfolio_root: Path
) -> list[tuple[str, str]]:
    """Re-hash references in a run-evidence packet and compare against stored.

    Returns a list of (kind, reason) failure tuples. Empty list means the
    packet's stored hashes all match what the referenced files hash to
    on disk. The check covers ``run_record_ref/hash``, ``event_log_ref/hash``,
    and each ``artifact_hashes[]`` entry. Refs that cannot be resolved
    (e.g. ``artifact://`` URIs) are reported as a single failure rather
    than silently skipped.
    """
    failures: list[tuple[str, str]] = []

    pairs = [
        ("run_record", packet.get("run_record_ref"), packet.get("run_record_hash")),
        ("event_log", packet.get("event_log_ref"), packet.get("event_log_hash")),
    ]
    for kind, ref, stored_hash in pairs:
        if not ref or not stored_hash:
            failures.append((kind, f"missing ref or stored hash"))
            continue
        path = resolve_ref(ref, portfolio_root)
        if path is None:
            failures.append((kind, f"ref does not resolve to a file: {ref}"))
            continue
        actual = _sha256_file(path)
        if actual is None:
            failures.append((kind, f"could not read resolved path: {path}"))
            continue
        if actual != stored_hash:
            failures.append(
                (kind, f"hash mismatch: stored={stored_hash[:16]}... actual={actual[:16]}... at {path}")
            )

    for entry in packet.get("artifact_hashes", []) or []:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("ref")
        stored_hash = entry.get("hash")
        if not ref or not stored_hash:
            failures.append(("artifact", "missing ref or stored hash on artifact entry"))
            continue
        path = resolve_ref(ref, portfolio_root)
        if path is None:
            failures.append(("artifact", f"ref does not resolve: {ref}"))
            continue
        actual = _sha256_file(path)
        if actual is None:
            failures.append(("artifact", f"could not read resolved path: {path}"))
            continue
        if actual != stored_hash:
            failures.append(
                ("artifact", f"hash mismatch at {ref}: stored={stored_hash[:16]}... actual={actual[:16]}...")
            )

    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trace-to-eval",
        description="Build eval cases from traces and run deterministic checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="turn one failed trace into a YAML case")
    ingest.add_argument("trace", type=Path)
    ingest.add_argument("--out", type=Path, required=True)

    cdcp_events = subparsers.add_parser(
        "from-cdcp-events",
        help="turn CDCP event-log JSONL entries into draft eval cases",
    )
    cdcp_events.add_argument("path", type=Path)
    cdcp_events.add_argument("--out", type=Path, required=True)

    evidence = subparsers.add_parser(
        "evidence",
        help="validate or generate run evidence packets",
    )
    evidence_subparsers = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_validate = evidence_subparsers.add_parser(
        "validate",
        help="validate run evidence packets",
    )
    evidence_validate.add_argument("paths", type=Path, nargs="+")
    evidence_validate.add_argument(
        "--schema-dir",
        type=Path,
        default=None,
        help="override the schema directory for testing or local schema drafts",
    )
    evidence_validate.add_argument(
        "--strict",
        action="store_true",
        help=(
            "in addition to schema validation, re-hash the referenced run record, "
            "event log, and artifacts and compare against the packet's stored "
            "hashes; exits nonzero on any mismatch. Promotes the v2.1.0 "
            "replay-equivalence claim from advisory to enforced."
        ),
    )
    evidence_validate.add_argument(
        "--portfolio-root",
        type=Path,
        default=None,
        help=(
            "portfolio root for resolving repo:// URIs in --strict mode. "
            "Default: $PORTFOLIO_ROOT env var, else the parent directory of this repo."
        ),
    )
    evidence_cdcp = evidence_subparsers.add_parser(
        "from-cdcp-events",
        help="turn CDCP event-log JSONL entries into a run evidence packet",
    )
    evidence_cdcp.add_argument("path", type=Path)
    evidence_cdcp.add_argument("--out", type=Path, required=True)
    evidence_cdcp.add_argument(
        "--run-record",
        type=str,
        default=None,
        help=(
            "explicit path or repo:// URI to the producer Run record JSON. "
            "Default: auto-discover at <event-log>/../run-records/<run_id>.json."
        ),
    )
    evidence_cdcp.add_argument(
        "--portfolio-root",
        type=Path,
        default=None,
        help=(
            "portfolio root for resolving repo:// URIs. "
            "Default: $PORTFOLIO_ROOT env var, else the parent directory of this repo."
        ),
    )

    run = subparsers.add_parser("run", help="run eval cases against trace JSON files")
    run.add_argument("eval_cases", type=Path)
    run.add_argument("--traces", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument(
        "--fail-on-failure",
        action="store_true",
        help="exit 1 when any case fails",
    )

    validate = subparsers.add_parser("validate", help="validate files against published schemas")
    validate.add_argument("kind", choices=schema_kinds())
    validate.add_argument("paths", type=Path, nargs="+")
    validate.add_argument(
        "--schema-dir",
        type=Path,
        default=None,
        help="override the schema directory for testing or local schema drafts",
    )

    validate_chain = subparsers.add_parser(
        "validate-chain",
        help=(
            "run the full DEC-CDCP-015 chain: validate events, generate packet, "
            "validate packet, then cross-check Run record vs. ledger"
        ),
    )
    validate_chain.add_argument("ledger_path", type=Path)
    validate_chain.add_argument(
        "--run-record",
        type=str,
        default=None,
        help=(
            "explicit path or repo:// URI to the producer Run record. "
            "Default: auto-discover at <ledger>/../run-records/<run_id>.json."
        ),
    )
    validate_chain.add_argument(
        "--portfolio-root",
        type=Path,
        default=None,
        help="portfolio root for resolving repo:// URIs (default: PORTFOLIO_ROOT env var or repo parent).",
    )
    validate_chain.add_argument(
        "--audit-log",
        type=Path,
        default=AUDIT_LOG_DEFAULT,
        help="path to the audit log file (default: ops/audit-log.jsonl).",
    )
    validate_chain.add_argument(
        "--no-audit",
        action="store_true",
        help="suppress the audit-log append on success.",
    )

    audit = subparsers.add_parser(
        "audit",
        help="inspect the trace-to-eval CLI audit log",
    )
    audit_subparsers = audit.add_subparsers(dest="audit_command", required=True)
    audit_summary = audit_subparsers.add_parser(
        "summary",
        help="aggregate the audit log into a usage summary",
    )
    audit_summary.add_argument(
        "--log-path",
        type=Path,
        default=AUDIT_LOG_DEFAULT,
        help="path to the audit log file (default: ops/audit-log.jsonl).",
    )
    audit_summary.add_argument(
        "--since",
        type=str,
        default=None,
        help="filter entries with timestamp >= --since (YYYY-MM-DD or RFC 3339).",
    )
    audit_summary.add_argument(
        "--top",
        type=int,
        default=5,
        help="how many top ledger paths to show (default: 5).",
    )

    dashboard = subparsers.add_parser(
        "dashboard",
        help="render a per-producer-repo summary of run-evidence packets",
    )
    dashboard.add_argument(
        "paths",
        type=Path,
        nargs="*",
        default=[Path("examples/run_evidence")],
        help="packet file(s) or directory(ies). Default: examples/run_evidence",
    )
    dashboard.add_argument(
        "--out",
        type=Path,
        default=None,
        help="optional output path. Default: stdout.",
    )
    dashboard.add_argument(
        "--portfolio-root",
        type=Path,
        default=None,
        help=(
            "optional portfolio root; also walks <root>/<repo>/examples/run_evidence "
            "for every sibling repo with one."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        payload = ingest_trace(args.trace, args.out)
        checks = sum(len(case.get("checks", [])) for case in payload["cases"])
        print(f"wrote {args.out} ({len(payload['cases'])} case, {checks} checks)")
        return 0

    if args.command == "from-cdcp-events":
        result = import_cdcp_events(args.path, args.out)
        for error in result.line_errors:
            print(
                f"warning: skipped {error.source_path}:{error.line_number}: {error.message}",
                file=sys.stderr,
            )
        if result.output_path is None:
            print(
                f"no candidate eval cases found ({result.events_read} events read, "
                f"{result.ignored_events} ignored)",
                file=sys.stderr,
            )
            return 1
        print(
            f"wrote {result.output_path} "
            f"({result.case_count} draft case(s), {result.ignored_events} ignored event(s))"
        )
        if result.line_errors:
            print(
                f"skipped {len(result.line_errors)} malformed JSONL line(s)",
                file=sys.stderr,
            )
        return 0

    if args.command == "evidence":
        if args.evidence_command == "from-cdcp-events":
            output_path = args.out
            if output_path.suffix == "":
                output_path = output_path / EVIDENCE_OUTPUT_FILENAME
            result = write_run_evidence_from_cdcp_events(
                args.path,
                output_path,
                run_record_path=args.run_record,
                portfolio_root=args.portfolio_root,
            )
            for error in result.line_errors:
                print(
                    f"warning: skipped {error.source_path}:{error.line_number}: {error.message}",
                    file=sys.stderr,
                )
            print(
                f"wrote {result.output_path} "
                f"({result.events_read} events, "
                f"{len(result.packet['gate_results'])} gate result(s), "
                f"{len(result.packet['policy_decisions'])} policy decision(s))"
            )
            if result.line_errors:
                print(
                    f"skipped {len(result.line_errors)} malformed JSONL line(s)",
                    file=sys.stderr,
                )
            append_audit_entry(
                command="evidence.from-cdcp-events",
                ledger_path=str(args.path),
                run_id=result.packet.get("run_id"),
                result="ok",
            )
            return 0

        if args.evidence_command == "validate":
            failed = False
            for path in args.paths:
                try:
                    result = validate_document(
                        "evidence", path, schema_dir=args.schema_dir
                    )
                except Exception as exc:
                    print(f"invalid: {path}: {exc}", file=sys.stderr)
                    failed = True
                    continue
                if not result.passed:
                    failed = True
                    print(
                        f"invalid: {path} does not match {result.schema_id}",
                        file=sys.stderr,
                    )
                    for issue in result.issues:
                        print(f"  - {issue.location}: {issue.message}", file=sys.stderr)
                    continue
                print(f"valid: {path} matches {result.schema_id}")

                if not getattr(args, "strict", False):
                    continue

                # Strict mode: re-hash referenced run record + event log +
                # artifacts and compare against the packet's stored hashes.
                portfolio_root = (
                    args.portfolio_root
                    or Path(__import__("os").environ.get("PORTFOLIO_ROOT") or path.resolve().parent.parent.parent)
                )
                packet = json.loads(path.read_text(encoding="utf-8"))
                strict_failures = _strict_rehash_packet(packet, portfolio_root)
                if strict_failures:
                    failed = True
                    print(
                        f"strict-rehash failure(s) for {path}:",
                        file=sys.stderr,
                    )
                    for kind, reason in strict_failures:
                        print(f"  - {kind}: {reason}", file=sys.stderr)
                else:
                    print(f"strict: {path} re-hash matches stored hashes")
            return 1 if failed else 0

    if args.command == "run":
        payload = run_eval_file(args.eval_cases, args.traces)
        markdown_path = write_reports(payload, args.out)
        summary = payload["summary"]
        print(
            f"wrote {args.out} and {markdown_path} "
            f"({summary['failed_cases']} failed cases, {summary['failed_checks']} failed checks)"
        )
        if args.fail_on_failure and summary["failed_cases"]:
            return 1
        return 0

    if args.command == "validate":
        failed = False
        for path in args.paths:
            try:
                result = validate_document(args.kind, path, schema_dir=args.schema_dir)
            except Exception as exc:
                print(f"invalid: {path}: {exc}", file=sys.stderr)
                failed = True
                continue
            if result.passed:
                print(f"valid: {path} matches {result.schema_id}")
                continue
            failed = True
            print(f"invalid: {path} does not match {result.schema_id}", file=sys.stderr)
            for issue in result.issues:
                print(f"  - {issue.location}: {issue.message}", file=sys.stderr)
        return 1 if failed else 0

    if args.command == "validate-chain":
        try:
            chain = run_validate_chain(
                args.ledger_path,
                run_record_path=args.run_record,
                portfolio_root=args.portfolio_root,
            )
        except ChainValidationError as exc:
            print(f"FAIL: {exc.stage}", file=sys.stderr)
            print(f"  reason: {exc.message}", file=sys.stderr)
            if not args.no_audit:
                append_audit_entry(
                    command="validate-chain",
                    ledger_path=str(args.ledger_path),
                    run_id=None,
                    result="fail",
                    failing_stage=exc.stage,
                    error_message=exc.message,
                    log_path=args.audit_log,
                )
            return 1
        summary = chain.to_summary()
        print("OK validate-chain")
        print(json.dumps(summary, indent=2, sort_keys=True))
        if not args.no_audit:
            append_audit_entry(
                command="validate-chain",
                ledger_path=str(args.ledger_path),
                run_id=chain.run_id,
                result="ok",
                packet_hash=chain.packet_hash,
                log_path=args.audit_log,
            )
        return 0

    if args.command == "audit":
        if args.audit_command == "summary":
            summary = summarize(
                log_path=args.log_path,
                since=args.since,
                top_n=args.top,
            )
            print(format_summary(summary))
            return 0

    if args.command == "dashboard":
        paths = args.paths if isinstance(args.paths, list) else [args.paths]
        rendered = run_dashboard(
            paths=paths,
            output=args.out,
            portfolio_root=args.portfolio_root,
        )
        if args.out is None:
            print(rendered, end="")
        else:
            print(f"wrote {args.out}")
        return 0

    parser.error("unknown command")
    return 2
