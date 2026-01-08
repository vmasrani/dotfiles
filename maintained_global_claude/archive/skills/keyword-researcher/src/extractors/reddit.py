"""
Reddit feed reader using config-driven approach.

Extracts post data from Reddit search results and subreddit feeds.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


REDDIT_CONFIG = ExtractorConfig(
    platform_name="Reddit",
    container_selectors=["div[data-testid='search-post-with-content-preview']", "article"],
    title_selectors=["a[data-testid='post-title-text']", "h3 a"],
    author_selectors=["a[data-testid='post-author-name']", "a[href^='/user/']"],
    url_selectors=["a[data-testid='post-title-text']", "h3 a"],
    content_selectors=["a.text-ellipsis"],
    timestamp_selectors=["time"],
    base_url="https://reddit.com",
    try_http_first=True,
    link_prefix="View on Reddit"
)


class RedditFeedReader(GenericCardExtractor):
    """Parser for Reddit feeds and search results."""

    def __init__(self, url: str):
        super().__init__(url, REDDIT_CONFIG)
