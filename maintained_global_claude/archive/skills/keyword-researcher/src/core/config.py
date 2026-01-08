"""
Configuration constants for feed extractors.

Centralized constants for timeouts, user agents, and common settings.
"""

DEFAULT_TIMEOUT = 60000  # 60 seconds
DEFAULT_SCROLL_DELAY = 1000  # 1 second
DEFAULT_SCROLL_TIMES = 3

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PLATFORM_BASE_URLS = {
    "substack": "https://substack.com",
    "twitter": "https://twitter.com",
    "reddit": "https://reddit.com",
    "hackernews": "https://news.ycombinator.com",
    "medium": "https://medium.com",
    "youtube": "https://youtube.com",
    "linkedin": "https://linkedin.com",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
}
