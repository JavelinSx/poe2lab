"""Minimal client for OpenAI-compatible chat APIs with tool calling (DeepSeek by default).

Configuration comes from the environment so the key never lives in the repo:
  POE2LAB_LLM_API_KEY (or DEEPSEEK_API_KEY)  - required
  POE2LAB_LLM_BASE_URL  - default https://api.deepseek.com
  POE2LAB_LLM_MODEL     - default deepseek-flash
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = 180.0

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        key = os.environ.get("POE2LAB_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            return None
        return cls(key, os.environ.get("POE2LAB_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
                   os.environ.get("POE2LAB_LLM_MODEL", DEFAULT_MODEL))


class ChatClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """One chat completion; returns the assistant message (content and/or tool_calls)."""
        body = {"model": self.config.model, "messages": messages}
        if tools:
            body["tools"] = tools
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            raise LLMError(f"LLM API error {err.code}: {err.read().decode('utf-8', 'replace')[:500]}") from None
        except urllib.error.URLError as err:
            raise LLMError(f"LLM API unreachable: {err.reason}") from None
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise LLMError(f"unexpected LLM response: {str(data)[:500]}") from None
