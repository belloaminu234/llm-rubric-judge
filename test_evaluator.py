import unittest

from rubricjudge.evaluator import evaluate
from rubricjudge.judge import JudgeResult, ScriptedJudge
from rubricjudge.rubric import Rubric, RubricCriterion


def deterministic_rubric(**kwargs):
    crit = RubricCriterion("no TODOs", 1.0, {"kind": "not_contains", "substring": "TODO"})
    return Rubric(criteria=(crit,), **kwargs)


class TestDeterministicOnly(unittest.TestCase):
    def test_pass(self):
        result = evaluate(deterministic_rubric(), "all done", judge=None)
        self.assertEqual(result.overall_status, "pass")
        self.assertEqual(result.overall_score, 1.0)
        self.assertFalse(result.needs_review)

    def test_fail(self):
        result = evaluate(deterministic_rubric(), "TODO: finish this", judge=None)
        self.assertEqual(result.overall_status, "fail")


class TestDeterministicGateOverridesLlmJudge(unittest.TestCase):
    def test_deterministic_failure_fails_overall_even_with_perfect_llm_score(self):
        rubric = Rubric(criteria=(
            RubricCriterion("no TODOs", 1.0, {"kind": "not_contains", "substring": "TODO"}),
            RubricCriterion("polite", 5.0, {"kind": "llm_judge", "prompt": "polite?"}),
        ))
        judge = ScriptedJudge(default=JudgeResult(score=1.0, confidence=1.0, rationale="perfect"))
        result = evaluate(rubric, "TODO: fix this politely", judge)
        self.assertEqual(result.overall_status, "fail")

    def test_deterministic_pass_lets_llm_score_decide(self):
        rubric = Rubric(criteria=(
            RubricCriterion("no TODOs", 1.0, {"kind": "not_contains", "substring": "TODO"}),
            RubricCriterion("polite", 1.0, {"kind": "llm_judge", "prompt": "polite?"}),
        ))
        judge = ScriptedJudge(default=JudgeResult(score=0.9, confidence=0.9, rationale="polite"))
        result = evaluate(rubric, "all done, thank you", judge)
        self.assertEqual(result.overall_status, "pass")


class TestLlmJudgeScoring(unittest.TestCase):
    def test_weighted_average(self):
        rubric = Rubric(criteria=(
            RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"}),
            RubricCriterion("b", 3.0, {"kind": "llm_judge", "prompt": "b?"}),
        ))
        judge = ScriptedJudge({
            "a?": JudgeResult(score=0.0, confidence=1.0, rationale="bad"),
            "b?": JudgeResult(score=1.0, confidence=1.0, rationale="great"),
        })
        result = evaluate(rubric, "output", judge)
        # (1*0.0 + 3*1.0) / 4 = 0.75
        self.assertAlmostEqual(result.overall_score, 0.75)

    def test_score_below_pass_threshold_fails(self):
        crit = RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"})
        rubric = Rubric(criteria=(crit,), pass_threshold=0.8)
        judge = ScriptedJudge(default=JudgeResult(score=0.5, confidence=1.0, rationale="mediocre"))
        result = evaluate(rubric, "output", judge)
        self.assertEqual(result.overall_status, "fail")

    def test_missing_judge_for_llm_criterion_raises(self):
        crit = RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"})
        rubric = Rubric(criteria=(crit,))
        with self.assertRaises(ValueError):
            evaluate(rubric, "output", judge=None)


class TestConfidenceGating(unittest.TestCase):
    def test_low_confidence_marked_uncertain_and_excluded_from_score(self):
        rubric = Rubric(
            criteria=(
                RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"}),
                RubricCriterion("b", 1.0, {"kind": "llm_judge", "prompt": "b?"}),
            ),
            confidence_threshold=0.7,
        )
        judge = ScriptedJudge({
            "a?": JudgeResult(score=1.0, confidence=0.9, rationale="confident"),
            "b?": JudgeResult(score=0.0, confidence=0.2, rationale="unsure"),
        })
        result = evaluate(rubric, "output", judge)
        self.assertTrue(result.needs_review)
        # Only "a" is trusted -- its score of 1.0 alone determines overall_score,
        # NOT a blend that would drag it down toward "b"'s low score.
        self.assertEqual(result.overall_score, 1.0)

    def test_all_uncertain_gives_none_score(self):
        crit = RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"})
        rubric = Rubric(criteria=(crit,), confidence_threshold=0.7)
        judge = ScriptedJudge(default=JudgeResult(score=1.0, confidence=0.1, rationale="unsure"))
        result = evaluate(rubric, "output", judge)
        self.assertIsNone(result.overall_score)
        self.assertTrue(result.needs_review)
        self.assertEqual(result.overall_status, "fail")  # can't confirm a pass with nothing trusted

    def test_confidence_exactly_at_threshold_is_trusted(self):
        crit = RubricCriterion("a", 1.0, {"kind": "llm_judge", "prompt": "a?"})
        rubric = Rubric(criteria=(crit,), confidence_threshold=0.7, pass_threshold=0.5)
        judge = ScriptedJudge(default=JudgeResult(score=0.9, confidence=0.7, rationale="ok"))
        result = evaluate(rubric, "output", judge)
        self.assertFalse(result.needs_review)


if __name__ == "__main__":
    unittest.main()
