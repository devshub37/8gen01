"""Image and game asset generation engine supporting proxies, native Gemini image models, and Gemini SVG synthesis."""

import base64
import re
import time
from typing import Any, Dict, Optional, Tuple
import httpx

from eightgen.config.settings import Settings, is_vercel
from eightgen.llm.base import LLMMessage
from eightgen.llm.gemini import GEMINI_API_BASE, GeminiProvider
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.image_gen")

NATIVE_IMAGE_MODELS = (
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image",
)

STYLE_DESCRIPTIONS = {
    "pixel-art": "16-bit pixel art sprite rendered with crisp pixelated rect clusters and shape-rendering='crispEdges' on a dark background",
    "retro-arcade": "Vibrant retro 80s neon arcade graphic with glowing gradients, crisp edges, and high-contrast highlights on a dark background",
    "scifi-background": "Layered parallax 2D sci-fi game background scene with deep atmospheric sky gradient, stars, planets, and neon horizon",
    "default": "Crisp stylized 2D game asset with clean silhouette, rich shading, and vibrant colors",
}


class ImageGenerationError(Exception):
    """Raised when AI image generation fails."""


def _parse_size(size: str) -> Tuple[int, int]:
    """Parse WxH size strings safely within [256, 2048]."""
    try:
        parts = size.lower().split("x", 1)
        w = max(256, min(2048, int(parts[0])))
        h = max(256, min(2048, int(parts[1])))
        return w, h
    except Exception:
        return 1024, 1024


