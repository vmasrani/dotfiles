#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "dspy",
#     "python-dotenv",
#     "typer",
# ]
# ///

import os
import sys
from pathlib import Path
from typing import Optional

import dspy
import typer
from dotenv import load_dotenv

app = typer.Typer()


def sanitize_text(text: Optional[str]) -> Optional[str]:
    return None if text is None else "".join([ch for ch in text if ch in ("\n", "\t") or (32 <= ord(ch) != 127)])


def truncate_text(text: Optional[str], max_chars: Optional[int]) -> tuple[Optional[str], bool]:
    if max_chars is None or max_chars <= 0 or text is None or len(text) <= max_chars:
        return text, False
    return text[-max_chars:], True


def read_sysprompt(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8") if Path(path).exists() else None


def read_env_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if not value:
        return None
    return int(value) if value.isdigit() else None


def prompt_llm(prompt_text: str, system_prompt: Optional[str] = None) -> Optional[str]:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        typer.echo("OPENAI_API_KEY is not set.", err=True)
        return None

    lm = dspy.LM("openai/gpt-4.1-nano", api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt_text})

    response = lm(messages=messages)

    if isinstance(response, list):
        result = response[0] if response else ""
        return result.strip()
    elif isinstance(response, str):
        return response.strip()
    else:
        result = response.choices[0].message.content
        return result.strip()


@app.command()
def main(
    prompt: list[str] = typer.Argument(None, help="Prompt text to send"),
    sysprompt: Optional[str] = typer.Option(None, "-s", "--sysprompt", help="Path to a system prompt file"),
    max_context_chars: Optional[int] = typer.Option(None, "--max-context-chars", help="Max chars from piped context"),
) -> None:
    """OpenAI LLM helper using DSPy"""

    prompt_text = " ".join(prompt).strip() if prompt else ""
    piped_text = None

    if not sys.stdin.isatty():
        piped_text = sanitize_text(sys.stdin.read().rstrip())

    max_chars = max_context_chars or read_env_int("OAI_MAX_CONTEXT_CHARS")

    if piped_text:
        piped_text, truncated = truncate_text(piped_text, max_chars)
        if truncated:
            typer.echo(f"Context truncated to last {max_chars} characters.", err=True)
        prompt_text = f"{prompt_text}\n\nContext:\n{piped_text}" if prompt_text else piped_text

    if not prompt_text:
        typer.echo("Usage: oai 'your prompt here' or echo 'text' | oai 'your prompt here'")
        raise typer.Exit(1)

    system_prompt = read_sysprompt(sysprompt)
    if sysprompt and system_prompt is None:
        typer.echo(f"Error reading system prompt file: {sysprompt}", err=True)
        raise typer.Exit(1)

    response = prompt_llm(prompt_text, system_prompt=system_prompt)
    if response:
        typer.echo(response)
    else:
        typer.echo("Error calling OpenAI API", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()



