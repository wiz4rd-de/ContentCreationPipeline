"""Data models for extracted page content and metadata."""

from pydantic import BaseModel, ConfigDict, Field

from seo_pipeline.models.common import Heading, HtmlSignals, LinkCount


class ExtractedPage(BaseModel):
    """Extracted page content and metadata.

    Attributes:
        url: The URL of the page.
        title: The page title from the <title> tag.
        meta_description: The page meta description.
        canonical_url: The canonical URL if specified.
        og_title: The Open Graph title.
        og_description: The Open Graph description.
        h1: The main H1 heading text.
        headings: List of headings (H2-H4) found on the page.
        word_count: Total word count of the main content.
        link_count: Count of internal and external links.
        main_content_text: The extracted main content text.
        main_content_preview: Preview of the main content (first 300 chars).
        readability_title: Title extracted by Readability.
        html_signals: Structural signals detected in the content.
    """

    url: str
    title: str = Field(default="")
    meta_description: str = Field(default="")
    canonical_url: str = Field(default="")
    og_title: str = Field(default="")
    og_description: str = Field(default="")
    h1: str = Field(default="")
    headings: list[Heading] = Field(default_factory=list)
    word_count: int = Field(default=0)
    link_count: LinkCount = Field(
        default_factory=lambda: LinkCount(internal=0, external=0)
    )
    main_content_text: str = Field(default="")
    main_content_preview: str = Field(default="")
    readability_title: str = Field(default="")
    html_signals: HtmlSignals = Field(
        default_factory=lambda: HtmlSignals(
            faq_sections=0,
            tables=0,
            ordered_lists=0,
            unordered_lists=0,
            video_embeds=0,
            forms=0,
            images_in_content=0,
        )
    )

    model_config = ConfigDict(populate_by_name=True)


class ExtractedPageError(BaseModel):
    """Error response from page extraction.

    Attributes:
        error: The error message.
        url: The URL that was being extracted when the error occurred.
    """

    error: str
    url: str

    model_config = ConfigDict(populate_by_name=True)
