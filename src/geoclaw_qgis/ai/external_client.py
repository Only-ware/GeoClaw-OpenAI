from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class ExternalAIConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60

    @classmethod
    def from_env(cls) -> ExternalAIConfig:
        base_url = os.environ.get("GEOCLAW_OPENAI_BASE_URL", "").strip()
        api_key = os.environ.get("GEOCLAW_OPENAI_API_KEY", "").strip()
        model = os.environ.get("GEOCLAW_OPENAI_MODEL", "").strip()
        timeout = int(os.environ.get("GEOCLAW_OPENAI_TIMEOUT", "60").strip() or "60")
        if not (base_url and api_key and model):
            raise ValueError("GEOCLAW_OPENAI_BASE_URL, GEOCLAW_OPENAI_API_KEY, GEOCLAW_OPENAI_MODEL are required")
        return cls(base_url=base_url, api_key=api_key, model=model, timeout=timeout)


class ExternalAIClient:
    """OpenAI-compatible Chat Completions client for external AI APIs."""

    def __init__(self, config: ExternalAIConfig) -> None:
        self.config = config

    def chat(self, user_prompt: str, system_prompt: str = "") -> str:
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a GIS assistant."},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"AI API HTTP error: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"AI API request failed: {exc}") from exc

        # TODO: Support non-OpenAI response schemas through provider adapters.
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"AI API response missing choices: {payload}")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"AI API returned empty content: {payload}")
        return content.strip()
