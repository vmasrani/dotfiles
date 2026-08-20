#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import argparse
import os
import sys
from dotenv import load_dotenv
import traceback


def debug_print(enabled, message):
    if enabled:
        print(message, file=sys.stderr)


def mask_key(value):
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def prompt_llm(prompt_text, system_prompt=None, debug=False):
    """
    Base OpenAI LLM prompting method using fastest model.

    Args:
        prompt_text (str): The prompt to send to the model
        system_prompt (str): Optional system prompt content

    Returns:
        str: The model's response text, or None if error
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return None

    debug_print(
        debug,
        "OpenAI env: "
        f"OPENAI_API_KEY={mask_key(api_key)} "
        f"OPENAI_BASE_URL={os.getenv('OPENAI_BASE_URL')} "
        f"OPENAI_ORG={os.getenv('OPENAI_ORG')} "
        f"OPENAI_PROJECT={os.getenv('OPENAI_PROJECT')}",
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt_text})

        debug_print(
            debug,
            f"Request: model=gpt-5-nano messages={len(messages)} "
            f"system_chars={len(system_prompt) if system_prompt else 0} "
            f"user_chars={len(prompt_text) if prompt_text else 0} "
        )

        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # Fastest OpenAI model
            # model="gpt-5-nano",  # Fastest OpenAI model
            messages=messages,
        )

        if debug and response and response.choices:
            choice = response.choices[0]
            debug_print(
                debug,
                "Response: "
                f"finish_reason={getattr(choice, 'finish_reason', None)} "
                f"content_chars={len(choice.message.content) if choice.message and choice.message.content else 0}",
            )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error calling OpenAI API: {type(e).__name__}: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return None


def read_sysprompt(path):
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def read_env_int(name):
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def sanitize_text(text):
    if text is None:
        return None
    sanitized = []
    for ch in text:
        code = ord(ch)
        if ch in ("\n", "\t") or (code >= 32 and code != 127):
            sanitized.append(ch)
    return "".join(sanitized)


def truncate_text(text, max_chars):
    if max_chars is None or max_chars <= 0 or text is None:
        return text, False
    if len(text) <= max_chars:
        return text, False
    return text[-max_chars:], True



def main():
    """Command line interface for testing."""
    parser = argparse.ArgumentParser(
        description="OpenAI LLM helper",
        prog=os.path.basename(sys.argv[0]),
    )
    parser.add_argument(
        "-s",
        "--sysprompt",
        dest="sysprompt",
        help="Path to a system prompt file",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text to send",
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        help="Max chars to include from piped context (defaults to OAI_MAX_CONTEXT_CHARS).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug output.",
    )

    args = parser.parse_args()

    debug = args.debug or os.getenv("OAI_DEBUG") in ("1", "true", "TRUE", "yes", "YES")

    prompt_text = " ".join(args.prompt).strip()
    piped_text = None
    if not sys.stdin.isatty():
        piped_text = sys.stdin.read()
        if piped_text is not None:
            piped_text = sanitize_text(piped_text.rstrip())
        debug_print(
            debug,
            f"STDIN: isatty=False raw_chars={len(piped_text) if piped_text else 0}",
        )
    else:
        debug_print(debug, "STDIN: isatty=True")

    max_context_chars = args.max_context_chars
    if max_context_chars is None:
        max_context_chars = read_env_int("OAI_MAX_CONTEXT_CHARS")
    debug_print(debug, f"Context: max_context_chars={max_context_chars}")

    if piped_text:
        piped_text, truncated = truncate_text(piped_text, max_context_chars)
        if truncated:
            print(
                f"Context truncated to last {max_context_chars} characters.",
                file=sys.stderr,
            )
        debug_print(
            debug,
            f"Context: truncated={truncated} final_chars={len(piped_text)}",
        )
        if prompt_text:
            prompt_text = f"{prompt_text}\n\nContext:\n{piped_text}"
        else:
            prompt_text = piped_text
    debug_print(
        debug,
        f"Prompt: chars={len(prompt_text) if prompt_text else 0} "
        f"sysprompt_path={args.sysprompt}",
    )

    if not prompt_text:
        print("Usage: oai 'your prompt here' or echo 'text' | oai 'your prompt here' or oai --completion")
        return

    system_prompt = read_sysprompt(args.sysprompt)
    if args.sysprompt and system_prompt is None:
        print(f"Error reading system prompt file: {args.sysprompt}")
        return
    if args.sysprompt:
        debug_print(
            debug,
            f"System prompt: chars={len(system_prompt) if system_prompt else 0}",
        )

    response = prompt_llm(prompt_text, system_prompt=system_prompt, debug=debug)
    if response:
        print(response)
    else:
        print("Error calling OpenAI API")


if __name__ == "__main__":
    main()