def _extract_svg(raw_text: str, width: int, height: int) -> str:
    """Extract and normalize standalone SVG markup from LLM output."""
    text = raw_text.strip()
    fence_match = re.search(r"```(?:svg|xml|html)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    svg_match = re.search(r"<svg[\s\S]*?</svg>", text, re.IGNORECASE)
    if not svg_match:
        raise ImageGenerationError("Generated SVG output was incomplete or missing <svg> tags.")

    svg = svg_match.group(0).strip()
    if "xmlns=" not in svg[:200]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if "viewBox=" not in svg[:200]:
        svg = svg.replace("<svg", '<svg viewBox="0 0 512 512"', 1)
    if "width=" not in svg[:200]:
        svg = svg.replace("<svg", f'<svg width="{width}" height="{height}"', 1)
    return svg


class ImageGenerator:
    """Generates game sprites, backgrounds, and cover art via proxy, native Gemini image models, or Gemini SVG synthesis."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.assets_dir = settings.output_dir / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    async def generate_image(
        self,
        prompt: str,
        style: str = "pixel-art",
        size: str = "1024x1024",
    ) -> Dict[str, Any]:
        """Generate a game asset and return metadata, saved file path, and base64 data URL."""
        styled_prompt = self._build_styled_prompt(prompt, style)
        errors: list[str] = []

        # Attempt 1: Gemini Web-to-API proxy (explicitly configured or local dev)
        proxy_endpoints = []
        if self.settings.gemini_proxy_url:
            proxy_endpoints.append(self.settings.gemini_proxy_url)
        if not is_vercel():
            proxy_endpoints.extend([
                "http://127.0.0.1:4981/openai/v1",
                "http://localhost:4981/openai/v1",
                "http://127.0.0.1:8081/v1",
                "http://localhost:8081/v1",
            ])

        for base_proxy in proxy_endpoints:
            try:
                result = await self._generate_via_proxy(base_proxy, styled_prompt, size)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Proxy attempt at {base_proxy} failed: {e}")

        # Attempt 2: Official Google Gemini native image models (works on billed tiers)
        if self.settings.gemini_api_key:
            try:
                result = await self._generate_via_google_native_image(styled_prompt)
                if result:
                    return result
            except Exception as e:
                errors.append(f"Native image API: {e}")
                logger.info(f"Native Gemini image unavailable ({e}); falling back to Gemini SVG synthesis.")

            # Attempt 3: Gemini Flash SVG sprite & scene synthesis (works on all Gemini API tiers)
            try:
                return await self._generate_via_gemini_svg(prompt, style, size)
            except Exception as e:
                errors.append(f"Gemini SVG synthesis: {e}")
                logger.warning(f"Gemini SVG synthesis failed: {e}")
        else:
            errors.append("GEMINI_API_KEY is not configured.")

        detail = " | ".join(errors) if errors else "No image provider available."
        raise ImageGenerationError(f"Asset synthesis failed: {detail}")

    def _build_styled_prompt(self, prompt: str, style: str) -> str:
        if style == "pixel-art" and "pixel" not in prompt.lower():
            return f"16-bit pixel art game asset, isolated on clean dark background: {prompt}"
        if style == "retro-arcade" and "arcade" not in prompt.lower():
            return f"Vibrant retro neon arcade game graphic, clean edges: {prompt}"
        if style == "scifi-background" and "background" not in prompt.lower():
            return f"Parallax scrolling 2D game background scene, wide angle: {prompt}"
        return prompt

    async def _generate_via_proxy(
        self, proxy_base: str, prompt: str, size: str
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI-compatible /images/generations on gemini-web-to-api."""
        url = f"{proxy_base.rstrip('/')}/images/generations"
        payload = {
            "model": "gemini-pro",
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer not-needed",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                return None

            image_items = res.json().get("data", [])
            b64_str = image_items[0].get("b64_json", "") if image_items else ""
            if not b64_str:
                return None

            return self._save_asset_bytes(base64.b64decode(b64_str), prompt, "image/png", "png")

    async def _generate_via_google_native_image(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Try Gemini native image generation models via generateContent."""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }

        last_err = ""
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model in NATIVE_IMAGE_MODELS:
                url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={self.settings.gemini_api_key}"
                res = await client.post(url, json=payload)
                if res.status_code in (400, 404, 429, 503):
                    last_err = f"{model} HTTP {res.status_code}"
                    continue
                if res.status_code != 200:
                    last_err = f"{model} HTTP {res.status_code}: {res.text[:200]}"
                    continue

                candidates = res.json().get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                for part in parts:
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                        ext = "jpg" if "jpeg" in mime else ("webp" if "webp" in mime else "png")
                        return self._save_asset_bytes(
                            base64.b64decode(inline["data"]),
                            prompt,
                            mime,
                            ext,
                        )
                last_err = f"{model} returned no inline image data"

        if last_err:
            raise RuntimeError(last_err)
        return None

    async def _generate_via_gemini_svg(
        self, prompt: str, style: str, size: str
    ) -> Dict[str, Any]:
        """Synthesize detailed game sprite or background SVG artwork via Gemini Flash."""
        width, height = _parse_size(size)
        style_guide = STYLE_DESCRIPTIONS.get(style, STYLE_DESCRIPTIONS["default"])

        provider = GeminiProvider(
            api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            proxy_url=self.settings.gemini_proxy_url,
            timeout=min(self.settings.timeout, 60.0),
        )

        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are an expert pixel-art and vector 2D game artist. "
                    "Output ONLY complete, valid standalone SVG markup starting with <svg and ending with </svg>. "
                    "Always include xmlns=\"http://www.w3.org/2000/svg\" and viewBox=\"0 0 512 512\". "
                    "Keep SVG compact (under 100 primitives) so it finishes cleanly without truncation. No markdown or prose."
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Create a detailed game asset SVG (width=\"{width}\" height=\"{height}\" viewBox=\"0 0 512 512\") for:\n"
                    f"Subject: {prompt}\n"
                    f"Art Direction: {style_guide}\n"
                    "Include rich colors, shading/gradients (<defs>), highlights, and a clean cohesive composition."
                ),
            ),
        ]

        llm_res = await provider.generate(messages, temperature=0.4)
        svg_markup = _extract_svg(llm_res.content, width, height)
        return self._save_asset_bytes(
            svg_markup.encode("utf-8"),
            prompt,
            "image/svg+xml",
            "svg",
        )

    def _save_asset_bytes(
        self, raw_bytes: bytes, prompt: str, mime_type: str, ext: str
    ) -> Dict[str, Any]:
        """Save generated image or SVG bytes to disk and return API metadata."""
        slug = re.sub(r"[^\w\s-]", "", prompt.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-_")[:30] or "asset"
        timestamp = int(time.time())
        filename = f"{timestamp}_{slug}.{ext}"
        filepath = self.assets_dir / filename
        filepath.write_bytes(raw_bytes)

        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64_str}"
        return {
            "filename": filename,
            "filepath": str(filepath.resolve()),
            "url": f"/static/assets/{filename}",
            "data_url": data_url,
            "mime_type": mime_type,
            "format": ext,
            "prompt": prompt,
        }
