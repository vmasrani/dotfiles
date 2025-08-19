#!/bin/bash
# Cross-platform Claude wrapper script
# Automatically detects the best available Claude installation

# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="mac"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
else
    echo "Unsupported operating system: $OSTYPE" >&2
    exit 1
fi

# Function to find the best Claude installation
find_claude() {
    # Priority order: migrated ~/.claude > bun > npm (latest version) > system
    
    # Check migrated Claude installation first (after running claude migrate)
    if [[ -x "$HOME/.claude/claude" ]]; then
        echo "$HOME/.claude/claude"
        return 0
    fi
    
    # Check for Claude in ~/.claude/bin/ (alternative migration location)
    if [[ -x "$HOME/.claude/bin/claude" ]]; then
        echo "$HOME/.claude/bin/claude"
        return 0
    fi
    
    # Check bun installation (fastest for non-migrated installs)
    if [[ -x "$HOME/.bun/bin/claude" ]]; then
        echo "$HOME/.bun/bin/claude"
        return 0
    fi
    
    # Check npm installations (prefer latest version)
    if command -v nvm >/dev/null 2>&1; then
        # Source nvm if available
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        
        # Find the latest npm installation
        for version in $(ls -1v "$HOME/.nvm/versions/node/" 2>/dev/null | tac); do
            claude_path="$HOME/.nvm/versions/node/$version/bin/claude"
            if [[ -x "$claude_path" ]]; then
                echo "$claude_path"
                return 0
            fi
        done
    fi
    
    # Check system installation
    if command -v claude >/dev/null 2>&1; then
        echo "claude"
        return 0
    fi
    
    # No Claude installation found
    echo "Error: Claude Code CLI not found. Please install it with: npm install -g @anthropic-ai/claude-code" >&2
    exit 1
}

# Find and execute Claude
claude_path=$(find_claude)
exec "$claude_path" "$@"