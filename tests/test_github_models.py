from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from voiceprompt import github_models
from voiceprompt.config import Config
from voiceprompt.reformulator import AuthError, QuotaExceededError


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info) -> None:  # noqa: ANN002
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class GithubModelsProviderTests(unittest.TestCase):
    def test_reformulate_posts_chat_completion_to_github_models(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {"choices": [{"message": {"content": "Refined prompt"}}]}
            )

        cfg = Config(
            provider="github_models",
            github_models_token="github_pat_1234567890",
            github_models_model="openai/gpt-5-mini",
            system_prompt="Rewrite cleanly.",
            max_output_tokens=123,
            temperature=0.2,
        )

        with patch.object(github_models.request, "urlopen", side_effect=fake_urlopen):
            result = github_models.reformulate_text("hola mundo", cfg, max_retries=1)

        self.assertEqual(result, "Refined prompt")
        self.assertEqual(
            captured["url"],
            "https://models.github.ai/inference/chat/completions",
        )
        self.assertEqual(captured["timeout"], github_models.REQUEST_TIMEOUT_SECS)
        self.assertEqual(
            captured["headers"]["Authorization"],
            "Bearer github_pat_1234567890",
        )
        self.assertEqual(captured["payload"]["model"], "openai/gpt-5-mini")
        self.assertEqual(captured["payload"]["max_completion_tokens"], 123)
        self.assertNotIn("max_tokens", captured["payload"])
        self.assertNotIn("temperature", captured["payload"])
        self.assertEqual(
            captured["payload"]["messages"],
            [
                {"role": "system", "content": "Rewrite cleanly."},
                {
                    "role": "user",
                    "content": (
                        "Rewrite the following transcription into one clean prompt, "
                        "keeping the speaker's original language.\n\n---\nhola mundo\n---"
                    ),
                },
            ],
        )

    def test_quick_test_uses_short_ok_prompt(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "OK"}}]})

        cfg = Config(
            github_models_token="github_pat_1234567890",
            github_models_model="openai/gpt-5-mini",
        )

        with patch.object(github_models.request, "urlopen", side_effect=fake_urlopen):
            result = github_models.quick_test(cfg)

        self.assertEqual(result, "OK")
        self.assertEqual(
            captured["payload"]["messages"],
            [{"role": "user", "content": "Reply with exactly the word: OK"}],
        )
        self.assertEqual(captured["payload"]["max_completion_tokens"], 20)
        self.assertNotIn("max_tokens", captured["payload"])

    def test_gpt4_models_use_legacy_max_tokens_parameter(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "OK"}}]})

        cfg = Config(
            github_models_token="github_pat_1234567890",
            github_models_model="openai/gpt-4.1",
        )

        with patch.object(github_models.request, "urlopen", side_effect=fake_urlopen):
            result = github_models.quick_test(cfg)

        self.assertEqual(result, "OK")
        self.assertEqual(captured["payload"]["max_tokens"], 20)
        self.assertNotIn("max_completion_tokens", captured["payload"])
        self.assertEqual(captured["payload"]["temperature"], cfg.temperature)

    def test_missing_token_raises_auth_error(self) -> None:
        with self.assertRaises(AuthError):
            github_models.reformulate_text("hi", Config(), max_retries=1)

    def test_unauthorized_http_error_maps_to_auth_error(self) -> None:
        err = HTTPError(
            github_models.API_URL,
            401,
            "Unauthorized github_pat_secret",
            hdrs={},
            fp=None,
        )

        cfg = Config(github_models_token="github_pat_secret")
        with (
            patch.object(github_models.request, "urlopen", side_effect=err),
            self.assertRaises(AuthError) as raised,
        ):
            github_models.quick_test(cfg)

        self.assertNotIn("github_pat_secret", str(raised.exception))

    def test_rate_limit_http_error_maps_to_quota_error(self) -> None:
        err = HTTPError(
            github_models.API_URL,
            429,
            "rate limited",
            hdrs={"retry-after": "3"},
            fp=None,
        )

        cfg = Config(github_models_token="github_pat_1234567890")
        with (
            patch.object(github_models.request, "urlopen", side_effect=err),
            self.assertRaises(QuotaExceededError) as raised,
        ):
            github_models.quick_test(cfg)

        self.assertEqual(raised.exception.retry_after, 3.0)

    def test_http_error_includes_sanitized_response_body(self) -> None:
        err = HTTPError(
            github_models.API_URL,
            400,
            "Bad Request",
            hdrs={},
            fp=io.BytesIO(
                b'{"error":{"message":"Unsupported parameter: max_tokens for github_pat_secret"}}'
            ),
        )

        cfg = Config(github_models_token="github_pat_secret")
        with (
            patch.object(github_models.request, "urlopen", side_effect=err),
            self.assertRaises(github_models.GithubModelsError) as raised,
        ):
            github_models.quick_test(cfg)

        message = str(raised.exception)
        self.assertIn("Unsupported parameter: max_tokens", message)
        self.assertNotIn("github_pat_secret", message)


if __name__ == "__main__":
    unittest.main()
