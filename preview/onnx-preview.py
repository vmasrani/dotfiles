#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["onnx", "rich"]
# ///
import sys
from collections import Counter
from pathlib import Path

import onnx
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console(force_terminal=True)
path = Path(sys.argv[1])
model = onnx.load(path)
graph = model.graph

DTYPE_MAP = {
    1: "float32", 2: "uint8", 3: "int8", 4: "uint16", 5: "int16",
    6: "int32", 7: "int64", 9: "bool", 10: "float16", 11: "double",
    16: "bfloat16",
}


def shape_str(type_proto):
    tensor = type_proto.tensor_type
    if not tensor.HasField("shape"):
        return "scalar"
    dims = []
    for d in tensor.shape.dim:
        dims.append(str(d.dim_value) if d.dim_value > 0 else d.dim_param or "?")
    dtype = DTYPE_MAP.get(tensor.elem_type, f"type_{tensor.elem_type}")
    return f"{dtype}[{','.join(dims)}]"


# Header
console.print(f"[bold cyan]{path.name}[/] — ONNX Model")
opsets = ", ".join(f"{o.domain or 'ai.onnx'}:{o.version}" for o in model.opset_import)
console.print(f"  IR: v{model.ir_version}  Opset: {opsets}")
if model.producer_name:
    console.print(f"  Producer: {model.producer_name} {model.producer_version}")
console.print()

# Inputs / Outputs
io_table = Table(title="I/O", show_lines=False)
io_table.add_column("Direction", style="bold")
io_table.add_column("Name", style="white")
io_table.add_column("Type", style="green")
for inp in graph.input:
    io_table.add_row("→ in", inp.name, shape_str(inp.type))
for out in graph.output:
    io_table.add_row("← out", out.name, shape_str(out.type))
console.print(io_table)
console.print()

# Op breakdown
ops = Counter(n.op_type for n in graph.node)
console.print(f"[bold]Nodes:[/] {len(graph.node)}  |  Initializers: {len(graph.initializer)}")
op_table = Table(title="Op Distribution", show_lines=False)
op_table.add_column("Op", style="yellow")
op_table.add_column("Count", style="magenta", justify="right")
for op, count in ops.most_common(20):
    op_table.add_row(op, str(count))
console.print(op_table)
