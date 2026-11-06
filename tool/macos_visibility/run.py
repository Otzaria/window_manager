import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("packages/window_manager/macos/window_manager/Sources/window_manager/WindowManager.swift")
BASELINE = "4f37655288ce8b803a9bd50294c5d6983850f622"
CASES = ("show", "hide", "rapid", "noop", "refusal", "independent", "focus-minimize", "panel")


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
    receipt = {"command": command, "timeoutSeconds": timeout, "status": "running"}
    process = None
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
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
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
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
        receipt["stdoutSha256"] = digest(stdout) if stdout.exists() else None
        receipt["stderrSha256"] = digest(stderr) if stderr.exists() else None
        (output / f"{label}.command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def validate_report(receipt, report, case, negative=False):
    if receipt.get("status") != "completed":
        raise ValueError("Native command did not complete")
    if not isinstance(report, dict) or type(report.get("schemaVersion")) is not int:
        raise ValueError("Native report schema is missing or invalid")
    if report.get("schemaVersion") != 1 or report.get("case") != case:
        raise ValueError("Native report identity does not match the requested case")
    if type(report.get("pid")) is not int or report["pid"] != receipt.get("pid"):
        raise ValueError("Native report PID does not match the owned process")
    if report.get("nativeWindowExecution") is not True or report.get("performanceAcceptance") is not False:
        raise ValueError("Native report scope is missing or invalid")
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
    receipt = execute([str(executable), case], output, label, 45)
    log = output / f"{label}.stdout.log"
    if log.stat().st_size > 1024 * 1024:
        raise ValueError("Native report exceeds its bound; raw output is retained")
    report = json.loads(log.read_text())
    verdict = validate_report(receipt, report, case, negative)
    return {"case": case, "verdict": verdict, "exitCode": receipt["exitCode"],
            "reportSha256": digest(log)}


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
    if receipt.get("status") != "completed" or receipt.get("exitCode") != 0:
        raise RuntimeError("Native compilation failed; compiler output is retained")
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
               "nativeWindowExecution": False, "performanceAcceptance": False, "cases": {}}
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
            if receipt.get("status") != "completed" or receipt.get("exitCode") != 0:
                raise RuntimeError("Could not record the native toolchain")
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
                (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        summary["status"] = "passed"
        summary["nativeWindowExecution"] = True
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
