#!/bin/bash
# shellcheck shell=bash

source "$HOME/dotfiles/shell/helper_functions.sh"
source "$HOME/dotfiles/shell/gum_utils.sh"


# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="mac"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
else
    gum_error "Unsupported operating system: $OSTYPE"
    exit 1
fi


install_on_brew_or_mac() {
    local linux_package=$1
    local mac_package=${2:-$1}  # Use first arg if second not provided

    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt -y install "$linux_package"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install "$mac_package"
    fi
}


install_if_missing() {
    local command_name=$1
    local install_function=$2

    if ! command_exists "$command_name"; then
        gum_dim "$command_name is not installed. Installing $command_name..."
        $install_function
        gum_success "$command_name installed successfully."
    else
        gum_dim "$command_name is already installed."
    fi
}

install_if_dir_missing() {
    local dir_path=$1
    local install_function=$2

    if [ ! -d "$dir_path" ]; then
        gum_dim "Directory $dir_path does not exist. Installing..."
        $install_function
        gum_success "Installation completed successfully."
    else
        gum_dim "$dir_path is already installed."
    fi
}

install_dotfiles() {

    mkdir -p "$HOME"/bin
    mkdir -p "$HOME/dev/projects"
    mkdir -p "$HOME/.config/helix"
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.claude"
    mkdir -p "$HOME/.codex"
    # chmod bash files
    find $HOME/dotfiles -name "*.sh" -type f -exec chmod +x {} \;
    touch $HOME/dotfiles/local/.local_env.sh

    gum_dim "Creating symbolic links..."

  # Define base paths
    local dotfiles="$HOME/dotfiles"
    local bin="$HOME/bin"
    local home="$HOME"

    # Ensure Dracula tmux plugin directory exists so we can symlink our custom scripts into it.
    # We ensure TPM exists first since `install_plugins` lives under it.
    local tpm_dir="$HOME/.tmux/plugins/tpm"
    local dracula_plugin="$HOME/.tmux/plugins/tmux"
    local tmux_scripts="$dracula_plugin/scripts"

    # Targets we always want to match the repo source (delete existing non-matching
    # file/dir and re-symlink). This keeps setup idempotent for Claude/Codex config.
    declare -a force_replace_targets=(
        "$home/.claude/commands"
        "$home/.claude/hooks"
        "$home/.claude/skills"
        "$home/.claude/plugins"
        "$home/.claude/CLAUDE.md"
        "$home/.claude/settings.json"
        "$home/.codex/config.toml"
    )

    if [ ! -d "$tpm_dir" ]; then
        gum_info "Installing tmux plugin manager (tpm)..."
        install_tpm
    fi

    if [ ! -d "$dracula_plugin" ]; then
        gum_info "Installing tmux plugins (including Dracula theme)..."
        "$tpm_dir/bin/install_plugins"
    fi

    mkdir -p "$tmux_scripts"

    array_contains() {
        local needle="$1"
        shift
        for item in "$@"; do
            if [[ "$item" == "$needle" ]]; then
                return 0
            fi
        done
        return 1
    }

    should_force_link() {
        local target="$1"
        if [[ "$target" == "$tmux_scripts/"* ]]; then
            return 0
        fi
        if array_contains "$target" "${force_replace_targets[@]}"; then
            return 0
        fi
        return 1
    }

    ensure_symlink() {
        local source="$1"
        local target="$2"
        local force_link="$3"

        # Check if target already exists and points to the correct source
        if [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$source")" ]; then
            gum_dim "Symlink already exists: $(basename "$source") -> $target"
            return 0
        fi

        gum_info "Linking $(basename "$source") to $target"

        if [[ "$force_link" == "true" ]]; then
            if [ -e "$target" ] || [ -L "$target" ]; then
                gum_warning "Replacing existing path at $target (will re-symlink to $source)"
                rm -rf "$target"
            fi
            ln -sf "$source" "$target"
            return 0
        fi

        # Only remove if it's a broken symlink
        if [ -L "$target" ] && [ ! -e "$target" ]; then
            rm -f "$target"
        fi

        # Create symlink only if target doesn't exist
        if [ ! -e "$target" ]; then
            ln -sf "$source" "$target"
            return 0
        fi

        gum_warning "Warning: $target already exists and is not a symlink to $source"
    }

    # Create an array of source:target pairs
    declare -a file_pairs=(
        # Symlink entire tools directory to $HOME
        "$dotfiles/tools:$home/tools"

        # Preview files
        "$dotfiles/preview/fzf-preview.sh:$bin/fzf-preview"
        "$dotfiles/preview/torch-preview.sh:$bin/torch-preview"
        "$dotfiles/preview/npy-preview.py:$bin/npy-preview"
        "$dotfiles/preview/feather-preview.py:$bin/feather-preview"
        "$dotfiles/preview/pkl-preview.py:$bin/pkl-preview"

        # editor dotfiles
        "$dotfiles/tmux/.tmux.conf:$home/.tmux.conf"
        "$dotfiles/editors/.vimrc:$home/.vimrc"

        # tmux scripts (Dracula plugin)
        "$dotfiles/tmux/scripts/dracula.sh:$tmux_scripts/dracula.sh"
        "$dotfiles/tmux/scripts/pm2_status.sh:$tmux_scripts/pm2_status.sh"
        "$dotfiles/tmux/scripts/pm2_status_wrapper.sh:$tmux_scripts/pm2_status_wrapper.sh"

        # linters dotfiles
        "$dotfiles/linters/.pylintrc:$home/.pylintrc"
        "$dotfiles/linters/.sourcery.yaml:$home/.sourcery.yaml"

        # Shell dotfiles
        "$dotfiles/fzf/.fzf-config.zsh:$home/.fzf-config.zsh"
        "$dotfiles/fzf/.fzf.bash:$home/.fzf.bash"
        "$dotfiles/fzf/.fzf.zsh:$home/.fzf.zsh"
        "$dotfiles/fzf/.fzf-env.zsh:$home/.fzf-env.zsh"


        # Shell dotfiles
        "$dotfiles/shell/.p10k.zsh:$home/.p10k.zsh"
        "$dotfiles/shell/.aliases-and-envs.zsh:$home/.aliases-and-envs.zsh"
        "$dotfiles/shell/.paths.zsh:$home/.paths.zsh"
        "$dotfiles/shell/.bash_logout:$home/.bash_logout"
        "$dotfiles/shell/.bash_profile:$home/.bash_profile"
        "$dotfiles/shell/.bashrc:$home/.bashrc"
        "$dotfiles/shell/.zlogin:$home/.zlogin"
        "$dotfiles/shell/.zlogout:$home/.zlogout"
        "$dotfiles/shell/.zpreztorc:$home/.zpreztorc"
        "$dotfiles/shell/.zprofile:$home/.zprofile"
        "$dotfiles/shell/.profile:$home/.profile"
        "$dotfiles/shell/.zshenv:$home/.zshenv"
        "$dotfiles/shell/.zshrc:$home/.zshrc"
        "$dotfiles/shell/lscolors.sh:$home/lscolors.sh"
        "$dotfiles/shell/helper_functions.sh:$home/helper_functions.sh"
        "$dotfiles/shell/gum_utils.sh:$home/gum_utils.sh"
        "$dotfiles/shell/update_startup.sh:$home/update_startup.sh"


        # local dotfiles
        "$dotfiles/local/.local_env.sh:$home/.local_env.sh"
        "$dotfiles/local/.secrets:$home/.secrets"

        # helix
        "$dotfiles/editors/hx_languages.toml:$home/.config/helix/languages.toml"
        "$dotfiles/editors/hx_config.toml:$home/.config/helix/config.toml"

        # claude directories and files (symlink contents to ~/.claude)
        "$dotfiles/maintained_global_claude/commands:$home/.claude/commands"
        "$dotfiles/maintained_global_claude/hooks:$home/.claude/hooks"
        "$dotfiles/maintained_global_claude/skills:$home/.claude/skills"
        "$dotfiles/maintained_global_claude/plugins:$home/.claude/plugins"
        "$dotfiles/maintained_global_claude/settings.json:$home/.claude/settings.json"
        "$dotfiles/maintained_global_claude/CLAUDE.md:$home/.claude/CLAUDE.md"

        # codex config
        "$dotfiles/codex/config.toml:$home/.codex/config.toml"
    )

    # Create all symlinks in a single loop
    for pair in "${file_pairs[@]}"; do
        source="${pair%%:*}"
        target="${pair#*:}"

        # Ensure the parent directory exists for any target we link.
        mkdir -p "$(dirname "$target")"

        local force_link="false"
        if should_force_link "$target"; then
            force_link="true"
        fi
        ensure_symlink "$source" "$target" "$force_link"

        # Only chmod +x if it's a file, not a directory
        if [ -f "$source" ]; then
            chmod +x "$source"
        fi
    done

    if [ -d "$dracula_plugin" ]; then
        gum_dim "Custom tmux scripts symlinked successfully."
    else
        gum_warning "Dracula tmux plugin directory not found at $dracula_plugin; skipping custom tmux script symlinks."
    fi

if [ -d "$HOME/.cursor" ]; then
    ln -sf "$HOME/.cursor" "$HOME/.cursor-server"
    gum_dim "Symlink created from ~/.cursor to ~/.cursor-server"
fi

}



