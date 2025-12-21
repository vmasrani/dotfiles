"""
Keyword Researcher - Social media feed extraction toolkit.

A refactored, DRY implementation for extracting content from multiple
social media platforms with a unified interface.
"""

__version__ = "2.0.0"

# Lazy imports to avoid circular dependencies
__all__ = [
    "create_feed_reader",
    "Tweet",
    "LinkedInPost",
    "InstagramPost",
    "FacebookPost",
    "RedditPost",
    "SubstackCard",
    "HackerNewsItem",
    "MediumPost",
    "YouTubeVideo",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "create_feed_reader":
        from src.feed_reader import create_feed_reader
        return create_feed_reader
    elif name in ["Tweet", "LinkedInPost", "InstagramPost", "FacebookPost",
                  "RedditPost", "SubstackCard", "HackerNewsItem", "MediumPost", "YouTubeVideo"]:
        from src.core import models
        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
