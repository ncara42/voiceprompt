import CoreGraphics
import Foundation

// kVK_Space = 0x31 = 49
private let kSpaceKeyCode: Int64 = 49

class HotkeyManager {
    var onStartRecording: (() -> Void)?
    var onStopRecording: (() -> Void)?

    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private var isRecording = false

    func start() -> Bool {
        let mask: CGEventMask =
            (1 << CGEventType.keyDown.rawValue) |
            (1 << CGEventType.keyUp.rawValue) |
            (1 << CGEventType.flagsChanged.rawValue)

        let selfPtr = Unmanaged.passUnretained(self).toOpaque()

        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: { _, type, event, refcon -> Unmanaged<CGEvent>? in
                guard let refcon else { return Unmanaged.passRetained(event) }
                let mgr = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()
                return mgr.handle(type: type, event: event)
            },
            userInfo: selfPtr
        ) else {
            return false
        }

        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetMain(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    private func handle(type: CGEventType, event: CGEvent) -> Unmanaged<CGEvent>? {
        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
        let optionDown = event.flags.contains(.maskAlternate)

        switch type {
        case .keyDown where keyCode == kSpaceKeyCode && optionDown && !isRecording:
            isRecording = true
            DispatchQueue.main.async { self.onStartRecording?() }
            return nil  // consume ⌥Space so it doesn't reach other apps

        case .keyUp where keyCode == kSpaceKeyCode && isRecording:
            isRecording = false
            DispatchQueue.main.async { self.onStopRecording?() }
            return nil

        case .flagsChanged where !optionDown && isRecording:
            // Option released while still holding space
            isRecording = false
            DispatchQueue.main.async { self.onStopRecording?() }
            return Unmanaged.passRetained(event)

        default:
            return Unmanaged.passRetained(event)
        }
    }
}
