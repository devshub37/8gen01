"""Image generation engine supporting gemini-web-to-api and Google Imagen."""

import base64
from pathlib import Path
from typing import Dict, Optional, Any
import httpx

from eightgen.config.settings import Settings, is_vercel
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.image_gen")


class ImageGenerationError(Exception):
    """Raised when AI image generation fails."""
    pass


class ImageGenerator:
    """Generates game sprites, backgrounds, and cover art using Gemini Web-to-API or Google Imagen."""

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
        """Generate an image from prompt and return metadata with base64 and saved path."""
        # Enhance prompt with style instructions for games
        styled_prompt = prompt
        if style == "pixel-art" and "pixel" not in prompt.lower():
            styled_prompt = f"16-bit pixel art game asset, isolated on clean dark background: {prompt}"
        elif style == "retro-arcade" and "arcade" not in prompt.lower():
            styled_prompt = f"Vibrant retro neon arcade game graphic, clean edges: {prompt}"
        elif style == "scifi-background" and "background" not in prompt.lower():
            styled_prompt = f"Parallax scrolling 2D game background scene, wide angle: {prompt}"

        # Attempt 1: Gemini Web-to-API proxy (oorja proxy at localhost:4981 or localhost:8081)
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

        # Attempt 2: Official Google Imagen 3 API if GEMINI_API_KEY is available
        if self.settings.gemini_api_key:
            try:
                return await self._generate_via_google_imagen(styled_prompt)
            except Exception as e:
                logger.warning(f"Google Imagen API generation failed: {e}")

        raise ImageGenerationError(
            "Could not connect to gemini-web-to-api server (http://localhost:4981) or Google Imagen API. "
            "Please make sure your gemini-server from 'oorja' is running, or set GEMINI_API_KEY."
        )

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

        async with httpx.AsyncClient(timeout=90.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                return None

            data = res.json()
            image_items = data.get("data", [])
            if not image_items:
                return None

            b64_str = image_items[0].get("b64_json", "")
            if not b64_str:
                return None

            return self._save_b64_image(b64_str, prompt)

    async def _generate_via_google_imagen(self, prompt: str) -> Dict[str, Any]:
        """Call Google official Imagen 3 API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={self.settings.gemini_api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "1:1",
                "outputOptions": {"mimeType": "image/png"},
            },
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Google Imagen error {res.status_code}: {res.text}")

            data = res.json()
            predictions = data.get("predictions", [])
            if not predictions:
                raise RuntimeError("No predictions returned from Google Imagen.")

            b64_str = predictions[0].get("bytesBase64Encoded", "")
            if not b64_str:
                raise RuntimeError("Empty image bytes returned.")

            return self._save_b64_image(b64_str, prompt)

    def _save_b64_image(self, b64_str: str, prompt: str) -> Dict[str, Any]:
        """Decode and save PNG to disk."""
        import time
        import re

        slug = re.sub(r"[^\w\s-]", "", prompt.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-_")[:30] or "asset"
        timestamp = int(time.time())
        filename = f"{timestamp}_{slug}.png"
        filepath = self.assets_dir / filename

        image_bytes = base64.b64decode(b64_str)
        filepath.write_bytes(image_bytes)

        data_url = f"data:image/png;base64,{b64_str}"
        return {
            "filename": filename,
            "filepath": str(filepath.resolve()),
            "url": f"/static/assets/{filename}",
            "data_url": data_url,
            "prompt": prompt,
        }
