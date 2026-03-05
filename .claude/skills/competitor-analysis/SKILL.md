---
name: competitor-analysis
description: Analyze top-ranking pages for target keywords and extract actionable competitive intelligence. Use when the user wants to research competitors or understand the SERP landscape.
---

# Competitor Analysis

Analyze the top-ranking pages for target keywords and extract actionable competitive intelligence.

## Inputs

Ask the user for:
1. **Target keyword(s)** — or read from an existing keyword research file in `output/`
2. **Your domain** (optional — to exclude from competitor list)
3. **Number of competitors to analyze** (default: 5)

## Steps

### 1. Load config and prior data

```sh
source api.env
```

Check `output/` for existing keyword research files. If one exists for the topic, offer to use it.

### 2. Fetch SERP data

For each primary keyword, retrieve the top 10 search results.

Adapt URL, auth header, and payload to `$SEO_PROVIDER` — see `api.env.example` for provider-specific endpoints and credentials.

```sh
# Example (DataForSEO). Adapt for your provider.
curl -s -X POST "$DATAFORSEO_BASE/serp/google/organic/live/advanced" \
  -H "Authorization: Basic $DATAFORSEO_AUTH" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '[{"keyword": "<KEYWORD>", "language_code": "'"$SEO_LANGUAGE"'", "location_code": <LOCATION_CODE>, "depth": 10}]' \
  | jq '.tasks[0].result[0].items'
```

> **Encoding:** Always use `charset=utf-8` in the Content-Type header to support umlauts and special characters in keywords.

> `location_code` is derived from `$SEO_MARKET` (e.g. `de` → 2276 for Germany). Refer to your provider's docs for the full mapping.

> **Advanced endpoint:** The `live/advanced` endpoint returns richer data than `live/regular`, including `ai_overview` items with source references, `people_also_ask`, and `related_searches` alongside `organic` results. Filter items by `type == "organic"` to extract competitor URLs. The AI overview data can provide additional competitive insights (which domains Google cites as authoritative).

Use WebFetch to retrieve and analyze competitor pages for content analysis.

### 2b. Extract SERP features from advanced endpoint

The advanced endpoint can return up to 50 different item types. Record which types are present in `item_types_present` — the mix itself signals intent and SERP complexity.

Process items by category:

#### Core ranking items
- **`organic`** — competitor URLs, titles, descriptions, rank positions. Filter these for the competitor list.
- **`paid`** — paid ads signal commercial intent and show which competitors invest in PPC for this keyword.
- **`featured_snippet`** — the page Google elevates above organic #1. Note the format (paragraph, list, table) and source domain — this is the format to beat.
- **`ai_overview`** — Google's AI-generated answer. Extract:
  - The full markdown summary (what Google considers the authoritative answer)
  - Referenced domains and URLs (these are the sources Google trusts most)
  - Key topics and structure Google chose to highlight (by region, by list, etc.)

#### User intent & related queries
- **`people_also_ask`** — questions users also search for. Capture each question — these reveal subtopics and user intent gaps.
- **`people_also_search`** — related search refinements. Capture as secondary keyword opportunities.
- **`related_searches`** — additional related queries. Capture for keyword expansion.
- **`find_results_on`** — platforms Google suggests for this query (e.g. YouTube, Reddit). Signals where users expect to find answers.
- **`discussions_and_forums`** — forum threads Google surfaces. Extract questions and topics — these show real user pain points.
- **`perspectives`** — personal experience content Google highlights. Shows demand for first-person/authentic content.

#### Rich media & content format signals
- **`video`** / **`short_videos`** — video results signal demand for video content on this topic.
- **`images`** — image pack presence signals visual content demand.
- **`recipes`** — recipe cards (relevant for food/cooking topics).
- **`podcasts`** — podcast episodes surfaced for this query.
- **`courses`** — educational course results.
- **`top_stories`** — news results signal trending/timely topic.
- **`visual_stories`** — web stories featured for this query.

#### Commerce & product signals
- **`commercial_units`** — product listings signal transactional intent.
- **`shopping`** — shopping ads/results.
- **`popular_products`** — trending products for this query.
- **`product_considerations`** — product comparison/consideration features.
- **`refine_products`** — product refinement filters Google shows.
- **`explore_brands`** — brand exploration feature.
- **`compare_sites`** — comparison site suggestions.
- **`hotels_pack`** / **`google_hotels`** / **`google_flights`** — travel-specific commerce.
- **`local_pack`** / **`local_services`** / **`map`** — local intent signals.

#### Knowledge & authority signals
- **`knowledge_graph`** — entity panel. Shows Google has a clear entity understanding of the topic.
- **`answer_box`** — direct answer. Note the format and source.
- **`scholarly_articles`** — academic sources cited. Signals demand for authoritative/research-backed content.
- **`stocks_box`** / **`currency_box`** / **`math_solver`** — specialized data widgets.
- **`questions_and_answers`** — Q&A results (often from Stack Exchange, Quora).
- **`found_on_web`** — supplementary web mentions.

#### Social & engagement signals
- **`twitter`** — tweets surfaced for this query.
- **`google_posts`** — Google Business Profile posts.
- **`google_reviews`** / **`third_party_reviews`** — review content. Signals demand for opinion/evaluation content.
- **`mention_carousel`** — brand/entity mentions carousel.

