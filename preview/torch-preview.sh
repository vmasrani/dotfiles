#!/usr/bin/env python

# Get the filename from the command line arguments
file_name="$1"

# Run the Python command
$HOME/ml3/bin/python -c "from torch import load, __version__; print(__version__); print(load('$file_name'))"
