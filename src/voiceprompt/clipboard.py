"""Cross-platform clipboard helper. Wraps pyperclip with graceful fallback."""

from __future__ import annotations

import pyperclip


class ClipboardError(Exception):
    pass


def copy(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success, False otherwise.

    On Linux without xclip/xsel installed, pyperclip raises PyperclipException.
    We swallow it and return False so the caller can show a helpful message.
    """
    try:
        pyperclip.copy(text)
        return True
    except Exception:  # noqa: BLE001 — pyperclip raises a custom exception we don't want to import
        return False


def paste() -> str:
    try:
        return pyperclip.paste()
    except Exception as e:  # noqa: BLE001
        raise ClipboardError(str(e)) from e
