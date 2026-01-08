#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "beautifulsoup4",
#     "lxml",
#     "rich",
# ]
# ///

"""
Facebook Selectors Validator
Tests CSS selectors against sample HTML to verify they work.

This script can:
1. Validate selectors against saved HTML files
2. Compare selector performance
3. Generate test reports

Usage:
    # Test selectors against a saved HTML file
    uv run test_facebook_selectors.py --html debug_page.html

    # Create sample HTML for testing
    uv run test_facebook_selectors.py --generate-sample
"""

from bs4 import BeautifulSoup
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import List, Dict, Optional, Tuple
import json

console = Console()


class FacebookSelectorTester:
    """Test Facebook selectors against HTML"""

    def __init__(self, html_content: str):
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.test_results = []

    def test_selector(self, name: str, selector: str, should_find: int = None) -> Dict:
        """Test a single selector"""
        try:
            elements = self.soup.select(selector)
            found = len(elements)
            success = True if should_find is None else found >= should_find

            result = {
                'name': name,
                'selector': selector,
                'found': found,
                'success': success,
                'examples': [str(el)[:100] for el in elements[:3]],
            }

            self.test_results.append(result)
            return result

        except Exception as e:
            return {
                'name': name,
                'selector': selector,
                'error': str(e),
                'success': False,
            }

    def test_post_selectors(self) -> List[Dict]:
        """Test all post-related selectors"""
        console.print("\n[bold cyan]Testing Post Selectors[/bold cyan]")

        tests = [
            # Container selectors
            ("Post Container (role=article)", 'div[role="article"]', 1),
            ("Post Container (data-ft)", 'div[data-ft]', 1),
            ("Post Container (data-pagelet)", 'div[data-pagelet*="Feed"]', 0),

            # Author selectors
            ("Author Name", 'a[class*="actor"] span', 1),
            ("Author Link", 'a[href^="/"][class*="actor"]', 0),
            ("Author Avatar", 'img[class*="avatar"]', 0),

            # Content selectors
            ("Post Text (paragraph)", 'p', 0),
            ("Post Text (div p)", 'div p', 0),
            ("Post Word Break", 'div[style*="word-break"]', 0),

            # Timestamp selectors
            ("Timestamp (data-utime)", 'span[data-utime]', 0),
            ("Timestamp (abbr)", 'abbr[data-utime]', 0),
            ("Timestamp (any)", '[data-utime]', 0),

            # Engagement selectors
            ("Likes", 'a[href*="reaction"] span', 0),
            ("Comments", 'a[href*="comment"] span', 0),
            ("Shares", 'a[href*="share"] span', 0),

            # URL selectors
            ("Post URL", 'a[href*="/posts/"]', 0),
            ("Photo URL", 'a[href*="/photo.php"]', 0),
        ]

        for name, selector, min_expected in tests:
            result = self.test_selector(name, selector, min_expected)
            status = "✓" if result.get('success') else "✗"
            found = result.get('found', '?')
            console.print(f"{status} {name}: {found} elements")

        return self.test_results

    def generate_report(self) -> str:
        """Generate a summary report"""
        passed = sum(1 for r in self.test_results if r.get('success'))
        total = len(self.test_results)

        report = f"""
TEST RESULTS SUMMARY
{'='*50}
Total Tests: {total}
Passed: {passed}
Failed: {total - passed}
Success Rate: {(passed/total*100):.1f}%

DETAILED RESULTS
{'='*50}
"""
        for result in self.test_results:
            if result.get('success'):
                report += f"\n✓ {result['name']}"
                report += f"\n  Selector: {result['selector']}"
                report += f"\n  Found: {result.get('found')} elements"
            else:
                report += f"\n✗ {result['name']}"
                report += f"\n  Selector: {result['selector']}"
                report += f"\n  Error: {result.get('error', 'No matches')}"

        return report

    def display_results_table(self):
        """Display results in a formatted table"""
        table = Table(title="Selector Test Results")
        table.add_column("Status", style="cyan")
        table.add_column("Selector Name", style="magenta")
        table.add_column("CSS Selector", style="yellow")
        table.add_column("Found", style="green")
        table.add_column("Success", style="blue")

        for result in self.test_results:
            status = "✓" if result.get('success') else "✗"
            found = str(result.get('found', 'error'))
            success = str(result.get('success', False))

            table.add_row(
                status,
                result['name'],
                result['selector'][:40],
                found,
                success,
            )

        console.print(table)

    def compare_selectors(self, selector1: str, selector2: str) -> Tuple[int, int]:
        """Compare two selectors to see which finds more"""
        count1 = len(self.soup.select(selector1))
        count2 = len(self.soup.select(selector2))

        console.print(f"\nComparing selectors:")
        console.print(f"  Selector 1: {selector1}")
        console.print(f"    Found: {count1} elements")
        console.print(f"  Selector 2: {selector2}")
        console.print(f"    Found: {count2} elements")
        console.print(f"  Winner: {'Selector 1' if count1 > count2 else 'Selector 2' if count2 > count1 else 'Tie'}")

        return count1, count2


