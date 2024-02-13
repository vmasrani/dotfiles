export POWERLEVEL9K_INSTALLATION_DIR=/home/vaden/.zprezto/modules/prompt/external/powerlevel10k
export PATH="/home/vaden/miniconda/bin:$PATH"
export PATH=$HOME/local/bin:$PATH
export PATH=/home/vaden/local/texlive/2023/bin/x86_64-linux:$PATH


export SHELL=~/bin/zsh

export http_proxy=http://127.0.0.1:3128
export ftp_proxy=http://127.0.0.1:3128
export https_proxy=http://127.0.0.1:3128
export no_proxy=127.0.0.*,*.huawei.com,localhost
export cntlm_proxy=127.0.0.1:3128
export SSL_CERT_DIR=/etc/ssl/certs
#export REQUESTS_CA_BUNDLE=/etc/ssl/certs/my-custom-certificates.crt
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
exec ~/bin/zsh -l
. "$HOME/.cargo/env"


