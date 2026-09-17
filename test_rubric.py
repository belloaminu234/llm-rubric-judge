import unittest

from rubricjudge.rubric import Rubric, RubricCriterion, load_rubric


class TestRubricCriterion(unittest.TestCase):
    def test_zero_weight_rejected(self):
        with self.assertRaises(ValueError):
            RubricCriterion("x", 0.0, {"kind": "contains", "substring": "a"})

    def test_missing_kind_rejected(self):
        with self.assertRaises(ValueError):
            RubricCriterion("x", 1.0, {"substring": "a"})


class TestRubric(unittest.TestCase):
    def test_empty_criteria_rejected(self):
        with self.assertRaises(ValueError):
            Rubric(criteria=())

    def test_invalid_confidence_threshold_rejected(self):
        crit = RubricCriterion("x", 1.0, {"kind": "contains", "substring": "a"})
        with self.assertRaises(ValueError):
            Rubric(criteria=(crit,), confidence_threshold=1.5)


class TestLoadRubric(unittest.TestCase):
    def test_loads_from_json(self):
        json_text = """
        {
            "confidence_threshold": 0.8,
            "pass_threshold": 0.75,
            "criteria": [
                {"name": "no TODOs", "weight": 1.0, "check": {"kind": "not_contains", "substring": "TODO"}},
                {"name": "polite", "weight": 2.0, "check": {"kind": "llm_judge", "prompt": "Is it polite?"}}
            ]
        }
        """
        rubric = load_rubric(json_text)
        self.assertEqual(len(rubric.criteria), 2)
        self.assertEqual(rubric.confidence_threshold, 0.8)
        self.assertEqual(rubric.pass_threshold, 0.75)
        self.assertEqual(rubric.criteria[0].name, "no TODOs")

    def test_defaults_applied_when_omitted(self):
        json_text = """
        {"criteria": [{"name": "x", "check": {"kind": "contains", "substring": "a"}}]}
        """
        rubric = load_rubric(json_text)
        self.assertEqual(rubric.confidence_threshold, 0.7)
        self.assertEqual(rubric.pass_threshold, 0.7)
        self.assertEqual(rubric.criteria[0].weight, 1.0)  # default weight


if __name__ == "__main__":
    unittest.main()
