# ~/.profile: executed by the command interpreter for login shells.
# This file is not read by bash(1), if ~/.bash_profile or ~/.bash_login
# exists.
# see /usr/share/doc/bash/examples/startup-files for examples.
# the files are located in the bash-doc package.

# the default umask is set in /etc/profile; for setting the umask
# for ssh logins, install and configure the libpam-umask package.
#umask 022

source ~/dotfiles/lscolors.sh

# if running bash
if [ -n "$BASH_VERSION" ]; then
    # include .bashrc if it exists
    if [ -f "$HOME/.bashrc" ]; then
	. "$HOME/.bashrc"
    fi
fi

# set PATH so it includes user's private bin directories
export PATH="$HOME/bin:$HOME/bin/bin:$HOME/.local/bin:$PATH"
export PATH=$HOME/local/texlive/2023/bin/x86_64-linux:$PATH
# # handle proxy BS
# http_proxy=http://127.0.0.1:3128
# ftp_proxy=http://127.0.0.1:3128
# https_proxy=http://127.0.0.1:3128
# no_proxy=127.0.0.*,*.huawei.com,localhost
# cntlm_proxy=127.0.0.1:3128
# SSL_CERT_DIR=/etc/ssl/certs
# REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

echo "hello from profile"

