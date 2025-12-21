# Keyword-Researcher Repository Refactoring Plan

## Overview
Restructure the keyword-researcher repository from 24 files at root level into organized `src/` and `tests/` directories, eliminating ~38-43% of code duplication by extracting shared utilities and consolidating around the unified `feed_reader.py` architecture.

**Current State:** 8,069 lines across 23 Python files
**Target State:** ~4,500-5,000 lines in organized structure
**Reduction:** ~3,000-3,500 lines through deduplication and deletion

## User Decisions
1. ✅ **Delete** research/analysis files (*_research.py, *_structure_analyzer.py) - archived in git
2. ✅ **Unified feed_reader.py approach** - migrate features from individual extractors into FeedReader classes

## Target Directory Structure

```
keyword-researcher/
├── src/
│   ├── core/
│   │   ├── base.py              # FeedReader abstract base class
│   │   ├── browser.py           # BrowserManager (eliminates 20+ duplicates)
│   │   ├── models.py            # Unified Post models (11 dataclasses → hierarchy)
│   │   └── config.py            # Constants and configurations
│   ├── extractors/
│   │   ├── substack.py          # From feed_reader.py + substack_extractor.py
│   │   ├── twitter.py           # From feed_reader.py + twitter_extractor.py
│   │   ├── reddit.py            # From feed_reader.py
│   │   ├── hackernews.py        # From feed_reader.py
│   │   ├── medium.py            # From feed_reader.py
│   │   ├── youtube.py           # From feed_reader.py
│   │   ├── linkedin.py          # New: convert linkedin_extractor.py → FeedReader
│   │   ├── instagram.py         # New: convert instagram_post_extractor.py → FeedReader
│   │   └── facebook.py          # New: convert facebook_post_extractor.py → FeedReader
│   ├── utils/
│   │   ├── parsing.py           # BeautifulSoup + CSS selector fallback
│   │   ├── metrics.py           # K/M/B engagement number conversion
│   │   ├── formatting.py        # Markdown formatting helpers
│   │   └── scrolling.py         # Page scrolling utilities
│   ├── database/
│   │   └── db_tool.py           # Moved from root (unchanged)
│   └── feed_reader.py           # Main entry point with create_feed_reader()
├── tests/
│   ├── test_feed_readers.py     # Moved from root
│   ├── test_extractors.py       # Renamed from test_extractor.py
│   ├── test_reddit_extraction.py
│   ├── test_facebook_selectors.py
│   └── fixtures/
│       └── sample_instagram_post.html
└── scripts/
    └── read_markdown_feed.py    # Moved from root
```

## Key Deduplication Targets

### 1. Browser Management (`src/core/browser.py`)
**Eliminates 20+ instances** of:
```python
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=60000)
```

### 2. Scrolling Logic (`src/utils/scrolling.py`)
**Eliminates 15+ instances** of:
```python
for i in range(3):
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
```

### 3. Data Models (`src/core/models.py`)
**Consolidates 11 dataclasses** into hierarchy:
- BasePost (common fields)
- SocialMediaPost (adds engagement metrics)
- Platform-specific: Tweet, LinkedInPost, InstagramPost, FacebookPost, RedditPost, etc.

### 4. Engagement Metrics (`src/utils/metrics.py`)
**Extract from twitter_extractor.py:164-181** - K/M/B/T number conversion used by Twitter, LinkedIn, Instagram

### 5. CSS Selector Fallback (`src/utils/parsing.py`)
**Standardizes** repeated try-multiple-selectors patterns across all extractors

## Implementation Sequence

### Phase 1: Core Infrastructure (Foundation)
1. Create directory structure (src/, tests/, scripts/)
2. **src/core/models.py** - Unified Post hierarchy (all extractors depend on this)
3. **src/core/browser.py** - BrowserManager class
4. **src/core/base.py** - Copy FeedReader from feed_reader.py:18-68
5. **src/core/config.py** - Constants

### Phase 2: Utilities Layer
6. **src/utils/metrics.py** - Extract K/M/B conversion from twitter_extractor.py:164-181
7. **src/utils/scrolling.py** - Extract scroll_to_load() pattern
8. **src/utils/parsing.py** - BeautifulSoup helpers, find_with_fallback()
9. **src/utils/formatting.py** - Markdown formatting utilities

