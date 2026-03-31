# Pythonic Idiom Review (Phases 1-4)

Review date: 2026-03-31

## Summary

The codebase is well-structured with clean separation of concerns, consistent docstrings, and deterministic behavior where required. Most modules are idiomatic Python. The main findings fall into three categories: (1) duplicated utility code across modules, (2) opportunities to use stdlib/pathlib more consistently, and (3) minor structural improvements (missing `__all__`, untyped collections in models). The `js_round()` pattern in `math.py` is intentionally JS-faithful and should be preserved.

**Finding count by risk level:**
- HIGH: 2
- MEDIUM: 7
- LOW: 5

---

## Findings

### Finding 1: Duplicated `FOREIGN_RE` and `_is_foreign_language()` across modules

- **Files:** `seo_pipeline/keywords/filter_keywords.py` (lines 17-18, 77-86), `seo_pipeline/keywords/prepare_strategist_data.py` (lines 16-17, 19-28)
- **Pattern:** The exact same regex constant `FOREIGN_RE` and helper function `_is_foreign_language()` are defined independently in two modules.
- **Recommendation:** Extract to a shared location (e.g., `seo_pipeline/utils/text.py` or add to `tokenizer.py`) and import from both callers.
- **Risk level:** HIGH -- Divergent edits to one copy without updating the other will silently change filtering behavior between pipeline stages.

### Finding 2: Duplicated hand-rolled `.env` parser in `preflight.py`

