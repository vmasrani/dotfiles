"""
Engagement metrics parsing utilities.

Extracts and parses engagement numbers from social media platforms,
handling K/M/B/T suffixes (1.5K = 1500, 2.3M = 2300000, etc.).
"""

import re
from typing import Optional


def parse_engagement_number(text: str) -> Optional[int]:
    """
    Convert engagement text like '1.5K', '2.3M', '1B' to integers.

    Args:
        text: Text containing a number with optional K/M/B/T suffix

    Returns:
        Parsed integer value, or None if parsing fails

    Examples:
        >>> parse_engagement_number("1.5K")
        1500
        >>> parse_engagement_number("2.3M")
        2300000
        >>> parse_engagement_number("1B")
        1000000000
        >>> parse_engagement_number("500")
        500
    """
    if not text:
        return None

    match = re.search(r'(\d+(?:\.?\d+)?)\s*([KMBT]?)', text)
    if not match:
        return None

    number_str = match.group(1)
    multiplier = match.group(2) or ""

    try:
        num = float(number_str)
        if multiplier == 'K':
            num *= 1000
        elif multiplier == 'M':
            num *= 1000000
        elif multiplier == 'B':
            num *= 1000000000
        elif multiplier == 'T':
            num *= 1000000000000
        return int(num)
    except ValueError:
        return None


def extract_metric_from_text(text: str, metric_name: str) -> Optional[int]:
    """
    Extract engagement metric from text containing metric name.

    Args:
        text: Text like "123 likes" or "1.5K comments"
        metric_name: Name of metric to extract (likes, comments, etc.)

    Returns:
        Parsed integer value, or None if not found

    Examples:
        >>> extract_metric_from_text("123 likes", "likes")
        123
        >>> extract_metric_from_text("1.5K comments", "comments")
        1500
    """
    if not text or not metric_name:
        return None

    pattern = rf'(\d+(?:\.?\d+)?)\s*([KMBT]?)\s*{metric_name}'
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        number_str = match.group(1)
        multiplier = match.group(2) or ""
        try:
            num = float(number_str)
            if multiplier == 'K':
                num *= 1000
            elif multiplier == 'M':
                num *= 1000000
            elif multiplier == 'B':
                num *= 1000000000
            elif multiplier == 'T':
                num *= 1000000000000
            return int(num)
        except ValueError:
            return None

    return None


def parse_compact_number(text: str) -> int:
    """
    Parse compact number format (returns 0 if parsing fails).

    This is a convenience wrapper around parse_engagement_number
    that returns 0 instead of None for easier use in dataclasses.

    Args:
        text: Text containing a number

    Returns:
        Parsed integer value, or 0 if parsing fails
    """
    result = parse_engagement_number(text)
    return result if result is not None else 0
