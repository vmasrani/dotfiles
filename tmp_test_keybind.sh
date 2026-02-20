#!/usr/bin/env zsh
set -e

KEY="0x4b-0x120000-0x28"  # Cmd+Shift+K (0x4b=K, 0x120000=Cmd+Shift, 0x28=K keycode)
PLIST="$HOME/Library/Preferences/com.googlecode.iterm2.plist"

if [[ "$1" == "--reset" ]]; then
    /usr/libexec/PlistBuddy -c "Delete :GlobalKeyMap:$KEY" "$PLIST" 2>/dev/null && \
        echo "✓ Test mapping removed. Restart iTerm2." || \
        echo "Nothing to remove — mapping not found."
    exit 0
fi

# Map Cmd+Shift+K → type "KEYBIND WORKS!" + newline
defaults write com.googlecode.iterm2 GlobalKeyMap -dict-add \
    "$KEY" \
    '{"Action"=12;"Apply Mode"=1;"Escaping"=0;"Text"="echo KEYBIND_WORKS!\\n";"Version"=2;}'

echo "✓ Mapped Cmd+Shift+K → echo KEYBIND_WORKS!"
echo ""
echo "Next steps:"
echo "  1. Quit iTerm2 completely (Cmd+Q)"
echo "  2. Reopen iTerm2"
echo "  3. Press Cmd+Shift+K — should type and run 'echo KEYBIND_WORKS!'"
echo "  4. Run: ./tmp_test_keybind.sh --reset   (then restart iTerm2 again)"
