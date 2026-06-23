"""trace-to-eval-harness — live demo (Streamlit Community Cloud).

Mirrors the no-arg `python -m trace_to_eval show` verb: reads the committed
run report under reports/run.json and shows which pinned AI-failure
regressions are now frozen into deterministic eval cases — worst suite first.
No network, no secrets, no model key — runs entirely off the committed report.

Deploy: Streamlit Community Cloud -> New app -> repo
AthenaTheOwl/trace-to-eval-harness, branch main, main file streamlit_app.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

REPO = Path(__file__).resolve().parent
REPORT = REPO / "reports" / "run.json"


def load_report() -> dict[str, Any] | None:
    if not REPORT.exists():
        return None
    return json.loads(REPORT.read_text(encoding="utf-8"))


def observed_snippet(check: dict[str, Any]) -> str:
    observed = check.get("observed")
    if observed is None:
        return check.get("message", "")
    if isinstance(observed, list):
        observed = ", ".join(str(item) for item in observed)
    text = str(observed).replace("\n", " ").strip()
    if len(text) > 90:
        text = text[:87] + "..."
    return text


st.set_page_config(page_title="trace-to-eval-harness — pinned regressions", layout="wide")
st.title("trace-to-eval-harness")
st.caption(
    "which AI failures are now frozen into deterministic eval cases — "
    "a fabricated citation, a leaked credential, a tool used outside its "
    "allowlist. reads the committed reports/run.json, worst suite first."
)

payload = load_report()
if not payload:
    st.warning("no report found at reports/run.json — run `python -m trace_to_eval run ...` first")
    st.stop()

summary = payload["summary"]
cases = payload.get("cases", [])

c1, c2, c3 = st.columns(3)
c1.metric("cases failed", f"{summary['failed_cases']} / {summary['total_cases']}")
c2.metric("checks failed", f"{summary['failed_checks']} / {summary['total_checks']}")
c3.metric("suites", f"{len(summary.get('suites', {}))}")

# Ranked suites: most failed cases first, then name for stability.
suites = summary.get("suites", {})
ranked = sorted(
    suites.items(),
    key=lambda kv: (-kv[1].get("failed_cases", 0), kv[0]),
)

st.subheader("suites — ranked by failed cases")
st.dataframe(
    [
        {
            "suite": name,
            "failed cases": counts.get("failed_cases", 0),
            "cases": counts.get("cases", 0),
            "passed cases": counts.get("passed_cases", 0),
        }
        for name, counts in ranked
    ],
    use_container_width=True,
    hide_index=True,
)

# Interactive control: filter cases by suite.
suite_names = ["all suites"] + [name for name, _ in ranked]
chosen = st.selectbox("filter cases by suite", suite_names)

failing = [c for c in cases if not c.get("passed", True)]
if chosen != "all suites":
    failing = [c for c in failing if c.get("suite") == chosen]

st.subheader("failing cases")
if failing:
    rows = []
    for case in failing:
        broken = [ck for ck in case.get("checks", []) if not ck.get("passed", True)]
        for ck in broken:
            rows.append(
                {
                    "case": case["id"],
                    "suite": case["suite"],
                    "trace": case["trace_id"],
                    "check": ck["type"],
                    "why": ck.get("message", ""),
                    "observed": observed_snippet(ck),
                }
            )
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.success("no failing cases for this filter — all pinned eval cases pass.")

# Headline finding.
if summary["failed_cases"]:
    top_name, top_counts = ranked[0] if ranked else ("", {})
    st.info(
        f"**bottom line:** {summary['failed_cases']} regression(s) are now pinned as "
        f"deterministic eval cases across {len(suites)} suite(s). worst suite: "
        f"`{top_name}` with {top_counts.get('failed_cases', 0)} failed case(s). "
        "each is a real AI failure that can no longer ship twice unnoticed."
    )
else:
    st.success("**bottom line:** all pinned eval cases pass.")

with st.expander("evidence — full check detail per failing case"):
    for case in failing:
        st.markdown(f"**{case['id']}**  ·  suite `{case['suite']}`  ·  trace `{case['trace_id']}`")
        for ck in case.get("checks", []):
            if ck.get("passed", True):
                continue
            st.markdown(
                f"- x `{ck['type']}` — {ck.get('message', '')}  \n"
                f"  expected: `{ck.get('expected')}`  \n"
                f"  observed: `{observed_snippet(ck)}`"
            )

st.caption(
    "v0.1 ships one committed fixture report. the model + checks live in "
    "`trace_to_eval/`; this page mirrors `python -m trace_to_eval show` off the "
    "committed `reports/run.json`. repo: github.com/AthenaTheOwl/trace-to-eval-harness"
)
