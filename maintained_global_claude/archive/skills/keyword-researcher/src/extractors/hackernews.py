"""
Hacker News feed reader - API-only implementation.

Extracts story data from Hacker News using their Algolia API.
No browser required.
"""

import httpx
from datetime import datetime


class HackerNewsFeedReader:
    """Parser for Hacker News using Algolia API - no browser required."""

    def __init__(self, url: str):
        self.url = url

    def read_feed(self) -> str:
        """Fetch from API and format results."""
        response = httpx.get(self.url, timeout=30, follow_redirects=True)
        if response.status_code != 200:
            return f"Error fetching from Hacker News API: {response.status_code}\n"

        data = response.json()
        hits = data.get('hits', [])

        if not hits:
            return "No Hacker News stories found.\n"

        stories = [self._extract_story(hit) for hit in hits if hit.get('title')]
        return self._format_markdown(stories, data)

    def _extract_story(self, hit: dict) -> dict:
        """Extract data from a single HN API hit."""
        story = {
            'title': hit.get('title'),
            'url': hit.get('url'),
            'hn_url': f"https://news.ycombinator.com/item?id={hit['objectID']}" if hit.get('objectID') else None,
            'points': hit.get('points'),
            'author': hit.get('author'),
            'num_comments': hit.get('num_comments'),
            'created_at': hit.get('created_at')
        }

        if story['url']:
            from urllib.parse import urlparse
            parsed = urlparse(story['url'])
            story['domain'] = parsed.netloc or parsed.path

        return story

    def _format_markdown(self, stories: list, api_data: dict) -> str:
        """Format HN stories as markdown."""
        lines = ["# Hacker News Search Results\n"]
        lines.append(f"Found {len(stories)} stories\n\n")

        for story in stories:
            lines.append(f"## {story['title']}")

            meta = []
            if story.get('points'):
                meta.append(f"{story['points']} points")
            if story.get('author'):
                meta.append(f"by {story['author']}")
            if story.get('num_comments'):
                meta.append(f"{story['num_comments']} comments")

            if meta:
                lines.append(f"**{' • '.join(meta)}**")

            if story.get('domain'):
                lines.append(f"\n*{story['domain']}*")

            links = []
            if story.get('url'):
                links.append(f"[View Article]({story['url']})")
            if story.get('hn_url'):
                links.append(f"[HN Discussion]({story['hn_url']})")

            if links:
                lines.append(f"\n{' | '.join(links)}")

            lines.append("\n---\n")

        return "\n".join(lines)
