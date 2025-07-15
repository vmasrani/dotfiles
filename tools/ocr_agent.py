#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "openai",
# ]
# ///

import base64
import sys
import time
import random
from pathlib import Path
from openai import OpenAI

def read_image_as_base64(image_path):
    """Read image file and encode as base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_ocr_prompt():
    """Read the OCR prompt from the Claude commands directory"""
    prompt_path = Path.home() / ".claude" / "commands" / "ocr.md"
    return prompt_path.read_text().strip()

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: ocr_agent.py directory_path [--skip-existing]", file=sys.stderr)
        sys.exit(1)

    dir_path = Path(sys.argv[1])
    skip_existing = '--skip-existing' in sys.argv

    if not dir_path.is_dir():
        print(f"Error: Directory '{dir_path}' not found", file=sys.stderr)
        sys.exit(1)

    img_file = dir_path / "img.png"
    ocr_file = dir_path / "ocr.txt"
    output_path = dir_path / "ocr_output.md"

    if not img_file.exists():
        print(f"Error: Image file 'img.png' not found in directory '{dir_path}'", file=sys.stderr)
        sys.exit(1)

    if not ocr_file.exists():
        print(f"Error: OCR text file 'ocr.txt' not found in directory '{dir_path}'", file=sys.stderr)
        sys.exit(1)

    if skip_existing and output_path.exists():
        print(f"Skipping OCR as 'ocr_output.md' already exists in '{dir_path}'")
        return

    print(f"Running OCR on {dir_path}...")

    # Introduce random jitter time
    time.sleep(random.uniform(1, 20))

    # Read and encode the image
    image_data = read_image_as_base64(img_file)

    # Get the OCR prompt and add file-specific information
    base_prompt = get_ocr_prompt()
    prompt = f"{base_prompt} ---\nThe file to OCR is: {img_file}\nA preliminary OCR text file is available at: {ocr_file}\n"

    # Initialize OpenAI client (API key should be in environment variable OPENAI_API_KEY)
    client = OpenAI()

    # Create the message with proper image format
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    }
                ]
            }
        ],
        max_tokens=4096
    )

    # Write the response to ocr_output.md in the directory
    output_path.write_text(response.choices[0].message.content)

    print(f"OCR completed: {img_file} -> {output_path}")

if __name__ == "__main__":
    main()
