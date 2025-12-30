"""
Facebook feed reader using config-driven approach.

Extracts post data from Facebook feeds.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


FACEBOOK_CONFIG = ExtractorConfig(
    platform_name="Facebook",
    container_selectors=["div[role='article']"],
    title_selectors=["a[href*='/']"],
    author_selectors=["a[href*='/']"],
    url_selectors=["a[href*='/posts/']", "a[href*='/permalink/']"],
    content_selectors=["div[data-ad-preview='message']", "div[dir='auto']"],
    timestamp_selectors=["time", "span"],
    base_url="https://facebook.com",
    requires_auth=True,
    link_prefix="View on Facebook"
)


class FacebookFeedReader(GenericCardExtractor):
    """Parser for Facebook feeds."""

    def __init__(self, url: str):
        super().__init__(url, FACEBOOK_CONFIG)
