"""
Page scrolling utilities for loading dynamic content.

Eliminates 15+ instances of duplicated scrolling logic across extractors.
"""

from playwright.sync_api import Page
from playwright.async_api import Page as AsyncPage


def scroll_to_load(
    page: Page,
    iterations: int = 3,
    delay: int = 1000,
    scroll_type: str = "bottom"
) -> None:
    """
    Scroll page to load more dynamic content.

    Args:
        page: Playwright page object
        iterations: Number of times to scroll
        delay: Milliseconds to wait between scrolls
        scroll_type: "bottom" for scroll to bottom, "viewport" for one viewport height

    Examples:
        scroll_to_load(page, iterations=5, delay=2000)
        scroll_to_load(page, scroll_type="viewport")
    """
    for _ in range(iterations):
        if scroll_type == "bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif scroll_type == "viewport":
            page.evaluate("window.scrollBy(0, window.innerHeight)")

        page.wait_for_timeout(delay)


async def async_scroll_to_load(
    page: AsyncPage,
    iterations: int = 3,
    delay: int = 1000,
    scroll_type: str = "bottom"
) -> None:
    """
    Async version of scroll_to_load for async extractors.

    Args:
        page: Async Playwright page object
        iterations: Number of times to scroll
        delay: Milliseconds to wait between scrolls
        scroll_type: "bottom" for scroll to bottom, "viewport" for one viewport height
    """
    for _ in range(iterations):
        if scroll_type == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif scroll_type == "viewport":
            await page.evaluate("window.scrollBy(0, window.innerHeight)")

        await page.wait_for_timeout(delay)


def scroll_to_element(page: Page, selector: str, timeout: int = 5000) -> bool:
    """
    Scroll to make specific element visible.

    Args:
        page: Playwright page object
        selector: CSS selector for target element
        timeout: Milliseconds to wait for element

    Returns:
        True if element found and scrolled to, False otherwise
    """
    try:
        element = page.wait_for_selector(selector, timeout=timeout)
        if element:
            element.scroll_into_view_if_needed()
            return True
    except:
        pass
    return False
