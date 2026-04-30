import AppKit

class StatusBarController {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

    // Called by main.swift when the user clicks the icon
    var onStartRecording: (() -> Void)?
    var onStopRecording: (() -> Void)?

    private enum State { case idle, recording, processing }
    private var state: State = .idle

    init() {
        // Left-click → toggle recording. Right-click → menu.
        statusItem.button?.action = #selector(clicked(_:))
        statusItem.button?.target = self
        statusItem.button?.sendAction(on: [.leftMouseUp, .rightMouseUp])
        setIdle()
    }

    // MARK: - State

    func setIdle() {
        state = .idle
        DispatchQueue.main.async {
            self.statusItem.button?.image = Self.image("mic", template: true)
            self.statusItem.button?.toolTip = "voiceprompt — click or hold ⌥Space to record"
        }
    }

    func setRecording() {
        state = .recording
        DispatchQueue.main.async {
            self.statusItem.button?.image = Self.image("mic.fill", tint: .systemRed)
            self.statusItem.button?.toolTip = "voiceprompt — recording… click to stop"
        }
    }

    func setProcessing() {
        state = .processing
        DispatchQueue.main.async {
            self.statusItem.button?.image = Self.image("waveform", tint: .systemOrange)
            self.statusItem.button?.toolTip = "voiceprompt — processing…"
        }
    }

    // MARK: - Click handling

    @objc private func clicked(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else { return }

        if event.type == .rightMouseUp {
            showMenu()
            return
        }

        // Left click: toggle recording (ignore clicks while processing)
        switch state {
        case .idle:
            onStartRecording?()
        case .recording:
            onStopRecording?()
        case .processing:
            break
        }
    }

    private func showMenu() {
        let menu = NSMenu()

        let title = NSMenuItem(title: "voiceprompt", action: nil, keyEquivalent: "")
        title.isEnabled = false
        menu.addItem(title)

        let hint = NSMenuItem(title: "Click icon or hold ⌥Space to record", action: nil, keyEquivalent: "")
        hint.isEnabled = false
        menu.addItem(hint)

        menu.addItem(.separator())

        let quit = NSMenuItem(title: "Quit", action: #selector(quitApp), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)

        statusItem.menu = menu
        statusItem.button?.performClick(nil)
        statusItem.menu = nil  // remove so left-click works next time
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    // MARK: - Icons

    private static func image(_ symbol: String, template: Bool = false, tint: NSColor? = nil) -> NSImage? {
        guard let img = NSImage(systemSymbolName: symbol, accessibilityDescription: nil) else { return nil }
        if template {
            img.isTemplate = true
            return img
        }
        guard let color = tint else { return img }
        let tinted = NSImage(size: img.size, flipped: false) { rect in
            img.draw(in: rect)
            color.withAlphaComponent(0.9).set()
            rect.fill(using: .sourceAtop)
            return true
        }
        tinted.isTemplate = false
        return tinted
    }
}
