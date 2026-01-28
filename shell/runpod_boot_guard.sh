#!/bin/bash
# shellcheck shell=bash
# RunPod boot guard: re-establish /root -> /workspace/home bridge on every new shell.
# Sourced from .zshrc / .bashrc only when /workspace/home exists (no-op otherwise).

_BOOT_GUARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
_BOOT_GUARD_DOTFILES="$(dirname "$_BOOT_GUARD_DIR")"

source "$_BOOT_GUARD_DOTFILES/install/runpod_functions.sh"
bridge_root_to_workspace 2>/dev/null
