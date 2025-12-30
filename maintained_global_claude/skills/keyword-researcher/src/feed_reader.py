#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "playwright",
#     "html2text",
#     "beautifulsoup4",
#     "pydantic",
#     "requests",
# ]
# ///

"""
Feed Reader - Main entry point.

Factory function to create appropriate feed reader based on platform and search query.
Supports multiple social media platforms with unified interface.
"""

import sys
from pathlib import Path
from urllib.parse import quote, quote_plus

# Add parent directory to path so imports work when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.base import FeedReader
from src.extractors.substack import SubstackFeedReader
from src.extractors.twitter import TwitterFeedReader
from src.extractors.reddit import RedditFeedReader
from src.extractors.hackernews import HackerNewsFeedReader
from src.extractors.medium import MediumFeedReader
from src.extractors.youtube import YouTubeFeedReader
from src.extractors.linkedin import LinkedInFeedReader
from src.extractors.instagram import InstagramFeedReader
from src.extractors.facebook import FacebookFeedReader


PLATFORM_SEARCH_URLS = {
    "substack": lambda query: f"https://substack.com/search/{quote(query)}",
    "twitter": lambda query: f"https://twitter.com/search?q={quote(query)}",
    "x": lambda query: f"https://x.com/search?q={quote(query)}",
    "reddit": lambda query: f"https://www.reddit.com/search/?q={quote_plus(query)}",
    "hackernews": lambda query: f"https://hn.algolia.com/api/v1/search?query={quote(query)}&tags=story",
    "hn": lambda query: f"https://hn.algolia.com/api/v1/search?query={quote(query)}&tags=story",
    "medium": lambda query: f"https://medium.com/search?q={quote_plus(query)}",
    "youtube": lambda query: f"https://www.youtube.com/results?search_query={quote_plus(query)}",
    "linkedin": lambda query: f"https://www.linkedin.com/search/results/all/?keywords={quote(query)}",
    "instagram": lambda query: f"https://www.instagram.com/explore/tags/{query.replace(' ', '')}",
    "facebook": lambda query: f"https://www.facebook.com/search/top/?q={quote_plus(query)}",
}


def build_search_url(platform: str, query: str) -> str:
    """
    Build search URL for the specified platform and query.

    Args:
        platform: Platform name (e.g., 'substack', 'reddit', 'medium')
        query: Search query string

    Returns:
        Formatted search URL for the platform

    Raises:
        ValueError: If platform is not supported
    """
    platform_lower = platform.lower()

    if platform_lower not in PLATFORM_SEARCH_URLS:
        supported = ", ".join(sorted(set(PLATFORM_SEARCH_URLS.keys())))
        raise ValueError(
            f"Unsupported platform: {platform}\n"
            f"Supported platforms: {supported}"
        )

    return PLATFORM_SEARCH_URLS[platform_lower](query)


def create_feed_reader(platform: str, query: str) -> FeedReader:
    """
    Factory function to create appropriate FeedReader based on platform and search query.

    Supported platforms:
    - substack: Global Substack search
    - twitter/x: Twitter/X search
    - reddit: Reddit search
    - hackernews/hn: Hacker News search
    - medium: Medium search
    - youtube: YouTube search
    - linkedin: LinkedIn search (requires authentication)
    - instagram: Instagram hashtag search (REQUIRES AUTHENTICATION - see below)
    - facebook: Facebook search (requires authentication)

    Authentication Requirements:
    - Instagram: Requires valid Instagram account login. Instagram actively blocks
      unauthenticated access to hashtag pages and restricts content extraction per
      Terms of Service. No public API access available for hashtag searches.
    - LinkedIn: Requires LinkedIn account credentials
    - Facebook: Requires Facebook account credentials

    Args:
        platform: Platform name (case-insensitive)
        query: Search query string

    Returns:
        Appropriate FeedReader instance for the platform

    Raises:
        ValueError: If platform is not supported

    Examples:
        >>> reader = create_feed_reader("substack", "AI")
        >>> markdown = reader.read_feed()

        >>> reader = create_feed_reader("reddit", "machine learning")
        >>> markdown = reader.read_feed()
    """
    url = build_search_url(platform, query)
    platform_lower = platform.lower()

    if platform_lower == "substack":
        return SubstackFeedReader(url)
    elif platform_lower in ("twitter", "x"):
        return TwitterFeedReader(url)
    elif platform_lower == "reddit":
        return RedditFeedReader(url)
    elif platform_lower in ("hackernews", "hn"):
        return HackerNewsFeedReader(url)
    elif platform_lower == "medium":
        return MediumFeedReader(url)
    elif platform_lower == "youtube":
        return YouTubeFeedReader(url)
    elif platform_lower == "linkedin":
        return LinkedInFeedReader(url)
    elif platform_lower == "instagram":
        return InstagramFeedReader(url)
    elif platform_lower == "facebook":
        return FacebookFeedReader(url)
    else:
        supported = ", ".join(sorted(set(PLATFORM_SEARCH_URLS.keys())))
        raise ValueError(
            f"Unsupported platform: {platform}\n"
            f"Supported platforms: {supported}"
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: uv run src/feed_reader.py <platform> <search_query>")
        print("\nExample:")
        print('  uv run src/feed_reader.py medium "elon musk"')
        print('  uv run src/feed_reader.py reddit "machine learning"')
        print('  uv run src/feed_reader.py substack "AI newsletter"')
        print("\nSupported platforms:")
        print("  - substack: Global Substack search")
        print("  - twitter/x: Twitter/X search")
        print("  - reddit: Reddit search")
        print("  - hackernews/hn: Hacker News search")
        print("  - medium: Medium search")
        print("  - youtube: YouTube search")
        print("  - linkedin: LinkedIn search (requires authentication)")
        print("  - instagram: Instagram hashtag search (REQUIRES AUTHENTICATION)")
        print("  - facebook: Facebook search (requires authentication)")
        print("\nAuthentication Note:")
        print("  Instagram, LinkedIn, and Facebook require valid user account credentials.")
        print("  Instagram particularly restricts automated access and requires login.")
        sys.exit(1)

    platform = sys.argv[1]
    query = sys.argv[2]

    try:
        reader = create_feed_reader(platform, query)
        print(reader.read_feed())
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading feed: {e}")
        sys.exit(1)
