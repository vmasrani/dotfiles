#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "playwright",
#     "beautifulsoup4",
#     "httpx",
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

"""
Parallel feed reader for processing multiple URLs concurrently.

Uses pmap from machine_learning_helpers for embarrassingly parallel execution.
"""

from mlh.parallel import pmap
from typing import List, Tuple


def read_single_feed(url_reader_tuple: Tuple[str, object]) -> Tuple[str, str]:
    """
    Read a single feed and return (url, content).

    Args:
        url_reader_tuple: Tuple of (url, reader_class)

    Returns:
        Tuple of (url, markdown_content)
    """
    url, reader_class = url_reader_tuple
    reader = reader_class(url)
    content = reader.read_feed()
    return (url, content)


def read_feeds_parallel(urls_and_readers: List[Tuple[str, object]]) -> List[Tuple[str, str]]:
    """
    Read multiple feeds in parallel.

    Args:
        urls_and_readers: List of (url, reader_class) tuples

    Returns:
        List of (url, content) tuples

    Example:
        from src.extractors.substack import SubstackFeedReader
        from src.extractors.reddit import RedditFeedReader

        urls_and_readers = [
            ("https://substack.com/search?q=ai", SubstackFeedReader),
            ("https://reddit.com/r/python", RedditFeedReader),
        ]

        results = read_feeds_parallel(urls_and_readers)
        for url, content in results:
            print(f"Results from {url}:")
            print(content)
            print()
    """
    return pmap(read_single_feed, urls_and_readers)


def combine_results(results: List[Tuple[str, str]]) -> str:
    """
    Combine multiple feed results into a single markdown document.

    Args:
        results: List of (url, content) tuples

    Returns:
        Combined markdown content
    """
    lines = ["# Combined Feed Results\n\n"]

    for url, content in results:
        lines.append(f"## Source: {url}\n\n")
        lines.append(content)
        lines.append("\n\n" + "="*80 + "\n\n")

    return "".join(lines)
