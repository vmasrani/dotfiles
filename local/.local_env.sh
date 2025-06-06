# shellcheck shell=zsh

# autossh
alias ssh="autossh -M 0"
alias fr='open -a Finder .'
export OPENAI_API_KEY='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'
export ANTHROPIC_API_KEY='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'

unset SSL_CERT_FILE

# enable rbenv
if [ -d "$HOME/.rbenv/" ]; then
    export PATH="$HOME/.rbenv/bin:$PATH"
    eval "$(rbenv init - zsh)"
fi

export LDFLAGS="-L$(brew --prefix openssl)/lib"
export CPPFLAGS="-I$(brew --prefix openssl)/include"
export RUBY_CONFIGURE_OPTS="--with-openssl-dir=$(brew --prefix openssl)"
