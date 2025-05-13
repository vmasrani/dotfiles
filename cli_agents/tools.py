from pathlib import Path

import sys
import types
from cyclopts.types import PositiveInt, ExistingFile

from markitdown import MarkItDown
import tempfile

from agent_utils import save_first_n_pages
md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
MAX_CHARS = 1500*10

def to_markdown(file_path_str: str, **kwargs) -> str:
    if file_path_str.endswith(".pdf"):
        temp_file = save_first_n_pages(file_path_str, **kwargs)
        result = md.convert(temp_file)
    else:
        result = md.convert(file_path_str)

    return result.text_content[:MAX_CHARS]


def save_overwriting_original(args) -> None:
    old_file_path = Path(args.stdin)
    new_file_path = args.result + old_file_path.suffix
    new_file_path = Path(new_file_path)
    old_file_path = Path(old_file_path)
    new_file_path.write_bytes(old_file_path.read_bytes())
    bkup_file_path = old_file_path.with_name(f"bkup_{old_file_path.name}")
    old_file_path.replace(bkup_file_path)
    return new_file_path


PROCESS_FUNCTIONS = {
    name: obj for name, obj in vars(sys.modules[__name__]).items()
    if isinstance(obj, types.FunctionType) and not name.startswith('_')
}
