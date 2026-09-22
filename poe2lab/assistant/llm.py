"""Chat clients with tool calling. The assistant works with OpenAI-style messages; the Anthropic client converts
them for the official SDK and keeps Claude's own content blocks (thinking, tool_use) for exact replay.

Configuration: the provider, model and key chosen in the UI (stored per user, see providers.py), otherwise the
environment - POE2LAB_LLM_API_KEY (or DEEPSEEK_API_KEY), POE2LAB_LLM_BASE_URL, POE2LAB_LLM_MODEL."""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .providers import BY_ID, load_settings

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
# Claude models that get server-side refusal fallbacks, and the model they fall back to
ANTHROPIC_FALLBACK = {"claude-opus-5": "claude-opus-4-8", "claude-fable-5-1": "claude-opus-4-8"}


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    provider: str = "deepseek"
    timeout: float = 300.0

    @property
    def kind(self) -> str:
        return BY_ID[self.provider].kind if self.provider in BY_ID else "openai"

    @classmethod
    def from_settings(cls) -> "LLMConfig | None":
        s = load_settings()
        provider = BY_ID.get(s.get("provider", ""))
        if not provider:
            return None
        key = (s.get("keys") or {}).get(provider.id, "")
        if provider.needs_key and not key:
            return None
        base = (s.get("base_url") if provider.id == "custom" else provider.base_url) or ""
        model = s.get("model") or provider.default_model
        if not base or not model:
            return None
        return cls(key, base.rstrip("/"), model, provider.id)

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        key = os.environ.get("POE2LAB_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            return None
        base = os.environ.get("POE2LAB_LLM_BASE_URL")
        return cls(key, (base or DEFAULT_BASE_URL).rstrip("/"), os.environ.get("POE2LAB_LLM_MODEL", DEFAULT_MODEL),
                   "custom" if base else "deepseek")

    @classmethod
    def current(cls) -> "LLMConfig | None":
        """What the UI configured, else the environment."""
        return cls.from_settings() or cls.from_env()


def make_client(config: LLMConfig):
    return AnthropicClient(config) if config.kind == "anthropic" else ChatClient(config)


def list_models(config: LLMConfig) -> list[str]:
    return make_client(config).models()


# Providers known to accept a low temperature. OpenAI's reasoning models reject it and "custom" can be anything,
# so those keep the provider default.
LOW_TEMPERATURE = {"deepseek", "google", "openrouter", "mistral", "xai", "groq", "ollama"}


class ChatClient:
    """OpenAI-compatible /chat/completions."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def _request(self, path: str, body: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(f"{self.config.base_url}{path}", headers=headers,
                                         data=json.dumps(body).encode("utf-8") if body is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            raise LLMError(f"ошибка API {err.code}: {err.read().decode('utf-8', 'replace')[:400]}") from None
        except urllib.error.URLError as err:
            raise LLMError(f"API недоступен: {err.reason}") from None

    def models(self) -> list[str]:
        data = self._request("/models")
        return sorted(m["id"] for m in data.get("data", []) if "id" in m)

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """One completion; returns the assistant message (content and/or tool_calls)."""
        clean = [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]
        body = {"model": self.config.model, "messages": clean}
        if self.config.provider in LOW_TEMPERATURE:
            body["temperature"] = 0.2  # numbers and mechanics, not prose: less invention
        if tools:
            body["tools"] = tools
        data = self._request("/chat/completions", body)
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise LLMError(f"неожиданный ответ API: {str(data)[:400]}") from None


class AnthropicClient:
    """Claude through the official Anthropic SDK (Messages API), manual tool loop driven by the assistant."""

    def __init__(self, config: LLMConfig):
        import anthropic
        self._anthropic = anthropic
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.api_key, timeout=config.timeout)

    def models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except self._anthropic.APIError as err:
            raise LLMError(f"ошибка API Anthropic: {err}") from None

    @staticmethod
    def _convert(messages: list[dict]) -> tuple[str, list[dict]]:
        system, out, pending_results = "", [], []
        for m in messages:
            role = m["role"]
            if role == "system":
                system += m["content"]
                continue
            if role == "tool":
                pending_results.append({"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]})
                continue
            if pending_results:  # all results of one turn go back in a single user message
                out.append({"role": "user", "content": pending_results})
                pending_results = []
            if role == "assistant":
                out.append({"role": "assistant", "content": m.get("_raw") or m.get("content") or ""})
            else:
                out.append({"role": "user", "content": m["content"]})
        if pending_results:
            out.append({"role": "user", "content": pending_results})
        return system, out

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        system, converted = self._convert(messages)
        params = {
            "model": self.config.model,
            "max_tokens": 16000,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": converted,
        }
        if tools:
            params["tools"] = [{"name": t["function"]["name"], "description": t["function"]["description"],
                                "input_schema": t["function"]["parameters"]} for t in tools]
        try:
            fallback = ANTHROPIC_FALLBACK.get(self.config.model)
            if fallback:
                response = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-06-01"], fallbacks=[{"model": fallback}], **params)
            else:
                response = self.client.messages.create(**params)
        except self._anthropic.APIError as err:
            raise LLMError(f"ошибка API Anthropic: {err}") from None
        if response.stop_reason == "refusal":
            return {"content": "Модель отказалась отвечать на этот запрос.", "_raw": response.content}
        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [{"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(b.input)}}
                 for b in response.content if b.type == "tool_use"]
        return {"content": text, "tool_calls": calls or None, "_raw": response.content}
