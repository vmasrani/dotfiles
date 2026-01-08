"""
Instagram feed reader using config-driven approach.

Extracts post data from Instagram pages.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


INSTAGRAM_CONFIG = ExtractorConfig(
    platform_name="Instagram",
    container_selectors=["article", "div[role='button']"],
    title_selectors=["a[href*='/']"],
    author_selectors=["a[href*='/']"],
    url_selectors=["a[href*='/p/']"],
    content_selectors=["h1", "span"],
    timestamp_selectors=["time"],
    base_url="https://instagram.com",
    requires_auth=True,
    link_prefix="View on Instagram"
)


class InstagramFeedReader(GenericCardExtractor):
    """Parser for Instagram feeds and profiles."""

    def __init__(self, url: str):
        super().__init__(url, INSTAGRAM_CONFIG)
