"""Node / Remotion environment: version check, one shared `npm ci`, per-clip workspace linking.

Cross-platform (macOS / Windows / Linux). Fails loud with per-OS install instructions.
The skill's own `remotion/` dir holds the ONE node_modules; each clip workspace links to it.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "remotion"
MIN_NODE_MAJOR = 18

NODE_INSTALL_HELP = {
    "Darwin": "brew install node   (or https://nodejs.org/en/download)",
    "Windows": "winget install OpenJS.NodeJS.LTS   (or https://nodejs.org/en/download)",
    "Linux": "use your package manager (e.g. apt install nodejs npm) or https://nodejs.org/en/download",
}


class RemotionEnvError(RuntimeError):
    pass


def parse_node_major(version_output: str) -> int:
    m = re.match(r"v?(\d+)\.", version_output.strip())
    if not m:
        raise RemotionEnvError(f"cannot parse node version from {version_output!r}")
    return int(m.group(1))


def tool(name: str) -> str:
    """Absolute path of node / npm / npx (resolves npx.cmd on Windows)."""
    path = shutil.which(name)
    if not path:
        how = NODE_INSTALL_HELP.get(platform.system(), NODE_INSTALL_HELP["Linux"])
        raise RemotionEnvError(f"`{name}` not found on PATH. Install Node.js >= {MIN_NODE_MAJOR}: {how}")
    return path


def check_node() -> str:
    proc = subprocess.run([tool("node"), "--version"], capture_output=True, text=True)
    major = parse_node_major(proc.stdout)
    if major < MIN_NODE_MAJOR:
        how = NODE_INSTALL_HELP.get(platform.system(), NODE_INSTALL_HELP["Linux"])
        raise RemotionEnvError(f"Node {proc.stdout.strip()} is too old; need >= {MIN_NODE_MAJOR}. {how}")
    return proc.stdout.strip()


def lock_hash(template: Path = TEMPLATE_DIR) -> str:
    return hashlib.sha256((template / "package-lock.json").read_bytes()).hexdigest()[:16]


def ensure_node_modules(template: Path = TEMPLATE_DIR) -> Path:
    """`npm ci` in the skill's remotion dir once (re-run when the lockfile changes)."""
    check_node()
    stamp, want = template / "node_modules" / ".lock-hash", lock_hash(template)
    if (template / "node_modules" / ".bin").exists() and stamp.exists() and stamp.read_text().strip() == want:
        return template / "node_modules"
    proc = subprocess.run([tool("npm"), "ci", "--no-audit", "--no-fund"], cwd=template, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
        raise RemotionEnvError(f"npm ci failed in {template} (exit {proc.returncode}):\n{tail}")
    stamp.write_text(want)
    return template / "node_modules"


def link_dir(link: Path, target: Path) -> None:
    """Make `link` point at directory `target`: symlink (POSIX) or junction (Windows, no admin needed)."""
    if link.is_symlink() or link.exists():
        if link.resolve() == target.resolve():
            return
        raise RemotionEnvError(f"{link} exists and is not a link to {target}; delete it and re-run")
    if platform.system() == "Windows":
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RemotionEnvError(f"mklink /J failed: {proc.stdout.strip()} {proc.stderr.strip()}")
    else:
        os.symlink(target, link, target_is_directory=True)
