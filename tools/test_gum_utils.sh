#!/bin/zsh
# ===================================================================
# Gum Utilities Test Script
# ===================================================================
# Tests all gum utility functions with and without gum available
# Usage: zsh test_gum_utils.sh
# ===================================================================

# Source gum utilities
source ~/gum_utils.sh

test_all_functions() {
    echo "Testing all gum functions..."
    echo ""

    gum_success "Success message"
    gum_error "Error message" "Additional details line 2"
    gum_warning "Warning message"
    gum_info "Info message"
    gum_dim "Dimmed text"

    echo ""
    gum_box "Box title" "$GUM_COLOR_INFO"
    gum_box_success "Success box"

    echo ""
    gum_print_change "old_file.txt" "new_file.txt"

    echo ""
    gum_spin_quick "Quick operation..." sleep 0.5
    gum_spin_wait "Longer operation..." sleep 1

    echo ""
    echo "Testing confirmation (auto-approved in non-interactive):"
    if gum_confirm "Continue with test?"; then
        echo "Confirmed!"
    else
        echo "Not confirmed"
    fi

    echo ""
    echo "Testing choice selection:"
    choice=$(gum_choose --header "Select option:" "option1" "option2" "option3")
    echo "Selected: $choice"
}

# Test with gum enabled
echo "========================================="
echo "=== TESTING WITH GUM ENABLED ==="
echo "========================================="
unset NO_GUM
unset DOTFILES_NO_GUM
_GUM_AVAILABLE=""  # Reset detection
test_all_functions

echo ""
echo ""

# Test with gum disabled
echo "========================================="
echo "=== TESTING WITH GUM DISABLED (NO_GUM=1) ==="
echo "========================================="
export NO_GUM=1
_GUM_AVAILABLE=""  # Reset detection
test_all_functions

echo ""
echo "========================================="
echo "=== ALL TESTS COMPLETE ==="
echo "========================================="
