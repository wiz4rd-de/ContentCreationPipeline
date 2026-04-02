"""Page extractor using BeautifulSoup + trafilatura.

Fetches a URL and extracts structured page metadata, headings,
link counts, main content, and HTML signals. Uses trafilatura with
favor_recall=True for content extraction to match Node.js pipeline
word counts more closely than readability-lxml.

Usage:
    python -m seo_pipeline.extractor.extract_page <URL> [--output path]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; ContentExtractor/1.0)"
TIMEOUT_SECONDS = 15


def extract_page_from_html(html: str, url: str) -> dict:
    """Extract structured data from raw HTML.

    Pure function: same HTML + URL always produces identical output.
    Separated from fetch logic so tests can call this without network.
    """
    soup = BeautifulSoup(html, "lxml")

    # Title from <title> tag
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = (
        (meta_desc_tag.get("content", "") or "").strip()
        if meta_desc_tag
        else ""
    )

    # Canonical URL
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = (
        (canonical_tag.get("href", "") or "").strip()
        if canonical_tag
        else ""
    )

    # Open Graph
    og_title_tag = soup.find("meta", attrs={"property": "og:title"})
    og_title = (
        (og_title_tag.get("content", "") or "").strip()
        if og_title_tag
        else ""
    )

    og_desc_tag = soup.find("meta", attrs={"property": "og:description"})
    og_description = (
        (og_desc_tag.get("content", "") or "").strip()
        if og_desc_tag
        else ""
    )

    # H1 -- first h1, whitespace-collapsed
    h1_tag = soup.find("h1")
    h1 = re.sub(r"\s+", " ", h1_tag.get_text().strip()) if h1_tag else ""

    # Headings in DOM order (h2-h4)
    headings = []
    for tag in soup.find_all(["h2", "h3", "h4"]):
        level = int(tag.name[1])
        text = re.sub(r"\s+", " ", tag.get_text().strip())
        headings.append({"level": level, "text": text})

    # Link classification: internal vs external
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname or ""
    internal = 0
    external = 0
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        try:
            parsed_link = urlparse(href)
            # Resolve relative URLs: if no scheme/netloc, it's internal
            link_host = parsed_link.hostname
            if link_host is None:
                internal += 1
            elif link_host == hostname:
                internal += 1
            else:
                external += 1
        except ValueError:
            # Skip malformed URLs (urlparse raises ValueError)
            pass

    # Content extraction via trafilatura (favor_recall=True for broad extraction)
    main_text_raw = trafilatura.extract(
        html,
        url=url,
        favor_recall=True,
        include_tables=True,
        include_comments=False,
    ) or ""

    # Title from trafilatura metadata, falling back to <title> tag
    meta = trafilatura.extract_metadata(html, default_url=url)
    readability_title = (meta.title if meta and meta.title else "") or title

    word_count = len(main_text_raw.split()) if main_text_raw.strip() else 0
    main_content_text = re.sub(r"\s+", " ", main_text_raw).strip()
    main_content_preview = main_content_text[:300]

    # HTML signals counted from the full page body, since trafilatura
    # does not preserve structural HTML elements in its output
    html_signals = {
        "faq_sections": 0,
        "tables": 0,
        "ordered_lists": 0,
        "unordered_lists": 0,
        "video_embeds": 0,
        "forms": 0,
        "images_in_content": 0,
    }
    body_tag = soup.find("body")
    if body_tag:
        html_signals["faq_sections"] = len(
            body_tag.find_all(["details", "summary"])
        )
        html_signals["tables"] = len(body_tag.find_all("table"))
        html_signals["ordered_lists"] = len(body_tag.find_all("ol"))
        html_signals["unordered_lists"] = len(body_tag.find_all("ul"))
        html_signals["video_embeds"] = len(
            body_tag.find_all(["iframe", "video"])
        )
        html_signals["forms"] = len(body_tag.find_all("form"))
        html_signals["images_in_content"] = len(body_tag.find_all("img"))

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "canonical_url": canonical_url,
        "og_title": og_title,
        "og_description": og_description,
        "h1": h1,
        "headings": headings,
        "word_count": word_count,
        "link_count": {"internal": internal, "external": external},
        "main_content_text": main_content_text,
        "main_content_preview": main_content_preview,
        "readability_title": readability_title,
        "html_signals": html_signals,
    }


def extract_page(url: str) -> dict:
    """Fetch a URL and extract structured page data.

    On any error, returns {"error": message, "url": url}.
    """
    logger.info("Fetching %s", url)
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=TIMEOUT_SECONDS,
        )
        logger.info("Response %d for %s", response.status_code, url)
        html = response.text
        result = extract_page_from_html(html, url)
        logger.info(
            "Extracted: %d words, %d headings, h1=%r from %s",
            result.get("word_count", 0),
            len(result.get("headings", [])),
            result.get("h1", ""),
            url,
        )
        return result
    except Exception as err:
        logger.info("Extraction failed for %s: %s", url, err)
        return {"error": str(err), "url": url}


def main() -> None:
    """CLI entry point for extract_page."""
    parser = argparse.ArgumentParser(
        description="Fetch a URL and extract structured page metadata"
    )
    parser.add_argument("url", nargs="?", default=None, help="URL to extract")
    parser.add_argument("--output", help="Path to write output JSON file")

    args = parser.parse_args()

    if not args.url:
        msg = (
            "Usage: python -m seo_pipeline.extractor.extract_page"
            " <URL> [--output <path>]"
        )
        print(json.dumps({"error": msg}))
        sys.exit(1)

    print(f"Extracting: {args.url} ...", file=sys.stderr)

    result = extract_page(args.url)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
