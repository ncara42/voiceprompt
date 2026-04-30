import AppKit

class AppFocusTracker: NSObject {
    private(set) var lastApp: NSRunningApplication?
    private let myPID = ProcessInfo.processInfo.processIdentifier

    override init() {
        super.init()
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(appChanged(_:)),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )
    }

    @objc private func appChanged(_ notification: Notification) {
        guard
            let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
            app.processIdentifier != myPID
        else { return }
        lastApp = app
    }
}
