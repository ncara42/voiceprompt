"""Cross-platform paste-into-active-app: detect frontmost app, activate it, simulate paste.

Used by `voiceprompt listen` to deliver the reformulated prompt straight to the user's
agent CLI (terminal where Claude Code / aider / etc. is running) instead of just
sitting in voiceprompt's own window.

macOS  : AppleScript via `osascript` (no extra deps).
Linux  : xdotool (X11) or wtype (Wayland) — whichever is on PATH.
Windows: SendInput via ctypes (no extra deps).

macOS gotcha: `System Events keystroke` triggers a one-time Accessibility permission
prompt the first time the binary runs. The user must grant it in System Settings ->
Privacy & Security -> Accessibility.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import time

PLATFORM = platform.system()  # "Darwin" | "Linux" | "Windows"


def supported() -> bool:
    """True if this platform has a working paste-injection backend."""
    if PLATFORM == "Darwin":
        return shutil.which("osascript") is not None
    if PLATFORM == "Linux":
        return shutil.which("xdotool") is not None or shutil.which("wtype") is not None
    return PLATFORM == "Windows"  # ctypes is in stdlib


def missing_tool_hint() -> str:
    """Human-readable hint about what to install if `supported()` is False."""
    if PLATFORM == "Linux":
        return "Install xdotool (X11) or wtype (Wayland) so voiceprompt can paste."
    if PLATFORM == "Darwin":
        return "macOS without osascript? Install Apple Command Line Tools."
    return "auto-paste is not available on this platform."


def get_frontmost_app() -> str | None:
    """Return the name of the app currently in the foreground, or None if unknown."""
    try:
        if PLATFORM == "Darwin":
            r = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of first '
                    "application process whose frontmost is true",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            return r.stdout.strip() or None
        if PLATFORM == "Linux":
            if shutil.which("xdotool"):
                r = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                return r.stdout.strip() or None
            return None
        if PLATFORM == "Windows":
            import ctypes  # noqa: PLC0415

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or None
    except Exception:  # noqa: BLE001
        return None
    return None


_ACTIVATE_APP_SCRIPT = """
on run argv
    set appName to item 1 of argv
    tell application appName to activate
