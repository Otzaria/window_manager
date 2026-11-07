import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("packages/window_manager/macos/window_manager/Sources/window_manager/WindowManager.swift")
BASELINE = "4f37655288ce8b803a9bd50294c5d6983850f622"
CASES = ("show", "hide", "rapid", "noop", "refusal", "independent", "focus-minimize", "panel")


class NativeCaseFailure(ValueError):
    def __init__(self, result):
        self.result = result
        self.diagnosticErrors = result.setdefault("diagnosticErrors", [])
        super().__init__(
            f"Native case {result['case']} failed "
            f"(command={result.get('commandStatus')}, exit={result.get('exitCode')}): "
            f"{result['error']}")


class CommandFailure(RuntimeError):
    def __init__(self, message, receipt):
        self.commandReceipt = receipt
        self.diagnosticErrors = list(receipt.get("diagnosticErrors", []))
        super().__init__(f"{message} (command={receipt.get('status')}, exit={receipt.get('exitCode')})")


def describe_error(error):
    return f"{type(error).__name__}: {error}"


def record_diagnostic_error(errors, stage, operation, path, error):
    errors.append({"stage": stage, "operation": operation, "path": str(path),
                   "type": type(error).__name__, "message": str(error)})


def save_json(path, value, errors, stage):
    """Return a persistence error without discarding the caller's in-memory result."""
    operation = "serialize"
    try:
        text = json.dumps(value, indent=2) + "\n"
        operation = "write"
        path.write_text(text)
    except Exception as error:
        record_diagnostic_error(errors, stage, operation, path, error)
        return error
    return None


def require_command_diagnostics(receipt):
    if receipt.get("diagnosticErrors"):
        raise CommandFailure("Command diagnostics could not be retained", receipt)


def require_successful_command(receipt, message):
    if receipt.get("status") != "completed" or receipt.get("exitCode") != 0:
        raise CommandFailure(message, receipt)
    require_command_diagnostics(receipt)


def note_diagnostic_errors(error, errors):
    # The exception and its attached results remain usable even if stderr fails.
    for item in errors:
        message = (f"Secondary diagnostic failure at {item['stage']} ({item['operation']}): "
                   f"{item['type']}: {item['message']}; path={item['path']}")
        try:
            if hasattr(error, "add_note"):
                error.add_note(message)
            else:
                print(message, file=sys.stderr)
        except Exception:
            pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def drain_group(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not group_alive(process.pid):
            break
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + 5
        while group_alive(process.pid) and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.01)
    process.wait(timeout=5)
    return not group_alive(process.pid)


def execute(command, output, label, timeout):
    stdout = output / f"{label}.stdout.log"
    stderr = output / f"{label}.stderr.log"
    started = time.monotonic()
    receipt = {"command": command, "timeoutSeconds": timeout, "status": "running",
               "exitCode": None, "started": False, "diagnosticErrors": []}
    process = None
    primary_error = None
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            receipt["started"] = True
            receipt["pid"] = process.pid
            try:
                code = process.wait(timeout=timeout)
                receipt["status"] = "completed"
            except subprocess.TimeoutExpired:
                receipt["status"] = "timeout"
                code = None
            receipt["exitCode"] = code
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["error"] = describe_error(error)
        primary_error = error
    finally:
        receipt["cleanupAttempted"] = process is not None
        if process is not None:
            try:
                receipt["groupDrained"] = drain_group(process)
            except Exception as error:
                receipt["groupDrained"] = False
                receipt["cleanupError"] = f"{type(error).__name__}: {error}"
            receipt["processExitAfterCleanup"] = process.returncode
            if not receipt["groupDrained"]:
                receipt["status"] = "cleanupFailed"
        receipt["elapsedMs"] = (time.monotonic() - started) * 1000
        for stream_name, path in (("stdout", stdout), ("stderr", stderr)):
            receipt[f"{stream_name}Sha256"] = None
            try:
                receipt[f"{stream_name}Sha256"] = digest(path) if path.exists() else None
            except Exception as error:
                record_diagnostic_error(receipt["diagnosticErrors"], "commandReceipt", "hash", path, error)
        save_json(output / f"{label}.command.json", receipt,
                  receipt["diagnosticErrors"], "commandReceipt")
    if primary_error is not None:
        primary_error.commandReceipt = receipt
        primary_error.diagnosticErrors = list(receipt["diagnosticErrors"])
        raise primary_error
    return receipt


