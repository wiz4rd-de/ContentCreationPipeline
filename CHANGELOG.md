# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- <items for next release go here>

## [0.2.0] - 2026-03-11

### Added
- SERP cache with keyword validation and `--force` bypass
- Auto-derived `--outdir` from keyword slug
- Static SERP fixture support
- Full deterministic briefing pipeline (9-step chain)
- Content briefing skill with Phase 1/Phase 2 architecture
- SEO content pipeline skill (end-to-end orchestration)
- Shared slugify utility for directory name generation
- Keyword retry logic with exponential backoff
- TTL validation to SERP cache
- Pre-flight validation script for pipeline runs
- Stderr progress output to silent pipeline scripts
- Briefing-data.json metadata with input params and timestamps
- Shared tokenizer module with unit tests
- IDF computation script (build-idf-table.mjs)
- Production idf-de.json from Leipzig Wikipedia 1M corpus
- WDF*IDF content draft scoring script
- Cleanup script for old output directories

### Fixed
- fetch-difficulty 404 endpoint fix
- merge-keywords response shape handling
- Test fixture mutation by copying to tmp directory
- Stopwords umlaut variants and missing entries
- Page structure filtering for blocked/error pages
- AIO text encoding artifacts in SERP processing

## [0.1.0] - 2026-03-05

### Added
- Initial keyword research pipeline (fetch, merge, process, expand)
- DataForSEO integration (related_keywords, keyword_suggestions)
- Keyword difficulty endpoint and opportunity score formula
- Page extractor with Readability + jsdom
- Location code resolver
- Entity prominence computation
- SERP enrichment with AIO text/citations and PAA answers
- Page structure analyzer with module detection and content depth
- TF-IDF content topic analyzer with section weight analysis
- Keyword filtering (ethics, brand, off-topic)
- Briefing data assembly from pipeline outputs
- Content briefing and SEO content pipeline skills
- Async SERP fetching with task_post/task_get workflow
- SERP cache checking
- Test scaffolding with Node.js built-in test runner
- Data flow documentation
