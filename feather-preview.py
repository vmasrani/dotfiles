#!/usr/bin/env python
import sys
import pandas as pd

# Get the filename from the command line arguments
file_name = sys.argv[1]

df = pd.read_feather(file_name)
print(df)


