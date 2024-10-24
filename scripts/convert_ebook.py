#!/Users/vmasrani/miniconda/envs/ml3/bin/python

import sys
from pathlib import Path
import shutil
import time
from convertio import Client
import re
from pypdf import PdfReader
from tqdm import tqdm

def get_metadata(input_file):
    try:
        reader = PdfReader(input_file)
        info = reader.metadata
        author = info.get('/Author', 'unknown_author')
        title = info.get('/Title', input_file.stem)
    except Exception as e:
        print(f"Error reading metadata: {e}")
        author = "unknown_author"
        title = input_file.stem
    return author, title

def sanitize_name(name):
    return re.sub(r'_{2,}', '_', ''.join(c.lower() if c.isalnum() else '_' for c in name)).strip('_')


def convert_file(api, source, target, output_dir):
    output_file = output_dir / f"{source.stem}.{target}"
    print(f"Converting to {target}...")
    try:
        conversion_id = api.convert_by_filename(str(source), target)
        while api.check_conversion(conversion_id).step != 'finish':
            time.sleep(1)
        api.download(conversion_id, str(output_file))
        print(f"Conversion to {target} successful.")
    except Exception as e:
        print(f"Error: Conversion to {target} failed. {str(e)}")
    return output_file


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        sys.exit(1)

    input_file = Path(sys.argv[1]).expanduser().resolve()
    if not input_file.exists():
        print(f"Error: The file '{input_file}' does not exist.")
        sys.exit(1)

    with open(Path.home() / '.convertio_api_key') as f:
        api_key = f.read().strip()

    api = Client(api_key)
    output_dir = Path("temp_ebook")
    output_dir.mkdir(exist_ok=True)

    pdf_file = input_file if input_file.suffix.lower() == '.pdf' else convert_file(api, input_file, 'pdf', output_dir)
    epub_file = input_file if input_file.suffix.lower() == '.epub' else convert_file(api, input_file, 'epub', output_dir)

    if not pdf_file.exists():
        print(f"Error: The PDF file '{pdf_file}' was not created.")
        sys.exit(1)

    if not epub_file.exists():
        print(f"Error: The EPUB file '{epub_file}' was not created.")
        sys.exit(1)

    author, title = get_metadata(pdf_file)
    clean_name = sanitize_name(f"{author} - {title}")
    final_output_dir = Path(f"{clean_name}_ebook")
    final_output_dir.mkdir(exist_ok=True)

    shutil.copy(str(pdf_file), final_output_dir / f"{clean_name}.pdf")
    shutil.copy(str(epub_file), final_output_dir / f"{clean_name}.epub")

    shutil.rmtree(output_dir)
    print(f"Conversion complete. Output files are in the '{final_output_dir}' directory.")

if __name__ == "__main__":
    main()