install_local_dotfiles() {
    mkdir -p "$HOME/dotfiles/local"
    touch "$HOME/dotfiles/local/.local_env.sh"
    touch "$HOME/dotfiles/local/.secrets"
}

generate_plugin_configs() {
    local plugins_dir="$HOME/dotfiles/maintained_global_claude/plugins"
    local templates=(
        "known_marketplaces.json"
        "installed_plugins.json"
    )

    gum_dim "Generating plugin configuration files from templates..."

    for template_name in "${templates[@]}"; do
        local template_file="${plugins_dir}/${template_name}.template"
        local output_file="${plugins_dir}/${template_name}"

        if [ -f "$template_file" ]; then
            # Replace __HOME__ with actual home directory
            # Use a temp file and then move to avoid noclobber issues
            local temp_file="${output_file}.tmp"
            sed "s|__HOME__|$HOME|g" "$template_file" > "$temp_file"
            mv -f "$temp_file" "$output_file"
            gum_dim "  ✓ Generated $template_name"
        else
            gum_warning "  ⚠ Template not found: $template_file"
        fi
    done

    gum_success "Plugin configuration files generated successfully"
}


install_zsh() {
    read -p "zsh is not installed. Do you want to install zsh, build-essential, and vim? (y/n) " choice
    case "$choice" in
        y|Y )
            if [[ "$OS_TYPE" == "linux" ]]; then
                if [ "$(id -u)" -eq 0 ]; then
                    apt update && apt upgrade -y
                    apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                    chsh -s $(which zsh)
                else
                    sudo apt update && sudo apt upgrade -y
                    sudo apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                    sudo chsh -s $(which zsh) $USER
                fi
            elif [[ "$OS_TYPE" == "mac" ]]; then
                brew update
                brew install zsh vim
                chsh -s $(which zsh)
            fi
            gum_success "Installation complete. Please restart your shell to use zsh."
            ;;
        * )
            gum_info "Skipping installation."
            return 1
            ;;
    esac
}




