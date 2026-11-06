import Cocoa

struct ProbeFailure: Error {
    let code: String
    let message: String
}

struct Step {
    let name: String
    let action: () -> Void
    let ready: () -> Bool
    let verify: () throws -> Void

    init(_ name: String, action: @escaping () -> Void,
         ready: @escaping () -> Bool = { true },
         verify: @escaping () throws -> Void = {}) {
        self.name = name
        self.action = action
        self.ready = ready
        self.verify = verify
    }
}

final class RefusingWindow: NSWindow {
    var refuseShow = false
    var refuseHide = false

    override func setIsVisible(_ flag: Bool) {
        if !(flag && refuseShow) { super.setIsVisible(flag) }
    }

    override func makeKeyAndOrderFront(_ sender: Any?) {
        if !refuseShow { super.makeKeyAndOrderFront(sender) }
    }

    override func orderOut(_ sender: Any?) {
        if !refuseHide { super.orderOut(sender) }
    }
}

final class VisibilityProbe {
    let caseName: String
    let startup: [String: Any]
    let window: NSWindow
    let otherWindow: NSWindow
    let manager = WindowManager()
    let otherManager = WindowManager()
    let started = ProcessInfo.processInfo.systemUptime
    var events = [[String: Any]]()
    var completed = [String]()
    var steps = [Step]()
    var stage = "setup"
    var eventOffset = 0
    var stepStarted = 0.0
    var finished = false

    init(_ caseName: String, startup: [String: Any]) {
        self.caseName = caseName
        self.startup = startup
        let frame = NSRect(x: 80, y: 80, width: 400, height: 260)
        let style: NSWindow.StyleMask = [.titled, .closable, .miniaturizable]
        if caseName == "panel" {
            let panel = NSPanel(contentRect: frame, styleMask: style,
                                backing: .buffered, defer: false)
            panel.hidesOnDeactivate = false
            window = panel
        } else if caseName == "refusal" {
            window = RefusingWindow(contentRect: frame, styleMask: style,
                                    backing: .buffered, defer: false)
        } else {
            window = NSWindow(contentRect: frame, styleMask: style,
                              backing: .buffered, defer: false)
        }
        otherWindow = NSWindow(contentRect: frame.offsetBy(dx: 100, dy: 100),
                               styleMask: style, backing: .buffered, defer: false)
        for item in [window, otherWindow] {
            item.isReleasedWhenClosed = false
            item.animationBehavior = .none
            item.title = "window_manager visibility control"
        }
        manager.mainWindow = window
        otherManager.mainWindow = otherWindow
        manager.onEvent = { [weak self] event in self?.record(event, owner: "target") }
        otherManager.onEvent = { [weak self] event in self?.record(event, owner: "other") }
    }

    func state(_ item: NSWindow) -> [String: Any] {
        return ["visible": item.isVisible, "minimized": item.isMiniaturized,
                "key": item.isKeyWindow, "windowNumber": item.windowNumber]
    }

    func record(_ event: String, owner: String) {
        let item = owner == "target" ? window : otherWindow
        var entry = state(item)
        entry["owner"] = owner
        entry["event"] = event
        entry["stage"] = stage
        entry["mainThread"] = Thread.isMainThread
        entry["elapsedMs"] = (ProcessInfo.processInfo.systemUptime - started) * 1000
        events.append(entry)
    }

    func recent(_ owner: String = "target") -> [String] {
        return events.dropFirst(eventOffset).filter { $0["owner"] as? String == owner }
            .compactMap { $0["event"] as? String }
    }

    func visibility(_ owner: String = "target") -> [String] {
        return recent(owner).filter { $0 == "show" || $0 == "hide" }
    }

