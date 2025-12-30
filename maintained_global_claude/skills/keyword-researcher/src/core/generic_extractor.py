"""
Generic card extractor with config-driven approach.

Eliminates code duplication across platform extractors by using
a common extraction logic with platform-specific configurations.
"""

from dataclasses import dataclass, field
from typing import Optional
from playwright.sync_api import Page

from src.core.base import FeedReader
from src.utils.parsing import parse_html, find_with_fallback, extract_text, extract_link


@dataclass
class ExtractorConfig:
    """Configuration for platform-specific extraction."""
    platform_name: str
    container_selectors: list[str]
    title_selectors: list[str] = field(default_factory=list)
    author_selectors: list[str] = field(default_factory=list)
    url_selectors: list[str] = field(default_factory=list)
    content_selectors: list[str] = field(default_factory=list)
    timestamp_selectors: list[str] = field(default_factory=list)
    engagement_selectors: dict[str, list[str]] = field(default_factory=dict)
    base_url: str = ""
    requires_auth: bool = False
    try_http_first: bool = False
    link_prefix: str = ""


class GenericCardExtractor(FeedReader):
    """Generic extractor using config-driven approach."""

    def __init__(self, url: str, config: ExtractorConfig):
        super().__init__(url)
        self.config = config

    def read_feed(self) -> str:
        """Try HTTP first if configured, fallback to browser."""
        if self.config.try_http_first:
            html = self._try_http_fetch()
            if html:
                return self._parse_from_html(html)
        return super().read_feed()

    def _try_http_fetch(self) -> Optional[str]:
        """Try fetching via HTTP, return HTML or None."""
        import httpx
        response = httpx.get(
            self.url,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
            timeout=10,
            follow_redirects=True
        )
        return response.text if response.status_code == 200 else None

    def _parse_from_html(self, html: str) -> str:
        """Parse directly from HTML string."""
        soup = parse_html(html)
        return self._extract_and_format(soup)

    def parse_feed(self, page: Page) -> str:
        """Parse from Playwright page."""
        soup = parse_html(page.content())
        return self._extract_and_format(soup)

    def _extract_and_format(self, soup) -> str:
        """Shared extraction logic."""
        if self.config.requires_auth and 'login' in soup.get_text().lower():
            return self._auth_required_message()

        containers = find_with_fallback(soup, self.config.container_selectors, find_all=True)
        if not containers:
            return f"No {self.config.platform_name} content found.\n"

        items = [self._extract_item(c) for c in containers[:20]]
        items = [i for i in items if i]
        return self._format_feed(items)

    def _extract_item(self, container) -> Optional[dict]:
        """Extract using config + parsing helpers."""
        item = {}
        if self.config.title_selectors:
            item['title'] = extract_text(find_with_fallback(container, self.config.title_selectors))
        if self.config.author_selectors:
            item['author'] = extract_text(find_with_fallback(container, self.config.author_selectors))
        if self.config.url_selectors:
            item['url'] = extract_link(
                find_with_fallback(container, self.config.url_selectors),
                base_url=self.config.base_url
            )
        if self.config.content_selectors:
            item['content'] = extract_text(find_with_fallback(container, self.config.content_selectors))
        if self.config.timestamp_selectors:
            item['timestamp'] = extract_text(find_with_fallback(container, self.config.timestamp_selectors))

        for metric, selectors in self.config.engagement_selectors.items():
            val = extract_text(find_with_fallback(container, selectors))
            if val:
                item[metric] = val

        return item if any(item.values()) else None

    def _format_feed(self, items: list[dict]) -> str:
        """Format using list comprehension."""
        header = f"# {self.config.platform_name} Results\n\nFound {len(items)} posts\n\n"
        cards = "\n".join([self._format_card(item) for item in items])
        return header + cards

    def _format_card(self, item: dict) -> str:
        """Format single card."""
        lines = []
        lines.append(f"## {item.get('title', 'Post')}")

        meta = [v for k, v in [
            ('author', item.get('author')),
            ('timestamp', item.get('timestamp'))
        ] if v]
        if meta:
            lines.append(f"**{' • '.join(meta)}**")

        if item.get('content'):
            lines.append(f"\n{item['content']}")

        if item.get('url'):
            prefix = self.config.link_prefix or f"View on {self.config.platform_name}"
            lines.append(f"\n[{prefix}]({item['url']})")

        lines.append("\n---\n")
        return "\n".join(lines)

    def _auth_required_message(self) -> str:
        return (
            f"# {self.config.platform_name} - Authentication Required\n\n"
            f"{self.config.platform_name} requires authentication to access this content.\n"
        )
