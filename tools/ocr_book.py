#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pymupdf",
#     "pillow",
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

import sys
import subprocess
from pathlib import Path
from mlh.parallel import pmap
import time
import random

def run_ocr_on_image(image_path):
    """Run OCR on a single image using a shell script."""
    script_path = Path.home() / "tools" / "ocr_agent.py"
    subprocess.run([str(script_path), str(image_path), '--skip-existing'], check=True)

def main():
    if len(sys.argv) != 2:
        print("Usage: ocr_book.py path/to/dir")
        sys.exit(1)

    png_dir = Path(sys.argv[1])

    if not png_dir.is_dir():
        print(f"Error: Directory '{png_dir}' does not exist.")
        sys.exit(1)

    # List PNG files in the directory
    page_dirs = sorted(png_dir.glob("page_*"))

    valid_dirs = []
    for png_file in page_dirs:
        img_file = png_file / "img.png"
        ocr_file = png_file / "ocr.txt"
        if not img_file.exists() or not ocr_file.exists():
            print(f"Error: 'img.png' or 'ocr.txt' not found in directory '{png_file}'.")
            sys.exit(1)
        if not (png_file / "ocr_output.md").exists():
            valid_dirs.append(png_file)

    print(f"Running OCR on PNG files in directory: {png_dir}")

    # Run OCR on each PNG file using pmap
    pmap(run_ocr_on_image, valid_dirs, n_jobs=100, prefer="threads")

    print("\nOCR processing complete!")


if __name__ == "__main__":
    main()