def generate_sample_html() -> str:
    """Generate sample HTML for testing"""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Sample Facebook Feed</title></head>
    <body>
    <div role="feed">
        <div role="article" data-ft='{"mf_story_key":"123","type":"FeedStory"}' data-pagelet="FeedStory_123">
            <div>
                <a class="x1iyjqo2 xvmnnby" href="/profile/john.doe" aria-label="John Doe">
                    <img class="xds687c" src="/pic.jpg" alt="John" />
                </a>
                <div>
                    <a class="xvmnnby" href="/profile/john.doe">
                        <h3>John Doe</h3>
                    </a>
                    <a href="/posts/123456789">
                        <abbr title="December 10, 2023" data-utime="1702137600">
                            2 hours ago
                        </abbr>
                    </a>
                </div>
            </div>

            <div>
                <div style="word-break:break-word;">
                    <p>This is a sample Facebook post with some text content for testing selectors.</p>
                </div>
            </div>

            <div>
                <a href="/ufi/reaction/post/123/pokes/" aria-label="256 reactions">
                    <span>256</span>
                </a>
                <a href="/ufi/reaction/post/123/comments/" aria-label="45 comments">
                    <span>45</span>
                </a>
                <a href="/ufi/reaction/post/123/shares/" aria-label="12 shares">
                    <span>12</span>
                </a>
            </div>
        </div>

        <div role="article" data-ft='{"mf_story_key":"456"}' data-pagelet="FeedStory_456">
            <div>
                <a class="xvmnnby" href="/profile/jane.smith">
                    <img class="xds687c" src="/pic2.jpg" alt="Jane" />
                </a>
                <div>
                    <a class="xvmnnby" href="/profile/jane.smith">
                        <h3>Jane Smith</h3>
                    </a>
                    <a href="/posts/987654321">
                        <abbr title="December 10, 2023" data-utime="1702134000">
                            3 hours ago
                        </abbr>
                    </a>
                </div>
            </div>

            <div>
                <div style="word-break:break-word;">
                    <p>Another sample post for comprehensive selector testing.</p>
                </div>
            </div>

            <div>
                <a href="/ufi/reaction/post/456/pokes/" aria-label="512 reactions">
                    <span>512</span>
                </a>
                <a href="/ufi/reaction/post/456/comments/" aria-label="89 comments">
                    <span>89</span>
                </a>
                <a href="/ufi/reaction/post/456/shares/" aria-label="23 shares">
                    <span>23</span>
                </a>
            </div>
        </div>
    </div>
    </body>
    </html>
    '''


def main():
    """Main test function"""
    console.print(Panel.fit(
        "[bold cyan]Facebook Selectors Validator[/bold cyan]",
        border_style="cyan"
    ))

    # Generate sample HTML
    console.print("\n[bold]Generating sample HTML...[/bold]")
    html = generate_sample_html()

    # Save sample for reference
    sample_path = Path("facebook_sample.html")
    with open(sample_path, "w") as f:
        f.write(html)
    console.print(f"[green]Sample saved to {sample_path}[/green]")

    # Create tester
    tester = FacebookSelectorTester(html)

    # Run tests
    console.print("\n[bold]Running selector tests...[/bold]")
    tester.test_post_selectors()

    # Display results
    tester.display_results_table()

    # Generate report
    report = tester.generate_report()
    console.print(report)

    # Save report
    report_path = Path("selector_test_report.txt")
    with open(report_path, "w") as f:
        f.write(report)
    console.print(f"\n[green]Report saved to {report_path}[/green]")

    # Comparison examples
    console.print("\n[bold cyan]Selector Comparisons[/bold cyan]")

    comparisons = [
        ('a[class*="actor"] span', 'a[href^="/"] span'),
        ('div[role="article"] p', 'p'),
        ('span[data-utime]', 'abbr[data-utime]'),
    ]

    for sel1, sel2 in comparisons:
        tester.compare_selectors(sel1, sel2)

    console.print("\n[bold green]Testing complete![/bold green]")
    console.print("Check selector_test_report.txt for detailed results")


if __name__ == "__main__":
    main()
