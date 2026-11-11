"""Image generation and game asset API routes."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from eightgen.config.loader import get_settings
from eightgen.llm.image_gen import ImageGenerator, ImageGenerationError

router = APIRouter(prefix="/api/images", tags=["images"])


class ImageRequest(BaseModel):
    prompt: str
    style: Optional[str] = "pixel-art"
    size: Optional[str] = "1024x1024"


def get_generator() -> ImageGenerator:
    return ImageGenerator(get_settings())


@router.post("/generate")
async def generate_image(payload: ImageRequest, gen: ImageGenerator = Depends(get_generator)):
    """Generate game sprite or background via Gemini Web-to-API or Google Imagen."""
    try:
        result = await gen.generate_image(
            prompt=payload.prompt,
            style=payload.style or "pixel-art",
            size=payload.size or "1024x1024",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_assets(gen: ImageGenerator = Depends(get_generator)) -> List[dict]:
    """List all generated image assets."""
    assets = []
    if gen.assets_dir.exists():
        files = [
            p for p in gen.assets_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".webp", ".svg")
        ]
        for p in sorted(files, key=lambda f: f.stat().st_mtime, reverse=True):
            assets.append({
                "filename": p.name,
                "url": f"/static/assets/{p.name}",
                "size_bytes": p.stat().st_size,
            })
    return assets
