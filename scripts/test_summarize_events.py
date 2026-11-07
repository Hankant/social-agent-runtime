import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from summarize_events import summarize


def record(attempt="one", **overrides):
    return {"run_id": "fake", "attempt_id": attempt, "decision_key": "task-a",
            "start_s": 0, "end_s": 2, "status": "validated",
            "input_tokens": 100, "output_tokens": 20, **overrides}


class UsageTests(unittest.TestCase):
    def test_usage_unknown_cache_and_retry(self):
        records = [record("bad", status="format_error"),
                   record("ok", start_s=2, end_s=4),
                   record("unknown", status="unknown", input_tokens=None, output_tokens=None),
                   record("cache", status="cache_hit")]
        result = summarize(records)
        self.assertEqual(result["known_input_tokens"], 200)
        self.assertEqual(result["known_output_tokens"], 40)
        self.assertEqual(result["unknown_input_usage_attempts"], 1)
        self.assertEqual(result["unknown_outcome_records"], 1)
        self.assertEqual(result["new_validated_decisions"], 1)
        self.assertEqual(result["new_validated_decisions_per_minute"], 15)

    def test_duplicate_attempt_rejected_and_key_reuse_allowed(self):
        with self.assertRaises(ValueError):
            summarize([record(), copy.deepcopy(record())])
        result = summarize([record(), record("two")])
        self.assertEqual(result["new_validated_decisions"], 1)

    def test_invalid_data_and_empty(self):
        for changes in ({"end_s": -1}, {"start_s": float("nan")},
                        {"status": "made_up"}, {"input_tokens": -1},
                        {"output_tokens": True}):
            with self.assertRaises(ValueError):
                summarize([record(**changes)])
        self.assertIsNone(summarize([])["new_validated_decisions_per_minute"])

    def test_real_cli_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.jsonl"
            path.write_text(json.dumps(record())+"\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize_events.py")), str(path)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["known_input_tokens"], 100)


if __name__ == "__main__":
    unittest.main()
