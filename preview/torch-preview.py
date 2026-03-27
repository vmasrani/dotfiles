#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["torch", "rich"]
# ///
import sys
from collections import OrderedDict
from pathlib import Path

import torch
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console(force_terminal=True)
path = Path(sys.argv[1])
obj = torch.load(path, map_location="cpu", weights_only=False)


def format_size(n):
    for unit in ["", "K", "M", "B"]:
        if abs(n) < 1000:
            return f"{n:.1f}{unit}" if unit else str(n)
        n /= 1000
    return f"{n:.1f}T"


def is_state_dict(obj):
    return isinstance(obj, (dict, OrderedDict)) and all(
        isinstance(v, torch.Tensor) for v in obj.values()
    )


def show_state_dict(sd):
    table = Table(title=f"[bold cyan]{path.name}[/] — state_dict ({len(sd)} tensors)", show_lines=False)
    table.add_column("Layer", style="white", no_wrap=True, max_width=60)
    table.add_column("Shape", style="green")
    table.add_column("Dtype", style="yellow")
    table.add_column("Params", style="magenta", justify="right")

    total = 0
    for name, tensor in sd.items():
        n = tensor.numel()
        total += n
        table.add_row(name, str(list(tensor.shape)), str(tensor.dtype).replace("torch.", ""), format_size(n))

    console.print(table)
    console.print(f"\n[bold]Total parameters:[/] {format_size(total)} ({total:,})")


def show_module(model):
    console.print(f"[bold cyan]{path.name}[/] — nn.Module\n")
    console.print(str(model))
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    console.print(f"\n[bold]Parameters:[/] {format_size(total)} total, {format_size(trainable)} trainable")


def show_tensor(t):
    console.print(f"[bold cyan]{path.name}[/] — Tensor")
    console.print(f"  Shape: [green]{list(t.shape)}[/]")
    console.print(f"  Dtype: [yellow]{t.dtype}[/]")
    console.print(f"  Device: {t.device}")
    if t.numel() <= 20:
        console.print(f"  Values: {t}")


def show_other(obj):
    console.print(f"[bold cyan]{path.name}[/] — {type(obj).__name__}")
    from rich.pretty import pretty_repr
    console.print(pretty_repr(obj, max_length=50, max_string=80))


if is_state_dict(obj):
    show_state_dict(obj)
elif isinstance(obj, torch.nn.Module):
    show_module(obj)
elif isinstance(obj, torch.Tensor):
    show_tensor(obj)
else:
    show_other(obj)
