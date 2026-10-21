#!/bin/bash
# shellcheck shell=bash
# Point iTerm2 at the repo's iterm2/ folder as its live prefs folder (auto-save on).

ITERM2_DOMAIN="com.googlecode.iterm2"

# Rewrite every /Users/<name> home in the plist that differs from <new_home>. Idempotent.
iterm2_rewrite_home() {
	local plist="$1" new_home="$2"
	local old_home
	while IFS= read -r old_home; do
		[[ "$old_home" == "$new_home" ]] && continue
		sed -i '' "s#<string>$old_home\([/<]\)#<string>$new_home\1#g" "$plist"
		gum_info "Rewrote $old_home -> $new_home in $(basename "$plist")"
	done < <(grep -oE '<string>/Users/[^/<]+' "$plist" | sed 's/^<string>//' | sort -u)
	plutil -lint "$plist" >/dev/null || { gum_error "$plist is invalid after home rewrite"; return 1; }
}

install_iterm2_prefs() {
	if [[ "$OS_TYPE" != "mac" && "$OS_TYPE" != "macos" && "$(uname -s)" != "Darwin" ]]; then
		gum_dim "Skipping iTerm2 prefs (macOS only)"
		return 0
	fi

	local folder="$HOME/dotfiles/iterm2"
	if [[ ! -f "$folder/$ITERM2_DOMAIN.plist" ]]; then
		gum_error "Missing $folder/$ITERM2_DOMAIN.plist - run iterm2/export-prefs on a configured machine first"
		return 1
	fi

	iterm2_rewrite_home "$folder/$ITERM2_DOMAIN.plist" "$HOME" || return 1

	local cur_folder cur_load cur_sel
	cur_folder=$(defaults read "$ITERM2_DOMAIN" PrefsCustomFolder 2>/dev/null)
	cur_load=$(defaults read "$ITERM2_DOMAIN" LoadPrefsFromCustomFolder 2>/dev/null)
	cur_sel=$(defaults read "$ITERM2_DOMAIN" NoSyncNeverRemindPrefsChangesLostForFile_selection 2>/dev/null)
	if [[ "$cur_folder" == "$folder" && "$cur_load" == "1" && "$cur_sel" == "2" ]]; then
		gum_dim "iTerm2 prefs already configured"
		return 0
	fi

	if pgrep -xq iTerm2; then
		gum_error "iTerm2 is running and caches its prefs. Quit iTerm2 and run setup from Terminal.app (or quit iTerm2 and re-run ./setup.sh)"
		return 1
	fi

	defaults write "$ITERM2_DOMAIN" PrefsCustomFolder -string "$folder"
	defaults write "$ITERM2_DOMAIN" LoadPrefsFromCustomFolder -bool true
	defaults write "$ITERM2_DOMAIN" NoSyncNeverRemindPrefsChangesLostForFile_selection -int 2
	gum_success "iTerm2 will load and auto-save prefs in $folder (takes effect on next launch)"
}
