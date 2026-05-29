"""URI helpers for portable cross-repo refs.

DEC-CDCP-014 introduces two URI schemes for refs that travel between
product repos and the trace-to-eval-harness consumer:

* ``repo://<repo-name>@<sha>/<rel-path>`` — file at a specific commit
  in a portfolio repo. The SHA is advisory metadata; replay-strict
  consumers may verify it matches the producer repo's HEAD.
* ``artifact://<repo-name>/<artifact-id>`` — logical artifact reference,
  not a file path. Resolution is implementation-defined.

Legacy local paths remain accepted for migration interop.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

_REPO_URI_RE = re.compile(
    r"^repo://(?P<repo>[a-z][a-z0-9-]*)@(?P<sha>[a-f0-9]{40})/(?P<path>.*)$"
)
_ARTIFACT_URI_RE = re.compile(
    r"^artifact://(?P<repo>[a-z][a-z0-9-]*)/(?P<id>.+)$"
)


def parse_repo_uri(uri: str) -> Optional[Tuple[str, str, str]]:
    """Parse a ``repo://`` URI into ``(repo, sha, path)`` or return None."""
    match = _REPO_URI_RE.match(uri)
    if match is None:
        return None
    return match["repo"], match["sha"], match["path"]


def parse_artifact_uri(uri: str) -> Optional[Tuple[str, str]]:
    """Parse an ``artifact://`` URI into ``(repo, artifact_id)`` or return None."""
    match = _ARTIFACT_URI_RE.match(uri)
    if match is None:
        return None
    return match["repo"], match["id"]


def resolve_repo_uri(uri: str, portfolio_root: Path) -> Optional[Path]:
    """Resolve a ``repo://`` URI to a local path. Returns None on miss.

    The ``<sha>`` is advisory metadata; this function returns the file
    path under ``portfolio_root`` regardless of whether the producer
    repo's HEAD matches. Replay-strict callers should verify the SHA
    separately.
    """
    parsed = parse_repo_uri(uri)
    if parsed is None:
        return None
    repo, _sha, path = parsed
    return portfolio_root / repo / path


def resolve_ref(ref: str, portfolio_root: Path) -> Optional[Path]:
    """Resolve any ref (URI or legacy path) to a local ``Path``.

    Returns:
        * ``Path`` for ``repo://`` URIs (under ``portfolio_root``).
        * ``Path`` for legacy local paths (absolute kept as-is, relative
          resolved under ``portfolio_root``).
        * ``None`` for ``artifact://`` URIs (no file-system mapping).
    """
    if ref.startswith("repo://"):
        return resolve_repo_uri(ref, portfolio_root)
    if ref.startswith("artifact://"):
        return None
    candidate = Path(ref)
    if candidate.is_absolute():
        return candidate
    return portfolio_root / candidate
