"""Ollama LLM Provider implementation."""

import json
from typing import AsyncGenerator, Dict, List, Any
import httpx

from eightgen.llm.base import LLMMessage, LLMProvider, LLMResponse
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.ollama")


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider communicating over HTTP."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "huihui_ai/qwen2.5-coder-abliterate:7b",
        timeout: float = 180.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def is_healthy(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Fetch list of local model names installed in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return models
                return []
        except Exception as e:
            logger.debug(f"Failed to fetch models from Ollama: {e}")
            return []

    async def resolve_model(self) -> str:
        """Ensure active model is available in Ollama, or pick the best available one."""
        available = await self.list_models()
        if not available:
            return self.model

        if self.model in available:
            return self.model

        # Check for partial match (e.g. "qwen2.5-coder" matches "huihui_ai/qwen2.5-coder-abliterate:7b")
        for m in available:
            if self.model.lower() in m.lower():
                logger.info(f"Using matched model: {m}")
                self.model = m
                return m

        # Check for any code or llama model
        preferred_substrings = ["coder", "qwen", "llama", "deepseek", "codellama", "mistral"]
        for pref in preferred_substrings:
            for m in available:
                if pref in m.lower():
                    logger.info(f"Model '{self.model}' not found. Auto-selected code model: {m}")
                    self.model = m
                    return m

        # Fallback to first available
        fallback = available[0]
        logger.info(f"Auto-selected first available model: {fallback}")
        self.model = fallback
        return fallback

    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Non-streaming generation."""
        active_model = await self.resolve_model()
        payload = {
            "model": active_model,
            "messages": self._format_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                **kwargs.get("options", {})
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Ollama error {res.status_code}: {res.text}")
                data = res.json()
                content = data.get("message", {}).get("content", "")
                total_duration = data.get("total_duration")
                duration_ms = (total_duration / 1_000_000) if total_duration else None
                return LLMResponse(
                    content=content,
                    model=active_model,
                    total_duration_ms=duration_ms,
                    prompt_tokens=data.get("prompt_eval_count"),
                    completion_tokens=data.get("eval_count"),
                    raw=data
                )
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure Ollama is running (`ollama serve`)."
            )

    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Streaming generation chunk by chunk."""
        active_model = await self.resolve_model()
        payload = {
            "model": active_model,
            "messages": self._format_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature,
                **kwargs.get("options", {})
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise RuntimeError(f"Ollama error {response.status_code}: {body.decode()}")

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            delta = chunk.get("message", {}).get("content", "")
                            if delta:
                                yield delta
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Please ensure Ollama is running (`ollama serve`)."
            )
