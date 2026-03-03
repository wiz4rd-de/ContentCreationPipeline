---
name: content-strategy
description: Synthesize keyword research and competitor analysis into an actionable content strategy with prioritized recommendations. Use when the user wants to plan which content to create and in what order.
---

# Content Strategy

Synthesize keyword research and competitor analysis into an actionable content strategy.

## Inputs

Ask the user for:
1. **Topic / seed keyword** — or auto-detect from existing files in `output/`
2. **Business context** — what do you sell/offer? who is your audience?
3. **Content goals** — traffic, leads, authority, conversions? (default: organic traffic growth)

## Steps

### 1. Load prior pipeline data

Read all matching files from the current run's `output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/` subfolder:
- `keywords-*.json` — keyword clusters
- `competitors-*.json` — competitive landscape

If these files don't exist yet, tell the user to run the keyword research and/or competitor analysis skills first.

### 2. Analyze the opportunity landscape

From the keyword clusters, evaluate each cluster on:
- **Search volume potential** (total volume of cluster)
- **Competition level** (average keyword difficulty)
- **Business relevance** (how well it maps to what the user offers)
- **Content gap score** (from competitor analysis — how underserved is this topic?)

Rank clusters by a combined opportunity score:
```
opportunity = (volume × relevance × gap_score) / difficulty
```

### 3. Recommend content pieces

For each high-opportunity cluster, recommend:
- **Content type** (pillar page, blog post, comparison, guide, tool, etc.)
- **Target keyword** (primary) and **secondary keywords**
- **Suggested angle** (what makes this piece different from competitors)
- **Funnel stage** (awareness → consideration → decision)
- **Priority** (high / medium / low based on opportunity score)

### 4. Map the content calendar

Organize recommendations into a prioritized sequence:
1. **Quick wins** — low difficulty, decent volume, easy to produce
2. **Strategic pillars** — high volume, builds topical authority
3. **Long-tail fills** — supporting content that strengthens clusters

Suggest a logical publishing order that builds topical authority progressively.

### 5. Save output

Write to:
```
output/YYYY-MM-DD_<SEED_KEYWORD_SLUG>/strategy-<TOPIC_SLUG>.json
```

JSON schema:
```json
{
  "topic": "...",
  "business_context": "...",
  "goals": ["..."],
  "date": "YYYY-MM-DD",
  "content_pieces": [
    {
      "priority": "high|medium|low",
      "title_suggestion": "...",
      "content_type": "...",
      "primary_keyword": "...",
      "secondary_keywords": ["..."],
      "target_intent": "...",
      "funnel_stage": "...",
      "angle": "...",
      "estimated_word_count": 0,
      "opportunity_score": 0
    }
  ],
  "publishing_order": ["title1", "title2", "..."]
}
```

Print a clear, prioritized content strategy summary to the conversation.
