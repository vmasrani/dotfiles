"""
HTML parsing utilities using BeautifulSoup.

Provides reusable parsing functions and CSS selector fallback patterns.
"""

from bs4 import BeautifulSoup, Tag
from typing import Optional, List, Union
from urllib.parse import urljoin


def parse_html(html: str, parser: str = 'html.parser') -> BeautifulSoup:
    """
    Parse HTML string with BeautifulSoup.

    Args:
        html: HTML content as string
        parser: Parser to use ('html.parser' or 'lxml')

    Returns:
        BeautifulSoup object
    """
    return BeautifulSoup(html, parser)


def find_with_fallback(
    element: Union[BeautifulSoup, Tag],
    selectors: List[str],
    find_all: bool = False
) -> Optional[Union[Tag, List[Tag]]]:
    """
    Try multiple CSS selectors with fallback.

    Args:
        element: BeautifulSoup or Tag element to search within
        selectors: List of CSS selectors to try in order
        find_all: If True, return all matches; if False, return first match

    Returns:
        Found element(s) or None if nothing found

    Examples:
        title = find_with_fallback(soup, ["h1.title", "h2.heading", "h3"])
        posts = find_with_fallback(soup, ["article.post", "div.post"], find_all=True)
    """
    for selector in selectors:
        if find_all:
            results = element.select(selector)
            if results:
                return results
        else:
            result = element.select_one(selector)
            if result:
                return result
    return None


def extract_text(
    element: Optional[Tag],
    strip: bool = True,
    separator: str = " "
) -> Optional[str]:
    """
    Safely extract text from element with None handling.

    Args:
        element: BeautifulSoup Tag element
        strip: Whether to strip whitespace
        separator: Separator for joining text from nested elements

    Returns:
        Extracted text or None if element is None

    Examples:
        text = extract_text(title_element)
        text = extract_text(content_div, separator="\\n")
    """
    if element is None:
        return None

    text = element.get_text(separator=separator, strip=strip)
    return text if text else None


def extract_link(
    element: Optional[Tag],
    attribute: str = "href",
    base_url: str = ""
) -> Optional[str]:
    """
    Extract and normalize URL from element.

    Args:
        element: BeautifulSoup Tag element
        attribute: Attribute containing URL (default: 'href')
        base_url: Base URL for resolving relative URLs

    Returns:
        Normalized URL or None if not found

    Examples:
        url = extract_link(link_element, base_url="https://example.com")
        image_url = extract_link(img, attribute="src", base_url="https://example.com")
    """
    if element is None:
        return None

    url = element.get(attribute)
    if not url:
        return None

    if base_url:
        return urljoin(base_url, url)

    return url


def extract_attribute(
    element: Optional[Tag],
    attribute: str,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Safely extract attribute from element.

    Args:
        element: BeautifulSoup Tag element
        attribute: Attribute name to extract
        default: Default value if attribute not found

    Returns:
        Attribute value or default

    Examples:
        data_id = extract_attribute(post, "data-id")
        aria_label = extract_attribute(button, "aria-label", default="")
    """
    if element is None:
        return default

    return element.get(attribute, default)


def find_all_with_text(
    element: Union[BeautifulSoup, Tag],
    tag: str,
    text_pattern: str,
    limit: Optional[int] = None
) -> List[Tag]:
    """
    Find all elements matching tag and text pattern.

    Args:
        element: BeautifulSoup or Tag element to search within
        tag: Tag name to search for
        text_pattern: Regex pattern or string to match in text
        limit: Maximum number of results

    Returns:
        List of matching elements

    Examples:
        timestamps = find_all_with_text(soup, "time", r"\\d+ hours ago")
        likes = find_all_with_text(soup, "span", "likes", limit=10)
    """
    import re

    results = []
    for elem in element.find_all(tag, limit=limit):
        text = elem.get_text(strip=True)
        if isinstance(text_pattern, str):
            if text_pattern in text:
                results.append(elem)
        else:
            if re.search(text_pattern, text):
                results.append(elem)

    return results


def extract_json_from_script(soup: BeautifulSoup, script_id: Optional[str] = None) -> dict:
    """
    Extract JSON data from script tags.

    Args:
        soup: BeautifulSoup object
        script_id: Optional ID of specific script tag

    Returns:
        Parsed JSON data as dictionary, or empty dict if parsing fails
    """
    import json

    if script_id:
        script = soup.find('script', id=script_id)
        if script:
            try:
                return json.loads(script.string)
            except:
                return {}

    scripts = soup.find_all('script', type='application/json')
    for script in scripts:
        if script.string:
            try:
                return json.loads(script.string)
            except:
                continue

    return {}
