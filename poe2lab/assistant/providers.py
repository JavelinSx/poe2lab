"""AI providers the assistant can use, and where the user's choice and keys are stored.

Settings live in the user's profile (%APPDATA%/poe2lab/llm.json), never in the repository. Keys are only
ever returned to the browser as a short hint."""
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    kind: str  # "openai" (OpenAI-compatible chat completions) or "anthropic" (official Anthropic SDK)
    base_url: str
    default_model: str = ""
    needs_key: bool = True
    note: str = ""


PROVIDERS = [
    Provider("deepseek", "DeepSeek", "openai", "https://api.deepseek.com", "deepseek-flash",
             note="дёшево, 1M контекст; данные уходят на серверы DeepSeek"),
    Provider("anthropic", "Anthropic (Claude)", "anthropic", "https://api.anthropic.com", "claude-opus-5",
             note="официальный SDK Anthropic"),
    Provider("openai", "OpenAI", "openai", "https://api.openai.com/v1"),
    Provider("google", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai"),
    Provider("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1",
             note="один ключ — модели многих компаний"),
    Provider("mistral", "Mistral", "openai", "https://api.mistral.ai/v1"),
    Provider("xai", "xAI (Grok)", "openai", "https://api.x.ai/v1"),
    Provider("groq", "Groq", "openai", "https://api.groq.com/openai/v1"),
    Provider("ollama", "Ollama (локально)", "openai", "http://localhost:11434/v1", needs_key=False,
             note="модель на своём компьютере, ключ не нужен"),
    Provider("custom", "Свой (OpenAI-совместимый)", "openai", ""),
]
BY_ID = {p.id: p for p in PROVIDERS}


def settings_path() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(root) / "poe2lab" / "llm.json"


def load_settings() -> dict:
    p = settings_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_settings(data: dict) -> None:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def key_hint(key: str | None) -> str | None:
    if not key:
        return None
    return "…" + key[-4:] if len(key) > 8 else "задан"
