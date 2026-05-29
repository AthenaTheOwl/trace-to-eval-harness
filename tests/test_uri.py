from __future__ import annotations

from pathlib import Path

from trace_to_eval.uri import (
    parse_artifact_uri,
    parse_repo_uri,
    resolve_ref,
    resolve_repo_uri,
)


VALID_SHA = "f2291a447f39e4b4347b2be08fd43491feddfbc1"


def test_parse_repo_uri_positive() -> None:
    parsed = parse_repo_uri(f"repo://ai-field-brief@{VALID_SHA}/briefs/2026-W22/brief.md")
    assert parsed == ("ai-field-brief", VALID_SHA, "briefs/2026-W22/brief.md")


def test_parse_repo_uri_root_path() -> None:
    # Trailing slash with empty path component (sandbox_image_ref shape).
    parsed = parse_repo_uri(f"repo://chip-supply-chain-map@{VALID_SHA}/")
    assert parsed == ("chip-supply-chain-map", VALID_SHA, "")


def test_parse_repo_uri_negative_short_sha() -> None:
    # SHAs must be 40 hex chars.
    assert parse_repo_uri("repo://demo@abc123/file") is None


def test_parse_repo_uri_negative_uppercase_repo() -> None:
    # Repo names must be lowercase-kebab.
    assert parse_repo_uri(f"repo://DemoRepo@{VALID_SHA}/file") is None


def test_parse_repo_uri_negative_wrong_scheme() -> None:
    assert parse_repo_uri(f"artifact://demo/{VALID_SHA}") is None
    assert parse_repo_uri("/abs/path") is None
    assert parse_repo_uri("relative/path") is None


def test_parse_artifact_uri_positive() -> None:
    parsed = parse_artifact_uri("artifact://chip-supply-chain-map/watchlist-packet@run-6a665b303138")
    assert parsed == ("chip-supply-chain-map", "watchlist-packet@run-6a665b303138")


def test_parse_artifact_uri_negative() -> None:
    assert parse_artifact_uri(f"repo://demo@{VALID_SHA}/file") is None
    assert parse_artifact_uri("artifact://demo/") is None  # empty id
    assert parse_artifact_uri("just-a-path/file.md") is None


def test_resolve_repo_uri_uses_portfolio_root(tmp_path: Path) -> None:
    portfolio_root = tmp_path / "portfolio"
    portfolio_root.mkdir()
    uri = f"repo://ai-field-brief@{VALID_SHA}/briefs/2026-W22/brief.md"
    resolved = resolve_repo_uri(uri, portfolio_root)
    assert resolved == portfolio_root / "ai-field-brief" / "briefs/2026-W22/brief.md"


def test_resolve_repo_uri_returns_none_for_non_repo(tmp_path: Path) -> None:
    assert resolve_repo_uri("artifact://demo/abc", tmp_path) is None
    assert resolve_repo_uri("relative/path.md", tmp_path) is None


def test_resolve_ref_dispatches_repo_uri(tmp_path: Path) -> None:
    uri = f"repo://supplier-risk-rag-agent@{VALID_SHA}/eval_suites/refusal_cases.yaml"
    resolved = resolve_ref(uri, tmp_path)
    assert resolved == tmp_path / "supplier-risk-rag-agent" / "eval_suites/refusal_cases.yaml"


def test_resolve_ref_returns_none_for_artifact_uri(tmp_path: Path) -> None:
    assert resolve_ref("artifact://demo/some-artifact-id", tmp_path) is None


def test_resolve_ref_keeps_absolute_legacy_path(tmp_path: Path) -> None:
    absolute = tmp_path / "legacy.json"
    absolute.write_text("{}", encoding="utf-8")
    resolved = resolve_ref(str(absolute), tmp_path / "other-root")
    assert resolved == absolute


def test_resolve_ref_anchors_relative_legacy_path(tmp_path: Path) -> None:
    resolved = resolve_ref("ops/run-records/run-x.json", tmp_path)
    assert resolved == tmp_path / "ops/run-records/run-x.json"