- **File:** `seo_pipeline/utils/preflight.py` (lines 37-61)
- **Pattern:** `parse_env_content()` is a hand-rolled `.env` parser that duplicates the logic previously in `load_api_config.py`. Now that `load_api_config.py` uses `python-dotenv` (issue #48), `preflight.py` still has its own parser.
- **Recommendation:** Refactor `preflight.py` to use `dotenv_values()` from python-dotenv for parsing, keeping only the validation checks (`check_auth`, `check_base64`, `check_base`) as custom logic.
- **Risk level:** HIGH -- Two different parsers for the same file format can produce different results on edge cases (quoted values, inline comments, etc.).
- **Note:** Issue #48 is already tracked and resolved for `load_api_config.py`. This finding covers the remaining duplication in `preflight.py`.

### Finding 3: `importlib.resources` fallback code for Python < 3.9

- **Files:** `seo_pipeline/utils/tokenizer.py` (lines 64-85), `seo_pipeline/utils/resolve_location.py` (lines 24-35)
- **Pattern:** Both modules contain multi-branch fallback logic for `importlib.resources.files()` (Python 3.9+) vs older APIs (`importlib.resources.open_text`, `pkg_resources`). The project requires Python >= 3.11 (per `pyproject.toml`), so the fallback branches are dead code. In `tokenizer.py`, there is additionally a filesystem fallback using `os.path`.
- **Recommendation:** Remove all pre-3.9 fallback branches. Use only `importlib.resources.files()` which is guaranteed available on Python 3.11+. In `tokenizer.py`, remove the `os.path` fallback and the broad `except` clause.
- **Risk level:** MEDIUM -- Dead code increases maintenance burden and obscures the actual loading path. The broad `except` in `tokenizer.py` (line 80) could mask real errors.

### Finding 4: `open()` used instead of `Path.read_text()` / `Path.write_text()`

- **Files:** `seo_pipeline/keywords/filter_keywords.py` (lines 31, 36), `seo_pipeline/keywords/merge_keywords.py` (lines 112-115), `seo_pipeline/keywords/process_keywords.py` (lines 392-406)
- **Pattern:** Several modules use `open(path, encoding="utf-8") as f: json.load(f)` instead of `Path(path).read_text(encoding="utf-8")` + `json.loads()`. The codebase already uses `Path.read_text()` consistently in `process_serp.py`, `assemble_competitors.py`, and `fetch_serp.py`.
- **Recommendation:** Standardize on `Path.read_text()` / `json.loads()` throughout for consistency. This also avoids forgetting the `encoding` parameter on `open()`.
- **Risk level:** MEDIUM -- Inconsistency only; functionally equivalent.

### Finding 5: Untyped `list` fields in Pydantic models

- **Files:** `seo_pipeline/models/serp.py` (lines 241, 318-319, 321, 323-325), `seo_pipeline/models/keywords.py` (lines 25, 153-154, 156-160), `seo_pipeline/models/analysis.py` (lines 385-387, 520-524)
- **Pattern:** Several Pydantic model fields use bare `list` or `dict` without type parameters, e.g., `headings: list | None`, `topics: list | None`, `people_also_search: list`, `stats: dict`. This disables Pydantic's nested validation for those fields.
- **Recommendation:** Add type parameters where the element type is known (e.g., `list[Heading]`, `list[str]`, `dict[str, int]`). Where the shape is genuinely dynamic (e.g., `stats: dict`), document the expected shape in the docstring.
- **Risk level:** MEDIUM -- Reduces type safety and IDE support. No runtime impact since Pydantic passes through untyped collections.

### Finding 6: `model_config = ConfigDict(populate_by_name=True)` on every model

- **Files:** All files in `seo_pipeline/models/` (common.py, serp.py, page.py, keywords.py, analysis.py)
- **Pattern:** Every single Pydantic model class repeats `model_config = ConfigDict(populate_by_name=True)`. None of the models use `Field(alias=...)` except `EntityProminence.debug` (alias `_debug`). For models without aliases, `populate_by_name` has no effect.
- **Recommendation:** Create a `BaseModel` subclass in `common.py` with the shared config, and have all models inherit from it instead of repeating the line. This also provides a single place to add future shared config (e.g., `from_attributes=True`).
- **Risk level:** MEDIUM -- Pure DRY improvement. No behavioral change.

### Finding 7: Missing `__all__` in most module `__init__.py` files

- **Files:** `seo_pipeline/serp/__init__.py`, `seo_pipeline/keywords/__init__.py`, `seo_pipeline/utils/__init__.py`
- **Pattern:** Only `seo_pipeline/models/__init__.py` and `seo_pipeline/extractor/__init__.py` define `__all__`. Other packages lack it, making public API boundaries implicit.
- **Recommendation:** Add `__all__` to every package `__init__.py` to declare the public API. This helps IDE autocompletion, documentation generators, and prevents accidental imports of private symbols.
- **Risk level:** MEDIUM -- No runtime impact, but improves discoverability and API hygiene.

### Finding 8: CLI argument parsing inconsistency

- **Files:** `seo_pipeline/serp/process_serp.py` (lines 404-421), `seo_pipeline/serp/assemble_competitors.py` (lines 157-189), `seo_pipeline/extractor/extract_page.py` (lines 178-215) vs. `seo_pipeline/keywords/merge_keywords.py`, `process_keywords.py`, `fetch_keywords.py` (all use `argparse`)
- **Pattern:** Phase 3 modules use hand-rolled `sys.argv` parsing (index-based flag extraction), while Phase 4 modules use `argparse.ArgumentParser`. The hand-rolled parsers lack `--help` support, error messages for invalid flags, and are fragile (e.g., `args.index("--top")` will crash if flag is last arg without value).
- **Recommendation:** Standardize on `argparse` for all CLI entry points. Alternatively, if the project will adopt `typer` (already in optional deps), plan for that migration.
- **Risk level:** MEDIUM -- Fragile CLI parsing could cause confusing errors for users.

### Finding 9: `js_round()` in `math.py` -- intentionally JS-faithful (no change needed)

- **File:** `seo_pipeline/utils/math.py` (lines 1-27)
- **Pattern:** `js_round()` implements JavaScript `Math.round()` semantics using `math.floor(x + 0.5)`. This deliberately differs from Python's built-in `round()` (banker's rounding) to ensure byte-identical output with the Node.js original.
- **Recommendation:** No change. This is correctly documented and the JS-faithful approach is the right choice for this migration. The docstring clearly explains the difference.
- **Risk level:** N/A -- Correctly intentional.

