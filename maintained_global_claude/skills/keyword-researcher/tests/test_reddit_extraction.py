#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "beautifulsoup4",
# ]
# ///

"""
Test Reddit extraction logic with sample HTML

This script validates extraction selectors and patterns without needing
to hit Reddit's servers. Run this to verify the extraction logic works.
"""

import json
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class RedditPost:
    """Structured Reddit post"""
    title: str = None
    url: str = None
    author: str = None
    subreddit: str = None
    content: str = None
    timestamp: str = None
    upvotes: str = None
    comments: str = None
    post_id: str = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}

def create_sample_reddit_html() -> str:
    """Create realistic Reddit post HTML for testing"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Reddit Search Results</title>
    <meta charset="UTF-8">
</head>
<body>
<main role="main">
<div class="feed">

<!-- POST 1: Text Post with full metadata -->
<article data-testid="post" data-post-id="post_1" class="Post">
    <div class="Post-header">
        <h3 class="Post-title">
            <a href="/r/podcast/comments/abc123/incremental_improvements_discussion/" class="Post-link">
                Incremental Improvements in Software Development
            </a>
        </h3>
        <span class="Post-type">text post</span>
    </div>

    <div class="Post-meta">
        <span class="Post-author">
            <a href="/u/tech_blogger" data-testid="post-author-link" class="author-link">
                u/tech_blogger
            </a>
        </span>

        <span class="Post-subreddit">
            <a href="/r/programming/" data-testid="subreddit-link" class="subreddit-link">
                r/programming
            </a>
        </span>

        <span class="Post-timestamp">
            <time datetime="2024-01-15T10:30:00Z" title="January 15, 2024 10:30 AM">
                2 hours ago
            </time>
        </span>
    </div>

    <div class="Post-content">
        <p class="Post-text">
            Just published an article about incremental improvements in software development.
            The key insight is that small, consistent improvements compound over time.
            This applies to code quality, system architecture, and team processes.
        </p>
    </div>

    <div class="Post-footer">
        <div class="Vote-container" data-testid="upvote">
            <button aria-label="upvote">⬆</button>
            <span class="vote-count">1.2K</span>
            <button aria-label="downvote">⬇</button>
        </div>

        <a href="/r/programming/comments/abc123/incremental_improvements_discussion/" class="comments-link">
            💬 542 Comments
        </a>

        <button class="share-btn">↗ Share</button>
    </div>
</article>

<!-- POST 2: Link Post -->
<article data-testid="post" data-post-id="post_2" class="Post Post-link">
    <div class="Post-header">
        <h3 class="Post-title">
            <a href="/r/podcast/comments/def456/new_podcast_episode/" class="Post-link">
                New Podcast: Building Products Incrementally
            </a>
        </h3>
        <div class="Post-thumbnail">
            <img src="https://example.com/thumbnail.jpg" alt="thumbnail" />
        </div>
    </div>

    <div class="Post-meta">
        <span class="Post-author">
            <a href="/u/podcast_host" class="author-link">
                u/podcast_host
            </a>
        </span>

        <span class="Post-subreddit">
            <a href="/r/podcast/" class="subreddit-link">
                r/podcast
            </a>
        </span>

        <span class="Post-timestamp">
            <time datetime="2024-01-14T15:20:00Z" title="January 14, 2024 3:20 PM">
                1 day ago
            </time>
        </span>
    </div>

    <div class="Post-content">
        <p class="Post-text">
            Episode 47: How to deliver value through incremental changes.
            Featuring special guests from tech industry.
        </p>
    </div>

    <div class="Post-footer">
        <div class="Vote-container">
            <span class="vote-count">892</span>
        </div>

        <a href="/r/podcast/comments/def456/new_podcast_episode/">
            💬 156 Comments
        </a>

        <button class="share-btn">↗ Share</button>
    </div>
</article>

<!-- POST 3: Minimal post (edge case) -->
<article class="Post">
    <h3><a href="/r/incremental/comments/ghi789/discussion/">Incremental Strategy</a></h3>
    <div>
        <a href="/u/minimal_user">u/minimal_user</a>
        <a href="/r/incremental">r/incremental</a>
        <time datetime="2024-01-13T08:00:00Z">3 days ago</time>
    </div>
    <p>Short discussion about incremental approaches.</p>
    <div>
        <span>245</span>
        <a href="/r/incremental/comments/ghi789/discussion/">89 Comments</a>
    </div>
</article>

<!-- POST 4: Another test post -->
<article data-testid="post">
    <h3><a href="/r/webdev/comments/jkl012/increments_best_practices/">Increments: Best Practices Guide</a></h3>
    <div class="metadata">
        <a href="/u/webdev_expert">u/webdev_expert</a>
        <a href="/r/webdev">r/webdev</a>
        <time datetime="2024-01-12T14:45:00Z">4 days ago</time>
    </div>
    <p>A comprehensive guide to implementing incremental updates in your applications.</p>
    <div>
        <div class="score">567 upvotes</div>
        <a href="/r/webdev/comments/jkl012/increments_best_practices/">234 comments</a>
    </div>
</article>

</div>
</main>
</body>
</html>
"""

def extract_posts_primary_strategy(html: str) -> list[RedditPost]:
    """Extract posts using primary selectors (CSS-based)"""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for article in soup.find_all("article"):
        post = RedditPost()

        # TITLE - Primary selectors
        title_elem = article.find("h3")
        if title_elem:
            title_link = title_elem.find("a")
            if title_link:
                post.title = title_link.get_text(strip=True)
                post.url = title_link.get("href")

                # Extract post ID from URL
                if post.url and "/comments/" in post.url:
                    match = re.search(r"/comments/([a-z0-9]+)", post.url)
                    if match:
                        post.post_id = match.group(1)

        # AUTHOR - Primary selector: a[href*="/u/"]
        author_elem = article.find("a", href=re.compile(r"/u/"))
        if author_elem:
            post.author = author_elem.get_text(strip=True)

        # SUBREDDIT - Primary selector: a[href*="/r/"] (excluding /comments/)
        for link in article.find_all("a", href=re.compile(r"/r/")):
            if "/comments/" not in link.get("href", ""):
                post.subreddit = link.get_text(strip=True)
                break

        # TIMESTAMP - Primary selector: time
        time_elem = article.find("time")
        if time_elem:
            post.timestamp = time_elem.get("datetime") or time_elem.get("title")

        # CONTENT - Primary selector: p
        content_elem = article.find("p")
        if content_elem:
            post.content = content_elem.get_text(strip=True)

        # UPVOTES - Look for vote container
        vote_elem = article.find("div", class_=re.compile("vote|score", re.I))
        if not vote_elem:
            # Try to find in any div/span with vote-related text
            for elem in article.find_all(["div", "span"]):
                text = elem.get_text(strip=True)
                if any(k in text.lower() for k in ["upvote", "vote", "score", "k"]):
                    post.upvotes = text
                    break

        # COMMENTS - Count from comment link
        comment_link = article.find("a", href=re.compile(r"/comments/"))
        if comment_link:
            post.comments = comment_link.get_text(strip=True)

        # Only add if has essential data
        if post.title and (post.url or post.subreddit):
            posts.append(post)

    return posts

def validate_extraction(posts: list[RedditPost]) -> dict:
    """Validate extracted post data"""
    validation_results = {
        "total_posts": len(posts),
        "posts_with_title": sum(1 for p in posts if p.title),
        "posts_with_author": sum(1 for p in posts if p.author),
        "posts_with_subreddit": sum(1 for p in posts if p.subreddit),
        "posts_with_url": sum(1 for p in posts if p.url),
        "posts_with_timestamp": sum(1 for p in posts if p.timestamp),
        "posts_with_content": sum(1 for p in posts if p.content),
        "posts_with_post_id": sum(1 for p in posts if p.post_id),
        "completeness": {
            "title": sum(1 for p in posts if p.title) / len(posts) if posts else 0,
            "author": sum(1 for p in posts if p.author) / len(posts) if posts else 0,
            "subreddit": sum(1 for p in posts if p.subreddit) / len(posts) if posts else 0,
            "url": sum(1 for p in posts if p.url) / len(posts) if posts else 0,
        }
    }

    return validation_results

def test_selectors(html: str) -> dict:
    """Test individual selectors"""
    soup = BeautifulSoup(html, "html.parser")

    selectors_to_test = {
        "article": soup.find_all("article"),
        "h3": soup.find_all("h3"),
        "h3 a": soup.select("h3 a"),
        "a[href*='/u/']": soup.select("a[href*='/u/']"),
        "a[href*='/r/']": soup.select("a[href*='/r/']"),
        "a[href*='/comments/']": soup.select("a[href*='/comments/']"),
        "time": soup.find_all("time"),
        "p": soup.find_all("p"),
        "[data-testid='post']": soup.select("[data-testid='post']"),
    }

    results = {}
    for selector, elements in selectors_to_test.items():
        results[selector] = {
            "found": len(elements),
            "examples": [str(e)[:100] for e in elements[:2]]
        }

    return results

def main():
    """Run tests"""
    print("=" * 80)
    print("REDDIT EXTRACTION TEST - Sample Data Validation")
    print("=" * 80)

    # Create sample HTML
    html = create_sample_reddit_html()

    # Save sample HTML
    sample_file = Path("reddit_sample_test.html")
    sample_file.write_text(html)
    print(f"\nSaved sample HTML: {sample_file}")

    # Test selectors
    print("\n" + "-" * 80)
    print("SELECTOR TEST RESULTS")
    print("-" * 80)

    selector_results = test_selectors(html)
    for selector, result in selector_results.items():
        print(f"{selector:30s} : {result['found']:3d} found")

    # Extract posts
    print("\n" + "-" * 80)
    print("POST EXTRACTION RESULTS")
    print("-" * 80)

    posts = extract_posts_primary_strategy(html)

    print(f"\nExtracted {len(posts)} posts:\n")

    for i, post in enumerate(posts, 1):
        print(f"POST {i}")
        print(f"  Title:      {post.title}")
        print(f"  Author:     {post.author}")
        print(f"  Subreddit:  {post.subreddit}")
        print(f"  URL:        {post.url}")
        print(f"  Post ID:    {post.post_id}")
        print(f"  Timestamp:  {post.timestamp}")
        print(f"  Content:    {post.content[:50]}..." if post.content else "  Content:    (none)")
        print(f"  Upvotes:    {post.upvotes}")
        print(f"  Comments:   {post.comments}")
        print()

    # Validate extraction
    print("-" * 80)
    print("EXTRACTION VALIDATION")
    print("-" * 80)

    validation = validate_extraction(posts)
    print(f"\nTotal posts extracted: {validation['total_posts']}")
    print(f"Posts with title: {validation['posts_with_title']}")
    print(f"Posts with author: {validation['posts_with_author']}")
    print(f"Posts with subreddit: {validation['posts_with_subreddit']}")
    print(f"Posts with URL: {validation['posts_with_url']}")
    print(f"Posts with timestamp: {validation['posts_with_timestamp']}")
    print(f"Posts with content: {validation['posts_with_content']}")
    print(f"Posts with post ID: {validation['posts_with_post_id']}")

    print(f"\nData Completeness Rates:")
    for field, rate in validation['completeness'].items():
        print(f"  {field:15s}: {rate*100:5.1f}%")

    # Save results
    results = {
        "extraction_validation": validation,
        "sample_posts": [p.to_dict() for p in posts],
        "selector_effectiveness": selector_results,
    }

    results_file = Path("reddit_extraction_test_results.json")
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\n\nResults saved to: {results_file}")

    # Test status
    print("\n" + "=" * 80)
    if validation['completeness']['title'] == 1.0 and validation['posts_with_author'] > 0:
        print("TEST STATUS: PASS ✓")
        print("Extraction logic works correctly with sample data")
    else:
        print("TEST STATUS: WARNINGS")
        if validation['completeness']['title'] < 1.0:
            print("  - Some posts missing titles")
        if validation['posts_with_author'] == 0:
            print("  - No authors extracted")

    print("=" * 80)

if __name__ == "__main__":
    main()
