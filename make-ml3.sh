#!/bin/bash

set -e

echo "Creating ml3 conda env."
conda create -n ml3 python=3.10
conda activate ml3

pip install ipykernel joblib seaborn pandas transformers pyarrow wandb scipy datasets scipy scikit-learn ipykernel ipython pyjanitor seaborn matplotlib typing-extensions requests ruff pylint datasets transformers spacy polars jupyter ipdb plotly

conda install pytorch==1.12.1 -c pytorch
conda install cudatoolkit=10.2 -c pytorch
conda install torchvision==0.13.1 -c pytorch
conda install torchaudio==0.12.1 -c pytorch
