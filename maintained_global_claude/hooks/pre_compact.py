#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import os
import sys
from datetime import datetime
from pathlib import Path

MAX_SNAPSHOTS = 5


def main():
    input_data = json.load(sys.stdin)

    session_id = input_data.get("session_id", "unknown")
    cwd = input_data.get("cwd", os.getcwd())

    log_dir = Path(cwd) / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    snapshot = f"""## Compact Snapshot

- **Timestamp:** {datetime.now().isoformat()}
- **Working Directory:** {cwd}
- **Session ID:** {session_id}

---
"""

    summary_path = log_dir / "compact_summary.md"

    existing = ""
    if summary_path.exists():
        existing = summary_path.read_text()

    sections = [s for s in existing.split("## Compact Snapshot") if s.strip()]
    sections.append(snapshot.split("## Compact Snapshot", 1)[1])
    sections = sections[-MAX_SNAPSHOTS:]

    summary_path.write_text("".join(f"## Compact Snapshot{s}" for s in sections))
    sys.exit(0)


if __name__ == "__main__":
    main()
