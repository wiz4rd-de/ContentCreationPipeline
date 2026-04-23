"""LLM abstraction layer — config, client, and prompt utilities."""

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.config import LLMConfig

__all__ = ["LLMConfig", "complete"]
