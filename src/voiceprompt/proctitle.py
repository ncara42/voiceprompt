"""Make the running interpreter present itself as ``voiceprompt``.

Without this, macOS shows "Python" in the menu bar (when the hotkey daemon
activates an AppKit event loop), in Privacy & Security permission prompts, in
Activity Monitor, and in ``ps``. We patch three places:

1. ``setproctitle`` -- ``ps`` / ``top`` / Activity Monitor.
2. ``NSProcessInfo.processName`` -- macOS top menu bar when AppKit is active.
3. ``NSBundle.mainBundle().infoDictionary[CFBundleName]`` -- accessibility /
   notification prompts and any other surface that reads bundle metadata.

All steps are best-effort: if a dependency is missing we silently skip that
step rather than blowing up at startup.

This must run BEFORE any code that initializes AppKit (notably ``pynput`` on
macOS), otherwise the menu bar latches the original "Python" name.
"""

from __future__ import annotations

import contextlib
import sys

DEFAULT_NAME = "voiceprompt"

_APPLIED = False


def apply(name: str = DEFAULT_NAME) -> None:
    """Idempotently rename the current process. Safe to call multiple times."""
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    # 1. Process name visible to ps / top / Activity Monitor.
    try:
        import setproctitle  # type: ignore[import-not-found]  # noqa: PLC0415

        setproctitle.setproctitle(name)
    except Exception:  # noqa: BLE001 -- optional best-effort
        pass

    # 2 + 3. macOS-specific AppKit / Bundle metadata. Foundation comes from
    # PyObjC, which pynput already depends on on macOS, so importing it here
    # adds no extra wheel.
    if sys.platform == "darwin":
        try:
            from Foundation import (  # type: ignore[import-not-found]  # noqa: PLC0415
                NSBundle,
                NSProcessInfo,
            )

            with contextlib.suppress(Exception):
                NSProcessInfo.processInfo().setProcessName_(name)

            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info is not None:
                # Both keys are read by different macOS subsystems (menu bar vs.
                # alerts/dialogs/permission prompts), so set both.
                info["CFBundleName"] = name
                info["CFBundleDisplayName"] = name
        except Exception:  # noqa: BLE001 -- optional best-effort
            pass
