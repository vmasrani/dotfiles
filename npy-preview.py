#!/home/vaden/.conda/envs/ml3/bin/python
import sys
import numpy as np

# Get the filename from the command line arguments
file_name = sys.argv[1]

print(np.lib.format.open_memmap(file_name, mode='r+').shape)
print(np.lib.format.open_memmap(file_name, mode='r+'))