def validate_startup(report):
    startup = report.get("startup")
    if not isinstance(startup, dict) or startup.get("ready") is not True:
        raise ValueError("Native startup readiness is missing")
    if type(startup.get("requestedActivationPolicy")) is not int or startup["requestedActivationPolicy"] != 0:
        raise ValueError("Native startup did not request regular activation policy")
    if type(startup.get("setActivationPolicyReturned")) is not bool:
        raise ValueError("Native policy-switch result was not recorded")
    before = startup.get("beforePolicy")
    if not isinstance(before, dict) or type(before.get("activationPolicy")) is not int or before["activationPolicy"] not in (0, 1, 2):
        raise ValueError("Native policy before the switch was not recorded")
    if startup.get("didFinishLaunchingObserved") is not True:
        raise ValueError("Native startup did not observe finished launch")
    for phase in ("afterPolicy", "afterFinishLaunching", "beforeCase"):
        state = startup.get(phase)
        if not isinstance(state, dict) or type(state.get("activationPolicy")) is not int or state["activationPolicy"] != 0:
            raise ValueError(f"Native startup was not regular at {phase}")
    ready = startup["beforeCase"]
    if ready.get("mainEventLoopRunning") is not True or ready.get("mainThread") is not True:
        raise ValueError("Native case did not start in the main event loop")
    if type(ready.get("screens")) is not int or ready["screens"] < 1:
        raise ValueError("Native case had no screen")


def validate_report(receipt, report, case, negative=False):
    if receipt.get("status") != "completed":
        raise ValueError("Native command did not complete")
    if not isinstance(report, dict) or type(report.get("schemaVersion")) is not int:
        raise ValueError("Native report schema is missing or invalid")
    if report.get("schemaVersion") != 1 or report.get("case") != case:
        raise ValueError("Native report identity does not match the requested case")
    if type(report.get("pid")) is not int or report["pid"] != receipt.get("pid"):
        raise ValueError("Native report PID does not match the owned process")
    if report.get("nativeWindowExecution") is False and report.get("stage") == "startup" and report.get("status") == "failed":
        raise ValueError(f"Native startup failed: {report.get('errorCode')}: {report.get('error')}")
    if report.get("nativeWindowExecution") is not True or report.get("performanceAcceptance") is not False:
        raise ValueError("Native report scope is missing or invalid")
    validate_startup(report)
    events = report.get("events")
    if not isinstance(events, list) or not isinstance(report.get("completedStages"), list):
        raise ValueError("Native event or stage evidence is missing")
    for event in events:
        if not isinstance(event, dict) or event.get("mainThread") is not True:
            raise ValueError("Invalid native callback thread evidence")
        if event.get("event") in ("show", "hide"):
            if event.get("visible") is not (event["event"] == "show"):
                raise ValueError("Visibility callback preceded the native state change")
    if negative:
        expected_visible = case == "show"
        if case not in ("show", "hide") or receipt.get("exitCode") != 1:
            raise ValueError("Baseline must reach the specific missing-event failure")
        if report.get("status") != "failed" or report.get("errorCode") != "visibilityEvents":
            raise ValueError("An unrelated baseline error is not a regression control")
        if report.get("stage") != case or report.get("target", {}).get("visible") is not expected_visible:
            raise ValueError("Baseline did not reach the requested native visibility")
        if any(event.get("event") in ("show", "hide") for event in events):
            raise ValueError("Baseline unexpectedly emitted visibility events")
        return "expectedFailure"
    if receipt.get("exitCode") != 0 or report.get("status") != "passed":
        raise ValueError("Native case did not pass")
    if not report["completedStages"]:
        raise ValueError("Native case completed no stages")
    return "passed"


