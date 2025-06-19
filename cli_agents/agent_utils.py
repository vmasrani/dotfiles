from pathlib import Path
import tempfile
from PyPDF2 import PdfReader, PdfWriter
import yaml
import json
import time
import random
from types import SimpleNamespace
from rich.panel import Panel
from rich.columns import Columns
from rich.console import Group, Console # Added Console here as it might be used by panel functions
from mlh.parallel import pmap
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import io
AGENT_CONFIG = Path.home() / "dotfiles" / "cli_agents" / "agent.yaml"


def save_first_n_pages(pdf_path: Path | str, n_pages: int = 5) -> Path:
    """Extract first n pages from PDF and save to temp file with optional OCR"""
    pdf_path = Path(pdf_path)
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Get pages to extract (min of n_pages or actual page count)
    pages_to_extract = min(n_pages, len(reader.pages))


    # Process each page, using OCR only if needed
    pages_needing_ocr = [
        i for i in range(pages_to_extract)
        if not reader.pages[i].extract_text().strip()
    ]

    if not pages_needing_ocr:
        # If no pages need OCR, just copy the original pages
        [writer.add_page(reader.pages[i]) for i in range(pages_to_extract)]
    else:
        # Convert only pages needing OCR
        images = convert_from_path(
            pdf_path,
            first_page=min(pages_needing_ocr) + 1,  # pdf2image uses 1-based indexing
            last_page=max(pages_needing_ocr) + 1
        )

        # Process pages in order, using OCR only when needed
        for i in range(pages_to_extract):
            if i in pages_needing_ocr:
                img_idx = pages_needing_ocr.index(i)
                _process_image_to_pdf(images[img_idx], writer)
            else:
                writer.add_page(reader.pages[i])

    # Create temp file with proper extension
    temp_file = Path(tempfile.mktemp(suffix='.pdf'))
    writer.write(temp_file)

    return temp_file

def _process_image_to_pdf(image: Image, writer: PdfWriter) -> None:
    """Helper to OCR an image and add it to the PDF writer"""
    # Perform OCR
    text = pytesseract.image_to_pdf_or_hocr(image, extension='pdf')

    # Convert bytes to PDF page and add to writer
    reader = PdfReader(io.BytesIO(text))
    writer.add_page(reader.pages[0])

def make_chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def estimate_llm_tokens(text: str) -> int:
    CHARS_PER_TOKEN = 4  # approximate
    return len(text) // CHARS_PER_TOKEN

def load_config(args):
    config = yaml.safe_load(AGENT_CONFIG.read_text())
    tool_cfg = config[args.tool]
    system_prompt = tool_cfg['system_prompt']
    model = tool_cfg.get('model', 'gpt-4')
    preprocess_fn = tool_cfg.get('preprocess_function', None)
    postprocess_fn = tool_cfg.get('postprocess_function', None)

    return system_prompt, model, preprocess_fn, postprocess_fn

def get_chunk_dir(args) -> Path:
    """Get the directory for storing chunk results."""
    chunk_dir = args.file_path.parent / f"{args.file_path.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)
    return chunk_dir

def get_chunk_path(chunk_dir: Path, chunk_index: int) -> Path:
    """Generate a path for saving a specific chunk result."""
    return chunk_dir / f"chunk_{chunk_index:04d}.txt"

def check_completed_chunks(args) -> str:
    """Check if all chunks are already processed and return combined result if so."""
    chunk_dir = get_chunk_dir(args)
    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
        return None

    total_chunks = json.loads(metadata_path.read_text())["total_chunks"]
    all_exist = all(get_chunk_path(chunk_dir, i).exists() for i in range(total_chunks))
    if all_exist:
        return '\n'.join(get_chunk_path(chunk_dir, i).read_text() for i in range(total_chunks))

    return None



