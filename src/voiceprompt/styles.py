"""Shared rich console, theme, and banner."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

theme = Theme(
    {
        "brand": "bold magenta",
        "brand2": "magenta",
        "accent": "bold cyan",
        "accent2": "cyan",
        "ok": "bold green",
        "ok2": "green",
        "warn": "yellow",
        "err": "bold red",
        "hint": "dim",
        "subtle": "grey50",
        "label": "cyan",
        "value": "white",
        "rule": "magenta",
        "kbd": "reverse white",
        "section": "bold dim",
        "muted": "grey50",
        "good": "green",
        "bad": "red",
    }
)

console = Console(theme=theme)


def banner(version: str = "") -> None:
    """Print the app banner. `version` is shown in the corner if provided."""
    title = Text()
    title.append("voice", style="brand")
    title.append("prompt", style="accent")
    if version:
        title.append(f"   v{version}", style="hint")

    subtitle = Text("Speak. AI refines. Paste.", style="subtle")

    body = Text("\n").join([title, subtitle])

    console.print()
    console.print(
        Panel(
            body,
            border_style="rule",
            padding=(0, 2),
            expand=False,
        )
    )
    console.print()
