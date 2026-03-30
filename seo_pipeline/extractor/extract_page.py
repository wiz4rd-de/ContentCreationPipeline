"""Page extractor using BeautifulSoup + readability-lxml.

Fetches a URL and extracts structured page metadata, headings,
link counts, readability content, and HTML signals. Deterministic
HTML parsing with tolerance for readability content differences.

Usage:
    python -m seo_pipeline.extractor.extract_page <URL> [--output path]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document as ReadabilityDocument

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
        except Exception:
            # Skip malformed URLs
            pass

    # Readability extraction for main content
    doc = ReadabilityDocument(html, url=url)
    article_html = doc.summary() or ""
    readability_title = doc.short_title() or ""

    # Extract text from readability HTML
    if article_html:
        content_soup = BeautifulSoup(article_html, "lxml")
        main_text_raw = content_soup.get_text()
    else:
        main_text_raw = ""

    word_count = len(main_text_raw.split()) if main_text_raw.strip() else 0
    main_content_text = re.sub(r"\s+", " ", main_text_raw).strip()
    main_content_preview = main_content_text[:300]

    # HTML signals from readability-extracted content
    html_signals = {
        "faq_sections": 0,
        "tables": 0,
        "ordered_lists": 0,
        "unordered_lists": 0,
        "video_embeds": 0,
        "forms": 0,
        "images_in_content": 0,
    }
    if article_html:
        content_soup = BeautifulSoup(article_html, "lxml")
        html_signals["faq_sections"] = len(
            content_soup.find_all(["details", "summary"])
        )
        html_signals["tables"] = len(content_soup.find_all("table"))
        html_signals["ordered_lists"] = len(content_soup.find_all("ol"))
        html_signals["unordered_lists"] = len(content_soup.find_all("ul"))
        html_signals["video_embeds"] = len(
            content_soup.find_all(["iframe", "video"])
        )
        html_signals["forms"] = len(content_soup.find_all("form"))
        html_signals["images_in_content"] = len(content_soup.find_all("img"))

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
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=TIMEOUT_SECONDS,
        )
        html = response.text
        return extract_page_from_html(html, url)
    except Exception as err:
        return {"error": str(err), "url": url}


def main() -> None:
    """CLI entry point for extract_page."""
    args = sys.argv[1:]
    url = None
    output_path = None

    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            url = args[i]
            i += 1
        else:
            i += 1

    if not url:
        msg = (
            "Usage: python -m seo_pipeline.extractor.extract_page"
            " <URL> [--output <path>]"
        )
        error_json = json.dumps({"error": msg})
        print(error_json)
        sys.exit(1)

    print(f"Extracting: {url} ...", file=sys.stderr)

    result = extract_page(url)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        Path(output_path).write_text(output, encoding="utf-8")
    else:
        print(output)

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
