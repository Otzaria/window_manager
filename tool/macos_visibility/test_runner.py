import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import run as runner


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.receipt = {"status": "completed", "exitCode": 0, "pid": 42}
        self.report = {
            "schemaVersion": 1, "case": "show", "status": "passed", "stage": "show",
            "pid": 42,
            "nativeWindowExecution": True, "performanceAcceptance": False,
            "completedStages": ["show"], "target": {"visible": True},
            "events": [{"event": "show", "owner": "target", "visible": True, "mainThread": True}],
        }

    def test_native_pass_requires_completed_command_and_matching_identity(self):
        self.assertEqual(runner.validate_report(self.receipt, self.report, "show"), "passed")
        for field, value in [("schemaVersion", 2), ("schemaVersion", True),
                             ("pid", 43), ("pid", True), ("case", "hide"), ("status", "failed"),
                             ("nativeWindowExecution", False), ("performanceAcceptance", True),
                             ("completedStages", []), ("events", None)]:
            with self.subTest(field=field):
                report = {**self.report, field: value}
                with self.assertRaises(ValueError):
                    runner.validate_report(self.receipt, report, "show")
        for receipt in ({**self.receipt, "status": "timeout"},
                        {**self.receipt, "exitCode": 37}):
            with self.assertRaises(ValueError):
                runner.validate_report(receipt, self.report, "show")

    def test_callback_requires_the_confirmed_native_state_and_main_thread(self):
        for changes in ({"visible": False}, {"mainThread": False}, {"event": "hide"}):
            report = copy.deepcopy(self.report)
            report["events"][0].update(changes)
            with self.assertRaises(ValueError):
                runner.validate_report(self.receipt, report, "show")

    def test_baseline_must_fail_for_missing_event_after_actual_transition(self):
        for case in ("show", "hide"):
            report = {**self.report, "case": case, "stage": case, "status": "failed",
                      "errorCode": "visibilityEvents", "target": {"visible": case == "show"},
                      "events": [], "completedStages": [] if case == "show" else ["visible setup"]}
            receipt = {"status": "completed", "exitCode": 1, "pid": 42}
            self.assertEqual(runner.validate_report(receipt, report, case, True), "expectedFailure")
            for changes in ({"status": "passed"}, {"errorCode": "timeout"}, {"stage": "setup"},
                            {"target": {"visible": case != "show"}},
                            {"events": self.report["events"]}):
                with self.subTest(case=case, changes=changes), self.assertRaises(ValueError):
                    runner.validate_report(receipt, {**report, **changes}, case, True)
            with self.assertRaises(ValueError):
                runner.validate_report({**receipt, "exitCode": 65}, report, case, True)

    def test_unknown_baseline_case_and_timeouts_cannot_count_as_expected_failure(self):
        report = {**self.report, "case": "refusal", "status": "failed", "stage": "refusal",
                  "errorCode": "visibilityEvents", "events": []}
        with self.assertRaises(ValueError):
            runner.validate_report({**self.receipt, "exitCode": 1}, report, "refusal", True)
        with self.assertRaises(ValueError):
            runner.validate_report({**self.receipt, "status": "timeout", "exitCode": 1}, report, "refusal", True)


class ProcessTest(unittest.TestCase):
    def test_nonzero_exit_and_both_streams_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = runner.execute(
                [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(37)"],
                output, "child", 5)
            self.assertEqual(receipt["exitCode"], 37)
            self.assertEqual(receipt["status"], "completed")
            self.assertTrue(receipt["groupDrained"])
            self.assertEqual((output / "child.stdout.log").read_text(), "out\n")
            self.assertEqual((output / "child.stderr.log").read_text(), "err\n")
            self.assertEqual(json.loads((output / "child.command.json").read_text()), receipt)

    def test_timeout_is_not_an_expected_test_failure_and_owned_group_is_drained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = runner.execute([sys.executable, "-c", "import time; time.sleep(30)"],
                                     output, "timed", 0.1)
            self.assertEqual(receipt["status"], "timeout")
            self.assertIsNone(receipt["exitCode"])
            self.assertTrue(receipt["groupDrained"])
            self.assertFalse(runner.group_alive(receipt["pid"]))

    def test_start_failure_keeps_command_receipt_and_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaises(FileNotFoundError):
                runner.execute([str(output / "does-not-exist")], output, "missing", 1)
            receipt = json.loads((output / "missing.command.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("FileNotFoundError", receipt["error"])


if __name__ == "__main__":
    unittest.main()
