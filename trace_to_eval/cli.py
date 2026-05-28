from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .cdcp_events import import_cdcp_events
from .ingest import ingest_trace
from .report import write_reports
from .run_evidence import OUTPUT_FILENAME as EVIDENCE_OUTPUT_FILENAME
from .run_evidence import write_run_evidence_from_cdcp_events
from .runner import run_eval_file
from .validation import schema_kinds, validate_document


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
    evidence_cdcp = evidence_subparsers.add_parser(
        "from-cdcp-events",
        help="turn CDCP event-log JSONL entries into a run evidence packet",
    )
    evidence_cdcp.add_argument("path", type=Path)
    evidence_cdcp.add_argument("--out", type=Path, required=True)
    evidence_cdcp.add_argument(
        "--run-record",
        type=Path,
        default=None,
        help=(
            "explicit path to the producer Run record JSON. "
            "Default: auto-discover at <event-log>/../run-records/<run_id>.json."
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
                if result.passed:
                    print(f"valid: {path} matches {result.schema_id}")
                    continue
                failed = True
                print(
                    f"invalid: {path} does not match {result.schema_id}",
                    file=sys.stderr,
                )
                for issue in result.issues:
                    print(f"  - {issue.location}: {issue.message}", file=sys.stderr)
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

    parser.error("unknown command")
    return 2
