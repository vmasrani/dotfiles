#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pandas", "pyarrow"]
# ///
import sys
import pyarrow as pa
import pyarrow.ipc as ipc

file_name = sys.argv[1]

# Arrow IPC comes in two flavors: file format (random-access) and stream
# format. Try file first, fall back to stream.
try:
    with pa.memory_map(file_name, "r") as source:
        table = ipc.open_file(source).read_all()
except (pa.ArrowInvalid, OSError):
    with pa.OSFile(file_name, "rb") as source:
        table = ipc.open_stream(source).read_all()

print(table.to_pandas())
