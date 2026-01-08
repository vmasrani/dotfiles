"""
Core components for feed readers.

Base classes, browser management, data models, and configuration.
"""

# Lazy imports to avoid circular dependencies when used as script
__all__ = [
    "FeedReader",
    "BrowserManager",
    "SimpleBrowserContext",
    "AsyncBrowserManager",
    "BasePost",
    "SocialMediaPost",
    "Tweet",
    "LinkedInPost",
    "InstagramPost",
    "FacebookPost",
    "RedditPost",
    "SubstackCard",
    "HackerNewsItem",
    "MediumPost",
    "YouTubeVideo",
    "AuthorInfo",
    "EngagementMetrics",
    "DEFAULT_TIMEOUT",
    "DEFAULT_SCROLL_DELAY",
    "DEFAULT_SCROLL_TIMES",
    "DEFAULT_USER_AGENT",
    "PLATFORM_BASE_URLS",
]