install_cargo() {
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
}


install_uv() {
    curl -LsSf https://astral.sh/uv/install.sh | sh

}


install_tealdeer() {
    source "$HOME/.cargo/env"
    export PATH="$HOME/.cargo/bin:$PATH"
    cargo install tealdeer
    tldr --update
}

install_zprezto() {
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "${ZDOTDIR:-$HOME}/.zprezto"
}


install_npm() {
    bash install/install_npm.sh
}

install_go() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo add-apt-repository -y ppa:longsleep/golang-backports
        sudo apt update
        sudo apt install golang-go -y
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install go
    fi
}

install_fzf() {
    git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf"
    "$HOME/.fzf/install" --all --no-update-rc
}

install_helix() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        snap install --classic helix
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install helix
    fi

    hx --grammar fetch
    hx --grammar build
    gum_success "Helix grammars updated successfully."
}

update_helix_grammars() {
    gum_info "Fetching and building Helix grammars..."
    hx --grammar fetch || gum_warning "Some grammars failed to fetch (this is usually ok)"
    hx --grammar build || gum_warning "Some grammars failed to build (this is usually ok)"
    gum_success "Helix grammars updated."
}

install_glow() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/charmbracelet/glow@latest
}

install_lazygit() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/jesseduffield/lazygit@latest
}

