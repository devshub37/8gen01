"""Google Gemini API and Gemini-compatible proxy provider."""

import json
from typing import AsyncGenerator, Dict, List, Optional, Any
import httpx

from eightgen.llm.base import LLMMessage, LLMProvider, LLMResponse
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.gemini")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """Provider for Google Gemini API or local OpenAI-compatible Gemini proxy."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.5-flash",
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key.strip()
        self.model = model or "gemini-2.5-flash"
        self.proxy_url = proxy_url.rstrip("/") if proxy_url else None
        self.timeout = timeout

    async def is_healthy(self) -> bool:
        """Check if Gemini API or Proxy is reachable."""
        if self.proxy_url:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    res = await client.get(f"{self.proxy_url}/models")
                    return res.status_code == 200
            except Exception:
                return False

        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{GEMINI_API_BASE}/models?key={self.api_key}")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List available models."""
        if self.proxy_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(f"{self.proxy_url}/models")
                    if res.status_code == 200:
                        data = res.json().get("data", [])
                        return [m.get("id") for m in data if m.get("id")]
            except Exception:
                pass
            return ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"]

        return [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

    def _convert_messages_for_gemini(self, messages: List[LLMMessage]) -> Dict[str, Any]:
        """Convert standard messages to Gemini contents format."""
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content}]}
            elif msg.role in ("user", "assistant"):
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        return payload

    def _candidate_models(self) -> List[str]:
        """Build ordered list of Gemini models to try."""
        model_name = self.model.replace("models/", "")
        candidates = [model_name]
        for fallback in [
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
        ]:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    @staticmethod
    def _with_fast_config(model_name: str, base_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return payload with thinkingBudget=0 for thinking-enabled Flash models."""
        if any(tag in model_name for tag in ("3-flash", "3.1", "3.5", "3.6", "3.7", "3.8", "2.5")):
            return {
                **base_payload,
                "generationConfig": {
                    **base_payload["generationConfig"],
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
        return base_payload

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate complete response via Gemini API or Proxy."""
        if self.proxy_url:
            return await self._generate_via_proxy(messages, temperature, **kwargs)

        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY in your environment or .env file."
            )

        gemini_payload = self._convert_messages_for_gemini(messages)
        gemini_payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": 32768,
        }

        candidate_models = self._candidate_models()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                last_err = ""
                for m_name in candidate_models:
                    url = f"{GEMINI_API_BASE}/models/{m_name}:generateContent?key={self.api_key}"
                    req_payload = self._with_fast_config(m_name, gemini_payload)
                    try:
                        res = await client.post(url, json=req_payload)
                        if res.status_code == 400 and req_payload is not gemini_payload:
                            res = await client.post(url, json=gemini_payload)
                    except httpx.TimeoutException:
                        last_err = f"Model {m_name} timed out"
                        continue
                    if res.status_code in (404, 429, 503):
                        last_err = f"Model {m_name} status {res.status_code}: {res.text}"
                        continue
                    if res.status_code != 200:
                        err_msg = res.text
                        try:
                            err_json = res.json()
                            err_msg = err_json.get("error", {}).get("message", res.text)
                        except Exception:
                            pass
                        raise RuntimeError(f"Gemini API error ({res.status_code}): {err_msg}")

                    data = res.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("No candidates returned by Gemini.")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join([p.get("text", "") for p in parts])

                    usage = data.get("usageMetadata", {})
                    return LLMResponse(
                        content=content,
                        model=m_name,
                        prompt_tokens=usage.get("promptTokenCount"),
                        completion_tokens=usage.get("candidatesTokenCount"),
                        raw=data,
                    )
                raise RuntimeError(f"Gemini API error: {last_err}")
        except httpx.ConnectError:
            raise ConnectionError("Cannot connect to Google Gemini API servers.")

    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream chunks via Gemini API or Proxy."""
        if self.proxy_url:
            async for chunk in self._stream_via_proxy(messages, temperature, **kwargs):
                yield chunk
            return

        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY in your environment or .env file."
            )

        gemini_payload = self._convert_messages_for_gemini(messages)
        gemini_payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": 32768,
        }

        candidate_models = self._candidate_models()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                last_err = ""
                for idx, m_name in enumerate(candidate_models):
                    url = f"{GEMINI_API_BASE}/models/{m_name}:streamGenerateContent?alt=sse&key={self.api_key}"
                    fast_payload = self._with_fast_config(m_name, gemini_payload)
                    payload_attempts = [fast_payload, gemini_payload] if fast_payload is not gemini_payload else [gemini_payload]

                    model_failed_cleanly = False
                    for req_payload in payload_attempts:
                        try:
                            async with client.stream("POST", url, json=req_payload) as response:
                                if response.status_code in (404, 429, 503):
                                    last_err = f"Model {m_name} HTTP {response.status_code}"
                                    model_failed_cleanly = True
                                    break
                                if response.status_code == 400 and req_payload is not gemini_payload:
                                    # Retry this same model without thinkingConfig
                                    continue
                                if response.status_code != 200:
                                    err_body = await response.aread()
                                    raise RuntimeError(f"Gemini API streaming error ({response.status_code}): {err_body.decode()}")

                                yielded_any = False
                                got_finish = False
                                stream_errors: List[str] = []

                                async for line in response.aiter_lines():
                                    if not line:
                                        continue
                                    if not line.startswith("data:"):
                                        stream_errors.append(line.strip())
                                        continue
                                    json_str = line[len("data:"):].strip()
                                    if not json_str:
                                        continue
                                    try:
                                        data = json.loads(json_str)
                                        if "error" in data:
                                            stream_errors.append(str(data["error"]))
                                            break
                                        candidates = data.get("candidates", [])
                                        if candidates:
                                            if candidates[0].get("finishReason"):
                                                got_finish = True
                                            parts = candidates[0].get("content", {}).get("parts", [])
                                            for p in parts:
                                                text = p.get("text", "")
                                                if text:
                                                    yielded_any = True
                                                    yield text
                                    except json.JSONDecodeError:
                                        continue

                                if stream_errors or not got_finish:
                                    err_summary = " ".join(stream_errors)[:160] or "stream ended without finishReason"
                                    last_err = f"Model {m_name} interrupted mid-stream: {err_summary}"
                                    next_model = candidate_models[idx + 1] if idx + 1 < len(candidate_models) else candidate_models[0]
                                    if not yielded_any:
                                        model_failed_cleanly = True
                                        break
                                    # Partial chunks already streamed; switch default model so retry uses healthy model
                                    self.model = next_model
                                    raise RuntimeError(last_err)

                                self.model = m_name
                                return
                        except httpx.TimeoutException:
                            last_err = f"Model {m_name} timed out"
                            model_failed_cleanly = True
                            break

                    if model_failed_cleanly:
                        continue

                raise RuntimeError(f"Gemini API error: {last_err or 'All candidate models unavailable.'}")
        except httpx.ConnectError:
            raise ConnectionError("Cannot connect to Google Gemini API servers.")

    async def _generate_via_proxy(
        self, messages: List[LLMMessage], temperature: float, **kwargs: Any
    ) -> LLMResponse:
        """Call OpenAI-compatible proxy (e.g. oorja proxy)."""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key or 'not-needed'}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(f"{self.proxy_url}/chat/completions", json=payload, headers=headers)
            if res.status_code != 200:
                raise RuntimeError(f"Proxy error ({res.status_code}): {res.text}")
            data = res.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return LLMResponse(content=content, model=self.model, raw=data)

    async def _stream_via_proxy(
        self, messages: List[LLMMessage], temperature: float, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self.api_key or 'not-needed'}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.proxy_url}/chat/completions", json=payload, headers=headers) as res:
                if res.status_code != 200:
                    err = await res.aread()
                    raise RuntimeError(f"Proxy streaming error: {err.decode()}")
                async for line in res.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk_raw = line[len("data:"):].strip()
                    if chunk_raw == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk_raw).get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue
