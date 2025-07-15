#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pymupdf",
#     "pillow",
#     "machine-learning-helpers",
#     "pytesseract",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///

import sys
import os
import fitz
from pathlib import Path
import time
import io
import argparse
from mlh.parallel import pmap
from PIL import Image
import pytesseract

def process_single_page(pdf_path, page_num, output_dir, dpi=150):
    """Process a single page, save it as a PNG, and perform OCR to save text."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("ppm")
    page_img = Image.open(io.BytesIO(img_data))

    page_dir = output_dir / f"page_{page_num+1:03d}"
    page_dir.mkdir(parents=True, exist_ok=True)
    output_path = page_dir / "img.png"
    page_img.save(output_path, 'PNG', quality=95)

    # Perform OCR and save the text
    ocr_text = pytesseract.image_to_string(page_img)
    ocr_output_path = page_dir / "ocr.txt"
    ocr_output_path.write_text(ocr_text, encoding='utf-8')

    doc.close()
    return str(output_path.relative_to(output_dir))

def main():
    parser = argparse.ArgumentParser(description='Convert PDF pages to PNG images')
    parser.add_argument('pdf_file', help='PDF file to convert')
    parser.add_argument('--dpi', type=int, default=150,
                       help='DPI for output images (default: 150)')

    args = parser.parse_args()

    pdf_file = args.pdf_file
    dpi = args.dpi

    if not os.path.isfile(pdf_file):
        print(f"Error: File '{pdf_file}' does not exist.")
        sys.exit(1)

    # Create output directory
    basename = Path(pdf_file).stem
    output_dir = Path(basename)
    output_dir.mkdir(exist_ok=True)

    print(f"Processing PDF: {pdf_file}")
    print(f"Output directory: {output_dir}")
    print(f"DPI: {dpi}")

    # Open PDF to get page count
    try:
        doc = fitz.open(pdf_file)
        page_count = len(doc)
        doc.close()
        print(f"Total pages: {page_count}")
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)

    start_time = time.time()

    # Process each page individually
    page_numbers = range(page_count)
    results = pmap(lambda page_num: process_single_page(pdf_file, page_num, output_dir, dpi), page_numbers)

    for result in results:
        print(f"Processed: {result}")

    end_time = time.time()
    processing_time = end_time - start_time

    print(f"\nExtraction complete in {processing_time:.2f} seconds!")
    print(f"Pages per second: {page_count/processing_time:.2f}")
    print(f"Files created in '{output_dir}' directory:")

    # List created files
    for page_dir in sorted(output_dir.iterdir()):
        if page_dir.is_dir():
            png_file = page_dir / "img.png"
            file_size = png_file.stat().st_size / 1024  # KB
            print(f"  {page_dir.name}/img.png ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
