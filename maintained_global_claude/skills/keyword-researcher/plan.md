# Speed Up Feed Reader - Optimized Implementation Plan

## Executive Summary

**Problem**: Slow performance (8-12 seconds per request) + massive code duplication (1200+ lines)

**Solution**: Config-driven extractors + HTTP-first approach + smart defaults

**Results**: 3-10x speed improvement + 60% code reduction (1200 → 400 lines)

## Code Duplication Audit

### Identified Duplication Patterns

1. **`_format_markdown` (108-167 lines EACH × 10 extractors = 1000+ lines)**

   - Identical structure: header, metadata with `' • '`, content, URL, `---`
   - Solution EXISTS but UNUSED: `format_post_card()` in `src/utils/formatting.py`

2. **Element extraction (30-50 lines each)**

   - Solution EXISTS but UNDERUSED: `extract_text()`, `extract_link()`, `find_with_fallback()` in `src/utils/parsing.py`
   - Only LinkedIn & Instagram use these; others duplicate logic

3. **Browser setup duplication**

   - Medium reimplements entire browser setup (56 lines)
   - SimpleBrowserContext already exists but Medium doesn't use it

4. **Auth checking (20-30 lines each)**

   - Duplicated across Twitter, LinkedIn, Instagram, Facebook

5. **Parse feed structure (identical across all)**
   ```python
   get content → parse HTML → find containers → extract items → format markdown
   ```


## Optimized Implementation Strategy

### Phase 1: Quick Wins (5 minutes, 30-50% faster) ⚡ START HERE

**Why first**: Immediate speed improvement with minimal risk

**File: `src/core/base.py`**

```python
# In SimpleBrowserContext.__init__, change defaults:
scroll_times=2,         # was 3 (saves 1.5 seconds)
scroll_delay=800,       # was 1500 (saves 2.1 seconds total)

# In SimpleBrowserContext.__enter__, change:
wait_until="domcontentloaded",  # was "networkidle" (saves 2-5 seconds)
self.page.wait_for_timeout(500)  # was 2000 (saves 1.5 seconds)
```

**File: `src/core/browser.py`**

```python
# In BrowserManager.navigate(), change default:
wait_until: str = "domcontentloaded"  # was "networkidle"
```

**Expected speedup**: 8-12 seconds → 5-8 seconds (30-40% faster)

### Phase 2: Generic Extraction Framework (2 hours, 630 lines saved)

**New File: `src/core/generic_extractor.py`** (~100 lines)

```python
from dataclasses import dataclass, field
from typing import Optional
from src.utils.parsing import parse_html, find_with_fallback, extract_text, extract_link

@dataclass
class ExtractorConfig:
    platform_name: str
    container_selectors: list[str]
    title_selectors: list[str] = field(default_factory=list)
    author_selectors: list[str] = field(default_factory=list)
    url_selectors: list[str] = field(default_factory=list)
    content_selectors: list[str] = field(default_factory=list)
    timestamp_selectors: list[str] = field(default_factory=list)
    engagement_selectors: dict[str, list[str]] = field(default_factory=dict)
    base_url: str = ""
    requires_auth: bool = False
    try_http_first: bool = False  # NEW: HTTP before browser
    link_prefix: str = ""  # e.g., "Read on Substack"

class GenericCardExtractor(FeedReader):
    def __init__(self, url: str, config: ExtractorConfig):
        super().__init__(url)
        self.config = config
    
    def read_feed(self) -> str:
        """Try HTTP first if configured, fallback to browser"""
        if self.config.try_http_first:
            html = self._try_http_fetch()
            if html:
                return self._parse_from_html(html)
        # Fallback to browser
        return super().read_feed()
    
    def _try_http_fetch(self) -> Optional[str]:
        """Try fetching via HTTP, return HTML or None"""
        try:
            import httpx
            response = httpx.get(
                self.url,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                timeout=10,
                follow_redirects=True
            )
            return response.text if response.status_code == 200 else None
        except:
            return None
    
    def _parse_from_html(self, html: str) -> str:
        """Parse directly from HTML string"""
        soup = parse_html(html)
        return self._extract_and_format(soup)
    
    def parse_feed(self, page: Page) -> str:
        """Parse from Playwright page"""
        soup = parse_html(page.content())
        return self._extract_and_format(soup)
    
    def _extract_and_format(self, soup) -> str:
        """Shared extraction logic"""
        if self.config.requires_auth and 'login' in soup.get_text().lower():
            return self._auth_required_message()
        
        containers = find_with_fallback(soup, self.config.container_selectors, find_all=True)
        if not containers:
            return f"No {self.config.platform_name} content found.\n"
        
        items = [self._extract_item(c) for c in containers[:20]]
        items = [i for i in items if i]
        return self._format_feed(items)
    
    def _extract_item(self, container) -> Optional[dict]:
        """Extract using config + parsing helpers"""
        item = {}
        if self.config.title_selectors:
            item['title'] = extract_text(find_with_fallback(container, self.config.title_selectors))
        if self.config.author_selectors:
            item['author'] = extract_text(find_with_fallback(container, self.config.author_selectors))
        if self.config.url_selectors:
            item['url'] = extract_link(
                find_with_fallback(container, self.config.url_selectors),
                base_url=self.config.base_url
            )
        if self.config.content_selectors:
            item['content'] = extract_text(find_with_fallback(container, self.config.content_selectors))
        if self.config.timestamp_selectors:
            item['timestamp'] = extract_text(find_with_fallback(container, self.config.timestamp_selectors))
        
        # Extract engagement as strings (let formatter handle it)
        for metric, selectors in self.config.engagement_selectors.items():
            val = extract_text(find_with_fallback(container, selectors))
            if val:
                item[metric] = val
        
        return item if any(item.values()) else None
    
    def _format_feed(self, items: list[dict]) -> str:
        """Format using list comprehension"""
        header = f"# {self.config.platform_name} Results\n\nFound {len(items)} posts\n\n"
        cards = "\n".join([self._format_card(item) for item in items])
        return header + cards
    
    def _format_card(self, item: dict) -> str:
        """Format single card (simplified from format_post_card)"""
        lines = []
        lines.append(f"## {item.get('title', 'Post')}")
        
        # Metadata line
        meta = [v for k, v in [
            ('author', item.get('author')),
            ('timestamp', item.get('timestamp'))
        ] if v]
        if meta:
            lines.append(f"**{' • '.join(meta)}**")
        
        if item.get('content'):
            lines.append(f"\n{item['content']}")
        
        if item.get('url'):
            prefix = self.config.link_prefix or f"View on {self.config.platform_name}"
            lines.append(f"\n[{prefix}]({item['url']})")
        
        lines.append("\n---\n")
        return "\n".join(lines)
    
    def _auth_required_message(self) -> str:
        return (
            f"# {self.config.platform_name} - Authentication Required\n\n"
            f"{self.config.platform_name} requires authentication to access this content.\n"
        )
```

