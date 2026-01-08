#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "playwright",
#     "beautifulsoup4",
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

"""
Test script for Instagram post extractor

This script validates the Instagram post extraction functionality
using the sample HTML fixtures.

Usage:
    uv run test_extractor.py
"""

import json
from pathlib import Path
from instagram_post_extractor import InstagramPostExtractor


def test_sample_extraction():
    """Test extraction from sample HTML."""
    print("Instagram Post Extractor - Test Suite")
    print("=" * 60)

    # Load sample HTML
    sample_file = Path(__file__).parent / "sample_instagram_post.html"

    if not sample_file.exists():
        print(f"Error: Sample HTML file not found: {sample_file}")
        return False

    print(f"Loading sample HTML from {sample_file}")
    with open(sample_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Extract posts
    print("\nExtracting posts...")
    extractor = InstagramPostExtractor(verbose=True)
    posts = extractor.extract_from_html(html_content)

    print(f"\nExtracted {len(posts)} posts")

    if not posts:
        print("No posts extracted!")
        return False

    # Validate extraction
    print("\n" + "=" * 60)
    print("Validation Results")
    print("=" * 60)

    test_results = []

    for idx, post in enumerate(posts):
        print(f"\nPost #{idx + 1}:")
        print("-" * 40)

        tests = {
            "Username extracted": post.username is not None,
            "Caption extracted": post.caption is not None,
            "Timestamp extracted": post.timestamp is not None,
            "Post URL extracted": post.post_url is not None,
            "Likes count extracted": post.likes_count is not None,
            "Comments count extracted": post.comments_count is not None,
            "Media type identified": post.media_type is not None,
        }

        for test_name, result in tests.items():
            status = "PASS" if result else "FAIL"
            print(f"  {test_name}: {status}")
            test_results.append((test_name, result))

        # Print extracted data
        print("\nExtracted Data:")
        post_dict = post.to_dict()
        for key, value in post_dict.items():
            if value:
                value_preview = str(value)
                if isinstance(value, str) and len(value) > 50:
                    value_preview = value[:50] + "..."
                print(f"  {key}: {value_preview}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"Tests passed: {passed}/{total} ({pass_rate:.1f}%)")

    # Save results
    output_file = Path(__file__).parent / "test_results.json"
    results_data = {
        "posts_extracted": len(posts),
        "test_results": {
            "passed": passed,
            "total": total,
            "pass_rate": pass_rate,
        },
        "sample_posts": [post.to_dict() for post in posts],
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"\nTest results saved to {output_file}")

    return passed == total


def test_individual_extractors():
    """Test individual extraction functions."""
    print("\n" + "=" * 60)
    print("Testing Individual Extraction Functions")
    print("=" * 60)

    from bs4 import BeautifulSoup

    # Load sample HTML
    sample_file = Path(__file__).parent / "sample_instagram_post.html"
    with open(sample_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    posts = soup.find_all('article')

    if not posts:
        print("No posts found in sample HTML")
        return False

    post = posts[0]
    extractor = InstagramPostExtractor(verbose=False)

    print("\nTesting with first post element:")
    print("-" * 40)

    # Test individual functions
    tests = [
        ("Username", extractor._extract_username(post)),
        ("Caption", extractor._extract_caption(post)),
        ("Post URL", extractor._extract_post_url(post)),
        ("Timestamp", extractor._extract_timestamp(post)),
        ("Likes", extractor._extract_likes(post)),
        ("Comments", extractor._extract_comments(post)),
        ("Shares", extractor._extract_shares(post)),
        ("Images", extractor._extract_images(post)),
        ("Videos", extractor._extract_videos(post)),
        ("Alt text", extractor._extract_alt_text(post)),
    ]

    for test_name, result in tests:
        print(f"{test_name}: {result}")

    return True


def test_css_selectors():
    """Validate CSS selectors are working."""
    print("\n" + "=" * 60)
    print("Testing CSS Selectors")
    print("=" * 60)

    from bs4 import BeautifulSoup

    sample_file = Path(__file__).parent / "sample_instagram_post.html"
    with open(sample_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    selectors = {
        "Post containers": ('article', None),
        "User links": ('[data-testid="user-link"]', None),
        "Captions": ('[data-testid="post-caption"]', None),
        "Timestamps": ('time', None),
        "Like buttons": ('button[aria-label="Like"]', None),
        "Comment buttons": ('button[aria-label="Comment"]', None),
        "Images": ('img', 'alt'),
    }

    print("\nCSSSelector Test Results:")
    print("-" * 40)

    for selector_name, (selector, attr) in selectors.items():
        if attr:
            elements = soup.select(selector)
            results = [el.get(attr) for el in elements if el.get(attr)]
        else:
            results = soup.select(selector)

        count = len(results)
        status = "FOUND" if count > 0 else "NOT FOUND"
        print(f"{selector_name} ({selector}): {status} - {count} elements")

        if results and count <= 3:
            for idx, result in enumerate(results):
                if isinstance(result, str):
                    preview = result[:50] + "..." if len(result) > 50 else result
                else:
                    preview = str(result)[:50] + "..."
                print(f"    {idx + 1}. {preview}")

    return True


def main():
    """Run all tests."""
    try:
        print("\n")

        # Run tests
        test1 = test_sample_extraction()
        test2 = test_individual_extractors()
        test3 = test_css_selectors()

        # Final result
        print("\n" + "=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        all_passed = test1 and test2 and test3
        status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
        print(f"{status}")

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
