"""
Utility functions for parsing, formatting, scrolling, and metrics.

Shared utilities used across all platform extractors to eliminate duplication.
"""

# Lazy imports - no eager loading
__all__ = [
    # Parsing
    "parse_html",
    "find_with_fallback",
    "extract_text",
    "extract_link",
    "extract_attribute",
    "find_all_with_text",
    "extract_json_from_script",
    # Metrics
    "parse_engagement_number",
    "extract_metric_from_text",
    "parse_compact_number",
    # Scrolling
    "scroll_to_load",
    "async_scroll_to_load",
    "scroll_to_element",
    # Formatting
    "format_markdown_header",
    "format_metadata",
    "format_engagement_line",
    "format_link",
    "format_post_card",
    "truncate_text",
    "escape_markdown",
    "create_table",
]