install_lazydocker() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/jesseduffield/lazydocker@latest
}

install_btop() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo snap install btop
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install btop
    fi
    gum_success "btop installed successfully."
}

install_ctop() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo curl -Lo /usr/local/bin/ctop https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-linux-amd64
    elif [[ "$OS_TYPE" == "mac" ]]; then
        sudo curl -Lo /usr/local/bin/ctop https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-darwin-amd64
    fi
    sudo chmod +x /usr/local/bin/ctop
    gum_success "ctop installed successfully."
}

install_bfs() {
    install_on_brew_or_mac "bfs" "tavianator/tap/bfs"
}

install_shellcheck() {
    install_on_brew_or_mac "shellcheck"
}

install_claude_code_cli() {
    # Install via npm
    curl -fsSL https://claude.ai/install.sh | bash
}

install_chafa() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt install chafa -y
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install chafa
    fi
}




install_yq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo snap install yq
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install yq
    fi
}

install_csvcut() {
    install_on_brew_or_mac "csvkit"
    gum_success "csvkit installed successfully; csvcut is now available."
}



install_xclip() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt install -y xclip
        gum_warning "NOTE: For remote tmux clipboard functionality, ensure X11 forwarding is enabled in your SSH config:"
        gum_warning "  Add 'ForwardX11 yes' to your ~/.ssh/config for the relevant hosts"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        gum_info "pbcopy and pbpaste are built into macOS - no additional xclip installation needed"
    fi
}

install_xsel() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt install -y xsel
        gum_success "xsel installed successfully."
    elif [[ "$OS_TYPE" == "mac" ]]; then
        gum_info "pbcopy and pbpaste are built into macOS - no additional xsel installation needed"
    fi
}


install_nbpreview() {
    uv tool install nbcat
}

install_tmux() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/tmux" "n0p.me/bin/tmux" && chmod +x "$HOME/bin/tmux"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install tmux
    fi
    gum_success "tmux installed successfully."
}

install_rg() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/rg" "n0p.me/bin/rg" && chmod +x "$HOME/bin/rg"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install ripgrep
    fi
    gum_success "rg installed successfully."
}

install_fd() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/fd" "n0p.me/bin/fd" && chmod +x "$HOME/bin/fd"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install fd
    fi
    gum_success "fd installed successfully."
}

install_jq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/jq" "n0p.me/bin/jq" && chmod +x "$HOME/bin/jq"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install jq
    fi
    gum_success "jq installed successfully."
}

install_pq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/pq" "https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq" && chmod +x "$HOME/bin/pq"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        wget -O "$HOME/bin/pq" "https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq" && chmod +x "$HOME/bin/pq"
    fi
    gum_success "pq installed successfully."
}

