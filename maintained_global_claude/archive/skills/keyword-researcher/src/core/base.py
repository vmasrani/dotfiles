"""
Abstract base class for feed readers across all platforms.

This module defines the common interface and shared functionality for
extracting content from social media feeds.
"""

from abc import ABC, abstractmethod
from playwright.sync_api import Page
from typing import Dict
import json

from src.core.browser import SimpleBrowserContext


class FeedReader(ABC):
    """Abstract base class for reading card-based feeds from social media platforms."""

    def __init__(self, url: str):
        self.url = url

    @abstractmethod
    def parse_feed(self, page: Page) -> str:
        """
        Parse the feed and return markdown formatted content.

        Args:
            page: Playwright page object with loaded content

        Returns:
            Markdown formatted string with feed content
        """
        pass

    def read_feed(self) -> str:
        """
        Main entry point - launches browser and calls parse_feed.

        Uses SimpleBrowserContext to automatically handle browser lifecycle
        and perform initial scrolling to load content.
        """
        with SimpleBrowserContext(
            url=self.url,
            headless=True,
            timeout=90000,
            scroll_times=2,
            scroll_delay=800
        ) as page:
            result = self.parse_feed(page)
            return result

    def _extract_json_data(self, page: Page, selector: str = None) -> Dict:
        """
        Extract JSON data from script tags.

        Args:
            page: Playwright page object
            selector: Optional CSS selector for specific script tag

        Returns:
            Parsed JSON data as dictionary, or empty dict if parsing fails
        """
        if selector:
            script_content = page.locator(selector).inner_text()
        else:
            script_content = page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/json"]'));
                    return scripts.map(s => s.textContent).join('\\n');
                }
            """)

        try:
            return json.loads(script_content)
        except:
            return {}
