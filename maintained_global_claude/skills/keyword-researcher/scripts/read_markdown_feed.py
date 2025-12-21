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

from playwright.sync_api import sync_playwright
import re

def markdown_card_reader(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        # Universal extraction script
        blocks = page.evaluate("""
        () => {
            function isVisible(el) {
                const style = window.getComputedStyle(el);
                if (!style) return false;
                if (style.visibility === "hidden") return false;
                if (style.display === "none") return false;
                if (el.offsetWidth + el.offsetHeight === 0) return false;
                return true;
            }

            // collect nodes with substantial text
            const candidates = [];
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_ELEMENT,
                null
            );

            let node;
            while (node = walker.nextNode()) {
                if (!isVisible(node)) continue;

                const text = node.innerText?.trim();
                if (!text) continue;

                // Skip UI chrome (buttons, menus, nav bars)
                const tag = node.tagName.toLowerCase();
                if (["nav", "header", "footer", "button", "svg"].includes(tag)) continue;

                // Require at least some non-navigation-like text
                if (text.length < 25) continue;

                // Treat this element as a "content block"
                const links = [...node.querySelectorAll("a[href]")]
                    .map(a => ({
                        text: a.innerText.trim().replace(/\\s+/g, " "),
                        href: a.href
                    }))
                    .filter(x => x.text.length > 2);

                candidates.push({
                    text,
                    links,
                    tag,
                    depth: node.getBoundingClientRect().top,
                    len: text.length
                });
            }

            // Sort by vertical position (top to bottom)
            candidates.sort((a, b) => a.depth - b.depth);

            return candidates;
        }
        """)

        # Convert blocks → Markdown
        md = []
        for blk in blocks:
            text = blk["text"]
            text = re.sub(r"\s+", " ", text)

            md.append(f"### {text[:80]}")     # title/subtitle guess
            md.append("")

            md.append(text)                   # full text
            md.append("")

            for link in blk["links"]:
                md.append(f"- [{link['text']}]({link['href']})")
            md.append("")

        return "\n".join(md)


# Example:
if __name__ == "__main__":
    print(markdown_card_reader("https://substack.com/search/%22increments%20podcast%22"))
