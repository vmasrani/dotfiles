#!/bin/bash
set -e

mkdir -p ~/miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda/miniconda.sh
bash ~/miniconda/miniconda.sh -b -u -p ~/miniconda
rm -rf ~/miniconda/miniconda.sh

echo "Creating ml3 conda env."
conda create -n ml3 python=3.10
conda activate ml3

pip install ipykernel joblib seaborn pandas transformers pyarrow wandb scipy datasets scipy scikit-learn ipykernel ipython pyjanitor seaborn matplotlib typing-extensions requests ruff pylint datasets transformers spacy polars jupyter ipdb plotly

conda install pytorch==1.12.1 -c pytorch
conda install cudatoolkit=10.2 -c pytorch
conda install torchvision==0.13.1 -c pytorch
conda install torchaudio==0.12.1 -c pytorch


