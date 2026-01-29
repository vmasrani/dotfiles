Create a parallel processing pipeline following the established pattern. The pipeline consists of three files:

1. **Worker script** (`worker.py`) — a standalone `uv run` script that:
   - Takes a single item identifier as a CLI argument
   - Supports `--skip-existing` to skip already-processed items
   - Calls the OpenAI API (model `gpt-5.2`) with a system prompt loaded from a separate file
   - Adds random jitter (`time.sleep(random.uniform(0.5, 5))`) before the API call
   - Saves the result as JSON to a `results/` subdirectory
   - Uses inline script dependencies: `openai`

2. **Runner script** (`run.py`) — a standalone `uv run` script that:
   - Discovers all items to process
   - Filters out items that already have results in `results/`
   - Prints progress: total, already done, pending
   - Uses `pmap` from `mlh.parallel` to call the worker via `subprocess.run(["uv", "run", "worker.py", item_id, "--skip-existing"])`
   - Uses `n_jobs=50, prefer="threads"`
   - Uses inline script dependencies: `machine-learning-helpers` (from git), `rich`

3. **System prompt** (`system_prompt.md`) — a markdown file containing the LLM instructions

Key conventions:
- All scripts use the `#!/usr/bin/env -S uv run --script` shebang with inline PEP 723 metadata
- All scripts use `pathlib.Path` for file paths
- The worker is fully self-contained and callable independently
- Results are saved as individual JSON files for fault tolerance
- The runner skips completed work, making re-runs safe
- Use `rich` for printing in the runner, standard `print` in the worker

Ask the user what task they want to parallelize, then create the three files accordingly.