"""
Camada de abstração para provedores de LLM.

Configure via variáveis de ambiente:
  LLM_PROVIDER = anthropic | openai | gemini | ollama
  LLM_MODEL    = nome do modelo (usa padrão do provider se omitido)
  LLM_API_URL  = base URL (obrigatório apenas para ollama)

  ANTHROPIC_API_KEY = sk-ant-...
  OPENAI_API_KEY    = sk-...
  GEMINI_API_KEY    = ...
"""

from __future__ import annotations
import os
from typing import Protocol, runtime_checkable
from loguru import logger


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, max_tokens: int = 512) -> str:
        ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class AnthropicProvider:
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str, model: str = ""):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, max_tokens: int = 512) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
class OpenAIProvider:
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str, model: str = ""):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, max_tokens: int = 512) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------
class GeminiProvider:
    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(self, api_key: str, model: str = ""):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model or self.DEFAULT_MODEL)

    def complete(self, prompt: str, max_tokens: int = 512) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text.strip()


# ---------------------------------------------------------------------------
# Ollama  (API compatível com OpenAI — self-hosted)
# ---------------------------------------------------------------------------
class OllamaProvider:
    DEFAULT_MODEL = "llama3"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = ""):
        from openai import OpenAI
        self.client = OpenAI(base_url=f"{base_url}/v1", api_key="ollama")
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, max_tokens: int = 512) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def create_provider() -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    model = os.environ.get("LLM_MODEL", "")
    api_url = os.environ.get("LLM_API_URL", "http://localhost:11434")

    logger.info(f"LLM provider: {name} | modelo: {model or 'padrão'}")

    if name == "anthropic":
        return AnthropicProvider(os.environ["ANTHROPIC_API_KEY"], model)
    if name == "openai":
        return OpenAIProvider(os.environ["OPENAI_API_KEY"], model)
    if name == "gemini":
        return GeminiProvider(os.environ["GEMINI_API_KEY"], model)
    if name == "ollama":
        return OllamaProvider(api_url, model)

    raise ValueError(
        f"LLM_PROVIDER '{name}' inválido. Use: anthropic | openai | gemini | ollama"
    )
