#!/bin/bash

# AICore Service Management Setup Script
# This script sets up the aicore service management system by creating symlinks and verifying prerequisites.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AICORE_SCRIPT="${SCRIPT_DIR}/aicore"
BIN_DIR="${HOME}/bin"
SYMLINK_TARGET="${BIN_DIR}/aicore"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if ~/bin is in PATH
check_bin_in_path() {
    if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
        return 0
    else
        return 1
    fi
}

# Function to check sudo privileges
check_sudo_privileges() {
    if sudo -n true 2>/dev/null; then
        return 0
    else
        print_info "Testing sudo privileges..."
        if sudo -v; then
            return 0
        else
            return 1
        fi
    fi
}

# Function to verify systemd availability
check_systemd() {
    if command_exists systemctl; then
        return 0
    else
        return 1
    fi
}

# Main setup function
main() {
    print_info "Starting AICore Service Management setup..."
    echo

    # Check if aicore script exists
    if [[ ! -f "$AICORE_SCRIPT" ]]; then
        print_error "aicore script not found at: $AICORE_SCRIPT"
        print_error "Please ensure the aicore script is created before running setup."
        exit 1
    fi

    # Check prerequisites
    print_info "Checking prerequisites..."
    
    # Check systemd availability
    if ! check_systemd; then
        print_error "systemctl command not found. This system requires systemd."
        print_error "Please ensure you're running on a systemd-based Linux distribution."
        exit 1
    fi
    print_success "systemd is available"

    # Check sudo privileges
    if ! check_sudo_privileges; then
        print_error "sudo privileges are required for systemctl operations."
        print_error "Please ensure you have sudo access and try again."
        exit 1
    fi
    print_success "sudo privileges verified"

    # Create ~/bin directory if it doesn't exist
    if [[ ! -d "$BIN_DIR" ]]; then
        print_info "Creating ~/bin directory..."
        mkdir -p "$BIN_DIR"
        print_success "Created ~/bin directory"
    else
        print_success "~/bin directory already exists"
    fi

    # Make aicore script executable
    print_info "Making aicore script executable..."
    chmod +x "$AICORE_SCRIPT"
    print_success "aicore script is now executable"

    # Create symlink (remove existing one if present)
    if [[ -L "$SYMLINK_TARGET" ]]; then
        print_info "Removing existing symlink..."
        rm "$SYMLINK_TARGET"
    elif [[ -f "$SYMLINK_TARGET" ]]; then
        print_warning "A file already exists at $SYMLINK_TARGET (not a symlink)"
        print_warning "Backing up existing file to ${SYMLINK_TARGET}.backup"
        mv "$SYMLINK_TARGET" "${SYMLINK_TARGET}.backup"
    fi

    print_info "Creating symlink from ~/bin/aicore to $AICORE_SCRIPT..."
    ln -sf "$AICORE_SCRIPT" "$SYMLINK_TARGET"
    print_success "Symlink created successfully"

    # Verify symlink
    if [[ -L "$SYMLINK_TARGET" && -x "$SYMLINK_TARGET" ]]; then
        print_success "Symlink verification passed"
    else
        print_error "Symlink verification failed"
        exit 1
    fi

    # Check if ~/bin is in PATH
    if ! check_bin_in_path; then
        print_warning "~/bin is not in your PATH"
        print_warning "You may need to add it to your shell configuration:"
        print_warning "  echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.bashrc"
        print_warning "  echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.zshrc"
        print_warning "Then restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
        echo
        print_info "You can also run the aicore command directly using the full path:"
        print_info "  $SYMLINK_TARGET --help"
    else
        print_success "~/bin is in your PATH"
    fi

    # Test the installation
    print_info "Testing installation..."
    if command_exists aicore; then
        print_success "aicore command is available in PATH"
        print_info "Testing aicore command..."
        if aicore --help >/dev/null 2>&1; then
            print_success "aicore command executed successfully"
        else
            print_warning "aicore command exists but may have issues"
        fi
    else
        print_warning "aicore command not found in PATH"
        print_info "This is expected if ~/bin is not in your PATH"
        print_info "You can still use: $SYMLINK_TARGET"
    fi

    echo
    print_success "Setup completed successfully!"
    echo
    print_info "Next steps:"
    print_info "1. If ~/bin is not in your PATH, add it to your shell configuration"
    print_info "2. Test the installation with: aicore --help"
    print_info "3. Start using aicore to manage your AI Core services"
    echo
    print_info "For usage examples, see the README.md file in this directory"
}

# Error handling
trap 'print_error "Setup failed. Please check the error messages above."' ERR

# Run main function
main "$@"