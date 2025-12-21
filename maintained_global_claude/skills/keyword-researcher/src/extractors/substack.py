"""
Substack feed reader using config-driven approach.

Extracts card-based content from Substack search results.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


SUBSTACK_CONFIG = ExtractorConfig(
    platform_name="Substack",
    container_selectors=["div[role='article']"],
    title_selectors=["div.reset-IxiVJZ", "a.pressable-lg-kV7yq8"],
    author_selectors=["a[href^='/@']"],
    url_selectors=["a.pressable-lg-kV7yq8", "a[href*='/p/']", "a[href*='/note/']"],
    content_selectors=["p"],
    timestamp_selectors=["time"],
    try_http_first=True,
    link_prefix="Read on Substack"
)


class SubstackFeedReader(GenericCardExtractor):
    """Parser for Substack search results and feeds."""

    def __init__(self, url: str):
        super().__init__(url, SUBSTACK_CONFIG)