**Convert 6 Extractors to Configs** (~20-30 lines each):

```python
# src/extractors/substack.py - 115 lines → 25 lines
from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig

SUBSTACK_CONFIG = ExtractorConfig(
    platform_name="Substack",
    container_selectors=["div[role='article']"],
    title_selectors=["div.reset-IxiVJZ"],
    author_selectors=["a[href^='/@']"],
    url_selectors=["a.pressable-lg-kV7yq8", "a[href*='/p/']", "a[href*='/note/']"],
    content_selectors=["p"],
    try_http_first=True,  # Substack works with HTTP
    link_prefix="Read on Substack"
)

class SubstackFeedReader(GenericCardExtractor):
    def __init__(self, url: str):
        super().__init__(url, SUBSTACK_CONFIG)
```

**Works for**: Substack (HTTP), Reddit (HTTP), Medium (HTTP), LinkedIn, Instagram, Facebook

**Reduction**: 6 × ~130 lines = 780 → 6 × 25 = 150 = **630 lines saved**

### Phase 3: Consolidate Special Cases (1 hour, 200 lines saved)

**HackerNews** - Remove browser entirely (API-only):

```python
class HackerNewsFeedReader(FeedReader):
    def read_feed(self) -> str:
        import requests
        data = requests.get(self.url, timeout=10).json()
        items = [self._extract(h) for h in data.get('hits', [])]
        return self._format(items)
    
    def parse_feed(self, page: Page) -> str:
        # Not used, but required by base class
        pass
```

**Saved**: 107 → 40 lines = **67 lines**

**YouTube** - Keep extraction logic, use formatting helpers:

- Replace `_format_markdown` with simplified version using helpers

**Saved**: 116 → 85 lines = **31 lines**

**Twitter** - Convert to GenericCardExtractor with custom handling:

**Saved**: 140 → 60 lines = **80 lines**

**Medium** - Remove duplicated browser setup, use SimpleBrowserContext:

```python
class MediumFeedReader(GenericCardExtractor):
    def __init__(self, url: str):
        super().__init__(url, MEDIUM_CONFIG)
    
    # read_feed uses parent's SimpleBrowserContext automatically
    # No need for custom browser setup!
```

**Saved**: 136 → 30 lines = **106 lines**

### Phase 4: Parallel Processing (30 minutes)

**New File: `src/parallel_reader.py`** (~35 lines)

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["machine-learning-helpers"]
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

from mlh.parallel import pmap
from src.feed_reader import create_feed_reader

def read_single(args: tuple[str, str]) -> str:
    """Read single platform feed"""
    platform, query = args
    return create_feed_reader(platform, query).read_feed()

def read_parallel(searches: list[tuple[str, str]]) -> list[str]:
    """
    Parallel feed reading using pmap.
    
    Args:
        searches: [(platform, query), ...]
    
    Returns:
        [markdown_result, ...]
    
    Example:
        results = read_parallel([
            ('substack', 'AI'),
            ('reddit', 'machine learning'),
            ('hackernews', 'python')
        ])
    """
    return pmap(read_single, searches)