def run_case(executable, output, case, negative=False):
    label = f"case-{case}"
    log = output / f"{label}.stdout.log"
    result_path = output / f"{label}.result.json"
    command_path = output / f"{label}.command.json"
    result = {"case": case, "verdict": "failed", "negativeControl": negative,
              "performanceAcceptance": False, "diagnosticErrors": []}
    result_write_attempted = False
    try:
        receipt = execute([str(executable), case], output, label, 45)
        result.update(commandStatus=receipt.get("status"), exitCode=receipt.get("exitCode"),
                      commandReceipt=receipt, diagnosticErrors=list(receipt.get("diagnosticErrors", [])))
        result["reportBytes"] = log.stat().st_size
        if result["reportBytes"] > 1024 * 1024:
            raise ValueError("Native report exceeds its bound; raw output is retained")
        result["reportSha256"] = digest(log)
        if result["reportBytes"] == 0:
            raise ValueError("Native process produced no JSON report; raw output and command receipt are retained")
        try:
            report = json.loads(log.read_text())
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Native process produced invalid JSON; raw output and command receipt are retained") from error
        if isinstance(report, dict):
            result.update(reportedStatus=report.get("status"), reportedStage=report.get("stage"),
                          reportedErrorCode=report.get("errorCode"), reportedError=report.get("error"),
                          reportedNativeWindowExecution=report.get("nativeWindowExecution"))
        verdict = validate_report(receipt, report, case, negative)
        # Inspect the native result before reporting errors, so an earlier native
        # failure remains primary. An otherwise valid case still needs evidence.
        require_command_diagnostics(receipt)
        result["verdict"] = verdict
        result_write_attempted = True
        write_error = save_json(result_path, result, result["diagnosticErrors"], "caseResult")
        if write_error is not None:
            result["diagnosticWriteError"] = describe_error(write_error)
            raise write_error
        return result
    except BaseException as error:
        result.update(verdict="failed", error=describe_error(error))
        # Ownership and the first process error never depend on a successful file
        # write. execute() attaches its receipt to the original start exception.
        receipt = getattr(error, "commandReceipt", None)
        if "commandReceipt" not in result and isinstance(receipt, dict):
            result.update(commandStatus=receipt.get("status"), exitCode=receipt.get("exitCode"),
                          commandReceipt=receipt, diagnosticErrors=list(receipt.get("diagnosticErrors", [])))
        if "commandReceipt" not in result:
            try:
                if command_path.exists():
                    receipt = json.loads(command_path.read_text())
                    result.update(commandStatus=receipt.get("status"), exitCode=receipt.get("exitCode"),
                                  commandReceipt=receipt, diagnosticErrors=list(receipt.get("diagnosticErrors", [])))
            except (OSError, UnicodeError, json.JSONDecodeError) as receipt_error:
                result["receiptReadError"] = describe_error(receipt_error)
                record_diagnostic_error(result["diagnosticErrors"], "commandReceipt", "read", command_path, receipt_error)
        if not result_write_attempted:
            write_error = save_json(result_path, result, result["diagnosticErrors"], "caseResult")
            if write_error is not None:
                result["diagnosticWriteError"] = describe_error(write_error)
        if not isinstance(error, Exception):
            error.result = result
            error.diagnosticErrors = result["diagnosticErrors"]
            raise
        raise NativeCaseFailure(result) from error


