"""Cross-platform paste simulator: send ⌘V / Ctrl+V to the focused window.

The listen daemon runs in the background and never steals focus, so whichever
app the user was already in receives the simulated paste. No PID/TTY/AppleScript
detection — if you want to paste into a specific tool, switch to it before
pressing the hotkey.

macOS  : AppleScript via ``osascript`` (no extra deps).
Linux  : ``xdotool`` (X11) or ``wtype`` (Wayland) — whichever is on PATH.
Windows: ``SendInput`` via ctypes (no extra deps).

macOS gotcha: the very first keystroke triggers an Accessibility permission
prompt the user must grant under
System Settings → Privacy & Security → Accessibility.
"""

from __future__ import annotations

import platform
import shutil
import subprocess

PLATFORM = platform.system()  # "Darwin" | "Linux" | "Windows"


def supported() -> bool:
    """True if this platform has a working paste-injection backend."""
    if PLATFORM == "Darwin":
        return shutil.which("osascript") is not None
    if PLATFORM == "Linux":
        return shutil.which("xdotool") is not None or shutil.which("wtype") is not None
    return PLATFORM == "Windows"  # ctypes is in stdlib


def missing_tool_hint() -> str:
    """Human-readable hint about what to install if ``supported()`` is False."""
    if PLATFORM == "Linux":
        return "Install xdotool (X11) or wtype (Wayland) so voiceprompt can paste."
    if PLATFORM == "Darwin":
        return "macOS without osascript? Install Apple Command Line Tools."
    return "auto-paste is not available on this platform."


def paste() -> bool:
    """Simulate the paste shortcut on the currently-focused window."""
    try:
        if PLATFORM == "Darwin":
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to keystroke "v" using {command down}',
                ],
                check=True,
                timeout=2,
                capture_output=True,
            )
            return True
        if PLATFORM == "Linux":
            if shutil.which("xdotool"):
                subprocess.run(["xdotool", "key", "ctrl+v"], check=True, timeout=2)
                return True
            if shutil.which("wtype"):
                subprocess.run(["wtype", "-M", "ctrl", "v"], check=True, timeout=2)
                return True
            return False
        if PLATFORM == "Windows":
            import ctypes  # noqa: PLC0415

            VK_CONTROL = 0x11
            VK_V = 0x56
            KEYEVENTF_KEYUP = 0x0002
            user32 = ctypes.windll.user32
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            return True
    except Exception:  # noqa: BLE001
        return False
    return False
