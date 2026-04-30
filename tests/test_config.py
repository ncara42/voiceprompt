from __future__ import annotations

import json
import tempfile
import unittest
from base64 import b64decode
from pathlib import Path
from unittest.mock import patch

from voiceprompt import config

LEGACY_DEFAULT_PROMPT_B64 = (
    "RXJlcyB1biByZWZvcm11bGFkb3IgZGUgcHJvbXB0cyBwYXJhIGFzaXN0ZW50ZXMgZGUgcHJv"
    "Z3JhbWFjacOzbiBjb21vIENsYXVkZSBDb2RlLiBSZWNpYmlyw6FzIHVuYSB0cmFuc2NyaXBj"
    "acOzbiBkZSB2b3ogZGljdGFkYSBxdWUgcHVlZGUgdGVuZXIgbXVsZXRpbGxhcywgcmVwZXRp"
    "Y2lvbmVzIG8gZnJhc2VzIGFtYmlndWFzLiBEZXZ1ZWx2ZSBVTiDDum5pY28gcHJvbXB0IGNs"
    "YXJvLCBkaXJlY3RvIHkgYmllbiBlc3RydWN0dXJhZG8gZW4gZWwgbWlzbW8gaWRpb21hIGRl"
    "bCB1c3VhcmlvLCBsaXN0byBwYXJhIGVudmlhciBhIHVuIGFzaXN0ZW50ZSBkZSBjb2Rpbmcu"
    "IERldnVlbHZlIEVYQ0xVU0lWQU1FTlRFIGVsIHByb21wdCBmaW5hbCDigJQgc2luIHByZcOh"
    "bWJ1bG9zLCBzaW4gZXhwbGljYWNpb25lcywgc2luIG1ldGEtY29tZW50YXJpb3Mu"
)


class ConfigLoadTests(unittest.TestCase):
    def test_load_migrates_legacy_spanish_default_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            legacy_prompt = b64decode(LEGACY_DEFAULT_PROMPT_B64).decode("utf-8")
            path.write_text(
                json.dumps({"system_prompt": legacy_prompt}),
                encoding="utf-8",
            )

            with patch.object(config, "config_path", return_value=path):
                loaded = config.load()

        self.assertEqual(loaded.system_prompt, config.DEFAULT_SYSTEM_PROMPT)

    def test_load_drops_legacy_whisper_model_field(self) -> None:
        """Old configs storing whisper_model: 'small' under the pre-0.2 key
        should fall back to the current default (the legacy key is no longer
        recognised by the dataclass)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps({"whisper_model": "small"}),
                encoding="utf-8",
            )

            with patch.object(config, "config_path", return_value=path):
                loaded = config.load()

        self.assertEqual(loaded.transcription_model, config.DEFAULT_TRANSCRIPTION_MODEL)

    def test_load_migrates_parakeet_model_to_whisper_default(self) -> None:
        """Configs from the Parakeet era ('mlx-community/parakeet-...') must
        be migrated to the new faster-whisper default — those ids cannot be
        loaded by the current transcriber."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps({"transcription_model": "mlx-community/parakeet-tdt-0.6b-v3"}),
                encoding="utf-8",
            )

            with patch.object(config, "config_path", return_value=path):
                loaded = config.load()

        self.assertEqual(loaded.transcription_model, config.DEFAULT_TRANSCRIPTION_MODEL)

    def test_load_prefills_github_models_token_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"

            with (
                patch.object(config, "config_path", return_value=path),
                patch.dict("os.environ", {"GITHUB_MODELS_TOKEN": "github_pat_env"}, clear=True),
            ):
                loaded = config.load()

        self.assertEqual(loaded.github_models_token, "github_pat_env")

    def test_load_accepts_github_models_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps({"provider": "github_models"}),
                encoding="utf-8",
            )

            with patch.object(config, "config_path", return_value=path):
                loaded = config.load()

        self.assertEqual(loaded.provider, "github_models")

    def test_default_github_models_model_prioritizes_fast_stable_model(self) -> None:
        self.assertEqual(config.Config().github_models_model, "openai/gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
