"""
Medium feed reader using config-driven approach.

Extracts article data from Medium.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


MEDIUM_CONFIG = ExtractorConfig(
    platform_name="Medium",
    container_selectors=["article", "div[data-post-id]"],
    title_selectors=["h2", "h3", "h1"],
    author_selectors=["a[data-action='show-user-card']", "a[href*='/@']", "a[rel='author']"],
    url_selectors=["h2 a", "h3 a", "h1 a"],
    content_selectors=["p"],
    timestamp_selectors=["time"],
    base_url="https://medium.com",
    try_http_first=True,
    link_prefix="Read on Medium"
)


class MediumFeedReader(GenericCardExtractor):
    """Parser for Medium articles and search results."""

    def __init__(self, url: str):
        super().__init__(url, MEDIUM_CONFIG)
