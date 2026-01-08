# Gum Utilities Standardization - Implementation Plan

## Overview
Create a comprehensive gum utilities library to standardize all terminal UI output across dotfiles. This will reduce ~100 lines of duplicated code, enable consistent styling, provide graceful fallback for non-TTY environments, and improve maintainability.

## Implementation Strategy

### 1. Create New gum_utils.sh File

**File:** `/Users/vmasrani/dotfiles/shell/gum_utils.sh` (new file)

**Why:** Substantial enough (~120 lines) to warrant its own file, keeps helper_functions.sh focused

**Add to .zshrc:** Source it alongside helper_functions.sh

**Create these sections:**

#### A. Color and Style Constants (~15 lines)
```bash
# === Gum Color Constants ===
readonly GUM_COLOR_SUCCESS=46      # Green
readonly GUM_COLOR_ERROR=196       # Red
readonly GUM_COLOR_WARNING=208     # Orange
readonly GUM_COLOR_INFO=212        # Magenta
readonly GUM_COLOR_DIM=245         # Gray
readonly GUM_COLOR_GRAY=242        # Darker gray
readonly GUM_COLOR_BLUE=111        # Blue highlights

# === Symbol Constants ===
readonly GUM_SYMBOL_SUCCESS="✓"
readonly GUM_SYMBOL_ERROR="✗"
readonly GUM_SYMBOL_WARNING="⚠"
readonly GUM_SYMBOL_PROGRESS="→"
```

#### B. Fallback Detection (~25 lines)
```bash
# === Gum Availability Detection ===
_GUM_AVAILABLE=""

_gum_init() {
    # Check env variable (NO_GUM or DOTFILES_NO_GUM)
    if [[ -n "${NO_GUM:-}" || -n "${DOTFILES_NO_GUM:-}" ]]; then
        _GUM_AVAILABLE=0
        return
    fi

    # Check if TTY (stdin and stdout)
    if [[ ! -t 0 || ! -t 1 ]]; then
        _GUM_AVAILABLE=0
        return
    fi

    # Check if gum command exists
    if ! command -v gum >/dev/null 2>&1; then
        _GUM_AVAILABLE=0
        return
    fi

    _GUM_AVAILABLE=1
}

_gum_check() {
    if [[ -z "$_GUM_AVAILABLE" ]]; then
        _gum_init
    fi
    [[ "$_GUM_AVAILABLE" -eq 1 ]]
}
```

#### C. Wrapper Functions (~80 lines)

**Status Messages:**
```bash
gum_success() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_SUCCESS" "$GUM_SYMBOL_SUCCESS $*"
    else
        echo "$GUM_SYMBOL_SUCCESS $*"
    fi
}

gum_error() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_ERROR" --border double \
            --padding "0 1" --margin "1" "$@"
    else
        echo "ERROR: $*" >&2
    fi
}

gum_warning() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_WARNING" "$GUM_SYMBOL_WARNING $*"
    else
        echo "WARNING: $*"
    fi
}

gum_info() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_INFO" "$GUM_SYMBOL_PROGRESS $*"
    else
        echo "$GUM_SYMBOL_PROGRESS $*"
    fi
}

gum_dim() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_DIM" "$@"
    else
        echo "$@"
    fi
}
```

**Boxes and Headers:**
```bash
gum_box() {
    local title="$1"
    local color="${2:-$GUM_COLOR_INFO}"

    if _gum_check; then
        gum style --border rounded --padding "1 2" \
            --border-foreground "$color" "$title"
    else
        echo "=== $title ==="
    fi
}

gum_box_success() {
    if _gum_check; then
        gum style --border rounded --padding "0 2" \
            --border-foreground "$GUM_COLOR_SUCCESS" \
            --foreground "$GUM_COLOR_SUCCESS" "$@"
    else
        echo "=== $* ==="
    fi
}
```

**Spinners:**
```bash
gum_spin_quick() {
    local title="$1"
    shift

    if _gum_check; then
        gum spin --spinner dot --title "$title" -- "$@"
    else
        echo "[$title]"
        "$@"
    fi
}

gum_spin_wait() {
    local title="$1"
    shift

    if _gum_check; then
        gum spin --spinner meter --title "$title" -- "$@"
    else
        echo "[$title]"
        "$@"
    fi
}
```

**Interactive Prompts:**
```bash
gum_confirm() {
    if _gum_check; then
        gum confirm "$@"
    else
        # Auto-approve in non-interactive mode
        return 0
    fi
}

gum_choose() {
    if _gum_check; then
        gum choose "$@"
    else
        # Return first non-header option
        local skip_next=0
        for arg in "$@"; do
            if [[ "$arg" == "--header" ]]; then
                skip_next=1
                continue
            fi
            if [[ $skip_next -eq 1 ]]; then
                skip_next=0
                continue
            fi
            echo "$arg"
            return 0
        done
    fi
}
```

**Multi-colored Output:**
```bash
gum_print_change() {
    local old="$1"
    local new="$2"

    if _gum_check; then
        printf "%s %s %s\n" \
            "$(gum style --foreground "$GUM_COLOR_GRAY" "$old")" \
            "$(gum style --foreground "$GUM_COLOR_DIM" "$GUM_SYMBOL_PROGRESS")" \
            "$(gum style --foreground "$GUM_COLOR_BLUE" "$new")"
    else
        printf "%s -> %s\n" "$old" "$new"
    fi
}
```

