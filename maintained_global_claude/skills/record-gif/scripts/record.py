#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generate a VHS tape file and record a terminal command as a GIF.

Usage:
    uv run record.py "uv run demo/simple_bar.py" -o screenshots/simple-bar.gif
    uv run record.py "python train.py" -o demo.gif --theme "Catppuccin Mocha" --width 1000
    uv run record.py "ls --color" -o ls.gif --padding 40 --no-typing
    uv run record.py "uv run demo/job_bars.py" -o demo.gif --window-bar Colorful --hide-setup
    uv run record.py "uv run demo/job_bars.py" -o hero.png --screenshot-at 3
    uv run record.py "uv run demo/demo.py" -o demo.gif --also-mp4 --also-frames frames/
    uv run record.py "uv run demo/demo.py" -o demo.gif --setup "source .env && cd project"
    uv run record.py "uv run demo/demo.py" -o demo.gif --env COLUMNS=120 --env NO_COLOR=1
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def measure_duration(command: str, shell: str = "zsh") -> float:
    """Run the command once to measure how long it takes."""
    print(f"Measuring duration: {command}")
    start = time.monotonic()
    result = subprocess.run(command, shell=True, executable=f"/bin/{shell}")
    elapsed = time.monotonic() - start
    if result.returncode != 0:
        print(f"Warning: command exited with code {result.returncode}", file=sys.stderr)
    print(f"Command took {elapsed:.1f}s")
    return elapsed


