from __future__ import annotations

import json
from pathlib import Path

import yaml

from trace_to_eval.cdcp_events import cases_from_cdcp_events, parse_event_logs
from trace_to_eval.cli import main
from trace_to_eval.validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EVENT_LOG = ROOT / "tests" / "fixtures" / "cdcp_events" / "event-log"


def test_parse_event_logs_skips_bad_lines() -> None:
    events, errors = parse_event_logs(FIXTURE_EVENT_LOG)

    assert len(events) == 2
    assert len(errors) == 1
    assert errors[0].line_number == 3
    assert errors[0].message.startswith("invalid JSON")


def test_from_cdcp_events_cli_writes_schema_valid_review_drafts(tmp_path, capsys) -> None:
    out_dir = tmp_path / "out"

    code = main(["from-cdcp-events", str(FIXTURE_EVENT_LOG), "--out", str(out_dir)])

    captured = capsys.readouterr()
    assert code == 0
    assert "malformed JSONL" in captured.err

    out_file = out_dir / "cdcp_event_cases.yaml"
    validation = validate_document("eval", out_file)
    assert validation.passed, validation.issues

    payload = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 1
    case = payload["cases"][0]
    assert case["id"] == "cdcp_bad_citation_gate_failed_draft"
    assert case["suite"] == "citation_integrity"
    assert case["trace_id"] == "cdcp_bad_citation"
    assert case["trace_file"] == "bad_citation.json"
    assert case["human_review"]["status"] == "review-needed"
    assert case["failure_tags"] == ["bad_citation"]
    assert case["checks"] == [{"type": "citation_span_present", "value": "missing support span"}]


def test_review_finding_event_maps_explicit_check(tmp_path) -> None:
    event_log = tmp_path / "events.jsonl"
    event_log.write_text(
        json.dumps(
            {
                "type": "review.finding.created",
                "payload": {
                    "trace_id": "reviewed_trace",
                    "input": "Return the support summary.",
                    "checks": [
                        {
                            "type": "does_not_contain_text",
                            "value": "unsupported claim",
                        }
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, errors = parse_event_logs(event_log)
    cases, ignored = cases_from_cdcp_events(events)

    assert errors == []
    assert ignored == 0
    assert cases[0]["id"] == "reviewed_trace_review_finding_created_draft"
    assert cases[0]["human_review"]["status"] == "review-needed"
    assert cases[0]["checks"] == [
        {"type": "does_not_contain_text", "value": "unsupported claim"}
    ]
