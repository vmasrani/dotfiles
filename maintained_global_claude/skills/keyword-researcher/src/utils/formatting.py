"""
Markdown formatting utilities for feed output.

Provides consistent formatting across all platform extractors.
"""

from typing import List, Dict, Optional, Any


def format_markdown_header(title: str, level: int = 2) -> str:
    """
    Create markdown header.

    Args:
        title: Header text
        level: Header level (1-6)

    Returns:
        Formatted markdown header

    Examples:
        >>> format_markdown_header("My Title", level=1)
        "# My Title"
        >>> format_markdown_header("Subtitle", level=2)
        "## Subtitle"
    """
    prefix = "#" * level
    return f"{prefix} {title}"


def format_metadata(items: List[str], separator: str = " • ") -> str:
    """
    Format metadata line with separator.

    Args:
        items: List of metadata items
        separator: String to join items

    Returns:
        Formatted metadata string

    Examples:
        >>> format_metadata(["Author Name", "2 hours ago", "123 views"])
        "Author Name • 2 hours ago • 123 views"
    """
    filtered_items = [item for item in items if item]
    return separator.join(filtered_items)


def format_engagement_line(metrics: Dict[str, Optional[int]], labels: Optional[Dict[str, str]] = None) -> str:
    """
    Format engagement metrics line.

    Args:
        metrics: Dictionary of metric name to value
        labels: Optional custom labels for metrics

    Returns:
        Formatted engagement string

    Examples:
        >>> format_engagement_line({"likes": 123, "comments": 45, "shares": 10})
        "👍 123 | 💬 45 | 🔄 10"
    """
    default_labels = {
        "likes": "👍",
        "comments": "💬",
        "shares": "🔄",
        "retweets": "🔄",
        "replies": "💬",
        "views": "👁",
        "upvotes": "⬆",
        "points": "⭐",
        "claps": "👏",
    }

    if labels:
        default_labels.update(labels)

    parts = []
    for key, value in metrics.items():
        if value is not None and value > 0:
            label = default_labels.get(key, key)
            parts.append(f"{label} {value}")

    return " | ".join(parts) if parts else ""


def format_link(text: str, url: str) -> str:
    """
    Format markdown link.

    Args:
        text: Link text
        url: URL

    Returns:
        Formatted markdown link

    Examples:
        >>> format_link("Click here", "https://example.com")
        "[Click here](https://example.com)"
    """
    return f"[{text}]({url})"


def format_post_card(
    title: Optional[str] = None,
    author: Optional[str] = None,
    url: Optional[str] = None,
    content: Optional[str] = None,
    timestamp: Optional[str] = None,
    engagement: Optional[Dict[str, int]] = None,
    metadata: Optional[List[str]] = None,
    separator: str = "---"
) -> str:
    """
    Format a complete post card in markdown.

    Args:
        title: Post title
        author: Author name
        url: Post URL
        content: Post content/excerpt
        timestamp: Timestamp string
        engagement: Dictionary of engagement metrics
        metadata: Additional metadata items
        separator: Separator line

    Returns:
        Formatted markdown post card
    """
    lines = []

    if title:
        if url:
            lines.append(format_markdown_header(format_link(title, url), level=3))
        else:
            lines.append(format_markdown_header(title, level=3))

    meta_items = []
    if author:
        meta_items.append(f"**{author}**")
    if timestamp:
        meta_items.append(timestamp)
    if metadata:
        meta_items.extend(metadata)

    if meta_items:
        lines.append(format_metadata(meta_items))

    if content:
        lines.append("")
        lines.append(content)

    if engagement:
        engagement_line = format_engagement_line(engagement)
        if engagement_line:
            lines.append("")
            lines.append(engagement_line)

    if separator:
        lines.append("")
        lines.append(separator)

    return "\n".join(lines)


def truncate_text(text: str, max_length: int = 300, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated

    Returns:
        Truncated text

    Examples:
        >>> truncate_text("Long text here", max_length=10)
        "Long te..."
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """
    Escape special markdown characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    special_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def create_table(headers: List[str], rows: List[List[Any]]) -> str:
    """
    Create markdown table.

    Args:
        headers: Table headers
        rows: Table rows

    Returns:
        Formatted markdown table

    Examples:
        >>> create_table(["Name", "Age"], [["Alice", 30], ["Bob", 25]])
        "| Name | Age |\\n|------|-----|\\n| Alice | 30 |\\n| Bob | 25 |"
    """
    if not headers or not rows:
        return ""

    lines = []

    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "|" + "|".join(["---" for _ in headers]) + "|"

    lines.append(header_line)
    lines.append(separator)

    for row in rows:
        row_line = "| " + " | ".join(str(cell) for cell in row) + " |"
        lines.append(row_line)

    return "\n".join(lines)
