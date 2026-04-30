from __future__ import annotations

import unittest
from unittest.mock import patch

from voiceprompt import reformulator
from voiceprompt.config import Config


class ReformulatorDispatchTests(unittest.TestCase):
    def test_default_provider_is_claude(self) -> None:
        cfg = Config()
        self.assertEqual(reformulator.active_provider(cfg), "claude")
        self.assertEqual(reformulator.active_model(cfg), cfg.model)

    def test_invalid_provider_falls_back_to_claude(self) -> None:
        cfg = Config(provider="bogus")  # type: ignore[arg-type]
        self.assertEqual(reformulator.active_provider(cfg), "claude")

    def test_short_model_for_claude_compacts_id(self) -> None:
        cfg = Config(model="claude-haiku-4-5-20251001")
        self.assertEqual(reformulator.short_model(cfg), "haiku 4.5")

    def test_short_model_for_ollama_uses_ollama_model(self) -> None:
        cfg = Config(provider="ollama", ollama_model="gpt-oss:120b")
        self.assertEqual(reformulator.short_model(cfg), "gpt-oss:120b")

    def test_reformulate_dispatches_to_claude(self) -> None:
        cfg = Config(anthropic_api_key="x")
        with patch("voiceprompt.providers.claude.reformulate_text", return_value="C") as m:
            self.assertEqual(reformulator.reformulate_text("hi", cfg), "C")
        m.assert_called_once_with("hi", cfg)

    def test_reformulate_dispatches_to_ollama(self) -> None:
        cfg = Config(provider="ollama", ollama_api_key="x")
        with patch("voiceprompt.providers.ollama.reformulate_text", return_value="O") as m:
            self.assertEqual(reformulator.reformulate_text("hi", cfg), "O")
        m.assert_called_once_with("hi", cfg)

    def test_reformulate_dispatches_to_gemini(self) -> None:
        cfg = Config(provider="gemini", gemini_api_key="x")
        with patch("voiceprompt.providers.gemini.reformulate_text", return_value="G") as m:
            self.assertEqual(reformulator.reformulate_text("hi", cfg), "G")
        m.assert_called_once_with("hi", cfg)

    def test_reformulate_dispatches_to_github_models(self) -> None:
        cfg = Config(provider="github_models", github_models_token="github_pat_x")
        with patch("voiceprompt.providers.github_models.reformulate_text", return_value="GH") as m:
            self.assertEqual(reformulator.reformulate_text("hi", cfg), "GH")
        m.assert_called_once_with("hi", cfg)

    def test_short_model_for_gemini_uses_gemini_model(self) -> None:
        cfg = Config(provider="gemini", gemini_model="gemini-2.5-flash")
        self.assertEqual(reformulator.short_model(cfg), "gemini-2.5-flash")

    def test_short_model_for_github_models_strips_publisher(self) -> None:
        cfg = Config(provider="github_models", github_models_model="openai/gpt-5-mini")
        self.assertEqual(reformulator.short_model(cfg), "gpt-5-mini")


class ConfigProviderTests(unittest.TestCase):
    def test_is_configured_checks_active_provider_key(self) -> None:
        cfg = Config(provider="claude", anthropic_api_key="sk-ant-x", ollama_api_key="")
        self.assertTrue(cfg.is_configured)

        cfg = Config(provider="ollama", anthropic_api_key="sk-ant-x", ollama_api_key="")
        self.assertFalse(cfg.is_configured)

        cfg = Config(provider="ollama", ollama_api_key="abc")
        self.assertTrue(cfg.is_configured)

        cfg = Config(provider="gemini", gemini_api_key="AIzaTest123")
        self.assertTrue(cfg.is_configured)

        cfg = Config(provider="gemini", anthropic_api_key="sk-ant-x", gemini_api_key="")
        self.assertFalse(cfg.is_configured)

        cfg = Config(provider="github_models", github_models_token="github_pat_x")
        self.assertTrue(cfg.is_configured)

        cfg = Config(
            provider="github_models",
            anthropic_api_key="sk-ant-x",
            github_models_token="",
        )
        self.assertFalse(cfg.is_configured)

    def test_github_provider_alias_normalizes_to_github_models(self) -> None:
        self.assertEqual(reformulator.normalize("github"), "github_models")


if __name__ == "__main__":
    unittest.main()
