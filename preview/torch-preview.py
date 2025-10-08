#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["torch"]
# ///
import sys
from pprint import pprint
from torch import load, __version__

# Get the filename from the command line arguments
file_name = sys.argv[1]

# Print the torch version and load the file
print(__version__)
pprint(load(file_name))
