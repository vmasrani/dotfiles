"""
LinkedIn feed reader using config-driven approach.

Extracts post data from LinkedIn feeds.
"""

from src.core.generic_extractor import GenericCardExtractor, ExtractorConfig


LINKEDIN_CONFIG = ExtractorConfig(
    platform_name="LinkedIn",
    container_selectors=[
        "div[data-id*='urn:li:activity']",
        "div.feed-shared-update-v2",
        "div[data-urn*='activity']",
        "article"
    ],
    title_selectors=[
        "span.update-components-actor__name",
        "span[aria-hidden='true']",
        "a.update-components-actor__meta-link"
    ],
    author_selectors=[
        "span.update-components-actor__name",
        "span[aria-hidden='true']",
        "a.update-components-actor__meta-link"
    ],
    url_selectors=["a[href*='/posts/']", "a[href*='activity']"],
    content_selectors=[
        "div.feed-shared-update-v2__description",
        "div.update-components-text",
        "span.break-words",
        "div[dir='ltr']"
    ],
    timestamp_selectors=["time"],
    base_url="https://linkedin.com",
    requires_auth=True,
    link_prefix="View on LinkedIn"
)


class LinkedInFeedReader(GenericCardExtractor):
    """Parser for LinkedIn feeds."""

    def __init__(self, url: str):
        super().__init__(url, LINKEDIN_CONFIG)
