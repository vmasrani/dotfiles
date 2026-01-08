"""
Browser management utilities for Playwright.

Eliminates 20+ instances of duplicated browser setup/teardown code across
platform extractors by providing reusable BrowserManager classes.
"""

from playwright.sync_api import sync_playwright, Browser, Page, Playwright
from playwright.async_api import async_playwright, Browser as AsyncBrowser, Page as AsyncPage
from typing import Optional, Dict
from contextlib import contextmanager


class BrowserManager:
    """
    Synchronous browser manager for Playwright.

    Handles browser lifecycle: launch, navigation, cleanup.
    Supports custom headers, authentication, and timeout configuration.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None

    def launch(self) -> Browser:
        """Launch browser and return browser instance."""
        if not self.playwright:
            self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        return self.browser

    def create_page(
        self,
        browser: Optional[Browser] = None,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Page:
        """Create new page with optional custom headers."""
        if browser is None:
            if self.browser is None:
                browser = self.launch()
            else:
                browser = self.browser

        context = browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )

        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        if extra_headers:
            page.set_extra_http_headers(extra_headers)

        return page

    def navigate(
        self,
        page: Page,
        url: str,
        wait_until: str = "domcontentloaded"
    ) -> None:
        """Navigate to URL with timeout."""
        page.goto(url, wait_until=wait_until, timeout=self.timeout)

    def cleanup(self) -> None:
        """Close browser and stop playwright."""
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    @contextmanager
    def managed_browser(self):
        """Context manager for automatic cleanup."""
        try:
            browser = self.launch()
            yield browser
        finally:
            self.cleanup()

    @contextmanager
    def managed_page(self, url: Optional[str] = None, **kwargs):
        """Context manager for page with automatic cleanup."""
        try:
            browser = self.launch()
            page = self.create_page(browser)
            if url:
                self.navigate(page, url, **kwargs)
            yield page
        finally:
            self.cleanup()


class SimpleBrowserContext:
    """
    Simplified context manager for quick browser operations.

    Usage:
        with SimpleBrowserContext(url) as page:
            html = page.content()
    """

    def __init__(
        self,
        url: Optional[str] = None,
        headless: bool = True,
        timeout: int = 60000,
        scroll_times: int = 0,
        scroll_delay: int = 1000
    ):
        self.url = url
        self.headless = headless
        self.timeout = timeout
        self.scroll_times = scroll_times
        self.scroll_delay = scroll_delay
        self.playwright = None
        self.browser = None
        self.page = None

    def __enter__(self) -> Page:
        """Launch browser and navigate to URL."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )

        self.page = context.new_page()

        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        if self.url:
            self.page.goto(self.url, wait_until="domcontentloaded", timeout=self.timeout)
            self.page.wait_for_timeout(500)

            if self.scroll_times > 0:
                prev_height = self.page.evaluate("document.body.scrollHeight")
                for i in range(self.scroll_times):
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    self.page.wait_for_timeout(self.scroll_delay)

                    new_height = self.page.evaluate("document.body.scrollHeight")
                    if new_height == prev_height:
                        break
                    prev_height = new_height

        return self.page

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup browser and playwright."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        return False


class AsyncBrowserManager:
    """
    Asynchronous browser manager for Playwright.

    Used by LinkedIn and Facebook extractors that require async operations.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def launch(self):
        """Launch browser async."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        return playwright, browser

    async def create_page(
        self,
        browser: AsyncBrowser,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> AsyncPage:
        """Create new page with optional custom headers."""
        context = await browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )

        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        if extra_headers:
            await page.set_extra_http_headers(extra_headers)

        return page

    async def navigate(
        self,
        page: AsyncPage,
        url: str,
        wait_until: str = "networkidle"
    ) -> None:
        """Navigate to URL with timeout."""
        await page.goto(url, wait_until=wait_until, timeout=self.timeout)

    async def cleanup(self, browser: AsyncBrowser, playwright) -> None:
        """Close browser and stop playwright."""
        await browser.close()
        await playwright.stop()
