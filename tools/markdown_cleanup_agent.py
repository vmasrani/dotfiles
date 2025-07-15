#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "machine-learning-helpers",
#     "openai",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

import sys
from pathlib import Path
from openai import OpenAI
from mlh.parallel import pmap
import random
import time

def process_markdown_file(markdown_file_path):
    """Process a single markdown file through OpenAI cleanup"""
    markdown_file_path = Path(markdown_file_path)

    if not markdown_file_path.is_file():
        print(f"Error: File '{markdown_file_path}' not found", file=sys.stderr)
        return None

    output_path = markdown_file_path.with_name("cleaned_" + markdown_file_path.name)

    # Read the markdown file content
    markdown_content = markdown_file_path.read_text()

    # Introduce random sleep between 1 and 20 seconds
    time.sleep(random.uniform(1, 20))

    # Define the base prompt
    base_prompt = """
    You are a markdown cleanup agent. You are given a markdown file with broken markdown syntax. Your task is to clean up the markdown so that the footnotes are in correct markdown syntax, and latex is used for all formula. don't change the footnote numbering, DON'T CHANGE ANY OF THE TEXT.
    clean this up so the footnotes are in correct markdown syntax, and latex is used for all formula. don't change the footnote numbering, DON'T CHANGE ANY OF THE TEXT.
    replace
    ```yaml
    var: 1
    var: 2
    ```
    with
    ---
    var: 1
    var: 2
    ---
    and remove any extraneous "```

    Don't add any additional text or commentary, just clean up the markdown.

    Do not include any additional text or commentary such as:
    - "I think this should be formatted differently."
    - "Here's a suggestion for improvement."
    - "This part seems unclear."
    """

    prompt = f"{base_prompt} ---\nThe content to clean up is:\n{markdown_content}\n"

    # Initialize OpenAI client (API key should be in environment variable OPENAI_API_KEY)
    client = OpenAI()

    # Create the message with the markdown content
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=4096
    )

    # Write the response to the output file
    output_path.write_text(response.choices[0].message.content)

    return f"Markdown cleanup completed: {markdown_file_path} -> {output_path}"

def main():
    if len(sys.argv) < 2:
        print("Usage: markdown_cleanup_agent.py markdown_file_path [markdown_file_path2] ...", file=sys.stderr)
        sys.exit(1)

    markdown_file_paths = [Path(arg) for arg in sys.argv[1:]]

    # Validate all files exist before processing
    for file_path in markdown_file_paths:
        if not file_path.is_file():
            print(f"Error: File '{file_path}' not found", file=sys.stderr)
            sys.exit(1)

    # Process all files in parallel using pmap
    pmap(process_markdown_file, markdown_file_paths, n_jobs=100, prefer="threads")

if __name__ == "__main__":
    main()