end run
"""


def activate_app(name: str) -> bool:
    """Bring `name` to the foreground. Returns True on success.

    `name` is passed to AppleScript as a script argument (argv), not interpolated
    into the script source — so a malicious value like `'"; do shell script "..."'`
    cannot escape the string literal. Same defense applied to xdotool/wmctrl,
    where the arg is passed as a single argv element (not a shell string).
    """
    if not name:
        return False
    try:
        if PLATFORM == "Darwin":
            subprocess.run(
                ["osascript", "-e", _ACTIVATE_APP_SCRIPT, name],
                check=True,
                timeout=2,
                capture_output=True,
            )
            return True
        if PLATFORM == "Linux":
            if shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-a", name], check=True, timeout=2)
                return True
            if shutil.which("xdotool"):
                subprocess.run(
                    ["xdotool", "search", "--name", name, "windowactivate"],
                    check=True,
                    timeout=2,
                    capture_output=True,
                )
                return True
        if PLATFORM == "Windows":
            # Activating by window title is non-trivial; if the user kept the same
            # terminal in front, paste() alone is enough — we just lose nothing.
            return False
    except Exception:  # noqa: BLE001
        return False
    return False


def paste() -> bool:
    """Simulate the paste shortcut on the currently-focused app."""
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


def paste_to(app_name: str | None, *, activate_delay: float = 0.18) -> bool:
    """Activate the target app (if given) and paste. Returns True on success."""
    if app_name and not activate_app(app_name):
        # Activation failed; still try paste — maybe the target is already in front.
        pass
    if app_name:
        time.sleep(activate_delay)
    return paste()


# ──────────────────────────────────────────────────────────────────────────────
# Claude Code auto-detection: find the terminal session running `claude` and
# focus exactly that pane/tab so the paste lands inside Claude Code's prompt.
# ──────────────────────────────────────────────────────────────────────────────


def _find_claude_pid() -> int | None:
    """Return the PID of a running Claude Code CLI process, or None."""
    import os  # noqa: PLC0415

    try:
        r = subprocess.run(
            ["pgrep", "-fl", "claude"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:  # noqa: BLE001
        return None
    if r.returncode != 0:
        return None

    candidates: list[tuple[int, str]] = []
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_s, cmd = parts
        if not pid_s.isdigit():
            continue
        cmd_lower = cmd.lower()
        # Skip ourselves and the Claude desktop app -- we want the CLI.
        if "voiceprompt" in cmd_lower:
            continue
        if "claude.app/contents" in cmd_lower:
            continue
        if cmd.startswith("/Applications/Claude.app/"):
            continue
        # Inspect the basename of argv[0] -- the CLI installs as a symlink named
        # exactly `claude` (e.g. ~/.local/bin/claude -> versions/X). When invoked
        # via PATH the cmdline is just "claude" with no slashes.
        # Stay strict: only `claude` itself, never wrappers like bun/node/deno
        # whose path happens to contain "/claude" (e.g. ~/.claude/plugins/...).
        argv0 = cmd.split()[0] if cmd.split() else ""
        base = os.path.basename(argv0).lower()
        if base == "claude":
            candidates.append((int(pid_s), cmd))

    if not candidates:
        return None
    # Prefer the most recently started one (highest PID is a decent proxy).
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][0]


def _get_pid_tty(pid: int) -> str | None:
    """Return the controlling TTY of a PID, e.g. '/dev/ttys003', or None."""
    try:
        r = subprocess.run(
            ["ps", "-o", "tty=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except Exception:  # noqa: BLE001
        return None
    tty = r.stdout.strip()
    if not tty or tty == "?" or tty == "??":
        return None
    if not tty.startswith("/dev/"):
        tty = f"/dev/{tty}"
    return tty


_ITERM_FOCUS_SCRIPT = '''
on run argv
    set targetTTY to item 1 of argv
    tell application "iTerm2"
        activate
        repeat with w in windows
            repeat with t in tabs of w
                repeat with s in sessions of t
                    if tty of s is targetTTY then
                        tell w to select
                        tell t to select
                        select s
                        return "ok"
                    end if
                end repeat
            end repeat
        end repeat
    end tell
    return "not_found"
end run
'''


_TERMINAL_FOCUS_SCRIPT = '''
on run argv
    set targetTTY to item 1 of argv
    tell application "Terminal"
        activate
        repeat with w in windows
            repeat with t in tabs of w
                if tty of t is targetTTY then
                    set selected of t to true
                    set frontmost of w to true
                    return "ok"
                end if
            end repeat
        end repeat
    end tell
    return "not_found"
end run
'''


def _focus_session_for_tty(tty: str) -> bool:
    """Try iTerm2 then Terminal.app to focus the exact pane/tab attached to `tty`."""
    if PLATFORM != "Darwin" or not tty:
        return False
    for script in (_ITERM_FOCUS_SCRIPT, _TERMINAL_FOCUS_SCRIPT):
        try:
            r = subprocess.run(
                ["osascript", "-e", script, tty],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip() == "ok":
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def find_claude_target() -> tuple[str, str] | None:
    """Detect a running Claude Code session.

    Returns (label, identifier) where identifier is a TTY (mac) we know how to
    focus, or None if no Claude is running / the platform isn't supported.
    """
    if PLATFORM != "Darwin":
        return None
    pid = _find_claude_pid()
    if pid is None:
        return None
    tty = _get_pid_tty(pid)
    if tty is None:
        return None
    return (f"Claude Code (pid {pid}, {tty})", tty)


def paste_to_claude(tty: str, *, activate_delay: float = 0.22) -> bool:
    """Focus the terminal session attached to `tty` and paste."""
    if not _focus_session_for_tty(tty):
        return False
    time.sleep(activate_delay)
    return paste()