### Finding 10: `typing.Set` instead of `set` in type hints

- **File:** `seo_pipeline/utils/tokenizer.py` (lines 9, 34, 49)
- **Pattern:** Uses `from typing import Set` and `Set[str]` in function signatures. Since Python 3.9+, the built-in `set[str]` is preferred and `typing.Set` is deprecated.
- **Recommendation:** Replace `Set[str]` with `set[str]` and remove the `typing` import.
- **Risk level:** LOW -- Cosmetic; `typing.Set` still works but is deprecated.

### Finding 11: Inline `import` inside functions

- **Files:** `seo_pipeline/utils/tokenizer.py` (lines 61-62: `import json`, `import os` inside `load_stopword_set`), `seo_pipeline/serp/fetch_serp.py` (line 461: `import time` inside `_monotonic_ms`)
- **Pattern:** Standard library imports placed inside functions rather than at module level.
- **Recommendation:** Move `import json` and `import os` to module top in `tokenizer.py`. For `fetch_serp.py`, `import time` at module level is fine since it's stdlib and always available. Inline imports are acceptable for optional dependencies to avoid import errors, but not for stdlib.
- **Risk level:** LOW -- No behavioral impact; style preference per PEP 8.

### Finding 12: `_normalize_number()` reimplements a common pattern

- **File:** `seo_pipeline/keywords/process_keywords.py` (lines 36-44)
- **Pattern:** `_normalize_number()` converts `4.0` to `4` for JSON serialization parity with Node.js. This is needed because `json.dumps(4.0)` produces `"4.0"` while JavaScript's `JSON.stringify(4)` produces `"4"`.
- **Recommendation:** Consider moving this to `seo_pipeline/utils/math.py` alongside `js_round()` since both exist for Node.js output parity. Other modules may need it in future phases.
- **Risk level:** LOW -- Single call site currently, but could benefit from centralization.

### Finding 13: Bare `except Exception` in `extract_page.py`

- **File:** `seo_pipeline/extractor/extract_page.py` (lines 98, 174)
- **Pattern:** Line 98 uses bare `except Exception: pass` for malformed URLs, and line 174 catches all exceptions to return error dict. The broad catch on line 174 is acceptable for a top-level extraction function (graceful degradation), but line 98 silently swallows parsing errors during link classification.
- **Recommendation:** Line 98: catch `ValueError` specifically (what `urlparse` can raise). Line 174: keep as-is (intentional graceful degradation for page extraction).
- **Risk level:** LOW -- Unlikely to cause issues since `urlparse` rarely raises, but narrower exceptions are better practice.

### Finding 14: `slugify.py` could use `str.translate()` for umlaut replacement

- **File:** `seo_pipeline/utils/slugify.py` (lines 49-50)
- **Pattern:** Iterates over `_UMLAUT_MAP` dict calling `s.replace()` in a loop (7 iterations). Python's `str.translate()` with `str.maketrans()` does this in a single pass.
- **Recommendation:** Build a translation table once at module level: `_UMLAUT_TABLE = str.maketrans(_UMLAUT_MAP)` and use `s = s.translate(_UMLAUT_TABLE)`. Minor performance improvement and more idiomatic.
- **Risk level:** LOW -- Micro-optimization; current approach is perfectly correct.

---

## Files Reviewed With No Findings

The following files were reviewed and found to be idiomatic Python with no issues:

- **`seo_pipeline/keywords/extract_keywords.py`** -- Clean module with proper type hints (`dict | None`, `list[dict]`), comprehensive docstrings, early returns for safe nested-dict traversal, and correct use of `dict.get()` with fallback values. No duplicated logic, no deprecated imports, no dead code.
