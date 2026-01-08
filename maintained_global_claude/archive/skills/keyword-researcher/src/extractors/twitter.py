"""
Twitter/X feed reader using config-driven approach.

Extracts tweets from Twitter search results and timelines.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


TWITTER_CONFIG = ExtractorConfig(
    platform_name="Twitter/X",
    container_selectors=["article"],
    title_selectors=["[data-testid='tweetText']"],
    author_selectors=["a[href^='/']"],
    url_selectors=["a[href*='/status/']"],
    content_selectors=["[data-testid='tweetText']"],
    timestamp_selectors=["time"],
    base_url="https://twitter.com",
    requires_auth=True,
    link_prefix="View Tweet"
)


class TwitterFeedReader(GenericCardExtractor):
    """Parser for Twitter/X feeds and search results."""

    def __init__(self, url: str):
        super().__init__(url, TWITTER_CONFIG)