    func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw ProbeFailure(code: "assertion", message: message) }
    }

    func expectVisibility(_ expected: [String], owner: String = "target") throws {
        let actual = visibility(owner)
        if actual != expected {
            throw ProbeFailure(code: "visibilityEvents",
                               message: "\(owner): expected \(expected), observed \(actual)")
        }
    }

    func setupVisible() -> Step {
        return Step("visible setup", action: {
            self.window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }, ready: { self.window.isVisible })
    }

    func configure() throws {
        switch caseName {
        case "show", "panel":
            steps = [Step("show", action: { self.manager.show() },
                          ready: { self.window.isVisible }, verify: {
                try self.expectVisibility(["show"])
            })]
            if caseName == "panel" {
                steps.append(Step("panel hide", action: { self.manager.hide() },
                                  ready: { !self.window.isVisible }, verify: {
                    try self.expectVisibility(["hide"])
                }))
            }
        case "hide":
            steps = [setupVisible(), Step("hide", action: { self.manager.hide() },
                                          ready: { !self.window.isVisible }, verify: {
                try self.expectVisibility(["hide"])
            })]
        case "rapid":
            steps = [Step("show hide show", action: {
                self.manager.show()
                self.manager.hide()
                self.manager.show()
            }, verify: {
                try self.require(self.window.isVisible, "Last queued show must win")
                try self.expectVisibility(["show", "hide", "show"])
            }), Step("hide hide show show hide", action: {
                self.manager.hide()
                self.manager.hide()
                self.manager.show()
                self.manager.show()
                self.manager.hide()
            }, verify: {
                try self.require(!self.window.isVisible, "Last queued hide must win")
                try self.expectVisibility(["hide", "show", "hide"])
            })]
        case "noop":
            steps = [Step("already hidden", action: {
                self.manager.hide()
                self.manager.hide()
            }, verify: {
                try self.require(!self.window.isVisible, "Hidden window changed")
                try self.expectVisibility([])
            }), setupVisible(), Step("already visible", action: {
                self.manager.show()
                self.manager.show()
            }, verify: {
                try self.require(self.window.isVisible, "Visible window changed")
                try self.expectVisibility([])
            })]
        case "refusal":
            let target = window as! RefusingWindow
            steps = [Step("refused show", action: {
                target.refuseShow = true
                self.manager.show()
            }, verify: {
                try self.require(!target.isVisible, "Refusal fixture became visible")
                try self.expectVisibility([])
                target.refuseShow = false
            }), setupVisible(), Step("refused hide", action: {
                target.refuseHide = true
                self.manager.hide()
            }, verify: {
                try self.require(target.isVisible, "Refusal fixture became hidden")
                try self.expectVisibility([])
                target.refuseHide = false
            })]
        case "independent":
            steps = [setupVisible(), Step("second window setup", action: {
                self.otherWindow.orderFront(nil)
            }, ready: { self.otherWindow.isVisible }),
            Step("target hide", action: { self.manager.hide() },
                 ready: { !self.window.isVisible }, verify: {
                try self.expectVisibility(["hide"])
                try self.expectVisibility([], owner: "other")
                try self.require(self.otherWindow.isVisible, "Other window was hidden")
            }), Step("target show", action: { self.manager.show() },
                     ready: { self.window.isVisible }, verify: {
                try self.expectVisibility(["show"])
                try self.expectVisibility([], owner: "other")
            }), Step("other hide", action: { self.otherManager.hide() },
                     ready: { !self.otherWindow.isVisible }, verify: {
                try self.expectVisibility([])
                try self.expectVisibility(["hide"], owner: "other")
                try self.require(self.window.isVisible, "Target window was hidden")
            })]
        case "focus-minimize":
            steps = [setupVisible(), Step("other focus", action: {
                self.otherWindow.makeKeyAndOrderFront(nil)
            }, ready: { self.otherWindow.isKeyWindow }, verify: {
                try self.expectVisibility([])
                try self.require(self.window.isVisible, "Focus loss hid target")
            }), Step("target focus", action: { self.manager.focus() },
                     ready: { self.window.isKeyWindow && self.recent().contains("focus") },
                     verify: { try self.expectVisibility([]) }),
            Step("blur", action: { self.manager.blur() }, verify: {
                try self.expectVisibility([])
                try self.require(self.window.isVisible, "Blur hid target")
            }), Step("minimize", action: { self.manager.minimize() },
                     ready: { self.window.isMiniaturized && self.recent().contains("minimize") },
                     verify: { try self.expectVisibility([]) }),
            Step("restore", action: { self.manager.restore() },
                 ready: { !self.window.isMiniaturized && self.window.isVisible && self.recent().contains("restore") },
                 verify: { try self.expectVisibility([]) })]
        default:
            throw ProbeFailure(code: "unknownCase", message: caseName)
        }
    }

    func advance() {
        if completed.count == steps.count {
            finish(nil)
            return
        }
        let step = steps[completed.count]
        stage = step.name
        eventOffset = events.count
        stepStarted = ProcessInfo.processInfo.systemUptime
        step.action()
        DispatchQueue.main.async { self.checkStep() }
    }

    func checkStep() {
        let step = steps[completed.count]
        if !step.ready() {
            if ProcessInfo.processInfo.systemUptime - stepStarted > 5 {
                finish(ProbeFailure(code: "timeout", message: "Native state did not reach \(stage)"))
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.01) { self.checkStep() }
            }
            return
        }
        do {
            try step.verify()
            for entry in events.dropFirst(eventOffset) {
                try require(entry["mainThread"] as? Bool == true, "Callback left the main thread")
                if entry["event"] as? String == "show" {
                    try require(entry["visible"] as? Bool == true, "Show callback preceded native visibility")
                } else if entry["event"] as? String == "hide" {
                    try require(entry["visible"] as? Bool == false, "Hide callback preceded native visibility")
                }
            }
            completed.append(step.name)
            DispatchQueue.main.async { self.advance() }
        } catch let error as ProbeFailure {
            finish(error)
        } catch {
            finish(ProbeFailure(code: "unexpected", message: String(describing: error)))
        }
    }

    func finish(_ failure: ProbeFailure?) {
        if finished { return }
        finished = true
        var report: [String: Any] = [
            "schemaVersion": 1, "case": caseName,
            "startup": startup,
            "status": failure == nil ? "passed" : "failed", "stage": stage,
            "completedStages": completed, "events": events,
            "target": state(window), "other": state(otherWindow),
            "pid": ProcessInfo.processInfo.processIdentifier,
            "osVersion": ProcessInfo.processInfo.operatingSystemVersionString,
            "activationPolicy": NSApp.activationPolicy().rawValue,
            "appBundleIdentifier": Bundle.main.bundleIdentifier.map { $0 as Any } ?? NSNull(),
            "screens": NSScreen.screens.count,
            "elapsedMs": (ProcessInfo.processInfo.systemUptime - started) * 1000,
            "nativeWindowExecution": true, "performanceAcceptance": false
        ]
        if let error = failure {
            report["errorCode"] = error.code
            report["error"] = error.message
        }
        manager.onEvent = nil
        otherManager.onEvent = nil
        (window as? RefusingWindow)?.refuseHide = false
        window.orderOut(nil)
        otherWindow.orderOut(nil)
        let data = try! JSONSerialization.data(withJSONObject: report, options: [.sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
        exit(failure == nil ? 0 : 1)
    }
}

func applicationState(_ application: NSApplication) -> [String: Any] {
    let current = NSRunningApplication.current
    return [
        "activationPolicy": application.activationPolicy().rawValue,
        "mainEventLoopRunning": application.isRunning,
        "mainThread": Thread.isMainThread,
        "active": application.isActive, "hidden": application.isHidden,
        "runningApplicationPolicy": current.activationPolicy.rawValue,
        "runningApplicationFinishedLaunching": current.isFinishedLaunching,
        "runningApplicationTerminated": current.isTerminated,
        "launchDate": current.launchDate.map { $0.timeIntervalSince1970 as Any } ?? NSNull(),
        "bundleURL": Bundle.main.bundleURL.path,
        "bundleIdentifier": Bundle.main.bundleIdentifier.map { $0 as Any } ?? NSNull(),
        "screens": NSScreen.screens.count
    ]
}

func failStartup(_ caseName: String, evidence: [String: Any],
                 code: String, message: String, exitCode: Int32 = 65) -> Never {
    let report: [String: Any] = [
        "schemaVersion": 1, "case": caseName, "status": "failed", "stage": "startup",
        "errorCode": code, "error": message, "startup": evidence,
        "completedStages": [], "events": [], "target": NSNull(), "other": NSNull(),
        "pid": ProcessInfo.processInfo.processIdentifier,
        "osVersion": ProcessInfo.processInfo.operatingSystemVersionString,
        "nativeWindowExecution": false, "performanceAcceptance": false
    ]
    let data = try! JSONSerialization.data(withJSONObject: report, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([10]))
    exit(exitCode)
}

final class LaunchObserver: NSObject {
    var finished = false

    @objc func didFinishLaunching(_ notification: Notification) {
        finished = true
    }
}

guard CommandLine.arguments.count == 2 else {
    failStartup("<invalid>", evidence: ["ready": false], code: "arguments",
                message: "Expected exactly one native case name", exitCode: 64)
}
let caseName = CommandLine.arguments[1]
let application = NSApplication.shared
var startup: [String: Any] = ["ready": false, "requestedActivationPolicy": 0]
startup["beforePolicy"] = applicationState(application)
startup["setActivationPolicyReturned"] = application.setActivationPolicy(.regular)
startup["afterPolicy"] = applicationState(application)
// The return value describes the switch attempt. The native state is the gate,
// including when this bundled process already has the requested regular policy.
guard application.activationPolicy() == .regular else {
    failStartup(caseName, evidence: startup, code: "activationPolicy",
                message: "The application did not reach regular activation policy")
}
let launchObserver = LaunchObserver()
NotificationCenter.default.addObserver(
    launchObserver, selector: #selector(LaunchObserver.didFinishLaunching(_:)),
    name: NSApplication.didFinishLaunchingNotification, object: application)
application.finishLaunching()
NotificationCenter.default.removeObserver(launchObserver)
startup["didFinishLaunchingObserved"] = launchObserver.finished
startup["afterFinishLaunching"] = applicationState(application)
DispatchQueue.main.async {
    startup["beforeCase"] = applicationState(application)
    guard application.activationPolicy() == .regular,
          application.isRunning, launchObserver.finished,
          Thread.isMainThread, !NSScreen.screens.isEmpty else {
        failStartup(caseName, evidence: startup, code: "applicationNotReady",
                    message: "Native cases require regular policy, finished launch, a main event loop and a screen")
    }
    startup["ready"] = true
    let probe = VisibilityProbe(caseName, startup: startup)
    do {
        try probe.configure()
        probe.advance()
    } catch let error as ProbeFailure {
        probe.finish(error)
    } catch {
        probe.finish(ProbeFailure(code: "unexpected", message: String(describing: error)))
    }
}
application.run()
startup["eventLoopReturned"] = applicationState(application)
failStartup(caseName, evidence: startup, code: "eventLoopReturned",
            message: "The main event loop returned before a case result")
