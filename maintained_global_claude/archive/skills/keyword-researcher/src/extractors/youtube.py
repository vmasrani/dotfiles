"""
YouTube feed reader - simplified version.

Extracts video data from YouTube search results using ytInitialData.
"""

from playwright.sync_api import Page
from src.core.base import FeedReader


class YouTubeFeedReader(FeedReader):
    """Parser for YouTube search results."""

    def parse_feed(self, page: Page) -> str:
        """Extract YouTube videos and convert to markdown."""
        yt_data = page.evaluate("() => window.ytInitialData")

        if not yt_data:
            return "No YouTube data found.\n"

        videos = self._extract_videos(yt_data)
        return self._format_markdown(videos)

    def _safe_get_text(self, obj, *keys):
        """Safely navigate nested dict and extract text."""
        current = obj
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)

        if isinstance(current, str):
            return current
        if isinstance(current, dict):
            if 'simpleText' in current:
                return current['simpleText']
            if 'runs' in current and current['runs']:
                return current['runs'][0].get('text')
        return None

    def _extract_videos(self, yt_data: dict) -> list:
        """Extract video data from ytInitialData."""
        videos = []
        contents = (yt_data.get('contents', {})
                   .get('twoColumnSearchResultsRenderer', {})
                   .get('primaryContents', {})
                   .get('sectionListRenderer', {})
                   .get('contents', []))

        for section in contents:
            items = section.get('itemSectionRenderer', {}).get('contents', [])
            for item in items:
                renderer = item.get('videoRenderer')
                if renderer:
                    video = {
                        'title': self._safe_get_text(renderer, 'title'),
                        'video_id': renderer.get('videoId'),
                        'channel': self._safe_get_text(renderer, 'ownerText'),
                        'views': self._safe_get_text(renderer, 'viewCountText'),
                        'published': self._safe_get_text(renderer, 'publishedTimeText'),
                        'length': self._safe_get_text(renderer, 'lengthText')
                    }
                    if video['title'] and video['video_id']:
                        video['url'] = f"https://www.youtube.com/watch?v={video['video_id']}"
                        videos.append(video)

        return videos

    def _format_markdown(self, videos: list) -> str:
        """Format YouTube videos as markdown."""
        lines = ["# YouTube Search Results\n"]
        lines.append(f"Found {len(videos)} videos\n\n")

        for video in videos:
            lines.append(f"## {video['title']}")

            meta = []
            if video.get('channel'):
                meta.append(video['channel'])
            if video.get('views'):
                meta.append(video['views'])
            if video.get('published'):
                meta.append(video['published'])
            if video.get('length'):
                meta.append(video['length'])

            if meta:
                lines.append(f"**{' • '.join(meta)}**")

            if video.get('url'):
                lines.append(f"\n[Watch on YouTube]({video['url']})")

            lines.append("\n---\n")

        return "\n".join(lines)
