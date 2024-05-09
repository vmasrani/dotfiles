#!/bin/bash
set -e

mkdir -p ~/miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda/miniconda.sh
bash ~/miniconda/miniconda.sh -b -u -p ~/miniconda
rm -rf ~/miniconda/miniconda.sh

echo "Creating ml3 conda env."
conda create -n ml3 python=3.10
conda activate ml3

pip ipdb ipykernel ipython joblib jupyter matplotlib pandas plotly polars pyarrow pyjanitor pylint requests ruff scikit-learn scipy seaborn tqdm wandb fastparquet pyarrow

conda install pytorch==1.12.1 -c pytorch
conda install cudatoolkit=10.2 -c pytorch
conda install torchvision==0.13.1 -c pytorch
conda install torchaudio==0.12.1 -c pytorch





