"""CLI: python -m rubricjudge.cli --rubric rubric.json --output output.txt [--no-llm-judge]

By default, uses AnthropicJudge for any llm_judge criteria, which
requires ANTHROPIC_API_KEY to be set. Pass --no-llm-judge to run only
the deterministic criteria (useful for a quick check, or when no API
key is configured) -- any llm_judge criteria are then skipped and
reported as such, not silently treated as passing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rubricjudge.evaluator import evaluate
from rubricjudge.judge import AnthropicJudge
from rubricjudge.report import render_report
from rubricjudge.rubric import load_rubric


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate output against a rubric of deterministic + LLM-judge criteria."
    )
    parser.add_argument("--rubric", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--no-llm-judge", action="store_true",
        help="Skip llm_judge criteria instead of calling a real judge.",
    )
    args = parser.parse_args(argv)

    if not args.rubric.exists():
        print(f"error: {args.rubric} does not exist", file=sys.stderr)
        return 1
    if not args.output.exists():
        print(f"error: {args.output} does not exist", file=sys.stderr)
        return 1

    rubric = load_rubric(args.rubric.read_text())
    output_text = args.output.read_text()

    has_llm_criteria = any(c.check["kind"] == "llm_judge" for c in rubric.criteria)
    judge = None
    if has_llm_criteria and not args.no_llm_judge:
        try:
            judge = AnthropicJudge()
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print("(pass --no-llm-judge to skip LLM-judge criteria)", file=sys.stderr)
            return 1

    if args.no_llm_judge:
        rubric = load_rubric(args.rubric.read_text())
        deterministic_only = tuple(c for c in rubric.criteria if c.check["kind"] != "llm_judge")
        if not deterministic_only:
            print("error: --no-llm-judge leaves no criteria to evaluate", file=sys.stderr)
            return 1
        from dataclasses import replace
        rubric = replace(rubric, criteria=deterministic_only)

    result = evaluate(rubric, output_text, judge)
    print(render_report(result), end="")

    return 0 if result.overall_status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
