import os
import yaml
from pathlib import Path


def load_yaml(filename: str) -> dict:
    """Load a YAML file and return its contents as a dict."""
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {filename}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_knowledge_path() -> Path:
    """Return the path to the knowledge directory."""
    # Look for knowledge dir relative to package or project root
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "knowledge",
        Path(__file__).resolve().parent.parent.parent.parent / "knowledge",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Default to a knowledge dir next to this package
    return Path(__file__).resolve().parent.parent.parent.parent / "knowledge"


def load_knowledge(name: str) -> dict:
    """Load a knowledge base YAML file by name (without extension)."""
    path = get_knowledge_path() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def slugify(text: str) -> str:
    """Convert a keyword into a URL-safe slug."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def keyword_slug(keyword: str) -> str:
    """Create a slug from a keyword for use in output filenames."""
    return slugify(keyword)


def ensure_output_dirs() -> None:
    """Create the output directory structure if it doesn't exist."""
    for d in ["output/blogs", "output/social", "output/reports"]:
        os.makedirs(d, exist_ok=True)
