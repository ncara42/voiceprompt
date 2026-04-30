from __future__ import annotations

import unittest
from unittest.mock import patch

from voiceprompt import menu, recorder
from voiceprompt.config import Config


class FakeConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *objects, **kwargs) -> None:  # noqa: ARG002
        self.messages.append(" ".join(str(obj) for obj in objects))


class DictateActionTests(unittest.TestCase):
    def test_no_input_device_shows_short_user_message(self) -> None:
        class RecorderWithoutInput:
            def __init__(self, *, sample_rate: int) -> None:
                self.sample_rate = sample_rate

            def start(self) -> None:
                raise recorder.NoInputDeviceError()

        fake_console = FakeConsole()

        with (
            patch.object(menu, "console", fake_console),
            patch.object(menu, "_ensure_transcription_model_downloaded", return_value=True),
            patch.object(menu.recorder, "Recorder", RecorderWithoutInput),
        ):
            menu._action_dictate(Config(), exit_after=True)

        self.assertEqual(
            fake_console.messages[-1],
            "  [err][!] No audio input found.[/err]",
        )


if __name__ == "__main__":
    unittest.main()
