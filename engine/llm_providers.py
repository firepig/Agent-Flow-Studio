from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMError(Exception):
    """Raised when an LLM provider encounters an error."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]: ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise LLMError("The 'openai' package is not installed. Run: pip install openai")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        try:
            messages: list[dict] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI generation failed: {e}") from e

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        try:
            messages: list[dict] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI streaming failed: {e}") from e


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise LLMError("The 'anthropic' package is not installed. Run: pip install anthropic")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        try:
            kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self.client.messages.create(**kwargs)
            return response.content[0].text
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Anthropic generation failed: {e}") from e

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        try:
            kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Anthropic streaming failed: {e}") from e


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        try:
            import httpx as _httpx  # noqa: F401
        except ImportError:
            raise LLMError("The 'httpx' package is not installed. Run: pip install httpx")
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        import httpx

        try:
            messages: list[dict] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Ollama generation failed: {e}") from e

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        import httpx

        try:
            messages: list[dict] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Ollama streaming failed: {e}") from e


def create_provider(
    provider_type: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Factory that returns the appropriate LLMProvider instance."""
    provider_type = (provider_type or "").lower().strip()

    if provider_type == "openai":
        if not api_key:
            raise LLMError("OpenAI requires an API key. Set it in Settings.")
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")

    if provider_type == "anthropic":
        if not api_key:
            raise LLMError("Anthropic requires an API key. Set it in Settings.")
        return AnthropicProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514")

    if provider_type == "ollama":
        return OllamaProvider(
            base_url=base_url or "http://localhost:11434",
            model=model or "llama3",
        )

    raise LLMError(
        f"Unknown provider '{provider_type}'. Supported: openai, anthropic, ollama"
    )
