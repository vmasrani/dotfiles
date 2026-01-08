"""
Unified data models for all platform extractors.

This module provides a consistent data model hierarchy for social media posts
across different platforms, reducing duplication and ensuring consistency.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


@dataclass
class BasePost:
    """Common fields across all platforms."""
    url: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, optionally excluding empty fields."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SocialMediaPost(BasePost):
    """For platforms with engagement metrics."""
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    views: Optional[int] = None


class Tweet(BaseModel):
    """Twitter/X tweet data structure (using Pydantic for validation)."""
    tweet_id: Optional[str] = None
    text: str
    author_handle: str
    author_name: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    relative_time: Optional[str] = None
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    has_media: bool = False
    has_links: bool = False
    extraction_success: bool = True
    errors: List[str] = Field(default_factory=list)

    def validate_content(self) -> bool:
        """Validate tweet has minimum required content."""
        if not self.text or len(self.text.strip()) < 1:
            self.errors.append("Empty text content")
            return False
        if not self.author_handle:
            self.errors.append("Missing author handle")
            return False
        return True


@dataclass
class AuthorInfo:
    """Author information from a post."""
    name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None


@dataclass
class EngagementMetrics:
    """Engagement metrics from a post."""
    likes: Optional[int] = None
    comments: Optional[int] = None
    reposts: Optional[int] = None
    views: Optional[int] = None
    reactions_breakdown: Optional[dict] = None


@dataclass
class LinkedInPost:
    """LinkedIn post data structure."""
    post_id: Optional[str] = None
    content: Optional[str] = None
    author: Optional[AuthorInfo] = None
    timestamp: Optional[str] = None
    post_url: Optional[str] = None
    engagement: Optional[EngagementMetrics] = None
    media_urls: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    raw_html: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InstagramPost:
    """Instagram post data structure."""
    username: Optional[str] = None
    author_url: Optional[str] = None
    caption: Optional[str] = None
    post_url: Optional[str] = None
    post_id: Optional[str] = None
    timestamp: Optional[str] = None
    likes_count: Optional[int] = None
    likes_text: Optional[str] = None
    comments_count: Optional[int] = None
    comments_text: Optional[str] = None
    shares_text: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)
    video_urls: List[str] = field(default_factory=list)
    alt_text: Optional[str] = None
    media_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding empty fields."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v}


@dataclass
class FacebookPost:
    """Facebook post data structure."""
    author: Optional[str] = None
    author_url: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    timestamp_unix: Optional[int] = None
    post_url: Optional[str] = None
    likes: Optional[str] = None
    comments: Optional[str] = None
    shares: Optional[str] = None
    raw_html: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RedditPost(SocialMediaPost):
    """Reddit post data structure."""
    post_id: Optional[str] = None
    title: Optional[str] = None
    subreddit: Optional[str] = None
    awards: Optional[int] = None


@dataclass
class SubstackCard:
    """Substack card data structure."""
    title: Optional[str] = None
    author: Optional[str] = None
    excerpt: Optional[str] = None
    url: Optional[str] = None
    image_src: Optional[str] = None
    image_alt: Optional[str] = None
    publication_type: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'author': self.author,
            'excerpt': self.excerpt,
            'url': self.url,
            'image_src': self.image_src,
            'image_alt': self.image_alt,
            'publication_type': self.publication_type,
            'metadata': self.metadata or {}
        }


@dataclass
class HackerNewsItem(BasePost):
    """Hacker News item data structure."""
    item_id: Optional[str] = None
    title: Optional[str] = None
    points: Optional[int] = None
    comment_count: Optional[int] = None


@dataclass
class MediumPost(BasePost):
    """Medium post data structure."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    reading_time: Optional[str] = None
    claps: Optional[int] = None
    responses: Optional[int] = None


@dataclass
class YouTubeVideo(BasePost):
    """YouTube video data structure."""
    video_id: Optional[str] = None
    title: Optional[str] = None
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    views: Optional[int] = None
    upload_date: Optional[str] = None
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None
