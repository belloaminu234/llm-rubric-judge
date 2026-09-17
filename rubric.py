"""A Rubric is a list of criteria, each either a deterministic check
(see deterministic.py) or an llm_judge check, plus the confidence
threshold below which an llm_judge score is treated as "uncertain"
rather than trusted (see evaluator.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RubricCriterion:
    name: str
    weight: float
    check: dict[str, Any]  # {"kind": "contains" | "not_contains" | "regex" |
                            #  "python_predicate" | "llm_judge", ...}

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError(f"criterion {self.name!r}: weight must be > 0, got {self.weight}")
        if "kind" not in self.check:
            raise ValueError(f"criterion {self.name!r}: check is missing 'kind'")


@dataclass(frozen=True)
class Rubric:
    criteria: tuple[RubricCriterion, ...]
    confidence_threshold: float = 0.7
    pass_threshold: float = 0.7  # an llm_judge criterion's own score must clear this to "pass"

    def __post_init__(self) -> None:
        if not self.criteria:
            raise ValueError("a rubric must have at least one criterion")
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        if not (0.0 <= self.pass_threshold <= 1.0):
            raise ValueError("pass_threshold must be between 0.0 and 1.0")


def load_rubric(json_text: str) -> Rubric:
    data = json.loads(json_text)
    criteria = tuple(
        RubricCriterion(name=c["name"], weight=c.get("weight", 1.0), check=c["check"])
        for c in data["criteria"]
    )
    return Rubric(
        criteria=criteria,
        confidence_threshold=data.get("confidence_threshold", 0.7),
        pass_threshold=data.get("pass_threshold", 0.7),
    )
