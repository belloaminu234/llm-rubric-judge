"""Ties deterministic checks and LLM-judge scoring together.

Policy:
  1. Deterministic criteria are hard gates. If ANY deterministic
     criterion fails, the overall result is "fail" immediately --
     regardless of weights, and regardless of what any llm_judge
     criterion would say. A rubric author uses a deterministic check
     specifically because they want a binary, non-negotiable
     requirement (e.g. "the response must not contain the string
     'TODO'"), and a good LLM judge score shouldn't be able to paper
     over a failed hard requirement.
  2. If all deterministic criteria pass (or there are none), llm_judge
     criteria are scored. A judge result whose confidence is below the
     rubric's confidence_threshold is marked "uncertain" rather than
     trusted -- it's excluded from the weighted score and instead
     raises the overall needs_review flag, since a low-confidence
     grade blended silently into a number would overstate how much was
     actually verified.
  3. The overall score is the weight-normalized average of every
     criterion that WAS trusted (deterministic passes count as 1.0;
     confident llm_judge criteria count as their own score). If every
     criterion ended up uncertain, overall_score is None -- there's
     nothing trustworthy to average.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from rubricjudge.deterministic import run_deterministic_check
from rubricjudge.judge import LlmJudge
from rubricjudge.rubric import Rubric, RubricCriterion

Status = Literal["pass", "fail", "uncertain"]

_DETERMINISTIC_KINDS = {"contains", "not_contains", "regex", "python_predicate"}


@dataclass(frozen=True)
class CriterionResult:
    name: str
    weight: float
    kind: str
    status: Status
    score: float          # 1.0/0.0 for deterministic; the judge's own score for llm_judge
    confidence: float
    detail: str


@dataclass(frozen=True)
class EvaluationResult:
    criterion_results: tuple[CriterionResult, ...]
    overall_status: Literal["pass", "fail"]
    overall_score: Optional[float]
    needs_review: bool


def _evaluate_criterion(
    criterion: RubricCriterion, output: str, judge: Optional[LlmJudge], threshold: float, pass_threshold: float
) -> CriterionResult:
    kind = criterion.check["kind"]

    if kind in _DETERMINISTIC_KINDS:
        result = run_deterministic_check(criterion.check, output)
        return CriterionResult(
            name=criterion.name,
            weight=criterion.weight,
            kind=kind,
            status="pass" if result.passed else "fail",
            score=1.0 if result.passed else 0.0,
            confidence=1.0,
            detail=result.detail,
        )

    if kind == "llm_judge":
        if judge is None:
            raise ValueError(
                f"criterion {criterion.name!r} needs an llm_judge but no judge was provided"
            )
        prompt = criterion.check.get("prompt", criterion.name)
        judge_result = judge.score(prompt, output)

        if judge_result.confidence < threshold:
            return CriterionResult(
                name=criterion.name,
                weight=criterion.weight,
                kind=kind,
                status="uncertain",
                score=judge_result.score,
                confidence=judge_result.confidence,
                detail=(
                    f"confidence {judge_result.confidence:.2f} below threshold "
                    f"{threshold:.2f}; rationale: {judge_result.rationale}"
                ),
            )

        status: Status = "pass" if judge_result.score >= pass_threshold else "fail"
        return CriterionResult(
            name=criterion.name,
            weight=criterion.weight,
            kind=kind,
            status=status,
            score=judge_result.score,
            confidence=judge_result.confidence,
            detail=judge_result.rationale,
        )

    raise ValueError(f"unknown check kind: {kind!r}")


def evaluate(
    rubric: Rubric, output: str, judge: Optional[LlmJudge] = None
) -> EvaluationResult:
    results = [
        _evaluate_criterion(c, output, judge, rubric.confidence_threshold, rubric.pass_threshold)
        for c in rubric.criteria
    ]

    deterministic_failed = any(
        r.kind in _DETERMINISTIC_KINDS and r.status == "fail" for r in results
    )
    needs_review = any(r.status == "uncertain" for r in results)

    trusted = [r for r in results if r.status != "uncertain"]
    if trusted:
        total_weight = sum(r.weight for r in trusted)
        overall_score = sum(r.weight * r.score for r in trusted) / total_weight
    else:
        overall_score = None

    if deterministic_failed:
        overall_status = "fail"
    elif overall_score is not None and overall_score >= rubric.pass_threshold:
        overall_status = "pass"
    else:
        overall_status = "fail"

    return EvaluationResult(
        criterion_results=tuple(results),
        overall_status=overall_status,
        overall_score=overall_score,
        needs_review=needs_review,
    )
