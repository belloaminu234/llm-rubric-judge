"""rubricjudge: a framework for evaluating agent/model output against a
rubric that mixes deterministic code checks (hard gates) with
LLM-as-a-judge scoring (graded, confidence-aware). Standard library
only; the LLM judge itself is injected, so the core logic is fully
testable without any network access."""
