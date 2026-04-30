"""Global hotkey listener via pynput.

Lets `voiceprompt listen` toggle recording from anywhere on the system without
the user having to change windows.

Permissions on macOS (one-time, the OS will prompt the first time pynput attaches):
  - System Settings -> Privacy & Security -> Input Monitoring
  - System Settings -> Privacy & Security -> Accessibility
Both must include the terminal you launch `voiceprompt listen` from
(Terminal / iTerm2 / Ghostty / Warp...). Without these the listener silently
no-ops on every press.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

# pynput is platform-specific; import errors should surface a clean message
# when the user runs `voiceprompt listen`, not when the package is imported.
try:
    from pynput import keyboard  # type: ignore[import-not-found]

    _PYNPUT_OK = True
    _PYNPUT_ERR: Exception | None = None
except Exception as e:  # noqa: BLE001
    keyboard = None  # type: ignore[assignment]
    _PYNPUT_OK = False
    _PYNPUT_ERR = e


_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "meta": "cmd",
}

# Multi-character key tokens pynput expects in <angle brackets>.
_NAMED_KEYS = {
    "space",
    "enter",
    "return",
    "tab",
    "esc",
    "escape",
    "backspace",
    "delete",
    "home",
    "end",
    "page_up",
    "page_down",
    "left",
    "right",
    "up",
    "down",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
}


def parse_hotkey(spec: str) -> str:
    """Convert a friendly spec like 'ctrl+space' to pynput's '<ctrl>+<space>'."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    out: list[str] = []
    for p in parts:
        if p in _MODIFIER_ALIASES:
            out.append(f"<{_MODIFIER_ALIASES[p]}>")
        elif p in _NAMED_KEYS:
            out.append(f"<{p}>")
        elif len(p) == 1:
            out.append(p)
        else:
            out.append(f"<{p}>")
    return "+".join(out)


class HotkeyContext:
    """Shared state between the pynput listener thread and the main daemon thread."""

    def __init__(self) -> None:
        self.start_event = threading.Event()
        self._current_app: Any | None = None
        self._lock = threading.Lock()

    def set_running_app(self, app: Any) -> None:
        with self._lock:
            self._current_app = app

    def clear_running_app(self) -> None:
        with self._lock:
            self._current_app = None

    def has_running_app(self) -> bool:
        with self._lock:
            return self._current_app is not None

    def trigger_start(self) -> None:
        """Fire the start event if not already recording."""
        with self._lock:
            app = self._current_app
        if app is None:
            self.start_event.set()

    def trigger_stop(self) -> None:
        """Stop a running recording."""
        with self._lock:
            app = self._current_app
        if app is not None:
            with contextlib.suppress(Exception):
                app.exit(result=True)

    def on_hotkey(self) -> None:
        """Called from the pynput thread. Toggles between start and stop."""
        with self._lock:
            app = self._current_app
        if app is not None:
            # We're recording -- ask prompt_toolkit to exit cleanly.
            with contextlib.suppress(Exception):
                app.exit(result=True)
        else:
            self.start_event.set()


class HotkeyError(Exception):
    pass


def is_supported() -> bool:
    return _PYNPUT_OK


def import_error_hint() -> str:
    if _PYNPUT_ERR is None:
        return ""
    return f"pynput no se pudo cargar: {_PYNPUT_ERR}"


def listen(combo: str, ctx: HotkeyContext):
    """Start a global hotkey listener. Returns the listener (call .stop() to stop)."""
    if not _PYNPUT_OK:
        raise HotkeyError(import_error_hint())
    pt_combo = parse_hotkey(combo)
    try:
        listener = keyboard.GlobalHotKeys({pt_combo: ctx.on_hotkey})  # type: ignore[union-attr]
        listener.start()
    except Exception as e:  # noqa: BLE001
        raise HotkeyError(f"Could not register hotkey '{combo}' ({pt_combo}): {e}") from e
    return listener


def listen_simple(combo: str, on_press: Callable[[], None]):
    """Variant for one-shot callbacks (no toggle). Used when you don't need a context."""
    if not _PYNPUT_OK:
        raise HotkeyError(import_error_hint())
    pt_combo = parse_hotkey(combo)
    try:
        listener = keyboard.GlobalHotKeys({pt_combo: on_press})  # type: ignore[union-attr]
        listener.start()
    except Exception as e:  # noqa: BLE001
        raise HotkeyError(f"Could not register hotkey '{combo}' ({pt_combo}): {e}") from e
    return listener


# pynput Key groups for modifier matching in listen_hold.
def _pynput_mod_groups():
    return {
        "ctrl":  {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
        "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
        "alt":   {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r},
        "cmd":   {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r},
    }


def listen_hold(combo: str, ctx: HotkeyContext):
    """Push-to-talk listener: trigger_start on key-combo press, trigger_stop on release.

    Unlike the toggle listener, holding the combo starts recording and releasing
    any key in the combo stops it.
    """
    if not _PYNPUT_OK:
        raise HotkeyError(import_error_hint())

    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    mod_groups = _pynput_mod_groups()

    # Separate modifiers from the main (non-modifier) key.
    req_mod_names = {_MODIFIER_ALIASES[p] for p in parts if p in _MODIFIER_ALIASES}
    main_parts = [p for p in parts if p not in _MODIFIER_ALIASES]
    main_str = main_parts[0] if main_parts else None

    req_mod_groups = [g for name, g in mod_groups.items() if name in req_mod_names]

    pressed: set = set()

    def _matches_main(key: Any) -> bool:
        if main_str is None:
            return False
        if main_str in _NAMED_KEYS:
            try:
                return key == getattr(keyboard.Key, main_str)  # type: ignore[union-attr]
            except AttributeError:
                return False
        char = getattr(key, "char", None)
        return char is not None and char.lower() == main_str

    def _all_mods_down() -> bool:
        return all(pressed & g for g in req_mod_groups)

    def _is_combo_key(key: Any) -> bool:
        if _matches_main(key):
            return True
        return any(key in g for g in req_mod_groups)

    def on_press_cb(key: Any) -> None:
        pressed.add(key)
        if _matches_main(key) and _all_mods_down():
            ctx.trigger_start()

    def on_release_cb(key: Any) -> None:
        if _is_combo_key(key) and ctx.has_running_app():
            ctx.trigger_stop()
        pressed.discard(key)

    try:
        listener = keyboard.Listener(  # type: ignore[union-attr]
            on_press=on_press_cb, on_release=on_release_cb
        )
        listener.start()
    except Exception as e:  # noqa: BLE001
        raise HotkeyError(f"Could not register hold hotkey '{combo}': {e}") from e
    return listener
