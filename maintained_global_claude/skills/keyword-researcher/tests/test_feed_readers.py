#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "playwright",
#     "html2text",
#     "beautifulsoup4",
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

import sys
from pathlib import Path

# Add parent directory to path so imports work when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feed_reader import create_feed_reader
from mlh.parallel import pmap
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TestCase:
    name: str
    url: str
    platform: str


def test_single_feed(test_case: TestCase) -> dict:
    """Test a single feed reader"""
    print(f"\n{'='*60}")
    print(f"Testing {test_case.platform}: {test_case.name}")
    print(f"URL: {test_case.url}")
    print(f"{'='*60}\n")

    try:
        reader = create_feed_reader(test_case.url)
        result = reader.read_feed()

        # Save result to file
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{test_case.platform}_{test_case.name.replace(' ', '_')}.md"

        with open(output_file, 'w') as f:
            f.write(result)

        print(f"✓ SUCCESS: {test_case.platform}")
        print(f"  Output saved to: {output_file}")
        print(f"  Preview:\n{result[:500]}...\n")

        return {
            'platform': test_case.platform,
            'name': test_case.name,
            'status': 'success',
            'output_file': str(output_file),
            'preview': result[:200]
        }

    except Exception as e:
        print(f"✗ FAILED: {test_case.platform}")
        print(f"  Error: {str(e)}\n")

        return {
            'platform': test_case.platform,
            'name': test_case.name,
            'status': 'failed',
            'error': str(e)
        }


def main():
    """Test all feed readers"""
    test_cases = [
        TestCase(
            name="search_increments_podcast",
            url="https://substack.com/search/%22increments%20podcast%22",
            platform="substack"
        ),
        TestCase(
            name="search_increments_podcast",
            url="https://www.reddit.com/search/?q=increments%20podcast",
            platform="reddit"
        ),
        TestCase(
            name="front_page",
            url="https://news.ycombinator.com/",
            platform="hackernews"
        ),
        TestCase(
            name="search_ai",
            url="https://medium.com/search?q=artificial%20intelligence",
            platform="medium"
        ),
        TestCase(
            name="search_python",
            url="https://www.youtube.com/results?search_query=python+tutorial",
            platform="youtube"
        ),
    ]

    print("\n" + "="*60)
    print("FEED READER TEST SUITE")
    print("="*60)
    print(f"Testing {len(test_cases)} platforms in parallel...\n")

    # Test all feeds in parallel
    results = pmap(test_single_feed, test_cases)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    success_count = sum(1 for r in results if r['status'] == 'success')
    fail_count = len(results) - success_count

    print(f"\nTotal tests: {len(results)}")
    print(f"✓ Passed: {success_count}")
    print(f"✗ Failed: {fail_count}\n")

    for result in results:
        status_icon = "✓" if result['status'] == 'success' else "✗"
        print(f"{status_icon} {result['platform']}: {result['name']}")
        if result['status'] == 'failed':
            print(f"  Error: {result['error']}")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
