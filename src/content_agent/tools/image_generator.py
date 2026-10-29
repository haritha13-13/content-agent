import hashlib
import os
import urllib.parse
from typing import Type

import requests
from PIL import Image, ImageFilter
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class ImageGenInput(BaseModel):
    """Input schema for the image generation tool."""
    prompt: str = Field(..., description="Detailed text prompt describing the image to generate")
    filepath: str = Field(..., description="File path to save the image, e.g. output/images/ai-invoice-processing.png")


class ImageGenerationTool(BaseTool):
    name: str = "image_generator"
    description: str = (
        "Generates an AI image from a text prompt using the Pollinations.ai API and saves it to "
        "a PNG file. Used to create a blog hero image related to the topic. Returns the saved "
        "file path."
    )
    args_schema: Type[BaseModel] = ImageGenInput

    def _run(self, prompt: str, filepath: str) -> str:
        try:
            prompt_url = urllib.parse.quote(prompt)
            seed = str(int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % 2000000000)
            url = (
                f"https://image.pollinations.ai/prompt/{prompt_url}"
                f"?width=1024&height=1024&seed={seed}&nologo=true"
                f"&model=flux&enhance=true"
            )
            resp = requests.get(url, timeout=180)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "").lower()
            ext = ".jpg" if content_type.startswith("image/jpeg") else ".png"
            base = filepath
            for cand in (".png", ".jpg", ".jpeg"):
                if base.lower().endswith(cand):
                    base = base[: -len(cand)]
            filepath = base + ext

            full_path = os.path.normpath(filepath)
            root = os.path.normpath("output" + os.sep + "images")
            if not full_path.startswith(os.path.normpath("output")):
                full_path = os.path.join("output/images", os.path.basename(full_path))

            os.makedirs(os.path.dirname(full_path) or root, exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(resp.content)

            _refine_image(full_path)
            return f"Successfully generated image at {full_path}"
        except Exception as e:
            return f"Error generating image: {str(e)}"


def _refine_image(path: str, target: int = 1536) -> None:
    """Upscale the generated 768px image to ~1536px and sharpen it.

    Pollinations caps output at 768x768 regardless of the requested size, so we
    post-process locally to deliver a crisper, higher-resolution hero image.
    """
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = target / max(w, h)
        if scale > 1:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
        im.save(path, "JPEG", quality=92, optimize=True)