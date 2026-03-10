from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .context import compress_context


PROVIDER_OPENAI = "openai"
PROVIDER_QWEN = "qwen"
PROVIDER_GEMINI = "gemini"
PROVIDER_OLLAMA = "ollama"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen-plus-latest"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"


@dataclass
class ExternalAIConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    max_context_chars: int = 12000

    @classmethod
    def from_env(cls) -> ExternalAIConfig:
        provider = os.environ.get("GEOCLAW_AI_PROVIDER", PROVIDER_OPENAI).strip().lower() or PROVIDER_OPENAI
        if provider not in {PROVIDER_OPENAI, PROVIDER_QWEN, PROVIDER_GEMINI, PROVIDER_OLLAMA}:
            raise ValueError("GEOCLAW_AI_PROVIDER must be one of: openai, qwen, gemini, ollama")

        if provider == PROVIDER_QWEN:
            default_base_url = DEFAULT_QWEN_BASE_URL
            default_model = DEFAULT_QWEN_MODEL
            provider_key = os.environ.get("GEOCLAW_QWEN_API_KEY", "").strip()
            provider_base = os.environ.get("GEOCLAW_QWEN_BASE_URL", "").strip()
            provider_model = os.environ.get("GEOCLAW_QWEN_MODEL", "").strip()
        elif provider == PROVIDER_GEMINI:
            default_base_url = DEFAULT_GEMINI_BASE_URL
            default_model = DEFAULT_GEMINI_MODEL
            provider_key = os.environ.get("GEOCLAW_GEMINI_API_KEY", "").strip()
            provider_base = os.environ.get("GEOCLAW_GEMINI_BASE_URL", "").strip()
            provider_model = os.environ.get("GEOCLAW_GEMINI_MODEL", "").strip()
        elif provider == PROVIDER_OLLAMA:
            default_base_url = DEFAULT_OLLAMA_BASE_URL
            default_model = DEFAULT_OLLAMA_MODEL
            provider_key = os.environ.get("GEOCLAW_OLLAMA_API_KEY", "").strip()
            provider_base = os.environ.get("GEOCLAW_OLLAMA_BASE_URL", "").strip()
            provider_model = os.environ.get("GEOCLAW_OLLAMA_MODEL", "").strip()
        else:
            default_base_url = DEFAULT_OPENAI_BASE_URL
            default_model = DEFAULT_OPENAI_MODEL
            provider_key = os.environ.get("GEOCLAW_OPENAI_API_KEY", "").strip()
            provider_base = os.environ.get("GEOCLAW_OPENAI_BASE_URL", "").strip()
            provider_model = os.environ.get("GEOCLAW_OPENAI_MODEL", "").strip()

        base_url = (
            os.environ.get("GEOCLAW_AI_BASE_URL", "").strip()
            or provider_base
            or default_base_url
        )
        api_key = (
            os.environ.get("GEOCLAW_AI_API_KEY", "").strip()
            or provider_key
        )
        model = (
            os.environ.get("GEOCLAW_AI_MODEL", "").strip()
            or provider_model
            or default_model
        )
        timeout = int(
            (
                os.environ.get("GEOCLAW_AI_TIMEOUT", "").strip()
                or os.environ.get("GEOCLAW_OPENAI_TIMEOUT", "60").strip()
                or "60"
            )
        )
        max_context_chars = int(os.environ.get("GEOCLAW_AI_MAX_CONTEXT_CHARS", "12000").strip() or "12000")
        if provider == PROVIDER_OLLAMA and not api_key:
            # Ollama local OpenAI-compatible endpoint typically does not require API key.
            api_key = "ollama-local"
        if not (base_url and api_key and model):
            raise ValueError(
                "AI config missing. Required: provider base_url/api_key/model "
                "(via GEOCLAW_AI_* or provider-specific env vars)."
            )
        return cls(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_context_chars=max(2000, max_context_chars),
        )


class ExternalAIClient:
    """OpenAI-compatible Chat Completions client for external AI APIs."""

    def __init__(self, config: ExternalAIConfig) -> None:
        self.config = config

    def chat(self, user_prompt: str, system_prompt: str = "") -> str:
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        system_text = system_prompt or "You are a GIS assistant."
        user_text = user_prompt or ""

        sys_cap = max(600, self.config.max_context_chars // 3)
        system_ctx = compress_context(system_text, max_chars=sys_cap)
        user_ctx = compress_context(user_text, max_chars=self.config.max_context_chars)

        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_ctx.text},
                {"role": "user", "content": user_ctx.text},
            ],
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=self._build_headers(),
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"AI API HTTP error: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"AI API request failed: {exc}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"AI API response missing choices: {payload}")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"AI API returned empty content: {payload}")
        return content.strip()

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.provider == PROVIDER_GEMINI and self.config.api_key:
            headers["x-goog-api-key"] = self.config.api_key
        return headers
