"""Hypothesis property tests for the URI parser (Round 6, DEC-TTE-009).

The regex-based parser in ``trace_to_eval/uri.py`` is the seam between
producer Run records and the consumer harness. A property-test pass
gives us coverage the example-fixture tests cannot: an exhaustive sweep
of the URI grammar instead of a handful of curated strings.

The properties under contract:

* Any well-formed ``repo://<repo>@<sha>/<path>`` URI round-trips
  through ``parse_repo_uri`` to its original components.
* Any well-formed ``artifact://<repo>/<id>`` URI round-trips through
  ``parse_artifact_uri``.
* ``resolve_ref`` returns the legacy path verbatim (anchored under
  ``portfolio_root``) when the input is not a URI.
* Malformed ``repo://`` inputs (short SHA, missing ``@``, missing
  ``/``, uppercase repo name, empty repo) return None.
* parse -> reconstruct -> parse is identity for both schemes.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from hypothesis import HealthCheck, given, settings, strategies as st

from trace_to_eval.uri import (
    parse_artifact_uri,
    parse_repo_uri,
    resolve_ref,
)


# --- Strategies -------------------------------------------------------

# Repo name: leading [a-z] then [a-z0-9-]*.
_repo_name = st.builds(
    lambda head, tail: head + tail,
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=1),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=0, max_size=20),
)

# 40-hex SHA-1 digest.
_sha = st.text(alphabet="0123456789abcdef", min_size=40, max_size=40)

# A "safe" repo:// path body. We avoid embedded newlines because the
# parser's grammar uses '.' which excludes newlines by default. Empty
# string is allowed (root-trailing slash case).
_path_segment = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="_-.",
    ),
    min_size=1,
    max_size=10,
)
_safe_path = st.builds(
    lambda parts: "/".join(parts),
    st.lists(_path_segment, min_size=0, max_size=4),
)

# Artifact id: any non-empty single-line string, no slashes-at-start
# constraint imposed by the grammar (only must be non-empty).
_artifact_id = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="_-.@:/",
    ),
    min_size=1,
    max_size=30,
)


# --- Properties: well-formed inputs round-trip ------------------------


@given(repo=_repo_name, sha=_sha, path=_safe_path)
def test_parse_repo_uri_roundtrip(repo: str, sha: str, path: str) -> None:
    uri = f"repo://{repo}@{sha}/{path}"
    parsed = parse_repo_uri(uri)
    assert parsed is not None, f"expected well-formed URI to parse: {uri!r}"
    assert parsed == (repo, sha, path)


@given(repo=_repo_name, sha=_sha, path=_safe_path)
def test_parse_repo_uri_reconstruct_is_identity(
    repo: str, sha: str, path: str
) -> None:
    uri = f"repo://{repo}@{sha}/{path}"
    parsed = parse_repo_uri(uri)
    assert parsed is not None
    reconstructed = f"repo://{parsed[0]}@{parsed[1]}/{parsed[2]}"
    assert reconstructed == uri
    # Parse-reconstruct-parse identity.
    assert parse_repo_uri(reconstructed) == parsed


@given(repo=_repo_name, artifact_id=_artifact_id)
def test_parse_artifact_uri_roundtrip(repo: str, artifact_id: str) -> None:
    uri = f"artifact://{repo}/{artifact_id}"
    parsed = parse_artifact_uri(uri)
    assert parsed is not None, f"expected well-formed artifact URI to parse: {uri!r}"
    assert parsed == (repo, artifact_id)


@given(repo=_repo_name, artifact_id=_artifact_id)
def test_parse_artifact_uri_reconstruct_is_identity(
    repo: str, artifact_id: str
) -> None:
    uri = f"artifact://{repo}/{artifact_id}"
    parsed = parse_artifact_uri(uri)
    assert parsed is not None
    reconstructed = f"artifact://{parsed[0]}/{parsed[1]}"
    assert reconstructed == uri
    assert parse_artifact_uri(reconstructed) == parsed


# --- Properties: malformed repo:// inputs are rejected ----------------


@given(
    repo=_repo_name,
    bad_sha=st.text(
        alphabet="0123456789abcdef",
        min_size=0,
        max_size=80,
    ).filter(lambda s: len(s) != 40),
    path=_safe_path,
)
def test_parse_repo_uri_rejects_wrong_sha_length(
    repo: str, bad_sha: str, path: str
) -> None:
    uri = f"repo://{repo}@{bad_sha}/{path}"
    assert parse_repo_uri(uri) is None


@given(repo=_repo_name, sha=_sha)
def test_parse_repo_uri_rejects_missing_at_sign(repo: str, sha: str) -> None:
    # Missing the '@' between repo and sha.
    uri = f"repo://{repo}{sha}/path"
    assert parse_repo_uri(uri) is None


@given(repo=_repo_name, sha=_sha)
def test_parse_repo_uri_rejects_missing_path_slash(repo: str, sha: str) -> None:
    # The grammar requires a '/' after <sha>, even if the path body is empty.
    uri = f"repo://{repo}@{sha}"
    assert parse_repo_uri(uri) is None


@given(
    bad_repo=st.text(
        alphabet=st.characters(whitelist_categories=("Lu",)),
        min_size=1,
        max_size=10,
    ),
    sha=_sha,
    path=_safe_path,
)
def test_parse_repo_uri_rejects_uppercase_repo(
    bad_repo: str, sha: str, path: str
) -> None:
    uri = f"repo://{bad_repo}@{sha}/{path}"
    assert parse_repo_uri(uri) is None


@given(sha=_sha, path=_safe_path)
def test_parse_repo_uri_rejects_empty_repo(sha: str, path: str) -> None:
    uri = f"repo://@{sha}/{path}"
    assert parse_repo_uri(uri) is None


@given(
    bad_lead=st.text(
        alphabet="0123456789-",
        min_size=1,
        max_size=1,
    ),
    repo_tail=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
        min_size=0,
        max_size=10,
    ),
    sha=_sha,
    path=_safe_path,
)
def test_parse_repo_uri_rejects_repo_starting_with_digit_or_dash(
    bad_lead: str, repo_tail: str, sha: str, path: str
) -> None:
    uri = f"repo://{bad_lead}{repo_tail}@{sha}/{path}"
    assert parse_repo_uri(uri) is None


# --- Properties: artifact:// rejects empty id -------------------------


@given(repo=_repo_name)
def test_parse_artifact_uri_rejects_empty_id(repo: str) -> None:
    assert parse_artifact_uri(f"artifact://{repo}/") is None


# --- Properties: non-URI inputs flow through resolve_ref --------------


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    legacy=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"),
            whitelist_characters="_-./",
        ),
        min_size=1,
        max_size=40,
    ).filter(
        lambda s: not s.startswith("repo://")
        and not s.startswith("artifact://")
        and not PurePosixPath(s).is_absolute()
    )
)
def test_resolve_ref_anchors_non_uri_under_portfolio_root(legacy: str) -> None:
    portfolio_root = Path("/tmp/portfolio")
    resolved = resolve_ref(legacy, portfolio_root)
    # The legacy path is anchored under portfolio_root verbatim.
    assert resolved == portfolio_root / Path(legacy)


@given(repo=_repo_name, artifact_id=_artifact_id)
def test_resolve_ref_returns_none_for_artifact_uri(
    repo: str, artifact_id: str
) -> None:
    uri = f"artifact://{repo}/{artifact_id}"
    assert resolve_ref(uri, Path("/tmp/portfolio")) is None


@given(repo=_repo_name, sha=_sha, path=_safe_path)
def test_resolve_ref_resolves_repo_uri_under_portfolio_root(
    repo: str, sha: str, path: str
) -> None:
    portfolio_root = Path("/tmp/portfolio")
    uri = f"repo://{repo}@{sha}/{path}"
    resolved = resolve_ref(uri, portfolio_root)
    assert resolved is not None
    # The SHA is advisory, so the resolver drops it from the on-disk path.
    expected = portfolio_root / repo / path
    assert resolved == expected
