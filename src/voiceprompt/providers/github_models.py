"""GitHub Models client. Reformulates transcribed text into a clean prompt.

This is the right integration point for people who want to use their GitHub /
Copilot ecosystem from voiceprompt: GitHub Models exposes a documented REST
inference API, while Copilot Chat itself is not a generic application API.
"""

from __future__ import annotations

import json
import re
import time
from urllib import error, request

from voiceprompt.config import Config
from voiceprompt.reformulator import AuthError, ProviderError, QuotaExceededError

API_URL = "https://models.github.ai/inference/chat/completions"
API_VERSION = "2026-03-10"
REQUEST_TIMEOUT_SECS = 30

# Curated GitHub Models IDs. Users can also edit ``github_models_model`` in
# config.json to use any catalog model their account has access to.
MODELS: list[tuple[str, str]] = [
    ("openai/gpt-4o-mini", "fast and stable (recommended)"),
    ("openai/gpt-5-mini", "cost-efficient, but stricter API parameters"),
    ("openai/gpt-4.1", "strong instruction following"),
    ("openai/gpt-5.4-nano", "fastest OpenAI nano option if enabled"),
]

DEFAULT_MAX_RETRIES = 3
MAX_RETRY_SLEEP_SECS = 10.0
INITIAL_BACKOFF_SECS = 1.0
MAX_BACKOFF_SECS = 8.0

_TOKEN_PREFIXES = ("github_pat_", "ghp_", "gho_", "ghs_", "ghu_", "ghr_")
_SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r'"[Aa]uthorization"\s*:\s*"[^"]+"'),
)


class GithubModelsError(ProviderError):
    """Base error for GitHub Models-specific failures."""


def looks_like_github_token(value: str) -> bool:
    """Best-effort sanity check for a GitHub token / PAT."""
    v = value.strip()
    return any(v.startswith(prefix) for prefix in _TOKEN_PREFIXES) and len(v) > 16


def _redact(message: str) -> str:
    out = message
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("***", out)
    return out


def _token(cfg: Config) -> str:
    token = cfg.github_models_token.strip()
    if not token:
        raise AuthError("GitHub Models token is not configured.")
    return token


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


def _retry_after(err: error.HTTPError) -> float | None:
    headers = getattr(err, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _classify_http_error(err: error.HTTPError) -> ProviderError:
    msg = _redact(_http_error_message(err))
    if err.code in (401, 403):
        return AuthError(msg)
    if err.code == 429:
        return QuotaExceededError(msg, retry_after=_retry_after(err))
    return GithubModelsError(msg)


def _http_error_message(err: error.HTTPError) -> str:
    """Return status plus response body when GitHub provides useful JSON detail."""
    try:
        body = err.read().decode("utf-8", "replace").strip()
    except (AttributeError, OSError, UnicodeDecodeError):
        body = ""
    if body:
        return f"{err}\n{body}"
    return str(err)


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _post_chat_completion(
    cfg: Config,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    body = {
        "model": cfg.github_models_model,
        "messages": messages,
    }
    if _supports_temperature(cfg.github_models_model):
        body["temperature"] = cfg.temperature
    token_limit_key = _token_limit_key(cfg.github_models_model)
    body[token_limit_key] = max_tokens
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        API_URL,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_token(cfg)}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )

    with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    text = _extract_text(payload)
    if not text:
        raise GithubModelsError("GitHub Models returned an empty response.")
    return text


def _token_limit_key(model_id: str) -> str:
    """GPT-5-family OpenAI models reject ``max_tokens``; older models use it."""
    model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id
    return "max_completion_tokens" if model_name.startswith("gpt-5") else "max_tokens"


def _supports_temperature(model_id: str) -> bool:
    """GPT-5-family OpenAI models only allow their default temperature."""
    model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id
    return not model_name.startswith("gpt-5")


