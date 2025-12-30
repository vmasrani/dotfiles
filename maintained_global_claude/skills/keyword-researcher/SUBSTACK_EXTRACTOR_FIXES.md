# Substack Extractor - Testing and Fixes

## Issues Identified

The original Substack extractor was failing because:

1. **Wrong CSS selector**: Used `data-testid="search-result-item"` which doesn't exist on Substack search results
2. **No URL extraction**: Failed to find any post links, only returning the site navigation link `/s/podcast`
3. **Missing fallback strategies**: Didn't handle different post URL patterns

## Root Cause Analysis

After inspecting the actual HTML structure of Substack search results, discovered that:

- Substack uses `div[role="article"]` to represent each search result (found 80 of them)
- Post titles are in `div` elements with class `reset-IxiVJZ`
- Post links come in different forms:
  - Main post links with class `pressable-lg-kV7yq8` (best quality)
  - Full posts with `/p/` in URL path
  - Notes/comments with `/note/` in URL path
- Author links start with `/@`

## Fixes Applied

### 1. **Updated Primary Selector**
- Changed from `data-testid="search-result-item"` to `div[role="article"]`
- Now correctly finds all 80 article elements on the search results page

### 2. **Improved Title Extraction**
- Looks for `div` with class `reset-IxiVJZ`
- Filters for text content > 10 characters
- Handles both full posts and notes

### 3. **Multi-Strategy URL Extraction**
- **Priority 1**: Look for main pressable container (class `pressable-lg-kV7yq8`)
  - Usually points to the actual article/post page
  - Works for most posts
- **Fallback 1**: Look for links with `/p/` (full articles)
  - Substack article URLs
  - External newsletter URLs (e.g., honest-broker.com/p/)
- **Fallback 2**: Look for links with `/note/` (comments/updates)
  - User notes and comments
  - Still valid content URLs

### 4. **Author Extraction**
- Looks for links starting with `/@` followed by username
- Extracts author name from link text
- Handles both full usernames and display names

### 5. **Removed Debug Output**
- Cleaned up all debug print statements
- Code now runs silently with clean markdown output

## Test Results

### Test 1: Search "AI"
- **Articles extracted**: 80/80 ✓
- **URLs found**: 80/80 ✓
- **Authors found**: 80/80 ✓
- **Output format**: Clean markdown with titles, authors, and clickable links ✓

### Test 2: Search "machine learning"
- **Results**: Successfully extracted diverse ML-related posts ✓
- **URL variety**: Mix of substack.com posts, external blogs, and user notes ✓

### Output Format
```markdown
## I Downloaded the AI Murder Code: Here's What I Found
**Author:** Phil Harper

[Read on Substack](https://philharper.substack.com/p/i-downloaded-the-ai-murder-code-heres)

---
```

## Files Modified

- `/Users/vmasrani/dotfiles/maintained_global_claude/skills/keyword-researcher/src/extractors/substack.py`

## Files Cleaned Up

- Removed temporary debug scripts
- Removed temporary HTML snapshot file

## Conclusion

The Substack extractor now works properly and reliably extracts:
- Article/post titles
- Author names
- Direct URLs to posts
- Both full articles and notes/comments

All 80 search results are extracted cleanly in markdown format, ready for further processing.