### 2. Migrate Scripts (in order of value)

#### A. rename_pdf (40 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/rename_pdf`

**Remove lines 7-43:** All the NO_GUM detection and say_* function definitions

**Replace with wrapper calls:**
- Line 23: `gum style --foreground 196...` → `gum_error`
- Line 32: `gum style --foreground 245` → `gum_dim`
- Line 41: `gum spin --spinner dot` → `gum_spin_quick`
- Lines 129-136: Multi-colored output → `gum_print_change "$old_basename" "${new_name}.${extension}"`

#### B. aws_common.sh (30 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/aws_common.sh`

**Replace throughout:**
- `gum style --foreground 46 "✓..."` → `gum_success "..."`
- `gum style --foreground 196 "✗..."` → `gum_error "..."`
- `gum style --foreground 208 "⚠..."` → `gum_warning "..."`
- `gum style --foreground 212 "→..."` → `gum_info "..."`
- `gum style --border rounded --padding "1 2"...` → `gum_box "..." [color]`
- `gum spin --spinner dot` → `gum_spin_quick`
- `gum spin --spinner meter` → `gum_spin_wait`
- `gum choose` → `gum_choose`

**Specific examples:**
- Line 28: `gum style --border rounded...` → `gum_box "$title" "$color"`
- Line 32: `gum style --foreground 196 "✗..."` → `gum_error "No instance selected"`
- Line 40: `gum style --foreground "$color" "→..."` → `gum_info "Selected: $instance_type ($DISPLAY_NAME)"`

#### C. start_aws (15 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/start_aws`

Same replacements as aws_common.sh

#### D. stop_aws (10 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/stop_aws`

Same replacements as aws_common.sh

#### E. tagger (5 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/tagger`

Replace simple gum style calls with wrappers

#### F. ocr_agent.sh (5 lines saved)
**File:** `/Users/vmasrani/dotfiles/tools/ocr_agent.sh`

Replace simple gum style calls with wrappers

### 3. Testing

Create `/Users/vmasrani/dotfiles/tools/test_gum_utils.sh`:

```bash
#!/bin/zsh
# Test gum utilities with and without gum available

test_all_functions() {
    echo "Testing all gum functions..."

    gum_success "Success message"
    gum_error "Error message" "Additional details"
    gum_warning "Warning message"
    gum_info "Info message"
    gum_dim "Dimmed text"
    gum_box "Box title" "$GUM_COLOR_INFO"
    gum_box_success "Success box"
    gum_print_change "old.txt" "new.txt"

    gum_spin_quick "Quick test..." sleep 0.5
    gum_spin_wait "Wait test..." sleep 1
}

# Test with gum enabled
echo "=== WITH GUM ==="
unset NO_GUM
test_all_functions

# Test with gum disabled
echo ""
echo "=== WITHOUT GUM (NO_GUM=1) ==="
export NO_GUM=1
test_all_functions
```

**Run:** `zsh test_gum_utils.sh`

## Benefits Summary

### Code Reduction
- **Total:** ~100 lines of duplicated boilerplate removed
- **rename_pdf:** 40 lines (remove entire NO_GUM detection + say_* functions)
- **aws_common.sh:** 30 lines (shorter, more semantic)
- **Other scripts:** 30 lines combined

### Maintainability
- **Single source of truth:** Change colors globally in helper_functions.sh
- **Consistent UX:** All scripts have identical look and feel
- **Self-documenting:** `gum_success()` vs `gum style --foreground 46 "✓..."`
- **No duplication:** Fallback logic written once

### User Experience
- **Graceful degradation:** Works in cron, launchd, pipes, SSH without TTY
- **Environment control:** `NO_GUM=1 ./script.sh` to disable
- **Predictable:** Same colors/symbols everywhere

### 4. Integration with Setup

**Source in .zshrc:**

Add after the existing helper_functions.sh source line:
```bash
source ~/gum_utils.sh
```

**Create symlink during setup:**

The setup.sh script will need to create a symlink from `~/gum_utils.sh` → `/Users/vmasrani/dotfiles/shell/gum_utils.sh` (similar to how helper_functions.sh is symlinked)

## Critical Files

1. `/Users/vmasrani/dotfiles/shell/gum_utils.sh` - **NEW FILE** ~120 lines of gum utilities
2. `/Users/vmasrani/dotfiles/shell/.zshrc` - Add source line for gum_utils.sh
3. `/Users/vmasrani/dotfiles/tools/rename_pdf` - Remove 40 lines, replace with wrapper calls
4. `/Users/vmasrani/dotfiles/tools/aws_common.sh` - Replace all gum calls with wrappers
5. `/Users/vmasrani/dotfiles/tools/start_aws` - Replace all gum calls with wrappers
6. `/Users/vmasrani/dotfiles/tools/stop_aws` - Replace all gum calls with wrappers
7. `/Users/vmasrani/dotfiles/tools/tagger` - Simple wrapper replacements
8. `/Users/vmasrani/dotfiles/tools/ocr_agent.sh` - Simple wrapper replacements
9. `/Users/vmasrani/dotfiles/tools/test_gum_utils.sh` - New test file (~50 lines)
