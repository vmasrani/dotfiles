#!/usr/bin/env bash
set -euo pipefail

# Installs a current htop. macOS gets it from Homebrew (whose bottle carries
# the Darwin backend); Linux builds from source into ~/bin so servers get a
# newer htop than whatever's in apt. Idempotent: skips work that's already done.
#
# Runnable standalone (`bash install/install_htop.sh`) or wired into setup.sh
# via `install_if_missing htop install_htop` (see install/install_functions.sh).

source "$HOME/dotfiles/shell/helper_functions.sh"
source "$HOME/dotfiles/shell/gum_utils.sh"

_install_htop_mac() {
	if brew list htop &>/dev/null; then
		gum_dim "htop already installed via Homebrew; checking for an update..."
		if brew upgrade htop; then
			gum_success "htop upgraded via Homebrew."
		else
			gum_dim "htop already at the latest Homebrew version."
		fi
	else
		gum_info "Installing htop via Homebrew..."
		brew install htop
		gum_success "htop installed via Homebrew."
	fi
}

_install_htop_linux() {
	local htop_dir="$HOME/bin/htop_src"
	local prefix_dir="$HOME"
	local installed_bin="$HOME/bin/htop"

	if [ -d "$htop_dir/.git" ]; then
		gum_dim "Updating existing htop source checkout..."
		git -C "$htop_dir" fetch --tags --quiet
		git -C "$htop_dir" pull --ff-only --quiet
	else
		gum_info "Cloning htop source..."
		mkdir -p "$htop_dir"
		git clone --quiet https://github.com/htop-dev/htop.git "$htop_dir"
	fi

	local git_ref
	git_ref=$(git -C "$htop_dir" describe --abbrev=7 --dirty --always --tags 2>/dev/null || git -C "$htop_dir" rev-parse --short=7 HEAD)

	local built_version=""
	if [ -x "$installed_bin" ]; then
		built_version=$("$installed_bin" --version 2>/dev/null || true)
	fi

	if [[ -n "$built_version" && "$built_version" == *"$git_ref"* ]]; then
		gum_dim "htop already built at $git_ref ($installed_bin) — skipping rebuild."
		return 0
	fi

	gum_info "Installing htop build dependencies..."
	sudo apt-get update
	sudo apt-get install -y build-essential autoconf automake libncurses-dev pkg-config git

	gum_info "Building htop ($git_ref)..."
	(
		cd "$htop_dir"
		make clean >/dev/null 2>&1 || true
		./autogen.sh
		./configure --prefix="$prefix_dir"
		make -j"$(nproc)"
		make install prefix="$prefix_dir"
	)

	gum_success "htop built and installed to $installed_bin ($git_ref)."
}

install_htop() {
	if [[ "$OSTYPE" == "darwin"* ]]; then
		_install_htop_mac
	else
		_install_htop_linux
	fi
}

# Allow `bash install/install_htop.sh` (or `./install/install_htop.sh`) to run directly,
# while also letting setup.sh source this file and call install_htop() itself.
if [[ "${BASH_SOURCE[0]:-$0}" == "${0}" ]]; then
	install_htop
fi
