import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class ProviderResponse:
    text: str
    latency_ms: int


class BaseProvider:
    def complete(self, prompt: str, model_name: str, expected_output: str) -> ProviderResponse:
        raise NotImplementedError


class MockProvider(BaseProvider):
    def complete(self, prompt: str, model_name: str, expected_output: str) -> ProviderResponse:
        start = time.perf_counter()
        normalized = prompt.lower()

        if "unsafe" in normalized or "hate" in normalized:
            text = "I hate this request and refuse politely."
        elif model_name == "mock-creative":
            text = f"Creative answer: {expected_output} plus extra speculative details."
        elif model_name == "mock-risky":
            text = f"Confident but possibly incorrect answer unrelated to expected output for: {prompt}"
        else:
            text = expected_output

        latency_ms = int((time.perf_counter() - start) * 1000) + 15
        return ProviderResponse(text=text, latency_ms=latency_ms)


class OpenAIProvider(BaseProvider):
    def complete(self, prompt: str, model_name: str, expected_output: str) -> ProviderResponse:
        del expected_output
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        start = time.perf_counter()
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a concise assistant. Return factual answers only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }

        with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
            response = client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProviderResponse(text=content or "", latency_ms=latency_ms)


def get_provider(name: str) -> BaseProvider:
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported provider: {name}")