if __name__ == "__main__":
    # Demo
    results = read_parallel([
        ('hackernews', 'python'),
        ('substack', 'AI')
    ])
    for r in results:
        print(r)
        print("\n" + "="*80 + "\n")
```

**Benefit**: N searches complete in time of 1 search

### Phase 5: Smart Scrolling (30 minutes)

**Update `src/core/browser.py` - SimpleBrowserContext**:

```python
def __enter__(self) -> Page:
    # ... existing setup ...
    
    if self.url:
        self.page.goto(self.url, wait_until="domcontentloaded", timeout=self.timeout)
        self.page.wait_for_timeout(500)
        
        if self.scroll_times > 0:
            # Smart scroll: stop early if no new content
            prev_height = 0
            for i in range(self.scroll_times):
                curr_height = self.page.evaluate("document.body.scrollHeight")
                if curr_height == prev_height:
                    break  # Early exit
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.page.wait_for_timeout(self.scroll_delay)
                prev_height = curr_height
    
    return self.page
```

**Benefit**: Saves 20-40% time when content loads quickly

### Phase 6 (Optional): Browser Pool

**Status**: DEFERRED - Adds complexity, minimal benefit with parallel approach

For parallel processing, each process gets its own browser (no sharing needed).

Browser pool would help for sequential requests, but with HTTP-first + parallel, we don't need it.

**If needed later**: Implement as singleton with connection reuse

## Performance Comparison

| Platform | Before | After (HTTP) | After (Browser) | Speedup |

|----------|--------|--------------|-----------------|---------|

| HackerNews | 8-12s | <1s | - | 10x+ |

| Substack | 8-12s | 1-2s | 4-6s | 4-6x or 2x |

| Reddit | 8-12s | 1-3s | 4-6s | 3-4x or 2x |

| Medium | 8-12s | 1-3s | 4-6s | 3-4x or 2x |

| Twitter | 8-12s | - | 4-6s | 2x |

| YouTube | 8-12s | - | 4-6s | 2x |

| Parallel (3 searches) | 24-36s | 1-3s | - | 10-30x |

## Code Reduction Summary

| Component | Before | After | Saved |

|-----------|--------|-------|-------|

| **Generic Extractors** |

| Substack | 115 | 25 | 90 |

| Reddit | 147 | 25 | 122 |

| LinkedIn | 167 | 25 | 142 |

| Instagram | 159 | 25 | 134 |

| Medium | 136 | 30 | 106 |

| Facebook | 132 | 25 | 107 |

| **Special Cases** |

| HackerNews | 107 | 40 | 67 |

| Twitter | 140 | 60 | 80 |

| YouTube | 116 | 85 | 31 |

| **Subtotal** | **1,219** | **340** | **879** |

| **New Code** | 0 | 135 | -135 |

| **Net Total** | **1,219** | **475** | **744 (61%)** |

## Implementation Checklist

**Phase 1: Quick Wins** (5 min)

- [ ] Update SimpleBrowserContext wait defaults
- [ ] Update scroll defaults
- [ ] Update BrowserManager defaults
- [ ] Test one platform (Substack)

**Phase 2: Generic Framework** (2 hrs)

- [ ] Create `src/core/generic_extractor.py`
- [ ] Convert Substack to config
- [ ] Convert Reddit to config
- [ ] Convert Medium to config
- [ ] Convert LinkedIn to config
- [ ] Convert Instagram to config
- [ ] Convert Facebook to config
- [ ] Test all 6 platforms

**Phase 3: Special Cases** (1 hr)

- [ ] Refactor HackerNews (remove browser)
- [ ] Simplify YouTube formatting
- [ ] Convert Twitter to GenericCardExtractor
- [ ] Test all 3 platforms

**Phase 4: Parallel** (30 min)

- [ ] Create `src/parallel_reader.py`
- [ ] Add mlh dependency via uv
- [ ] Test parallel execution

**Phase 5: Smart Scrolling** (30 min)

- [ ] Update SimpleBrowserContext with smart scroll
- [ ] Test with platforms that need scrolling

## Advanced Python Patterns Used

✅ **Dataclasses** - Type-safe config (no boilerplate)

✅ **List comprehensions** - Functional extraction/formatting

✅ **Composition** - GenericCardExtractor + Config (not inheritance)

✅ **Strategy pattern** - Multi-selector fallback via find_with_fallback

✅ **Early returns** - Guard clauses for auth checks

✅ **Context managers** - SimpleBrowserContext (already exists)

✅ **Type hints** - Throughout for IDE support

✅ **Functional utilities** - pmap for parallel processing

✅ **DRY principle** - Maximize use of existing utils

✅ **Config-driven** - Data over code

## Risk Mitigation

1. **Test after each phase** - Don't break working code
2. **Keep old extractors** - Rename to `*.old.py` during refactor
3. **HTTP fallback** - Always falls back to browser if HTTP fails
4. **Backwards compatible** - Same interface, same outputs
5. **Incremental** - Each phase stands alone
