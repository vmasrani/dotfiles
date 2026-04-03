---
name: record-gif
description: Record terminal commands as polished GIFs using VHS. Use this skill whenever the user wants to capture terminal output as a GIF, record a CLI demo, create animated screenshots of command-line tools, make terminal recordings for READMEs, or says things like "record this as a gif", "make a gif of", "capture the terminal output", "demo gif", or "screen recording of the terminal". Also use when the user is building a README and needs terminal recordings, or when they want to show off CLI tool output visually.
---

# Record GIF

Record any terminal command as a polished, deterministic GIF using [VHS](https://github.com/charmbracelet/vhs).

## Prerequisites

VHS must be installed: `brew install vhs`

## How it works

The bundled script at `{skill-directory}/scripts/record.py` handles everything:

1. **Measures duration** — runs the command once to time it, so the recording length is always correct
2. **Generates a VHS tape** — creates a `.tape` file with sensible defaults (Catppuccin Mocha theme, 14pt font, proper padding)
3. **Runs VHS** — executes the tape to produce the GIF (and optionally MP4, WebM, or PNG frames)
4. **Cleans up** — removes the temporary tape file

## Quick start

```bash
uv run {skill-directory}/scripts/record.py "COMMAND" -o OUTPUT_PATH
```

## Script reference

### Core options

| Flag | Default | Description |
|------|---------|-------------|
| `command` | (required) | Shell command to record |
| `-o, --output` | (required) | Output path (.gif, .mp4, .webm, or .png) |

### Dimensions

| Flag | Default | Description |
|------|---------|-------------|
| `--width` | `900` | Terminal width in pixels |
| `--height` | `500` | Terminal height in pixels |
| `--font-size` | `14` | Font size |
| `--padding` | `20` | Padding around terminal content |

### Appearance

| Flag | Default | Description |
|------|---------|-------------|
| `--theme` | `"Catppuccin Mocha"` | VHS theme name |
| `--window-bar` | off | Add macOS-style window chrome: `Colorful`, `ColorfulRight`, `Rings`, `RingsRight` |
| `--window-bar-size` | `40` | Window bar height in pixels |
| `--no-cursor-blink` | false | Disable cursor blinking for cleaner recordings |

### Typing control

| Flag | Default | Description |
|------|---------|-------------|
| `--shell` | `zsh` | Shell to use |
| `--no-typing` | false | Skip typing animation — hides command, shows only output |
| `--typing-speed` | `30ms` | Per-character delay for typing animation |
| `--hide-setup` | false | Hide command typing + initial startup, show only when output begins |

### Setup and environment

| Flag | Default | Description |
|------|---------|-------------|
| `--setup` | — | Hidden command to run before recording (e.g. `'cd project && source .env'`) |
| `--env KEY=VALUE` | — | Set environment variables (repeatable) |
| `--source TAPE` | — | Include another tape file for shared settings (repeatable) |

### Timing

| Flag | Default | Description |
|------|---------|-------------|
| `--framerate` | `30` | GIF framerate |
| `--duration` | auto | Override measured duration in seconds (skips the dry run) |

### Screenshot mode

| Flag | Default | Description |
|------|---------|-------------|
| `--screenshot-at SECONDS` | — | Capture a single PNG frame at this timestamp instead of a GIF |

This is useful for grabbing a hero image at the exact moment the UI looks best (e.g., a Rich panel at 60% progress). Skips the duration measurement since it only needs to wait until the screenshot moment.

### Multiple outputs

| Flag | Default | Description |
|------|---------|-------------|
| `--also-mp4` | false | Also produce an MP4 alongside the primary output |
| `--also-webm` | false | Also produce a WebM alongside the primary output |
| `--also-frames DIR` | — | Also output individual PNG frames to a directory |

A single recording run can produce several formats at once. The frames output is useful for picking the best single frame for a static image.

### Tape control

| Flag | Default | Description |
|------|---------|-------------|
| `--tape-only` | false | Print the generated tape to stdout without running VHS |
| `--save-tape PATH` | — | Save the generated tape file for manual editing |

## Examples

### Basic recording

```bash
# Record a Python script
uv run {skill-directory}/scripts/record.py "uv run demo/simple_bar.py" -o screenshots/simple-bar.gif

# Any shell command
uv run {skill-directory}/scripts/record.py "ls --color -la" -o screenshots/ls.gif
```

### Polished output with window chrome

```bash
# macOS-style title bar + no cursor blink = clean README hero image
uv run {skill-directory}/scripts/record.py "uv run demo/job_bars.py" \
  -o screenshots/job-bars.gif \
  --window-bar Colorful \
  --no-cursor-blink \
  --height 700
```

### Hide boring setup

```bash
# Skip command typing — recording starts when output appears
uv run {skill-directory}/scripts/record.py "uv run demo/simple_bar.py" \
  -o demo.gif --hide-setup

# Run hidden setup command first (activate venv, cd, etc.)
uv run {skill-directory}/scripts/record.py "python train.py" \
  -o demo.gif --setup "cd ~/project && source .venv/bin/activate"
```

### Screenshot at a specific moment

```bash
# Grab a PNG when the Rich panel is at peak visual interest
uv run {skill-directory}/scripts/record.py "uv run demo/job_bars.py" \
  -o screenshots/hero.png --screenshot-at 3
```

### Multiple output formats

```bash
# GIF for README + MP4 for docs site + individual frames to cherry-pick
uv run {skill-directory}/scripts/record.py "uv run demo/demo.py" \
  -o screenshots/demo.gif --also-mp4 --also-frames screenshots/frames/
```

### Environment control

```bash
# Force terminal width and disable colors
uv run {skill-directory}/scripts/record.py "python report.py" \
  -o report.gif --env COLUMNS=120 --env NO_COLOR=1
```

### Shared base tape

```bash
# Use a base tape with common settings, extend it for a specific command
uv run {skill-directory}/scripts/record.py "make test" \
  -o test.gif --source demo/base.tape
```

### Generate tape for manual editing

```bash
# Save the tape, tweak it by hand, then run with vhs directly
uv run {skill-directory}/scripts/record.py "python demo.py" \
  -o demo.gif --save-tape demo/demo.tape --tape-only

# Edit demo/demo.tape to add interactive keystrokes, then:
vhs demo/demo.tape
```

### Batch recording

```bash
for script in demo/*.py; do
    name=$(basename "$script" .py)
    uv run {skill-directory}/scripts/record.py "uv run $script" \
      -o "screenshots/${name}.gif" --window-bar Colorful --no-cursor-blink
done
```

## Choosing dimensions

| Use case | Recommended flags |
|----------|-------------------|
| Simple progress bar | `--width 900 --height 400` |
| Rich panel / job bars | `--width 900 --height 700` |
| Log output | `--width 900 --height 500` (default) |
| Full-screen TUI | `--width 1280 --height 800` |
| Wide table output | `--width 1200 --height 500` |

## Available themes

Common: `Catppuccin Mocha`, `Dracula`, `GitHub Dark`, `One Dark`, `Monokai`, `Nord`, `Tokyo Night`, `Solarized Dark`.

Run `vhs themes` for the full list.

---

## Advanced: Writing tape files by hand

The script covers most use cases, but for complex interactive demos, write a `.tape` file directly and run `vhs demo.tape`. This section documents VHS tape syntax beyond what the script generates.

### Interactive keystrokes

VHS can simulate any key sequence — useful for recording interactive workflows:

```tape
Type "python"
Enter
Sleep 500ms
Type "from pmap import pmap"
Enter
Type "pmap(lambda x: x**2, range(10))"
Enter
Sleep 3s
Ctrl+D
```

Available keys: `Enter`, `Tab`, `Escape`, `Backspace`, `Up`, `Down`, `Left`, `Right`, `Ctrl+C`, `Ctrl+L`, `Ctrl+R`, `Ctrl+D`, `Alt+.`, `Space`, `Delete`, `Home`, `End`, `PageUp`, `PageDown`.

### The `@` multiplier

Most commands support `@N` for repetition or timing overrides:

```tape
Type@100ms "slow dramatic typing"       # override typing speed for this line
Type@10ms "blazing fast"                # different speed
Enter@3                                  # press Enter 3 times
Backspace@15                             # delete 15 characters
Sleep@0.5 500ms                          # sleep 250ms (0.5 × 500ms)
```

### Hide/Show for selective recording

Suppress any part of the recording — setup, boring waits, cleanup:

```tape
Hide
Type "pip install -q some-package"
Enter
Sleep 5s
Show
# Recording resumes here — viewer never sees the install
Type "python demo.py"
Enter
Sleep 3s
```

### Source (compose tapes)

Factor common settings into a shared tape:

```tape
# base.tape
Set Shell zsh
Set FontSize 14
Set Width 900
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set CursorBlink false
```

```tape
# demo.tape
Source "base.tape"
Output screenshots/demo.gif
Type "python demo.py"
Enter
Sleep 5s
```

### Screenshot mid-recording

Capture a single frame at a specific moment without stopping the GIF:

```tape
Output demo.gif
Type "python train.py"
Enter
Sleep 3s
Screenshot screenshots/hero.png    # grab a frame here
Sleep 5s                            # GIF continues
```

### All Set options

| Setting | Example | Description |
|---------|---------|-------------|
| `Shell` | `Set Shell zsh` | Shell interpreter |
| `FontSize` | `Set FontSize 14` | Font size in pixels |
| `FontFamily` | `Set FontFamily "JetBrains Mono"` | Font face |
| `Width` | `Set Width 900` | Terminal width in pixels |
| `Height` | `Set Height 500` | Terminal height in pixels |
| `Theme` | `Set Theme "Dracula"` | Color theme |
| `Padding` | `Set Padding 20` | Margin around content |
| `Framerate` | `Set Framerate 30` | Output framerate |
| `TypingSpeed` | `Set TypingSpeed 50ms` | Default typing delay |
| `WindowBar` | `Set WindowBar Colorful` | Window chrome style |
| `WindowBarSize` | `Set WindowBarSize 40` | Chrome height |
| `CursorBlink` | `Set CursorBlink false` | Toggle cursor blink |
| `Env` | `Set Env "NO_COLOR" "1"` | Environment variable |
| `LetterSpacing` | `Set LetterSpacing 1` | Character spacing |
| `LineHeight` | `Set LineHeight 1.2` | Line spacing |