### Phase 3: Simple Extractors (Copy from feed_reader.py)
10. **src/extractors/substack.py** - Copy SubstackFeedReader, merge JSON extraction from substack_extractor.py
11. **src/extractors/reddit.py** - Copy RedditFeedReader (no merge needed)
12. **src/extractors/hackernews.py** - Copy HackerNewsFeedReader (no merge needed)
13. **src/extractors/medium.py** - Copy MediumFeedReader (no merge needed)
14. **src/extractors/youtube.py** - Copy YouTubeFeedReader (no merge needed)

### Phase 4: Complex Extractors (Merge standalone → FeedReader)
15. **src/extractors/twitter.py** - Copy TwitterFeedReader + merge engagement extraction from twitter_extractor.py
16. **src/extractors/linkedin.py** - Convert linkedin_extractor.py to LinkedInFeedReader pattern
17. **src/extractors/instagram.py** - Convert instagram_post_extractor.py to InstagramFeedReader pattern
18. **src/extractors/facebook.py** - Convert facebook_post_extractor.py to FacebookFeedReader pattern

### Phase 5: Main Entry Point
19. **src/feed_reader.py** - Copy create_feed_reader() factory + CLI, import all extractors
20. **src/database/db_tool.py** - Move from root (unchanged)
21. **scripts/read_markdown_feed.py** - Move from root (unchanged)

### Phase 6: Tests Migration
22. Move tests to tests/ directory
23. Update all imports: `from src.feed_reader import create_feed_reader`
24. Move sample_instagram_post.html to tests/fixtures/
25. Run test suite to verify

### Phase 7: Cleanup
26. **DELETE research files** (10 files, 2,559 lines):
   - twitter_research.py, substack_research.py, linkedin_html_research.py
   - instagram_structure_research.py, facebook_structure_analyzer.py
   - reddit_structure_analyzer.py, analyze_reddit_structure.py
   - reddit_playwright_scraper.py, linkedin_selector_validator.py
   - advanced_instagram_scraper.py

27. **DELETE old extractors** (5 files, 1,737 lines - features now in src/extractors/):
   - twitter_extractor.py, linkedin_extractor.py, instagram_post_extractor.py
   - facebook_post_extractor.py, substack_extractor.py

28. **DELETE old test** (1 file):
   - reddit_extractor_test.py (covered by tests/test_reddit_extraction.py)

29. **DELETE from root**:
   - feed_reader.py (now in src/)
   - db_tool.py (now in src/database/)
   - read_markdown_feed.py (now in scripts/)
   - sample_instagram_post.html (now in tests/fixtures/)
   - test_*.py files (now in tests/)

### Phase 8: Package Setup
30. Add __init__.py files to all packages
31. Create src/__init__.py with clean exports
32. Optional: Add compatibility shim at root with deprecation warning

## Critical Files

**Must implement first (dependencies):**
- `feed_reader.py` (734 lines) - source for all FeedReader classes
- `twitter_extractor.py:164-181` - engagement metrics parsing to extract
- `linkedin_extractor.py` - full file to convert to FeedReader pattern
- `instagram_post_extractor.py` - full file to convert to FeedReader pattern
- `facebook_post_extractor.py` - full file to convert to FeedReader pattern

**Files to migrate:**
- 5 test files → tests/
- 1 db file → src/database/
- 1 utility script → scripts/

**Files to delete:**
- 10 research files
- 5 old extractors
- 1 old test
- 4 root-level files after migration

## Import Changes

**Before:**
```python
from feed_reader import create_feed_reader
from twitter_extractor import TwitterExtractor
```

**After:**
```python
from src.feed_reader import create_feed_reader
from src.extractors.twitter import TwitterFeedReader
from src.core.models import Tweet, LinkedInPost
```

## Success Metrics

✅ All 24 root-level files moved to src/, tests/, or deleted
✅ ~3,000 lines eliminated through deduplication
✅ All tests pass with updated imports
✅ No duplicate browser management code
✅ No duplicate scrolling logic
✅ No duplicate engagement parsing
✅ Single unified data model hierarchy
✅ Clean package structure with __init__.py files

## Risk Mitigation

- Keep git history: research files archived, not lost
- Test after each phase to catch import errors early
- Start with simple extractors (Reddit, HackerNews) before complex ones
- Verify all extractor functionality preserved in migration
