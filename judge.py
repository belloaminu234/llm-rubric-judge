"""The LLM-as-a-judge layer, abstracted the same way depfix abstracts
its package registry: a Protocol so the confidence-gating logic in
evaluator.py is fully unit-testable with no network access, plus a real
implementation for actual use.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JudgeResult:
    score: float       # 0.0-1.0: how well the output satisfies the criterion
    confidence: float   # 0.0-1.0: how confident the judge is in that score
    rationale: str


class LlmJudge(Protocol):
    def score(self, criterion_prompt: str, output: str) -> JudgeResult: ...


class AnthropicJudge:
    """Calls the real Anthropic Messages API, asking the model to return
    its score/confidence/rationale as JSON. Requires an API key (passed
    directly or read from the ANTHROPIC_API_KEY environment variable).
    Never used in the test suite -- see ScriptedJudge -- since it needs
    network access and a real key.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "no API key provided and ANTHROPIC_API_KEY is not set in the environment"
            )
        self.model = model
        self.timeout_seconds = timeout_seconds

    def score(self, criterion_prompt: str, output: str) -> JudgeResult:
        prompt = (
            "You are grading a piece of text against one rubric criterion.\n\n"
            f"Criterion: {criterion_prompt}\n\n"
            f"Text to grade:\n---\n{output}\n---\n\n"
            "Respond with ONLY a JSON object of the exact shape "
            '{"score": <0.0-1.0>, "confidence": <0.0-1.0>, "rationale": "<one sentence>"}. '
            "score is how well the text satisfies the criterion. confidence is your own "
            "certainty in that score -- use a lower confidence when the criterion is "
            "ambiguous or the text is borderline, not just when you're being cautious."
        )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            self.API_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
            response = json.loads(resp.read())

        text = "".join(
            block["text"] for block in response["content"] if block.get("type") == "text"
        )
        parsed = json.loads(text)
        return JudgeResult(
            score=float(parsed["score"]),
            confidence=float(parsed["confidence"]),
            rationale=str(parsed["rationale"]),
        )


class ScriptedJudge:
    """Test fake: returns a pre-scripted JudgeResult per criterion prompt
    (matched exactly), or a default result for anything unscripted. Used
    throughout the test suite so the confidence-gating and score-blending
    logic can be tested deterministically with no network access.
    """

    def __init__(
        self,
        scripted: dict[str, JudgeResult] | None = None,
        default: JudgeResult | None = None,
    ) -> None:
        self._scripted = scripted or {}
        self._default = default or JudgeResult(score=1.0, confidence=1.0, rationale="default")

    def score(self, criterion_prompt: str, output: str) -> JudgeResult:
        return self._scripted.get(criterion_prompt, self._default)