def reformulate_text(
    transcript: str,
    cfg: Config,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Send transcript to GitHub Models. Returns the reformulated prompt."""
    user_text = _user_message(transcript, cfg.language)
    messages = [
        {"role": "system", "content": cfg.system_prompt},
        {"role": "user", "content": user_text},
    ]

    delay = INITIAL_BACKOFF_SECS
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return _post_chat_completion(
                cfg,
                messages=messages,
                max_tokens=cfg.max_output_tokens,
            )
        except error.HTTPError as e:
            last_error = e
            classified = _classify_http_error(e)
            if isinstance(classified, AuthError):
                raise classified from e
            if isinstance(classified, QuotaExceededError):
                if attempt == max_retries - 1:
                    raise classified from e
                time.sleep(min(classified.retry_after or delay, MAX_RETRY_SLEEP_SECS))
            else:
                if e.code < 500 or attempt == max_retries - 1:
                    raise classified from e
                time.sleep(delay)
        except (error.URLError, TimeoutError) as e:
            last_error = e
            if attempt == max_retries - 1:
                raise GithubModelsError(
                    f"GitHub Models transient error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)

        delay = min(delay * 2, MAX_BACKOFF_SECS)

    raise GithubModelsError(
        _redact(str(last_error)) if last_error else "Unknown GitHub Models failure."
    )


def _stream_chat_completion(cfg: Config, *, messages: list[dict[str, str]], max_tokens: int):
    """Yield incremental text chunks via SSE from the GitHub Models streaming endpoint."""
    body = {
        "model": cfg.github_models_model,
        "messages": messages,
        "stream": True,
    }
    if _supports_temperature(cfg.github_models_model):
        body["temperature"] = cfg.temperature
    token_limit_key = _token_limit_key(cfg.github_models_model)
    body[token_limit_key] = max_tokens
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        API_URL,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_token(cfg)}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECS) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", "replace").rstrip("\n\r")
            if not line.startswith("data: "):
                continue
            payload_str = line[6:]
            if payload_str.strip() == "[DONE]":
                break
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
            content = delta.get("content", "") if isinstance(delta, dict) else ""
            if content:
                yield content


def reformulate_text_stream(transcript: str, cfg: Config):
    """Yield incremental text chunks from GitHub Models."""
    user_text = _user_message(transcript, cfg.language)
    messages = [
        {"role": "system", "content": cfg.system_prompt},
        {"role": "user", "content": user_text},
    ]
    delay = INITIAL_BACKOFF_SECS
    last_error: BaseException | None = None
    for attempt in range(DEFAULT_MAX_RETRIES):
        try:
            yield from _stream_chat_completion(cfg, messages=messages, max_tokens=cfg.max_output_tokens)
            return
        except error.HTTPError as e:
            last_error = e
            classified = _classify_http_error(e)
            if isinstance(classified, AuthError):
                raise classified from e
            if isinstance(classified, QuotaExceededError):
                if attempt == DEFAULT_MAX_RETRIES - 1:
                    raise classified from e
                time.sleep(min(classified.retry_after or delay, MAX_RETRY_SLEEP_SECS))
            else:
                if e.code < 500 or attempt == DEFAULT_MAX_RETRIES - 1:
                    raise classified from e
                time.sleep(delay)
        except (error.URLError, TimeoutError) as e:
            last_error = e
            if attempt == DEFAULT_MAX_RETRIES - 1:
                raise GithubModelsError(
                    f"GitHub Models transient error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)
        delay = min(delay * 2, MAX_BACKOFF_SECS)
    raise GithubModelsError(_redact(str(last_error)) if last_error else "Unknown GitHub Models failure.")


def quick_test(cfg: Config) -> str:
    """Tiny round-trip to verify the token/model work. Returns the model response."""
    try:
        return _post_chat_completion(
            cfg,
            messages=[{"role": "user", "content": "Reply with exactly the word: OK"}],
            max_tokens=20,
        )
    except error.HTTPError as e:
        raise _classify_http_error(e) from e
    except (error.URLError, TimeoutError) as e:
        raise GithubModelsError(f"GitHub Models transient error: {_redact(str(e))}") from e
