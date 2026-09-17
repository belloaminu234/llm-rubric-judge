"""Deterministic checks: the "hard gate" layer. Each check is fully
objective and reproducible -- no model call involved -- so a failing
deterministic check vetoes the whole evaluation regardless of what an
LLM judge would say (see evaluator.py).

Supported check kinds:
  {"kind": "contains", "substring": "..."}
  {"kind": "not_contains", "substring": "..."}
  {"kind": "regex", "pattern": "..."}
  {"kind": "python_predicate", "expression": "..."}  -- see _safe_eval below
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    detail: str


class UnsafeExpressionError(ValueError):
    """Raised when a python_predicate expression trips a safety guard."""


# A deliberately small, safe-ish namespace for python_predicate
# expressions: no __builtins__ at all, plus a short allow-list of pure,
# harmless functions. This is a lightweight guard, NOT a hardened
# sandbox -- see the README's Limitations section. Rubric definitions
# should be treated as trusted input, the same way you'd treat a CI
# config file, not as arbitrary user-supplied code.
_SAFE_NAMESPACE: dict[str, Any] = {
    "len": len, "any": any, "all": all, "str": str, "int": int,
    "float": float, "bool": bool, "sorted": sorted, "min": min, "max": max,
    "sum": sum, "abs": abs,
}


def _safe_eval(expression: str, output: str) -> Any:
    if "__" in expression:
        # Blocks the common dunder-based sandbox-escape tricks (e.g.
        # `().__class__.__bases__`) as a defense-in-depth measure, on
        # top of the empty __builtins__ below.
        raise UnsafeExpressionError(
            "python_predicate expressions may not contain double underscores"
        )
    namespace = dict(_SAFE_NAMESPACE)
    namespace["output"] = output
    return eval(expression, {"__builtins__": {}}, namespace)  # noqa: S307


def check_contains(output: str, substring: str) -> CheckResult:
    passed = substring in output
    detail = f"substring {substring!r} {'found' if passed else 'NOT found'} in output"
    return CheckResult(passed, detail)


def check_not_contains(output: str, substring: str) -> CheckResult:
    passed = substring not in output
    detail = f"substring {substring!r} {'absent as required' if passed else 'unexpectedly present'}"
    return CheckResult(passed, detail)


def check_regex(output: str, pattern: str) -> CheckResult:
    passed = re.search(pattern, output) is not None
    detail = f"pattern {pattern!r} {'matched' if passed else 'did NOT match'}"
    return CheckResult(passed, detail)


def check_python_predicate(output: str, expression: str) -> CheckResult:
    try:
        result = _safe_eval(expression, output)
    except UnsafeExpressionError as exc:
        return CheckResult(False, f"expression rejected: {exc}")
    except Exception as exc:  # noqa: BLE001 - a bad expression is a check failure, not a crash
        return CheckResult(False, f"expression raised {type(exc).__name__}: {exc}")

    passed = bool(result)
    return CheckResult(passed, f"expression {expression!r} evaluated to {result!r}")


_DISPATCH = {
    "contains": lambda output, spec: check_contains(output, spec["substring"]),
    "not_contains": lambda output, spec: check_not_contains(output, spec["substring"]),
    "regex": lambda output, spec: check_regex(output, spec["pattern"]),
    "python_predicate": lambda output, spec: check_python_predicate(output, spec["expression"]),
}


def run_deterministic_check(spec: dict[str, Any], output: str) -> CheckResult:
    kind = spec.get("kind")
    if kind not in _DISPATCH:
        raise ValueError(f"unknown deterministic check kind: {kind!r}")
    return _DISPATCH[kind](output, spec)
