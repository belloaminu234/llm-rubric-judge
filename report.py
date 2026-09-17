"""Renders a plain-text report from an EvaluationResult."""

from __future__ import annotations

from rubricjudge.evaluator import EvaluationResult

_STATUS_MARKER = {"pass": "PASS", "fail": "FAIL", "uncertain": "? "}


def render_report(result: EvaluationResult) -> str:
    lines = ["=== Rubric Evaluation ==="]

    for r in result.criterion_results:
        marker = _STATUS_MARKER[r.status]
        lines.append(
            f"[{marker}] {r.name} (weight {r.weight}, kind {r.kind}) "
            f"score={r.score:.2f} confidence={r.confidence:.2f}"
        )
        lines.append(f"       {r.detail}")

    lines.append("")
    score_str = f"{result.overall_score:.2f}" if result.overall_score is not None else "n/a"
    lines.append(f"Overall: {result.overall_status.upper()}  (score: {score_str})")
    if result.needs_review:
        lines.append(
            "NEEDS REVIEW: at least one criterion's judge confidence was below "
            "threshold and was excluded from scoring."
        )

    return "\n".join(lines) + "\n"
