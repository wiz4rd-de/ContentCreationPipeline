"""Shared data models used across the entire pipeline."""

from pydantic import BaseModel, ConfigDict


class PipelineBaseModel(BaseModel):
    """Base model for all pipeline data contracts.

    Provides shared configuration: populate_by_name=True allows
    instantiation using either field names or aliases.
    """

    model_config = ConfigDict(populate_by_name=True)


class Heading(PipelineBaseModel):
    """Heading extracted from a webpage.

    Attributes:
        level: The heading level (1-6 for h1-h6).
        text: The heading text content.
    """

    level: int
    text: str


class LinkCount(PipelineBaseModel):
    """Count of links on a page.

    Attributes:
        internal: Number of internal links (same domain).
        external: Number of external links (different domain).
    """

    internal: int
    external: int


class HtmlSignals(PipelineBaseModel):
    """Structural signals detected in the HTML content.

    Attributes:
        faq_sections: Number of FAQ-like sections (details/summary elements).
        tables: Number of tables.
        ordered_lists: Number of ordered lists (ol).
        unordered_lists: Number of unordered lists (ul).
        video_embeds: Number of video embeds (iframe, video).
        forms: Number of forms.
        images_in_content: Number of images in content.
    """

    faq_sections: int
    tables: int
    ordered_lists: int
    unordered_lists: int
    video_embeds: int
    forms: int
    images_in_content: int
