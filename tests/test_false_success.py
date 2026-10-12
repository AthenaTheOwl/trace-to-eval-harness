from __future__ import annotations

import json
from pathlib import Path

import pytest

from trace_to_eval.cli import main
from trace_to_eval.false_success import audit_paths, audit_trace, tool_error_rule
from trace_to_eval.models import Trace
from trace_to_eval.validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = Path("examples/false_success")


def _trace(**fields) -> Trace:
    payload = {"trace_id": "t", "input": "do the thing", "output": "", **fields}
    return Trace.from_dict(payload)


def _classes(result: dict) -> list[str]:
    return [error["class"] for error in result["tool_errors"]]


def _write_trace(path: Path, **fields) -> Path:
    payload = {"trace_id": path.stem, "input": "do the thing", "output": "", **fields}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_examples_cover_each_class_once(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    summary = audit_paths([EXAMPLES])["summary"]

    assert summary["repaired"] == 1
    assert summary["ignored"] == 1
    assert summary["proceeded_as_success"] == 1
    assert summary["success_without_effect"] == 1
    assert summary["flagged_traces"] == 2


def test_committed_report_matches_examples(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    committed = json.loads((ROOT / "reports" / "false_success.json").read_text(encoding="utf-8"))

    assert committed == audit_paths([EXAMPLES])


def test_cli_fail_on_flag_exits_one_and_report_validates(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    out = tmp_path / "false_success.json"

    code = main(["false-success", str(EXAMPLES), "--out", str(out), "--fail-on-flag"])

    assert code == 1
    assert validate_document("false-success", out).passed
    assert out.with_suffix(".md").read_text(encoding="utf-8").startswith("# False-success audit")


def test_cli_without_fail_on_flag_exits_zero(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    assert main(["false-success", str(EXAMPLES), "--out", str(tmp_path / "r.json")]) == 0


def test_repaired_only_trace_passes_fail_on_flag(tmp_path) -> None:
    trace = _write_trace(
        tmp_path / "clean.json",
        output="Saved. Task complete.",
        tool_calls=[
            {"name": "save_note", "status": "error"},
            {"name": "save_note", "status": "ok"},
        ],
        terminal_state={"status": "success"},
        effects=[{"kind": "note.saved"}],
    )

    code = main(["false-success", str(trace), "--out", str(tmp_path / "r.json"), "--fail-on-flag"])

    assert code == 0


@pytest.mark.parametrize(
    ("call", "rule"),
    [
        ({"name": "x", "status": "error"}, "status=error"),
        ({"name": "x", "status": "FAILED"}, "status=failed"),
        ({"name": "x", "is_error": True}, "is_error"),
        ({"name": "x", "error": "timeout"}, "error_key"),
        ({"name": "x", "error": None}, None),
        ({"name": "x", "is_error": False, "status": "ok"}, None),
        ("x", None),
    ],
)
def test_tool_error_rule(call, rule) -> None:
    assert tool_error_rule(call) == rule


def test_success_on_a_different_tool_does_not_repair() -> None:
    result = audit_trace(
        _trace(
            tool_calls=[
                {"name": "fetch_page", "error": "404"},
                {"name": "fetch_cache", "status": "ok"},
            ],
            terminal_state={"status": "success"},
        ),
        "t.json",
    )

    assert _classes(result) == ["proceeded_as_success"]
    assert result["tool_errors"][0]["repaired_by"] is None


def test_completion_phrase_is_a_claim_and_names_its_rule() -> None:
    result = audit_trace(
        _trace(output="Report uploaded. Task COMPLETE.", tool_calls=[{"name": "upload", "status": "failed"}]),
        "t.json",
    )

    assert result["success_claim"]["rules"] == ["output_phrase:task complete"]
    assert _classes(result) == ["proceeded_as_success"]


def test_non_success_terminal_status_without_phrase_is_ignored() -> None:
    result = audit_trace(
        _trace(output="The upload failed.", tool_calls=[{"name": "upload", "status": "failed"}], terminal_state={"status": "approved"}),
        "t.json",
    )

    assert result["success_claim"] == {"claimed": False, "rules": []}
    assert _classes(result) == ["ignored"]
    assert result["flags"] == []


def test_write_tools_option_replaces_default_verbs(tmp_path) -> None:
    trace = _write_trace(
        tmp_path / "migrate.json",
        tool_calls=[{"name": "apply_migration", "status": "ok"}],
        terminal_state={"status": "success"},
        effects=[],
    )

    default = audit_paths([trace])
    option = audit_paths([trace], frozenset({"apply_migration"}))

    assert default["traces"][0]["flags"] == []
    assert option["traces"][0]["flags"] == ["success_without_effect"]
    assert option["rules"]["write_tools"] == {"source": "option", "values": ["apply_migration"]}


def test_default_write_verbs_match_name_tokens() -> None:
    result = audit_trace(
        _trace(
            tool_calls=["sendEmail", "fs.writeFile", "get_settings", "list_posts"],
            terminal_state={"status": "success"},
            effects=[],
        ),
        "t.json",
    )

    assert result["write_calls"] == 2


def test_missing_effects_is_not_read_as_empty() -> None:
    result = audit_trace(
        _trace(tool_calls=[{"name": "update_row", "status": "ok"}], terminal_state={"status": "success"}),
        "t.json",
    )

    assert result["effects_recorded"] is False
    assert result["flags"] == []


def test_bad_input_exits_two(tmp_path, capsys) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    valid = _write_trace(tmp_path / "valid.json")
    out = str(tmp_path / "r.json")

    assert main(["false-success", str(tmp_path / "missing"), "--out", out]) == 2
    assert main(["false-success", str(empty), "--out", out]) == 2
    assert main(["false-success", str(broken), "--out", out]) == 2
    assert main(["false-success", str(not_object), "--out", out]) == 2
    assert main(["false-success", str(valid), "--out", out, "--write-tools", " , "]) == 2
    assert "error: false-success:" in capsys.readouterr().err
