# Claude Content Creation Pipeline

AI-powered SEO content pipeline built entirely with Claude Code Skills — from keyword research to publish-ready articles. Zero custom code, no backend required.

## Overview

This project automates the end-to-end process of creating SEO-optimized content using a 5-step pipeline orchestrated by Claude Code Skills. Each step builds on the previous one, producing structured data and human-readable output at every stage.

```
Seed Keyword
     |
     v
 1. Keyword Research -----> keywords-<slug>.json
     |
     v
 2. Competitor Analysis ---> competitors-<slug>.json
     |
     v
 3. Content Strategy ------> strategy-<slug>.json
     |
     v
 4. Content Briefing ------> brief-<slug>.md
     |
     v
 5. Content Draft ---------> draft-<slug>.md
```

All outputs are saved to `output/YYYY-MM-DD_<topic>/`.

## Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- An SEO data provider account (one of: DataForSEO, SEMrush, Ahrefs, or any REST-based keyword API)

## Setup

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd ClaudeContentCreationPipeline
   ```

2. Configure your SEO API credentials:

   ```bash
   cp api.env.example api.env
   ```

3. Edit `api.env` — uncomment and fill in the block for your provider:

   | Provider | Auth |
   |----------|------|
   | DataForSEO | Login + password |
   | SEMrush | API key |
   | Ahrefs | API key (Bearer token) |
   | Generic REST | API key + custom endpoint URLs |

4. Set your market and language:

   ```env
   SEO_MARKET=us
   SEO_LANGUAGE=en
   ```

## Usage

### Full pipeline

Run the complete 5-step pipeline with a single command:

```
/seo-content-pipeline
```

Claude will ask for:
- **Seed keyword or topic** (e.g., "thailand urlaub")
- **Your domain** (excluded from competitor analysis)
- **Business context** (what you sell, your audience)
- **Content goals** (traffic, leads, authority)
- **Brand voice** (optional)

The pipeline runs each step sequentially with checkpoints between stages, letting you review and adjust before proceeding.

### Individual skills

Each pipeline step is also available as a standalone skill:

| Command | Description |
|---------|-------------|
| `/seo-keyword-research` | Retrieve keyword data from your SEO API, cluster by intent and volume |
| `/competitor-analysis` | Analyze top-ranking pages, extract structure and content gaps |
| `/content-strategy` | Synthesize keyword + competitor data into a prioritized content roadmap |
| `/content-briefing` | Generate a detailed writing brief using a content template |
| `/content-draft` | Write a complete, publish-ready article from a brief |

## Output Structure

Each pipeline run creates a dated folder:

```
output/
  2026-03-03_thailand-urlaub/
    keywords-thailand-urlaub.json
    competitors-thailand-urlaub.json
    strategy-thailand-urlaub.json
    brief-thailand-urlaub.md
    draft-thailand-urlaub.md
```

## Content Templates

Templates in `templates/` control the structure and format of generated briefs and articles:

| Template | Purpose |
|----------|---------|
| `template-urlaubsseite.md` | Transactional destination pages (11,000-15,000 characters) |
| `template-reisemagazin.md` | Inspirational travel magazine articles (1,500-2,500 words) |
| `dt-tov.md` | Brand tone of voice guide |

Add your own templates to `templates/` — they'll be offered as options during the briefing step.

## Customization

- **Templates** — Add `.md` files to `templates/` with your content structure, section guidelines, and character limits
- **API provider** — Switch providers by changing `SEO_PROVIDER` in `api.env`
- **New skills** — Add Claude Code Skills to `.claude/skills/` to extend the pipeline with additional steps

## Project Structure

```
ClaudeContentCreationPipeline/
  .claude/
    skills/
      seo-content-pipeline/    # Full pipeline orchestrator
      seo-keyword-research/    # Step 1: Keyword research
      competitor-analysis/     # Step 2: Competitor analysis
      content-strategy/        # Step 3: Content strategy
      content-briefing/        # Step 4: Content briefing
      content-draft/           # Step 5: Content draft
  templates/                   # Content structure templates
  output/                      # Generated pipeline outputs
  api.env.example              # API configuration template
```
