from __future__ import annotations

import argparse
from pathlib import Path

from .ingest import ingest_trace
from .report import write_reports
from .runner import run_eval_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trace_to_eval",
        description="Build eval cases from traces and run deterministic checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="turn one failed trace into a YAML case")
    ingest.add_argument("trace", type=Path)
    ingest.add_argument("--out", type=Path, required=True)

    run = subparsers.add_parser("run", help="run eval cases against trace JSON files")
    run.add_argument("eval_cases", type=Path)
    run.add_argument("--traces", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument(
        "--fail-on-failure",
        action="store_true",
        help="exit 1 when any case fails",
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

    parser.error("unknown command")
    return 2

