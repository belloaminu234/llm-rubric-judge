# llm-rubric-judge

A Python framework for evaluating agent/model output against a rubric that mixes **deterministic code checks** (objective, reproducible, no model call) with **LLM-as-a-judge scoring** (graded, subjective, confidence-aware) — built on the Python standard library, with the judge itself pluggable so the core logic needs no network access to test.

## The core idea

Two different kinds of rubric criteria need to be treated differently, not blended into one number naively:

- **Deterministic checks** (`contains`, `not_contains`, `regex`, `python_predicate`) are objective and reproducible. If a rubric author wrote one, they wanted a hard, non-negotiable requirement — so **any failing deterministic criterion vetoes the whole evaluation**, regardless of how well an LLM judge scores everything else. A great LLM-judged tone score shouldn't be able to paper over a response that still contains a literal `TODO`.
- **LLM-judge checks** are graded and come with their own uncertainty. A judge's score is only trusted if its **self-reported confidence clears a threshold**; below that, the criterion is marked `uncertain`, **excluded from the weighted score** (rather than silently dragging the average down or up), and raises a `needs_review` flag on the overall result instead.

## Usage

```bash
python -m rubricjudge.cli --rubric rubric.json --output agent_output.txt
```

Requires `ANTHROPIC_API_KEY` in the environment if the rubric has any `llm_judge` criteria. To run only the deterministic criteria (no API key needed):

```bash
python -m rubricjudge.cli --rubric rubric.json --output agent_output.txt --no-llm-judge
```

`rubric.json`:
```json
{
  "confidence_threshold": 0.7,
  "pass_threshold": 0.7,
  "criteria": [
    {"name": "no placeholder text", "weight": 1.0, "check": {"kind": "not_contains", "substring": "TODO"}},
    {"name": "reasonable length", "weight": 1.0, "check": {"kind": "python_predicate", "expression": "len(output) > 20"}},
    {"name": "polite tone", "weight": 2.0, "check": {"kind": "llm_judge", "prompt": "Is the tone polite and professional?"}}
  ]
}
```

Example output:
```
=== Rubric Evaluation ===
[PASS] no placeholder text (weight 1.0, kind not_contains) score=1.00 confidence=1.00
       substring 'TODO' absent as required
[FAIL] mentions the user's name (weight 1.0, kind regex) score=0.00 confidence=1.00
       pattern 'Ada' did NOT match

Overall: FAIL  (score: 0.33)
```

Exit code is `0` on overall pass, `1` on fail — usable directly as a CI gate.

## Supported deterministic check kinds

| kind | fields | checks |
|---|---|---|
| `contains` | `substring` | substring is present in the output |
| `not_contains` | `substring` | substring is absent from the output |
| `regex` | `pattern` | pattern matches somewhere in the output |
| `python_predicate` | `expression` | a boolean Python expression, with `output` bound to the text (see Security below) |

## Design notes

**The judge is injected, not hardcoded** — the same pattern as [depfix](https://github.com/)'s package-registry abstraction. `LlmJudge` is a `Protocol`; `AnthropicJudge` is the real implementation (plain `urllib`, asks the model to return `{"score", "confidence", "rationale"}` as JSON); `ScriptedJudge` is a test fake that returns pre-scripted results per prompt. This is what makes the confidence-gating and score-blending logic — the actual interesting part of this project — fully unit-testable with zero network access and zero API cost.

**`python_predicate` uses a restricted `eval`, not a real sandbox.** `__builtins__` is emptied and replaced with a short allow-list of pure functions (`len`, `any`, `all`, `str`, `sorted`, etc.), and any expression containing `__` is rejected outright as a defense-in-depth measure against the classic dunder-based sandbox-escape tricks (`().__class__.__bases__`, etc.). This is a lightweight guard, not a hardened sandbox — see Limitations.

## Testing

```bash
python -m unittest discover tests -v
```

35 tests, covering:

- **`test_deterministic.py`** — each check kind, plus explicit tests that the sandbox-escape guard and the empty-builtins restriction both independently block an attempted escape (`().__class__.__bases__` and `open(...)` respectively), and that a malformed expression fails the check cleanly instead of crashing.
- **`test_rubric.py`** — validation (zero weight, missing `kind`, invalid thresholds) and JSON loading with defaults.
- **`test_evaluator.py`** — the two policies described above, in isolation: a failing deterministic criterion overriding a perfect LLM score; a low-confidence judge result being excluded from the weighted average rather than blended in; the "all criteria uncertain → no score at all" edge case.
- **`test_cli.py`** — the real CLI entry point end-to-end against actual files on disk, including `--no-llm-judge`, exit codes, and the "no API key, no `--no-llm-judge` flag" error path.

Also manually smoke-tested against real files with the actual CLI (see the example output above) — a good response correctly passes all three criteria, and a bad response correctly fails on both the hard gate and the regex check while still evaluating the length check independently.

## Limitations

- `python_predicate`'s restricted `eval` is a lightweight guard (empty builtins + a dunder ban), not a hardened sandbox. Treat rubric files as trusted input — the same way you'd treat a CI config — not as arbitrary untrusted user input.
- Parameter/criterion-to-endpoint association isn't a concern here (unlike some of my other projects) since a rubric criterion's check is fully self-contained; there's no cross-criterion validation.
- `AnthropicJudge` asks the model to self-report a confidence score in the same response as the grade itself. A model's stated confidence is not a calibrated probability — it's a reasonable, cheap first-pass signal, not a substitute for actually validating judge calibration against held-out labeled data if this were used for anything higher-stakes.
- No retry/backoff logic on the Anthropic API call — a transient network error surfaces directly rather than being retried.

## License

MIT — see [LICENSE](LICENSE).
