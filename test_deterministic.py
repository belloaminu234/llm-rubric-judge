import unittest

from rubricjudge.deterministic import UnsafeExpressionError, run_deterministic_check


class TestContains(unittest.TestCase):
    def test_passes_when_substring_present(self):
        result = run_deterministic_check({"kind": "contains", "substring": "hello"}, "hello world")
        self.assertTrue(result.passed)

    def test_fails_when_substring_absent(self):
        result = run_deterministic_check({"kind": "contains", "substring": "xyz"}, "hello world")
        self.assertFalse(result.passed)


class TestNotContains(unittest.TestCase):
    def test_passes_when_substring_absent(self):
        result = run_deterministic_check({"kind": "not_contains", "substring": "TODO"}, "done")
        self.assertTrue(result.passed)

    def test_fails_when_substring_present(self):
        result = run_deterministic_check({"kind": "not_contains", "substring": "TODO"}, "TODO: fix")
        self.assertFalse(result.passed)


class TestRegex(unittest.TestCase):
    def test_passes_on_match(self):
        result = run_deterministic_check({"kind": "regex", "pattern": r"\d{3}-\d{4}"}, "call 555-1234")
        self.assertTrue(result.passed)

    def test_fails_on_no_match(self):
        result = run_deterministic_check({"kind": "regex", "pattern": r"\d{3}-\d{4}"}, "no numbers here")
        self.assertFalse(result.passed)


class TestPythonPredicate(unittest.TestCase):
    def test_simple_length_check(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "len(output) > 5"}, "hello world"
        )
        self.assertTrue(result.passed)

    def test_falsy_expression_fails(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "len(output) > 500"}, "short"
        )
        self.assertFalse(result.passed)

    def test_dunder_expression_rejected_not_crashed(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "().__class__.__bases__"}, "x"
        )
        self.assertFalse(result.passed)
        self.assertIn("rejected", result.detail)

    def test_builtins_unavailable(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "open('/etc/passwd')"}, "x"
        )
        self.assertFalse(result.passed)
        self.assertIn("NameError", result.detail)

    def test_syntax_error_does_not_crash(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "this is not valid python"}, "x"
        )
        self.assertFalse(result.passed)

    def test_allowed_safe_functions_work(self):
        result = run_deterministic_check(
            {"kind": "python_predicate", "expression": "all(c.isalpha() or c==' ' for c in output)"},
            "hello world",
        )
        self.assertTrue(result.passed)


class TestUnknownKind(unittest.TestCase):
    def test_raises_value_error(self):
        with self.assertRaises(ValueError):
            run_deterministic_check({"kind": "not_a_real_kind"}, "x")


if __name__ == "__main__":
    unittest.main()
