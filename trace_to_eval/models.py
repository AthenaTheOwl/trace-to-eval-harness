from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class Trace:
    trace_id: str
    input: Any
    output: str
    citations: list[Any] = field(default_factory=list)
    spans: list[Any] = field(default_factory=list)
    tool_calls: list[Any] = field(default_factory=list)
    terminal_state: Any = None
    effects: list[Any] = field(default_factory=list)
    expected_behavior: dict[str, Any] = field(default_factory=dict)
    failure_tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Trace":
        missing = [name for name in ("trace_id", "input", "output") if name not in payload]
        if missing:
            raise ValueError(f"trace missing required field(s): {', '.join(missing)}")
        expected = payload.get("expected_behavior") or {}
        if not isinstance(expected, dict):
            raise ValueError("expected_behavior must be an object when present")
        return cls(
            trace_id=str(payload["trace_id"]),
            input=payload["input"],
            output=_as_text(payload["output"]),
            citations=_as_list(payload.get("citations")),
            spans=_as_list(payload.get("spans")),
            tool_calls=_as_list(payload.get("tool_calls")),
            terminal_state=payload.get("terminal_state"),
            effects=_as_list(payload.get("effects")),
            expected_behavior=expected,
            failure_tags=[str(tag) for tag in _as_list(payload.get("failure_tags"))],
            raw=payload,
        )


@dataclass(frozen=True)
class CheckResult:
    check_type: str
    passed: bool
    message: str
    expected: Any = None
    observed: Any = None


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    suite: str
    trace_id: str
    passed: bool
    checks: list[CheckResult]


def tool_call_name(call: Any) -> str:
    if isinstance(call, str):
        return call
    if not isinstance(call, dict):
        return str(call)
    if isinstance(call.get("name"), str):
        return call["name"]
    if isinstance(call.get("tool_name"), str):
        return call["tool_name"]
    function = call.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    return json.dumps(call, sort_keys=True)