#### Other
- **`carousel`** / **`multi_carousel`** — visual carousels (images, entities, etc.).
- **`top_sights`** — tourist attraction features.
- **`app`** — app store results.
- **`jobs`** — job listings.
- **`events`** — event listings.

Use this data to enrich the competitive analysis: the mix of SERP features tells you what content formats Google expects, AI overview references show which domains Google considers authoritative, people_also_ask reveals content angles competitors may miss, and related searches surface keyword opportunities.

### 3. Analyze each competitor page

For each competitor URL, run the page extractor to get precise structural data:

```sh
node src/extractor/extract-page.mjs "<URL>"
```

This returns JSON with: title, meta_description, canonical_url, og_title, og_description, h1, headings, word_count, link_count, main_content_preview.

Use these precise values in your analysis instead of estimating from WebFetch. You may still use WebFetch for qualitative analysis (content format, topics, unique angles) that requires reading comprehension.

For each page, extract or determine:

- **URL and domain**
- **Title tag** and **meta description** (from extractor)
- **H1 and heading structure** (from extractor)
- **Word count** (from extractor)
- **Content format** (listicle, how-to, guide, comparison, etc.)
- **Key topics and subtopics covered**
- **Unique angles or differentiators**
- **Internal/external linking patterns** (from extractor)

### 4. Build the competitive landscape

Create a comparison matrix:

| Competitor | Word Count | Format | Key Topics | Unique Angle | Content Gap |
|-----------|-----------|--------|-----------|-------------|-------------|
| ...       | ...       | ...    | ...       | ...         | ...         |

Identify:
- **Common themes** all competitors cover (table stakes)
- **Content gaps** topics none or few competitors address well
- **Differentiation opportunities** angles you could own
- **Weaknesses** areas where competitors are thin or outdated
- **AI Overview insights** — which domains are cited, what structure/topics Google chose, and how to position content for AI overview inclusion
- **People Also Ask** — user questions that indicate subtopic demand; flag which competitors answer them and which don't
- **Related searches** — secondary keyword opportunities for content expansion or internal linking

### 5. Save output

Write to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/competitors-<KEYWORD_SLUG>.json
```

JSON schema:
```json
{
  "target_keyword": "...",
  "date": "YYYY-MM-DD",
  "serp_overview": {
    "total_results": 0,
    "location": "...",
    "language": "...",
    "item_types_present": ["ai_overview", "organic", "people_also_ask", "..."]
  },
  "serp_features": {
    "ai_overview": {
      "present": true,
      "summary": "The full AI overview text/markdown Google generated",
      "cited_domains": [
        { "domain": "...", "url": "...", "title": "..." }
      ],
      "key_topics_highlighted": ["..."],
      "structure_notes": "How Google organized the answer (e.g. by region, by list, etc.)"
    },
    "featured_snippet": {
      "present": false,
      "format": "paragraph|list|table|null",
      "source_domain": "...",
      "source_url": "..."
    },
    "people_also_ask": ["Question 1?", "Question 2?"],
    "people_also_search": ["query 1", "query 2"],
    "related_searches": ["query 1", "query 2"],
    "discussions_and_forums": [
      { "source": "...", "url": "...", "title": "..." }
    ],
    "video": [
      { "title": "...", "url": "...", "source": "..." }
    ],
    "top_stories": [
      { "title": "...", "url": "...", "source": "..." }
    ],
    "knowledge_graph": {
      "present": false,
      "title": "...",
      "description": "..."
    },
    "commercial_signals": {
      "paid_ads_present": false,
      "shopping_present": false,
      "commercial_units_present": false,
      "popular_products_present": false
    },
    "local_signals": {
      "local_pack_present": false,
      "map_present": false,
      "hotels_pack_present": false
    },
    "other_features_present": ["images", "recipes", "podcasts", "..."]
  },
  "competitors": [
    {
      "rank": 0,
      "url": "...",
      "domain": "...",
      "title": "...",
      "word_count": 0,
      "format": "...",
      "topics": ["..."],
      "unique_angle": "...",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "cited_in_ai_overview": false,
      "has_featured_snippet": false
    }
  ],
  "common_themes": ["..."],
  "content_gaps": ["..."],
  "opportunities": ["..."]
}
```

> **Note:** Only populate SERP feature sections that are actually present in the response. Omit empty sections to keep the output clean. The `other_features_present` array captures any remaining item types not covered by dedicated sections above.

Print a concise competitive landscape summary to the conversation, including:
- **SERP feature overview** — which features are present and what they signal about user intent (e.g. commercial_units → transactional, discussions_and_forums → informational/problem-solving)
- **Competitor comparison matrix**
- **AI Overview** — which domains Google cites and what structure it chose (signals for content optimization and AIO inclusion)
- **Featured snippet** — format, source, and how to win it
- **People Also Ask** — the questions users are asking (content angle opportunities)
- **Related searches / People Also Search** — secondary keyword opportunities
- **Rich media signals** — whether video, images, podcasts etc. are present (content format recommendations)
- **Forum/discussion insights** — real user questions and pain points from surfaced threads
- **Content gaps and strategic opportunities**