install_bat() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        bash install/install_tar.sh "https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install bat
    fi
    gum_success "bat installed successfully."
}

install_eza() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        bash install/install_tar.sh "https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install eza
    fi
    gum_success "eza installed successfully."
}

install_parquet_tools() {
    go install github.com/hangxie/parquet-tools@latest
    gum_success "parquet-tools installed successfully."
}

install_fzf_tab_completion() {
    git clone https://github.com/lincheney/fzf-tab-completion "$HOME/.zprezto/contrib/fzf-tab-completion"
    gum_success "fzf-tab-completion installed successfully."

    if [[ "$OS_TYPE" == "mac" ]]; then
        brew install gawk grep gnu-sed coreutils
    fi
}

install_ml_helpers() {
    gum_warning "WARNING!!!"
    gum_warning "REPLACE THIS WITH UV"
    git clone https://github.com/vmasrani/machine_learning_helpers.git "$HOME/.python"
    gum_warning "machine_learning_helpers installed successfully."
}


install_hypers() {
    gum_warning "WARNING!!!"
    gum_warning "REPLACE THIS WITH UV"
    git clone https://github.com/vmasrani/hypers.git "$HOME/hypers"
    gum_warning "hypers installed successfully."
}

install_tpm() {
    git clone https://github.com/tmux-plugins/tpm "$HOME/.tmux/plugins/tpm"
    gum_success "tmux plugin manager installed successfully."
}

install_git_fuzzy() {
    git clone https://github.com/bigH/git-fuzzy.git "$HOME/bin/_git-fuzzy"
    ln -s "$HOME/bin/_git-fuzzy/bin/git-fuzzy" "$HOME/bin/git-fuzzy"
    gum_success "git-fuzzy setup completed."
}

install_diff_so_fancy() {
    git clone https://github.com/so-fancy/diff-so-fancy.git "$HOME/bin/_diff-so-fancy"
    ln -s "$HOME/bin/_diff-so-fancy/diff-so-fancy" "$HOME/bin/diff-so-fancy"
    git config --global core.pager "diff-so-fancy | less --tabs=4 -RF"
    git config --global interactive.diffFilter "diff-so-fancy --patch"
    gum_success "diff-so-fancy setup completed."
}

install_finditfaster() {
    cp ~/dotfiles/tools/find_files.sh "$(find ~/.cursor_server/extensions -type d -name 'tomrijndorp*' 2>/dev/null)" || :
    gum_success "find_files.sh copied to cursor extension directory successfully."
}

install_zprezto() {
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
    gum_success "zprezto installed successfully."
}

install_meslo_font() {
    if ! fc-list -q "MesloLGS NF"; then
        gum_info "Installing MesloLGS NF font..."
        if [[ "$OS_TYPE" == "mac" ]]; then
            brew install --cask font-meslo-lg-nerd-font
        else
            sudo apt install fontconfig
            # Direct download method for Linux
            mkdir -p "$HOME/.local/share/fonts"
            curl -L "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Regular.ttf" \
                 --output "$HOME/.local/share/fonts/MesloLGS NF Regular.ttf"
            curl -L "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Bold.ttf" \
                 --output "$HOME/.local/share/fonts/MesloLGS NF Bold.ttf"
            curl -L "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Italic.ttf" \
                 --output "$HOME/.local/share/fonts/MesloLGS NF Italic.ttf"
            curl -L "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Bold%20Italic.ttf" \
                 --output "$HOME/.local/share/fonts/MesloLGS NF Bold Italic.ttf"
            fc-cache -f -v
        fi
        gum_success "MesloLGS NF font installed successfully."
    else
        gum_dim "MesloLGS NF font is already installed."
    fi
}

install_iterm2() {
    if [[ "$OS_TYPE" == "mac" ]]; then
        if [ ! -d "/Applications/iTerm.app" ]; then
            gum_info "Installing iTerm2..."
            brew install --cask iterm2
            gum_success "iTerm2 installed successfully."
        else
            gum_dim "iTerm2 is already installed."
        fi
    else
        gum_warning "iTerm2 is only available on macOS."
    fi
}

