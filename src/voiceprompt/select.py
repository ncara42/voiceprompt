"""Custom interactive list selector + password input built on prompt_toolkit.

Selector bindings:
  up / down (or k/j) -> navigate (skips Separator rows)
  right / enter      -> confirm selection (returns the chosen value)
  left / esc / q     -> go back (returns the `back_value`, or None)
  ctrl+c             -> raises KeyboardInterrupt

A row can be either a ``Choice`` (selectable) or a ``Separator`` (a non-selectable
divider used to group choices into visual sections). Choices may carry an optional
``hint`` rendered in a muted column on the right.

Password input bindings:
  enter              -> return the typed value
  esc                -> return None (cancel)
  ctrl+c             -> raises KeyboardInterrupt
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

T = TypeVar("T")

POINTER = "›"
INDENT = "  "
HINT_GAP = 3  # visible columns of padding between label and hint

PT_STYLE = Style.from_dict(
    {
        "title": "fg:ansiwhite bold",
        "pointer": "fg:ansimagenta bold",
        "active": "fg:ansicyan bold",
        "inactive": "",
        "hint": "fg:ansibrightblack",
        "section": "fg:ansibrightblack bold",
        "rule": "fg:ansibrightblack",
        "kbd": "reverse",
    }
)


@dataclass
class Choice(Generic[T]):
    label: str
    value: T
    hint: str = ""
    disabled: bool = False  # rendered but unselectable; useful for read-only rows


@dataclass
class Separator:
    """Non-selectable row. ``label`` empty → faint divider; otherwise → section header."""

    label: str = ""


def _is_selectable(item: object) -> bool:
    return isinstance(item, Choice) and not item.disabled


class _SelectState(Generic[T]):
    def __init__(
        self,
        title: str,
        choices: list,
        default_value: T | None,
        back_value: T | None,
        footer: bool,
    ) -> None:
        self.title = title
        self.choices = choices
        self.back_value = back_value
        self.footer = footer

        # First selectable index becomes the initial cursor position.
        self.index = next(
            (i for i, c in enumerate(choices) if _is_selectable(c)),
            0,
        )
        if default_value is not None:
            for i, c in enumerate(choices):
                if isinstance(c, Choice) and c.value == default_value and not c.disabled:
                    self.index = i
                    break

        # Pre-compute hint alignment column once; padding is in characters
        # (works for the latin-only labels this app uses).
        self._hint_column = max(
            (len(c.label) for c in choices if isinstance(c, Choice) and c.hint),
            default=0,
        )

    def _step(self, direction: int) -> None:
        n = len(self.choices)
        if n == 0:
            return
        i = (self.index + direction) % n
        for _ in range(n):
            if _is_selectable(self.choices[i]):
                self.index = i
                return
            i = (i + direction) % n

    def render(self) -> FormattedText:
        lines: list[tuple[str, str]] = []
        if self.title:
            lines.append(("class:title", f"{INDENT}{self.title}\n\n"))

        for i, item in enumerate(self.choices):
            if isinstance(item, Separator):
                if item.label:
                    # Section header: blank line above for breathing room.
                    lines.append(("", "\n"))
                    lines.append(("class:section", f"{INDENT}{item.label.upper()}\n"))
                else:
                    # Plain spacer.
                    lines.append(("", "\n"))
                continue

            choice: Choice = item  # type: ignore[assignment]
            is_active = i == self.index
            label = choice.label

            if choice.disabled:
                lines.append(("", f"{INDENT}  "))
                lines.append(("class:hint", label))
            elif is_active:
                lines.append(("class:pointer", f"{INDENT}{POINTER} "))
                lines.append(("class:active", label))
            else:
                lines.append(("", f"{INDENT}  "))
                lines.append(("class:inactive", label))

            if choice.hint:
                pad = max(self._hint_column - len(label), 0) + HINT_GAP
                lines.append(("", " " * pad))
                lines.append(("class:hint", choice.hint))

            lines.append(("", "\n"))

        if self.footer:
            lines.append(("", "\n"))
            lines.append(("", f"{INDENT}"))
            lines.append(("class:kbd", " ↑ "))
            lines.append(("class:kbd", " ↓ "))
            lines.append(("class:hint", "  navigate    "))
            lines.append(("class:kbd", " ↵ "))
            lines.append(("class:hint", "  select    "))
            lines.append(("class:kbd", " esc "))
            lines.append(("class:hint", "  back"))
        return FormattedText(lines)


def select(
    title: str,
    choices: list,
    *,
    default: T | None = None,
    back_value: T | None = None,
    can_go_back: bool = True,
    show_footer: bool = True,
) -> T | None:
    """Show an interactive list. Returns the selected value, ``back_value``, or None on ctrl+c.

    ``choices`` accepts a mix of ``Choice`` (selectable) and ``Separator`` rows.
    ``back_value`` is what gets returned when the user presses left / esc / q.
    Set ``can_go_back=False`` to disable left/esc/q (useful for top-level menus).
    Set ``show_footer=False`` to hide the keyboard hints (useful for nested screens).
    """
    if not any(_is_selectable(c) for c in choices):
        return None

    state: _SelectState[T] = _SelectState(title, choices, default, back_value, show_footer)

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _(event):  # noqa: ARG001
        state._step(-1)

    @kb.add("down")
    @kb.add("j")
    def _(event):  # noqa: ARG001
        state._step(1)

    @kb.add("home")
    def _(event):  # noqa: ARG001
        first = next((i for i, c in enumerate(state.choices) if _is_selectable(c)), 0)
        state.index = first

    @kb.add("end")
    def _(event):  # noqa: ARG001
        last = next(
            (i for i in range(len(state.choices) - 1, -1, -1) if _is_selectable(state.choices[i])),
            len(state.choices) - 1,
        )
        state.index = last

    @kb.add("enter")
    @kb.add("right")
    @kb.add("l")
    def _(event):
        item = state.choices[state.index]
        if isinstance(item, Choice) and not item.disabled:
            event.app.exit(result=item.value)

    if can_go_back:

        @kb.add("left")
        @kb.add("escape")
        @kb.add("q")
        @kb.add("h")
        def _(event):
            event.app.exit(result=back_value)

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt)

    control = FormattedTextControl(text=state.render, focusable=True, show_cursor=False)
    layout = Layout(HSplit([Window(content=control, always_hide_cursor=True)]))

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        style=PT_STYLE,
        full_screen=False,
        mouse_support=False,
    )
    return app.run()


def wait_continue(message: str = "record again") -> bool:
    """Wait for the user to press a key. True = continue (Enter), False = quit (Esc/q/Ctrl+C)."""
    from prompt_toolkit import Application as PTApplication  # noqa: PLC0415
    from prompt_toolkit.formatted_text import FormattedText as FT  # noqa: PLC0415

    state = {"go": True}

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        state["go"] = True
        event.app.exit()

    @kb.add("escape", eager=True)
    @kb.add("q")
    @kb.add("c-c")
    def _(event):
        state["go"] = False
        event.app.exit()

    text = FT(
        [
            ("", "  "),
            ("class:kbd", " ↵ "),
            ("class:hint", f"  {message}    "),
            ("class:kbd", " esc "),
            ("class:hint", "  quit"),
        ]
    )

    pt_style = Style.from_dict(
        {
            "kbd": "reverse",
            "hint": "fg:ansibrightblack",
        }
    )

    control = FormattedTextControl(text=text, focusable=True, show_cursor=False)
    layout = Layout(HSplit([Window(content=control, height=1)]))
    app: PTApplication = PTApplication(
        layout=layout, key_bindings=kb, style=pt_style, full_screen=False
    )
    app.run()
    return state["go"]


def password_input(message: str) -> str | None:
    """Read a hidden line of text. Returns the string, or None if Esc/empty was pressed."""
    from prompt_toolkit import prompt as pt_prompt  # noqa: PLC0415
    from prompt_toolkit.formatted_text import FormattedText as FT  # noqa: PLC0415

    kb = KeyBindings()

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=None)

    prompt_text = FT(
        [
            ("class:qmark", "?  "),
            ("class:question", message),
            ("", " "),
        ]
    )

    pt_style = Style.from_dict(
        {
            "qmark": "fg:ansimagenta bold",
            "question": "bold",
            "hint": "fg:ansibrightblack",
        }
    )

    # Print the hint inline — bottom_toolbar pins it to the screen bottom
    # and leaves a blank sea of whitespace in between.
    hint = FT([("class:hint", "  ↵ confirm    esc cancel    ctrl+c quit\n")])
    from prompt_toolkit import print_formatted_text  # noqa: PLC0415
    print_formatted_text(hint, style=pt_style)

    try:
        result = pt_prompt(
            prompt_text,
            is_password=True,
            key_bindings=kb,
            style=pt_style,
        )
    except EOFError:
        return None
    if result is None or result == "":
        return None
    return result
