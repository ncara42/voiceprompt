import AppKit
import CoreGraphics

enum PasteboardManager {
    static func copyAndPaste(_ text: String, into app: NSRunningApplication? = nil) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)

        if let app, !app.isTerminated {
            app.activate(options: .activateIgnoringOtherApps)
            usleep(200_000)  // wait for app to come to foreground
        } else {
            usleep(80_000)
        }
        simulateCmdV()
    }

    static func copyOnly(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    private static func simulateCmdV() {
        let src = CGEventSource(stateID: .combinedSessionState)
        let vKey: CGKeyCode = 0x09

        let down = CGEvent(keyboardEventSource: src, virtualKey: vKey, keyDown: true)
        down?.flags = .maskCommand
        down?.post(tap: .cghidEventTap)

        let up = CGEvent(keyboardEventSource: src, virtualKey: vKey, keyDown: false)
        up?.flags = .maskCommand
        up?.post(tap: .cghidEventTap)
    }
}