install_nvm() {
    if [ ! -d "$HOME/.nvm" ]; then
        gum_info "Installing NVM..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
        nvm install --lts
        nvm use --lts
        gum_success "NVM installed gum_success with latest LTS Node.js."
    else
        gum_dim "NVM is already installed."
    fi
}

install_unzip() {
    gum_info "Installing unzip..."
    install_on_brew_or_mac unzip unzip
    gum_success "unzip installed successfully."
}

install_bun() {
    gum_info "Installing Bun..."
    if [[ "$OS_TYPE" == "mac" ]]; then
        brew tap oven-sh/bun
        brew install bun
    else
        curl -fsSL https://bun.sh/install | bash
    fi
    gum_success "Bun installed successfully."
}

install_pm2() {
    gum_info "Installing PM2..."
    npm install pm2 -g
    gum_success "PM2 installed successfully."
}

install_yarn() {
    gum_info "Installing Yarn..."
    npm install --global yarn
    gum_success "Yarn installed successfully."
}

install_bash_language_server() {
    gum_info "Installing bash-language-server..."
    npm i -g bash-language-server
}

install_yaml_language_server() {
    gum_info "Installing yaml-language-server..."
    npm i -g yaml-language-server
}

install_vscode_langservers_extracted() {
    gum_info "Installing vscode-langservers-extracted..."
    npm i -g vscode-langservers-extracted
}

install_rich_cli() {
    uv tool install rich-cli
    gum_success "rich-cli installed successfully."
}

install_markitdown() {
    uv tool install "markitdown[all]"
    gum_success "markitdown installed successfully."
}

install_visidata() {
    uv tool install --with lxml --with pdfminer.six visidata
    gum_success "visidata installed successfully."
}

install_ty() {
    uv tool install ty@latest
}

install_cargo_tools() {
    cargo install --locked watchexec-cli
    gum_success "watchexec-cli installed successfully."
}

install_markdown_oxide() {
    source "$HOME/.cargo/env"
    export PATH="$HOME/.cargo/bin:$PATH"
    cargo install --locked --git https://github.com/Feel-ix-343/markdown-oxide.git markdown-oxide
}

install_simple_completion_language_server() {
    source "$HOME/.cargo/env"
    export PATH="$HOME/.cargo/bin:$PATH"
    cargo install --git https://github.com/estin/simple-completion-language-server.git
}

install_taplo_cli() {
    source "$HOME/.cargo/env"
    export PATH="$HOME/.cargo/bin:$PATH"
    cargo install taplo-cli --locked --features lsp
}

install_uwu() {
    gum_info "Installing uwu..."
    local temp_dir="/tmp/uwu_build_$$"

    # Clone and build in temp directory
    git clone https://github.com/context-labs/uwu.git "$temp_dir"
    cd "$temp_dir"

    # Check if bun is installed
    if ! command_exists "bun"; then
        gum_info "Bun is required for uwu. Installing bun first..."
        install_bun
    fi

    # Install dependencies and build
    bun install
    bun run build

    # Make binary executable and move to PATH
    chmod +x dist/uwu-cli

    if [[ "$OS_TYPE" == "mac" ]]; then
        # On macOS, use /usr/local/bin without sudo
        sudo mv dist/uwu-cli /usr/local/bin/uwu-cli
    else
        # On Linux, need sudo for /usr/local/bin
        sudo mv dist/uwu-cli /usr/local/bin/uwu-cli
    fi

    # Clean up temp directory
    cd /
    rm -rf "$temp_dir"

    gum_success "uwu installed successfully."
}

install_codex() {
    gum_info "Installing OpenAI Codex CLI..."
    npm install -g @openai/codex
    gum_success "Codex installed successfully."
}
