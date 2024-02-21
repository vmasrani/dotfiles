export POWERLEVEL9K_INSTALLATION_DIR=$HOME/.zprezto/modules/prompt/external/powerlevel10k
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize
export PATH=$HOME/local/bin:$PATH
export PATH=$HOME/local/texlive/2023/bin/x86_64-linux:$PATH


export SHELL=~/bin/zsh

# export http_proxy=http://127.0.0.1:3128
# export ftp_proxy=http://127.0.0.1:3128
# export https_proxy=http://127.0.0.1:3128
# export no_proxy=127.0.0.*,*.huawei.com,localhost
# export cntlm_proxy=127.0.0.1:3128
# export SSL_CERT_DIR=/etc/ssl/certs
# #export REQUESTS_CA_BUNDLE=/etc/ssl/certs/my-custom-certificates.crt
# export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
exec ~/bin/zsh -l




# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/Users/vmasrani/miniconda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/Users/vmasrani/miniconda/etc/profile.d/conda.sh" ]; then
        . "/Users/vmasrani/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="/Users/vmasrani/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

