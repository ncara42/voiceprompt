"""Ollama Cloud client. Reformulates a transcribed text into a clean prompt.

Talks to https://ollama.com using the official ``ollama`` Python SDK with a
Bearer-token API key. All public errors raised here are sanitized -- they never
include the API key or the raw request body, only the upstream status/code and a
short message.
"""

from __future__ import annotations

import re
import time

import httpx
import ollama as ollama_sdk

from voiceprompt.config import Config
from voiceprompt.reformulator import AuthError, ProviderError, QuotaExceededError

CLOUD_HOST = "https://ollama.com"

# Curated catalog of cloud-hosted models. Users can also edit ``ollama_model``
# in their config.json to use any model the account has access to.
MODELS: list[tuple[str, str]] = [
    ("gpt-oss:20b", "fast and cheap"),
    ("gpt-oss:120b", "balanced (recommended)"),
    ("qwen3-coder:480b", "specialised for code"),
    ("deepseek-v3.1:671b", "maximum quality, slowest"),
]

# How many retries to attempt on transient failures (5xx, connection drops, 429).
DEFAULT_MAX_RETRIES = 3
MAX_RETRY_SLEEP_SECS = 10.0
INITIAL_BACKOFF_SECS = 1.0
MAX_BACKOFF_SECS = 8.0

# Heuristic: Ollama keys today are long random tokens with no fixed prefix, so
# we just check that the value is non-empty and reasonably long.
_MIN_KEY_LENGTH = 16

_SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r'"[Aa]uthorization"\s*:\s*"[^"]+"'),
)


class OllamaError(ProviderError):
    """Base error for Ollama-related failures."""


def looks_like_ollama_key(value: str) -> bool:
    """Best-effort sanity check for an Ollama Cloud API key."""
    return len(value.strip()) >= _MIN_KEY_LENGTH


def _redact(message: str) -> str:
    out = message
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("***", out)
    return out


def _client(cfg: Config) -> ollama_sdk.Client:
    if not cfg.ollama_api_key:
        raise AuthError("Ollama API key is not configured.")
    return ollama_sdk.Client(
        host=CLOUD_HOST,
        headers={"Authorization": f"Bearer {cfg.ollama_api_key}"},
    )


def _user_message(transcript: str, language_hint: str) -> str:
    if language_hint == "auto":
        return (
            "Rewrite the following transcription into one clean prompt, "
            "keeping the speaker's original language.\n\n"
            f"---\n{transcript}\n---"
        )
    return (
        f"Rewrite the following transcription (language: {language_hint}) into one "
        f"clean prompt.\n\n---\n{transcript}\n---"
    )


def _extract_text(response) -> str:  # noqa: ANN001 -- ollama SDK return type varies
    msg = getattr(response, "message", None)
    if msg is None:
        return ""
    content = getattr(msg, "content", "") or ""
    return content.strip()


def _status_code(err: BaseException) -> int | None:
    response = getattr(err, "response", None)
    code = getattr(response, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(err, "status_code", None)
    return code if isinstance(code, int) else None


def _retry_after(err: BaseException) -> float | None:
    response = getattr(err, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _classify(err: BaseException) -> ProviderError:
    """Map an upstream exception to one of our sanitized provider errors."""
    msg = _redact(str(err))
    code = _status_code(err)
    if code in (401, 403):
        return AuthError(msg)
    if code == 429:
        return QuotaExceededError(msg, retry_after=_retry_after(err))
    return OllamaError(msg)


def reformulate_text(
    transcript: str,
    cfg: Config,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Send transcript to Ollama Cloud. Returns the reformulated prompt."""
    client = _client(cfg)
    user_text = _user_message(transcript, cfg.language)

    delay = INITIAL_BACKOFF_SECS
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            response = client.chat(
                model=cfg.ollama_model,
                messages=[
                    {"role": "system", "content": cfg.system_prompt},
                    {"role": "user", "content": user_text},
                ],
                options={
                    "temperature": cfg.temperature,
                    "num_predict": cfg.max_output_tokens,
                },
                stream=False,
            )
            text = _extract_text(response)
            if not text:
                raise OllamaError("Ollama returned an empty response.")
            return text

        except ollama_sdk.ResponseError as e:
            last_error = e
            classified = _classify(e)
            if isinstance(classified, AuthError):
                raise classified from e
            if isinstance(classified, QuotaExceededError):
                if attempt == max_retries - 1:
                    raise classified from e
                time.sleep(min(classified.retry_after or delay, MAX_RETRY_SLEEP_SECS))
            else:
                if attempt == max_retries - 1:
                    raise classified from e
                time.sleep(delay)
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException) as e:
            last_error = e
            if attempt == max_retries - 1:
                raise OllamaError(
                    f"Ollama transient error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)

        delay = min(delay * 2, MAX_BACKOFF_SECS)

    raise OllamaError(_redact(str(last_error)) if last_error else "Unknown Ollama failure.")


def quick_test(cfg: Config) -> str:
    """Tiny round-trip to verify the API key/model work. Returns Ollama's response."""
    client = _client(cfg)
    try:
        response = client.chat(
            model=cfg.ollama_model,
            messages=[{"role": "user", "content": "Reply with exactly the word: OK"}],
            options={"num_predict": 20},
            stream=False,
        )
    except ollama_sdk.ResponseError as e:
        raise _classify(e) from e
    except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException) as e:
        raise OllamaError(f"Ollama transient error: {_redact(str(e))}") from e

    return _extract_text(response)
