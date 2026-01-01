#!/usr/bin/env zsh
set -e

pm2 start "$HOME/dotfiles/listeners/watch_pdfs_in_downloads.sh" --name watch-pdfs
pm2 start "$HOME/dotfiles/listeners/watch_ebooks_in_downloads.sh" --name watch-epbs
pm2 startup
pm2 save