def generate_tape(
    command: str,
    output_path: str,
    duration_seconds: float,
    width: int = 900,
    height: int = 500,
    font_size: int = 14,
    theme: str = "Catppuccin Mocha",
    padding: int = 20,
    shell: str = "zsh",
    typing: bool = True,
    typing_speed: str = "30ms",
    framerate: int = 30,
    window_bar: str | None = None,
    window_bar_size: int = 40,
    cursor_blink: bool = True,
    hide_setup: bool = False,
    setup_command: str | None = None,
    screenshot_at: float | None = None,
    extra_outputs: list[str] | None = None,
    source_tapes: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
) -> str:
    """Generate a VHS tape file as a string."""
    lines = [f'Output "{output_path}"']
    lines.extend(f'Output "{extra}"' for extra in (extra_outputs or []))

    # Source included tapes
    lines.extend(f'Source "{source}"' for source in (source_tapes or []))

    lines.extend(
        (
            "",
            f"Set Shell {shell}",
            f"Set FontSize {font_size}",
            f"Set Width {width}",
            f"Set Height {height}",
            f'Set Theme "{theme}"',
            f"Set Padding {padding}",
            f"Set Framerate {framerate}",
        )
    )
    if window_bar:
        lines.extend(
            (
                f"Set WindowBar {window_bar}",
                f"Set WindowBarSize {window_bar_size}",
            )
        )
    if not cursor_blink:
        lines.append("Set CursorBlink false")

    # Environment variables
    lines.extend(f'Set Env "{key}" "{value}"' for key, value in (env_vars or {}).items())

    lines.append("")

    # Hidden setup command (runs before recording starts)
    if setup_command:
        lines.extend(("Hide", f'Type "{setup_command}"', "Enter", "Sleep 1s", "Show", ""))

    # Main command
    if typing and not hide_setup:
        lines.extend((f"Set TypingSpeed {typing_speed}", "", f'Type "{command}"', "Enter"))
    elif hide_setup:
        # Hide the typing + initial startup, show only the output
        lines.extend(("Hide", f'Type "{command}"', "Enter", "Sleep 1s", "Show"))
    else:
        # No typing animation — just run the command immediately
        lines.extend(("", "Hide", f'Type "{command}"', "Enter", "Sleep 500ms", "Show"))

    # Screenshot mode: sleep until the right moment, take screenshot, done
    if screenshot_at is not None:
        lines.extend((f"Sleep {screenshot_at:.1f}s", f'Screenshot "{output_path}"'))
    else:
        # Add buffer: 2s + 20% of measured time, minimum 3s total
        sleep_seconds = max(3, duration_seconds * 1.2 + 2)

        lines.append(f"Sleep {sleep_seconds:.0f}s")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Record a terminal command as a GIF via VHS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "uv run demo.py" -o demo.gif
  %(prog)s "python train.py" -o demo.gif --window-bar Colorful
  %(prog)s "make test" -o test.gif --hide-setup --no-cursor-blink
  %(prog)s "uv run demo.py" -o hero.png --screenshot-at 3
  %(prog)s "uv run demo.py" -o demo.gif --also-mp4 --also-frames frames/
  %(prog)s "uv run demo.py" -o demo.gif --setup "cd project && source .env"
  %(prog)s "uv run demo.py" -o demo.gif --env COLUMNS=120 --env NO_COLOR=1
  %(prog)s "uv run demo.py" -o demo.gif --source base.tape
        """,
    )

    # Core
    parser.add_argument("command", help="Shell command to record")
    parser.add_argument("-o", "--output", required=True, help="Output path (.gif, .mp4, .webm, or .png for screenshot)")

    # Dimensions
    parser.add_argument("--width", type=int, default=900, help="Terminal width in pixels (default: 900)")
    parser.add_argument("--height", type=int, default=500, help="Terminal height in pixels (default: 500)")
    parser.add_argument("--font-size", type=int, default=14, help="Font size (default: 14)")
    parser.add_argument("--padding", type=int, default=20, help="Padding in pixels (default: 20)")

    # Appearance
    parser.add_argument("--theme", default="Catppuccin Mocha", help='VHS theme (default: "Catppuccin Mocha")')
    parser.add_argument("--window-bar", choices=["Colorful", "ColorfulRight", "Rings", "RingsRight"],
                        help="Add macOS-style window chrome to the recording")
    parser.add_argument("--window-bar-size", type=int, default=40, help="Window bar height in pixels (default: 40)")
    parser.add_argument("--no-cursor-blink", action="store_true", help="Disable cursor blinking")

    # Typing
    parser.add_argument("--shell", default="zsh", help="Shell to use (default: zsh)")
    parser.add_argument("--no-typing", action="store_true", help="Skip the typing animation, just show output")
    parser.add_argument("--typing-speed", default="30ms", help="Typing speed (default: 30ms)")
    parser.add_argument("--hide-setup", action="store_true",
                        help="Hide the command typing and initial startup — recording starts when output appears")

    # Setup
    parser.add_argument("--setup", dest="setup_command",
                        help="Hidden setup command to run before recording (e.g. 'cd project && source .env')")
    parser.add_argument("--env", action="append", dest="env_vars", metavar="KEY=VALUE",
                        help="Set environment variable (repeatable, e.g. --env COLUMNS=120 --env NO_COLOR=1)")
    parser.add_argument("--source", action="append", dest="source_tapes", metavar="TAPE",
                        help="Include another tape file (repeatable, e.g. --source base.tape)")

    # Timing
    parser.add_argument("--framerate", type=int, default=30, help="GIF framerate (default: 30)")
    parser.add_argument("--duration", type=float, default=None,
                        help="Override duration in seconds (skip measuring)")

    # Screenshot mode
    parser.add_argument("--screenshot-at", type=float, metavar="SECONDS",
                        help="Capture a single PNG frame at this many seconds instead of recording a GIF")

    # Extra outputs
    parser.add_argument("--also-mp4", action="store_true", help="Also output an MP4 alongside the primary output")
    parser.add_argument("--also-webm", action="store_true", help="Also output a WebM alongside the primary output")
    parser.add_argument("--also-frames", metavar="DIR",
                        help="Also output individual PNG frames to this directory")

    # Tape control
    parser.add_argument("--tape-only", action="store_true", help="Only print the tape file, don't run VHS")
    parser.add_argument("--save-tape", help="Save the generated tape file to this path")

    args = parser.parse_args()

    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Parse env vars
    env_dict = {}
    for item in (args.env_vars or []):
        key, _, value = item.partition("=")
        env_dict[key] = value

    # Build extra outputs list
    extra_outputs = []
    stem = Path(args.output).stem
    out_dir = str(Path(args.output).parent)
    if args.also_mp4:
        extra_outputs.append(f"{out_dir}/{stem}.mp4")
    if args.also_webm:
        extra_outputs.append(f"{out_dir}/{stem}.webm")
    if args.also_frames:
        Path(args.also_frames).mkdir(parents=True, exist_ok=True)
        extra_outputs.append(f"{args.also_frames}/")

    # Measure or use provided duration
    if args.duration is not None:
        duration = args.duration
    elif args.screenshot_at is not None:
        duration = args.screenshot_at
    else:
        duration = measure_duration(args.command, args.shell)

    # Generate tape
    tape_content = generate_tape(
        command=args.command,
        output_path=args.output,
        duration_seconds=duration,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
        theme=args.theme,
        padding=args.padding,
        shell=args.shell,
        typing=not args.no_typing,
        typing_speed=args.typing_speed,
        framerate=args.framerate,
        window_bar=args.window_bar,
        window_bar_size=args.window_bar_size,
        cursor_blink=not args.no_cursor_blink,
        hide_setup=args.hide_setup,
        setup_command=args.setup_command,
        screenshot_at=args.screenshot_at,
        extra_outputs=extra_outputs,
        source_tapes=args.source_tapes or [],
        env_vars=env_dict,
    )

    # Save tape if requested
    if args.save_tape:
        Path(args.save_tape).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_tape).write_text(tape_content)
        print(f"Tape saved to {args.save_tape}")

    if args.tape_only:
        print(tape_content)
        return

    # Write temp tape and run VHS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tape", delete=False) as f:
        f.write(tape_content)
        tape_path = f.name

    try:
        print(f"Recording to {args.output}...")
        subprocess.run(["vhs", tape_path], check=True)
        print(f"Done! Saved to {args.output}")
        for extra in extra_outputs:
            print(f"  + {extra}")
    finally:
        Path(tape_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
