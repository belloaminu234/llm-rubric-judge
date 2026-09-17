"""End-to-end tests: writes real rubric.json and output files to a temp
directory and runs the actual CLI entry point against them, using
--no-llm-judge so no real Anthropic API call is needed."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from rubricjudge import cli

DETERMINISTIC_RUBRIC = """
{
    "criteria": [
        {"name": "no TODOs", "weight": 1.0, "check": {"kind": "not_contains", "substring": "TODO"}},
        {"name": "has greeting", "weight": 1.0, "check": {"kind": "regex", "pattern": "^(Hi|Hello)"}}
    ]
}
"""

MIXED_RUBRIC = """
{
    "criteria": [
        {"name": "no TODOs", "weight": 1.0, "check": {"kind": "not_contains", "substring": "TODO"}},
        {"name": "polite", "weight": 1.0, "check": {"kind": "llm_judge", "prompt": "Is it polite?"}}
    ]
}
"""


class TestCliEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _run(self, rubric_text: str, output_text: str, extra_args: list[str] | None = None):
        rubric_path = Path(self.tmp.name) / "rubric.json"
        output_path = Path(self.tmp.name) / "output.txt"
        rubric_path.write_text(rubric_text)
        output_path.write_text(output_text)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = cli.main(
                ["--rubric", str(rubric_path), "--output", str(output_path)] + (extra_args or [])
            )
        return exit_code, buf.getvalue()

    def test_deterministic_only_rubric_passes(self):
        exit_code, output = self._run(DETERMINISTIC_RUBRIC, "Hello, everything is done.")
        self.assertEqual(exit_code, 0)
        self.assertIn("PASS", output)

    def test_deterministic_only_rubric_fails(self):
        exit_code, output = self._run(DETERMINISTIC_RUBRIC, "Hello, TODO: finish this")
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL", output)

    def test_no_llm_judge_flag_skips_llm_criteria(self):
        exit_code, output = self._run(
            MIXED_RUBRIC, "all done, no todos here", extra_args=["--no-llm-judge"]
        )
        self.assertEqual(exit_code, 0)
        # The deterministic criterion alone should have run and passed.
        self.assertIn("no TODOs", output)

    def test_mixed_rubric_without_no_llm_judge_flag_and_no_api_key_fails_cleanly(self):
        import os
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            exit_code, _ = self._run(MIXED_RUBRIC, "all done")
            self.assertEqual(exit_code, 1)
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_missing_rubric_file_returns_nonzero(self):
        output_path = Path(self.tmp.name) / "output.txt"
        output_path.write_text("hello")
        exit_code = cli.main(["--rubric", "/nonexistent/rubric.json", "--output", str(output_path)])
        self.assertNotEqual(exit_code, 0)

    def test_missing_output_file_returns_nonzero(self):
        rubric_path = Path(self.tmp.name) / "rubric.json"
        rubric_path.write_text(DETERMINISTIC_RUBRIC)
        exit_code = cli.main(["--rubric", str(rubric_path), "--output", "/nonexistent/output.txt"])
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
