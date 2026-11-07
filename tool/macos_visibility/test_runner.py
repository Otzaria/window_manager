import copy
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import run as runner


def ready_startup():
    state = {"activationPolicy": 0, "mainEventLoopRunning": True,
             "mainThread": True, "screens": 1}
    return {"ready": True, "requestedActivationPolicy": 0,
            "setActivationPolicyReturned": False, "didFinishLaunchingObserved": True,
            "beforePolicy": {"activationPolicy": 0},
            "afterPolicy": {"activationPolicy": 0},
            "afterFinishLaunching": {"activationPolicy": 0}, "beforeCase": state}


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.receipt = {"status": "completed", "exitCode": 0, "pid": 42}
        self.report = {
            "schemaVersion": 1, "case": "show", "status": "passed", "stage": "show",
            "pid": 42,
            "startup": ready_startup(),
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

    def test_actual_policy_gates_readiness_independently_of_switch_return(self):
        for returned in (False, True):
            report = copy.deepcopy(self.report)
            report["startup"]["setActivationPolicyReturned"] = returned
            self.assertEqual(runner.validate_report(self.receipt, report, "show"), "passed")
            for phase in ("afterPolicy", "afterFinishLaunching", "beforeCase"):
                for policy in (1, 2, False):
                    with self.subTest(returned=returned, phase=phase, policy=policy):
                        wrong = copy.deepcopy(report)
                        wrong["startup"][phase]["activationPolicy"] = policy
                        with self.assertRaisesRegex(ValueError, "not regular"):
                            runner.validate_report(self.receipt, wrong, "show")

    def test_startup_flag_cannot_replace_launch_loop_screen_or_observed_policy(self):
        for changes in ({"ready": False}, {"ready": 1}, {"requestedActivationPolicy": False},
                        {"setActivationPolicyReturned": None}, {"setActivationPolicyReturned": 0},
                        {"didFinishLaunchingObserved": False}, {"beforePolicy": None},
                        {"beforePolicy": {"activationPolicy": True}}, {"afterPolicy": None}):
            report = copy.deepcopy(self.report)
            report["startup"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                runner.validate_report(self.receipt, report, "show")
        for changes in ({"mainEventLoopRunning": False}, {"mainThread": False},
                        {"screens": 0}, {"screens": True}):
            report = copy.deepcopy(self.report)
            report["startup"]["beforeCase"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                runner.validate_report(self.receipt, report, "show")
        for startup in (None, [], {}):
            with self.assertRaises(ValueError):
                runner.validate_report(self.receipt, {**self.report, "startup": startup}, "show")

    def test_setup_failure_preserves_reason_and_never_satisfies_baseline_control(self):
        report = {**self.report, "status": "failed", "stage": "startup",
                  "errorCode": "activationPolicy", "error": "Actual policy is prohibited",
                  "nativeWindowExecution": False, "startup": {"ready": False}}
        receipt = {**self.receipt, "exitCode": 65}
        for negative in (False, True):
            with self.assertRaisesRegex(ValueError, "Native startup failed: activationPolicy: Actual policy is prohibited"):
                runner.validate_report(receipt, report, "show", negative)
        with self.assertRaisesRegex(ValueError, "PID does not match"):
            runner.validate_report(receipt, {**report, "pid": 43}, "show", True)


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


class CaseResultTest(unittest.TestCase):
    def make_child(self, output, body):
        child = output / "controlled-child"
        child.write_text(f"#!{sys.executable}\n" + body + "\n")
        child.chmod(0o700)
        return child

    def startup_child(self, output):
        return self.make_child(output, """
import json, os, sys
print(json.dumps({'schemaVersion': 1, 'case': sys.argv[1], 'pid': os.getpid(),
    'status': 'failed', 'stage': 'startup', 'errorCode': 'activationPolicy',
    'error': 'Actual policy is prohibited', 'nativeWindowExecution': False,
    'performanceAcceptance': False, 'startup': {'ready': False}}))
sys.exit(65)
""")

    def test_empty_exit65_retains_exit_and_raw_streams_without_json_decode_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            child = self.make_child(output, "import sys; print('setup stderr', file=sys.stderr); sys.exit(65)")
            with self.assertRaises(runner.NativeCaseFailure) as caught:
                runner.run_case(child, output, "show")
            result = json.loads((output / "case-show.result.json").read_text())
            self.assertEqual(result, caught.exception.result)
            self.assertEqual(result["exitCode"], 65)
            self.assertEqual(result["commandStatus"], "completed")
            self.assertEqual(result["reportBytes"], 0)
            self.assertTrue(result["commandReceipt"]["groupDrained"])
            self.assertIn("no JSON report", result["error"])
            self.assertIn("exit=65", str(caught.exception))
            self.assertNotIn("JSONDecodeError", result["error"])
            self.assertEqual((output / "case-show.stdout.log").read_bytes(), b"")
            self.assertEqual((output / "case-show.stderr.log").read_text(), "setup stderr\n")

    def test_structured_startup_failure_is_preserved_and_not_an_expected_failure(self):
        for negative in (False, True):
            with self.subTest(negative=negative), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                with self.assertRaises(runner.NativeCaseFailure) as caught:
                    runner.run_case(self.startup_child(output), output, "show", negative)
                result = caught.exception.result
                self.assertEqual(result["verdict"], "failed")
                self.assertEqual(result["exitCode"], 65)
                self.assertEqual(result["reportedErrorCode"], "activationPolicy")
                self.assertEqual(result["reportedError"], "Actual policy is prohibited")
                self.assertFalse(result["reportedNativeWindowExecution"])
                raw = json.loads((output / "case-show.stdout.log").read_text())
                self.assertEqual(raw["pid"], result["commandReceipt"]["pid"])
                self.assertEqual(json.loads((output / "case-show.result.json").read_text()), result)

    def test_invalid_utf8_or_json_and_oversized_report_keep_exact_exit(self):
        for payload, reason in ((b"{ incomplete", "invalid JSON"), (b"\xff", "invalid JSON"),
                                (b"x" * (1024 * 1024 + 1), "exceeds its bound")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                data = output / "payload"
                data.write_bytes(payload)
                child = self.make_child(output, "import pathlib,sys; sys.stdout.buffer.write(pathlib.Path(__file__).with_name('payload').read_bytes())")
                with self.assertRaises(runner.NativeCaseFailure) as caught:
                    runner.run_case(child, output, "show")
                self.assertEqual(caught.exception.result["exitCode"], 0)
                self.assertIn(reason, caught.exception.result["error"])
                self.assertEqual((output / "case-show.stdout.log").read_bytes(), payload)

    def test_later_result_write_failure_cannot_replace_startup_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            child = self.startup_child(output)
            original_write = Path.write_text

            def fail_only_result(path, *args, **kwargs):
                if path.name == "case-show.result.json":
                    raise PermissionError("controlled result write failure")
                return original_write(path, *args, **kwargs)

            with patch.object(Path, "write_text", fail_only_result):
                with self.assertRaises(runner.NativeCaseFailure) as caught:
                    runner.run_case(child, output, "show")
            result = caught.exception.result
            self.assertIn("activationPolicy: Actual policy is prohibited", result["error"])
            self.assertIn("controlled result write failure", result["diagnosticWriteError"])
            self.assertEqual(result["exitCode"], 65)
            self.assertEqual(result["reportedErrorCode"], "activationPolicy")
            self.assertTrue((output / "case-show.command.json").exists())
            self.assertTrue((output / "case-show.stdout.log").read_bytes())

    def test_failed_process_creation_preserves_command_error_in_case_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaises(runner.NativeCaseFailure) as caught:
                runner.run_case(output / "absent", output, "show")
            result = caught.exception.result
            self.assertEqual(result["commandStatus"], "failed")
            self.assertIn("FileNotFoundError", result["error"])
            self.assertIsNone(result["exitCode"])
            self.assertEqual(json.loads((output / "case-show.result.json").read_text()), result)

    def test_valid_owned_case_report_passes_with_false_switch_return(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = {"schemaVersion": 1, "case": "show", "status": "passed", "stage": "show",
                      "nativeWindowExecution": True, "performanceAcceptance": False,
                      "startup": ready_startup(), "completedStages": ["show"],
                      "target": {"visible": True}, "events": [
                          {"event": "show", "owner": "target", "visible": True, "mainThread": True}]}
            child = self.make_child(output, f"import json,os\nreport = {report!r}\nreport['pid'] = os.getpid()\nprint(json.dumps(report))")
            result = runner.run_case(child, output, "show")
            self.assertEqual(result["verdict"], "passed")
            self.assertEqual(result["exitCode"], 0)
            self.assertTrue(result["commandReceipt"]["groupDrained"])
            self.assertEqual(json.loads((output / "case-show.result.json").read_text()), result)


class SummaryTest(unittest.TestCase):
    def test_main_summary_retains_failed_case_and_cannot_claim_native_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "flutter"
            framework = sdk / "bin/cache/artifacts/engine/darwin-x64/FlutterMacOS.xcframework/macos-controlled/FlutterMacOS.framework"
            framework.mkdir(parents=True)
            (framework / "FlutterMacOS").write_bytes(b"controlled framework fixture")
            (sdk / "bin/internal").mkdir()
            (sdk / "bin/internal/engine.version").write_text("controlled-engine\n")
            output = root / "evidence"
            failure = {"case": "show", "verdict": "failed", "commandStatus": "completed",
                       "exitCode": 65, "error": "ValueError: Native startup failed: activationPolicy",
                       "reportedNativeWindowExecution": False}
            with patch.object(sys, "argv", ["run.py", "--output", str(output), "--flutter-root", str(sdk)]), \
                    patch.object(runner.platform, "system", return_value="Darwin"), \
                    patch.object(runner.subprocess, "check_output", return_value="controlled-source\n"), \
                    patch.object(runner, "execute", return_value={"status": "completed", "exitCode": 0}), \
                    patch.object(runner, "compile_probe", return_value=root / "controlled-probe"), \
                    patch.object(runner, "run_case", side_effect=runner.NativeCaseFailure(failure)):
                with self.assertRaises(runner.NativeCaseFailure):
                    runner.main()
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["failedCase"], failure)
            self.assertFalse(summary["nativeWindowExecution"])
            self.assertFalse(summary["performanceAcceptance"])
            self.assertEqual(summary["cases"], {"candidate": []})


class DiagnosticFailureTest(unittest.TestCase):
    # These fixtures exercise the real owned subprocess and reporting paths on
    # any platform. The SDK/compiler metadata fixture does not execute AppKit.
    make_child = CaseResultTest.make_child
    startup_child = CaseResultTest.startup_child

    @contextlib.contextmanager
    def main_fixture(self, root, child):
        sdk = root / "flutter"
        framework = sdk / "bin/cache/artifacts/engine/darwin-x64/FlutterMacOS.xcframework/macos-controlled/FlutterMacOS.framework"
        framework.mkdir(parents=True)
        (framework / "FlutterMacOS").write_bytes(b"portable metadata fixture")
        (sdk / "bin/internal").mkdir()
        (sdk / "bin/internal/engine.version").write_text("controlled-engine\n")
        output = root / "output"
        original_execute = runner.execute

        def execute(command, directory, label, timeout):
            if label in ("swift-version", "xcode-version"):
                return {"status": "completed", "exitCode": 0}
            return original_execute(command, directory, label, timeout)

        def metadata(*args, **kwargs):
            return "controlled-source\n" if kwargs.get("text") else b"controlled-source\n"

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["run.py", "--output", str(output), "--flutter-root", str(sdk)]))
            stack.enter_context(patch.object(runner.platform, "system", return_value="Darwin"))
            stack.enter_context(patch.object(runner.subprocess, "check_output", side_effect=metadata))
            stack.enter_context(patch.object(runner, "compile_probe", return_value=child))
            stack.enter_context(patch.object(runner, "execute", side_effect=execute))
            yield output

    @contextlib.contextmanager
    def reporting_faults(self, modes):
        original_write = Path.write_text
        original_dumps = json.dumps
        observed = []
        names = {"case-show.command.json": "commandReceipt",
                 "case-show.result.json": "caseResult", "summary.json": "summary"}

        def write(path, *args, **kwargs):
            stage = names.get(path.name)
            if stage in modes and modes[stage] == "write":
                observed.append((stage, "write"))
                raise PermissionError(f"controlled {stage} write failure")
            return original_write(path, *args, **kwargs)

        def dumps(value, *args, **kwargs):
            stage = None
            if isinstance(value, dict):
                if "command" in value and "timeoutSeconds" in value:
                    stage = "commandReceipt"
                elif "case" in value and "verdict" in value:
                    stage = "caseResult"
                elif "baseline" in value and "cases" in value:
                    stage = "summary"
            if stage in modes and modes[stage] == "serialize":
                observed.append((stage, "serialize"))
                raise TypeError(f"controlled {stage} serialization failure")
            return original_dumps(value, *args, **kwargs)

        with patch.object(Path, "write_text", write), patch.object(json, "dumps", dumps):
            yield observed

    def test_all_reporting_layers_preserve_native_failure_and_ordered_errors(self):
        stages = ("commandReceipt", "caseResult", "summary")
        for modes in (dict.fromkeys(stages, "write"), dict.fromkeys(stages, "serialize"),
                      dict(zip(stages, ("serialize", "write", "serialize")))):
            with self.subTest(modes=modes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                child = self.startup_child(root)
                with self.main_fixture(root, child) as output, self.reporting_faults(modes) as faults:
                    with self.assertRaises(runner.NativeCaseFailure) as caught:
                        runner.main()
                error = caught.exception
                result = error.result
                receipt = result["commandReceipt"]
                self.assertEqual(result["exitCode"], 65)
                self.assertEqual(result["reportedErrorCode"], "activationPolicy")
                self.assertIn("Native startup failed: activationPolicy", str(error.__cause__))
                self.assertEqual(result["verdict"], "failed")
                self.assertTrue(receipt["started"])
                self.assertTrue(receipt["cleanupAttempted"])
                self.assertTrue(receipt["groupDrained"])
                self.assertEqual(receipt["processExitAfterCleanup"], 65)
                self.assertFalse(runner.group_alive(receipt["pid"]))
                self.assertIs(error.summary["failedCase"], result)
                self.assertIs(error.summary["diagnosticErrors"], result["diagnosticErrors"])
                self.assertEqual(error.summary["status"], "failed")
                self.assertFalse(error.summary["nativeWindowExecution"])
                expected = [(stage, modes[stage]) for stage in stages]
                self.assertEqual(faults, expected)
                self.assertEqual([(item["stage"], item["operation"]) for item in error.diagnosticErrors], expected)
                report = json.loads((output / "candidate/case-show.stdout.log").read_text())
                self.assertEqual(report["pid"], receipt["pid"])
                self.assertFalse((output / "summary.json").exists())
                self.assertFalse((output / "candidate/case-show.command.json").exists())
                self.assertFalse((output / "candidate/case-show.result.json").exists())

    def test_all_reporting_failures_preserve_missing_process_without_inventing_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modes = dict.fromkeys(("commandReceipt", "caseResult", "summary"), "write")
            with self.main_fixture(root, root / "absent") as output, self.reporting_faults(modes):
                with self.assertRaises(runner.NativeCaseFailure) as caught:
                    runner.main()
            error = caught.exception
            receipt = error.result["commandReceipt"]
            self.assertIsInstance(error.__cause__, FileNotFoundError)
            self.assertIn("FileNotFoundError", error.result["error"])
            self.assertIs(error.__cause__.commandReceipt, receipt)
            self.assertFalse(receipt["started"])
            self.assertFalse(receipt["cleanupAttempted"])
            self.assertNotIn("pid", receipt)
            self.assertIsNone(error.result["exitCode"])
            self.assertEqual(error.result["commandStatus"], "failed")
            self.assertEqual([item["stage"] for item in error.diagnosticErrors], list(modes))
            self.assertEqual((output / "candidate/case-show.stdout.log").read_bytes(), b"")

    def test_execute_preserves_exact_start_exception_when_receipt_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            original_popen = runner.subprocess.Popen
            start_errors = []

            def popen(*args, **kwargs):
                try:
                    return original_popen(*args, **kwargs)
                except FileNotFoundError as error:
                    start_errors.append(error)
                    raise

            with patch.object(runner.subprocess, "Popen", side_effect=popen), \
                    self.reporting_faults({"commandReceipt": "write"}):
                with self.assertRaises(FileNotFoundError) as caught:
                    runner.execute([str(output / "absent")], output, "case-show", 1)
            self.assertIs(caught.exception, start_errors[0])
            receipt = caught.exception.commandReceipt
            self.assertEqual(receipt["status"], "failed")
            self.assertFalse(receipt["started"])
            self.assertFalse(receipt["cleanupAttempted"])
            self.assertEqual(caught.exception.diagnosticErrors[0]["stage"], "commandReceipt")

    def test_output_open_failure_never_launches_or_claims_cleanup_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            original_open = Path.open
            first_error = PermissionError("controlled stdout open failure")

            def open_stream(path, *args, **kwargs):
                if path.name == "case-show.stdout.log":
                    raise first_error
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", open_stream), \
                    patch.object(runner.subprocess, "Popen") as popen, \
                    patch.object(runner, "drain_group") as drain, \
                    self.reporting_faults({"commandReceipt": "write"}):
                with self.assertRaises(PermissionError) as caught:
                    runner.execute([sys.executable, "-c", "raise SystemExit(0)"], output, "case-show", 1)
            self.assertIs(caught.exception, first_error)
            popen.assert_not_called()
            drain.assert_not_called()
            receipt = first_error.commandReceipt
            self.assertFalse(receipt["started"])
            self.assertFalse(receipt["cleanupAttempted"])
            self.assertNotIn("pid", receipt)
            self.assertEqual(receipt["error"], "PermissionError: controlled stdout open failure")

    def test_receipt_failure_happens_after_successful_child_is_recorded_and_drained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            original_write = Path.write_text
            observed = []

            def write(path, text, *args, **kwargs):
                if path.name == "case-show.command.json":
                    stored = json.loads(text)
                    observed.append(stored)
                    self.assertTrue(stored["started"])
                    self.assertEqual(stored["exitCode"], 0)
                    self.assertTrue(stored["groupDrained"])
                    self.assertFalse(runner.group_alive(stored["pid"]))
                    raise PermissionError("controlled post-cleanup write failure")
                return original_write(path, text, *args, **kwargs)

            with patch.object(Path, "write_text", write):
                receipt = runner.execute([sys.executable, "-c", "print('finished')"], output, "case-show", 1)
            self.assertEqual(len(observed), 1)
            self.assertEqual(receipt["exitCode"], 0)
            self.assertEqual(receipt["pid"], observed[0]["pid"])
            self.assertEqual(receipt["diagnosticErrors"][0]["operation"], "write")
            with self.assertRaises(runner.CommandFailure) as caught:
                runner.require_successful_command(receipt, "controlled command")
            self.assertIs(caught.exception.commandReceipt, receipt)

    def test_valid_native_result_cannot_pass_without_command_or_case_evidence(self):
        for stage in ("commandReceipt", "caseResult"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                report = {"schemaVersion": 1, "case": "show", "status": "passed", "stage": "show",
                          "nativeWindowExecution": True, "performanceAcceptance": False,
                          "startup": ready_startup(), "completedStages": ["show"],
                          "target": {"visible": True}, "events": []}
                child = self.make_child(output, f"import json,os\nreport = {report!r}\nreport['pid'] = os.getpid()\nprint(json.dumps(report))")
                with self.reporting_faults({stage: "write"}) as faults:
                    with self.assertRaises(runner.NativeCaseFailure) as caught:
                        runner.run_case(child, output, "show")
                result = caught.exception.result
                self.assertEqual(result["verdict"], "failed")
                self.assertEqual(result["reportedStatus"], "passed")
                self.assertEqual(result["exitCode"], 0)
                self.assertTrue(result["commandReceipt"]["groupDrained"])
                self.assertFalse(runner.group_alive(result["commandReceipt"]["pid"]))
                self.assertEqual(faults, [(stage, "write")])
                self.assertEqual([item["stage"] for item in result["diagnosticErrors"]], [stage])

    def test_compiler_success_cannot_hide_receipt_failure(self):
        receipt = {"status": "completed", "exitCode": 0,
                   "diagnosticErrors": [{"stage": "commandReceipt", "operation": "write",
                                         "type": "PermissionError", "message": "controlled compiler receipt", "path": "compile.command.json"}]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(runner, "execute", return_value=receipt):
                with self.assertRaises(runner.CommandFailure) as caught:
                    runner.compile_probe(output / "source.swift", output, output / "FlutterMacOS.framework")
            self.assertIs(caught.exception.commandReceipt, receipt)

    def test_toolchain_failure_stays_primary_when_summary_serialization_fails(self):
        receipt = {"status": "completed", "exitCode": 37,
                   "diagnosticErrors": [{"stage": "commandReceipt", "operation": "write",
                                         "type": "PermissionError", "message": "controlled toolchain receipt", "path": "swift-version.command.json"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.main_fixture(root, root / "unused"), \
                    patch.object(runner, "execute", return_value=receipt), \
                    self.reporting_faults({"summary": "serialize"}):
                with self.assertRaises(runner.CommandFailure) as caught:
                    runner.main()
            error = caught.exception
            self.assertIs(error.commandReceipt, receipt)
            self.assertIn("Could not record the native toolchain", str(error))
            self.assertEqual(error.summary["status"], "failed")
            self.assertFalse(error.summary["nativeWindowExecution"])
            self.assertEqual([item["stage"] for item in error.diagnosticErrors], ["commandReceipt", "summary"])

    def test_checkpoint_or_final_summary_failure_never_returns_success(self):
        for phase in ("checkpoint", "final"):
            for operation in ("write", "serialize"):
                with self.subTest(phase=phase, operation=operation), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    calls = []
                    faults = []
                    original_write, original_dumps = Path.write_text, json.dumps

                    def case(executable, output, name, negative=False):
                        calls.append((output.name, name, negative))
                        return {"case": name, "verdict": "expectedFailure" if negative else "passed"}

                    def selected(value):
                        return (isinstance(value, dict) and "baseline" in value and
                                (value["status"] == "passed" if phase == "final" else value["status"] == "running"))

                    def write(path, text, *args, **kwargs):
                        if operation == "write" and path.name == "summary.json" and selected(json.loads(text)):
                            faults.append(operation)
                            raise PermissionError("controlled summary persistence failure")
                        return original_write(path, text, *args, **kwargs)

                    def dumps(value, *args, **kwargs):
                        if operation == "serialize" and selected(value):
                            faults.append(operation)
                            raise TypeError("controlled summary serialization failure")
                        return original_dumps(value, *args, **kwargs)

                    with self.main_fixture(root, root / "unused") as output, \
                            patch.object(runner, "run_case", side_effect=case), \
                            patch.object(Path, "write_text", write), patch.object(json, "dumps", dumps):
                        with self.assertRaises(PermissionError if operation == "write" else TypeError) as caught:
                            runner.main()
                    self.assertEqual(faults, [operation])
                    self.assertEqual(caught.exception.summary["status"], "failed")
                    self.assertEqual(caught.exception.diagnosticErrors[0]["stage"], "summary")
                    self.assertEqual(len(calls), 13 if phase == "final" else 1)
                    if phase == "final":
                        expected = [("candidate", case, False) for case in runner.CASES]
                        expected += [("baseline", case, case in ("show", "hide"))
                                     for case in ("show", "hide", "noop", "refusal", "focus-minimize")]
                        self.assertEqual(calls, expected)
                        self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "running")


if __name__ == "__main__":
    unittest.main()