def compile_probe(source, output, framework):
    app = output / "VisibilityProbe.app"
    contents = app / "Contents"
    executable = contents / "MacOS" / "VisibilityProbe"
    executable.parent.mkdir(parents=True)
    plist = {"CFBundleIdentifier": f"org.otzaria.window-visibility.{output.name}",
             "CFBundleName": "Window visibility control", "CFBundleExecutable": executable.name,
             "CFBundlePackageType": "APPL", "CFBundleVersion": "1", "NSPrincipalClass": "NSApplication"}
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
    harness = ROOT / "tool/macos_visibility/main.swift"
    command = ["xcrun", "swiftc", "-swift-version", "5", "-Onone",
               "-F", str(framework.parent), "-framework", "FlutterMacOS",
               "-Xlinker", "-rpath", "-Xlinker", str(framework.parent),
               str(source), str(harness), "-o", str(executable)]
    receipt = execute(command, output, "compile", 120)
    require_successful_command(receipt, "Native compilation failed")
    return executable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flutter-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    output.mkdir(parents=True)
    summary = {"status": "running", "baseline": BASELINE, "platform": platform.platform(),
               "nativeWindowExecution": False, "performanceAcceptance": False, "cases": {},
               "diagnosticErrors": []}
    summary_path = output / "summary.json"
    summary_write_failed = False
    try:
        if platform.system() != "Darwin":
            raise RuntimeError("Native AppKit controls require macOS")
        engine = args.flutter_root.resolve() / "bin/cache/artifacts/engine/darwin-x64"
        frameworks = list(engine.glob("FlutterMacOS.xcframework/macos-*/FlutterMacOS.framework"))
        if len(frameworks) != 1:
            raise RuntimeError("Run flutter precache --macos; expected one universal macOS framework")
        summary["flutterFramework"] = str(frameworks[0])
        summary["flutterFrameworkSha256"] = digest(frameworks[0] / "FlutterMacOS")
        summary["flutterCommit"] = subprocess.check_output(
            ["git", "-C", str(args.flutter_root.resolve()), "rev-parse", "HEAD"], text=True).strip()
        summary["engineCommit"] = (args.flutter_root / "bin/internal/engine.version").read_text().strip()
        for label, command in (("swift-version", ["xcrun", "swiftc", "--version"]),
                               ("xcode-version", ["xcodebuild", "-version"])):
            receipt = execute(command, output, label, 30)
            require_successful_command(receipt, "Could not record the native toolchain")
        summary["candidateSourceSha256"] = digest(ROOT / SOURCE)
        summary["harnessSha256"] = digest(ROOT / "tool/macos_visibility/main.swift")
        summary["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        summary["trackedChanges"] = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines()
        for variant in ("candidate", "baseline"):
            current = output / variant
            current.mkdir()
            source = ROOT / SOURCE
            if variant == "baseline":
                source = current / "WindowManager.swift"
                source.write_bytes(subprocess.check_output(["git", "show", f"{BASELINE}:{SOURCE.as_posix()}"], cwd=ROOT))
                summary["baselineSourceSha256"] = digest(source)
            executable = compile_probe(source, current, frameworks[0])
            cases = CASES if variant == "candidate" else ("show", "hide", "noop", "refusal", "focus-minimize")
            results = summary["cases"][variant] = []
            for case in cases:
                result = run_case(executable, current, case,
                                  negative=variant == "baseline" and case in ("show", "hide"))
                results.append(result)
                write_error = save_json(summary_path, summary, summary["diagnosticErrors"], "summary")
                if write_error is not None:
                    summary_write_failed = True
                    raise write_error
        summary["status"] = "passed"
        summary["nativeWindowExecution"] = True
    except BaseException as error:
        summary["status"] = "failed"
        summary["error"] = describe_error(error)
        result = getattr(error, "result", None)
        if isinstance(result, dict):
            summary["failedCase"] = result
            summary["diagnosticErrors"] = result.setdefault("diagnosticErrors", [])
        elif hasattr(error, "commandReceipt"):
            summary["failedCommand"] = error.commandReceipt
            summary["diagnosticErrors"] = list(getattr(error, "diagnosticErrors", []))
        error.summary = summary
        error.diagnosticErrors = summary["diagnosticErrors"]
        if not summary_write_failed:
            save_json(summary_path, summary, summary["diagnosticErrors"], "summary")
        note_diagnostic_errors(error, summary["diagnosticErrors"])
        raise
    else:
        write_error = save_json(summary_path, summary, summary["diagnosticErrors"], "summary")
        if write_error is not None:
            summary["status"] = "failed"
            summary["error"] = describe_error(write_error)
            write_error.summary = summary
            write_error.diagnosticErrors = summary["diagnosticErrors"]
            note_diagnostic_errors(write_error, summary["diagnosticErrors"])
            raise write_error


if __name__ == "__main__":
    main()