def call_llm(args, chunk, verbose: bool = False) -> str:
    """Call the LLM with the given arguments and chunk."""
    if verbose:
        print(args.system_prompt)
        print(chunk)

    response = args.client.chat.completions.create(
        model=args.model,
        messages=[{"role": "system", "content": args.system_prompt}, {"role": "user", "content": "\n".join(chunk)}],
        timeout=300
    )

    return response.choices[0].message.content

def process_chunk(args, chunk, chunk_path:Path = None) -> str:
    """Process a single chunk with optional caching."""

    # Random delay between 0 and 2 seconds to avoid rate limiting
    time.sleep(random.uniform(0, 2))

    result = call_llm(args, chunk)

    # Save the result
    if chunk_path is not None:
        chunk_path.write_text(result)

    return result


def process_file_content(args) -> str:
    """Process content in chunks with fault tolerance."""
    lines = args.file_path.read_text().splitlines()
    total_lines = len(lines)

    if not lines:
        return ""

    chunks = list(make_chunks(lines, args.chunk_size))

    if len(chunks) == 1:
        return process_chunk(args, chunks[0])

    chunk_dir = get_chunk_dir(args)

    metadata = {
        "total_chunks": len(chunks),
        "lines_per_chunk": args.chunk_size,
        "total_lines": total_lines,
        "model": args.model,
        "timestamp": time.time(),
        "original_file": str(args.file_path)
    }

    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
         metadata_path.write_text(json.dumps(metadata, indent=2))

    helper = lambda i: (process_chunk(args, chunks[i], get_chunk_path(chunk_dir, i)))

    outputs = pmap(helper,
                  range(len(chunks)),
                  n_jobs=args.n_jobs,
                  prefer='threads',
                  desc=args.file_path.name,
                  )

    return '\n'.join(outputs)


def create_status_panel(files, current_file=None):
    """Create a status panel showing processed and pending files."""
    def get_file_status(file):
        if Path(f"{file}.bak").exists():
            return f"[green]✓ {file}[/]"  # Processed
        elif file == current_file:
            return f"[yellow]⋯ {file}[/]"  # Currently processing
        else:
            return f"[dim]• {file}[/]"     # Pending

    return Panel(
        Group(
            f"[bold]Processing {len(files)} files[/]",
            Columns(
                [get_file_status(file) for file in files],
                column_first=True,
                equal=True,
                expand=True
            ),
        ),
        padding=(0, 1)
    )

def create_system_prompt_panel(system_prompt):
    """Create a panel displaying the system prompt."""
    return Panel(
        f"[italic][cyan]{system_prompt}[/][/]",
        title="[bold]System Prompt[/]",
        border_style="green",
        padding=(1, 2)
    )

def create_combined_panel(global_args) -> Panel:
    # Load system prompt for the selected tool
    system_prompt, _ = load_config(global_args)

    return Panel(
        Group(
            # Arguments section
            Panel(
                Columns([
                    f"[bold]Tool:[/] [cyan]{global_args.tool}[/]",
                    f"[bold]Files:[/] [cyan]{len(global_args.files)} file(s)[/]",
                    f"[bold]In-place edit:[/] [{'green' if global_args.inplace else 'red'}]{global_args.inplace}[/]",
                    f"[bold]Parallel jobs:[/] [cyan]{global_args.n_jobs}[/]",
                    f"[bold]Chunk size:[/] [cyan]{global_args.chunk_size}[/]",
                    f"[bold]Clear backups:[/] [{'green' if global_args.clear_bkup else 'red'}]{global_args.clear_bkup}[/]",
                    f"[bold]API key:[/] [cyan]{global_args.api_key[:8]}...[/]"
                ], equal=True, expand=True),
                title="[bold]Arguments[/]",
                border_style="blue"
            ),
            # Files section
            create_status_panel(global_args.files),
            # System prompt section
            create_system_prompt_panel(system_prompt) if global_args.show_prompt else "",
        ),
        title="[bold]Processing Configuration[/]",
        border_style="cyan"
    )


