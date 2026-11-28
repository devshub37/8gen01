"""LLM model definitions and metadata."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelInfo:
    """Metadata about an LLM model."""
    name: str
    family: str = "unknown"
    parameter_size: str = ""
    context_length: Optional[int] = None
    is_code_model: bool = False
