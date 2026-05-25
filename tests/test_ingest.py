from __future__ import annotations

import yaml

from trace_to_eval.cli import main


def test_ingest_maps_failed_trace_to_review_case(tmp_path) -> None:
    trace = tmp_path / "bad.json"
    trace.write_text(
        """
{
  "trace_id": "t1",
  "input": "question",
  "output": "bad answer [C1]",
  "citations": [{"span": "other text"}],
  "expected_behavior": {"citation_spans": ["bad answer"]},
  "failure_tags": ["bad_citation"]
}
""".strip(),
        encoding="utf-8",
    )
    out = tmp_path / "generated.yaml"

    assert main(["ingest", str(trace), "--out", str(out)]) == 0

    payload = yaml.safe_load(out.read_text(encoding="utf-8"))
    case = payload["cases"][0]
    assert case["source_trace_id"] == "t1"
    assert case["human_review"]["status"] == "TODO"
    assert case["checks"] == [{"type": "citation_span_present", "value": "bad answer"}]

