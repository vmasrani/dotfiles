#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["numpy", "matplotlib"]
# ///
import sys
import os
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

# Get the filename from the command line arguments
file_name = sys.argv[1]

# Load the array
arr = np.lib.format.open_memmap(file_name, mode='r')

# Print shape
print(f"Shape: {arr.shape}")
print(f"Dtype: {arr.dtype}")

# Display based on dimensions
if arr.ndim == 2 or arr.ndim == 3:
    # Select the data to plot
    if arr.ndim == 2:
        data_to_plot = arr
        title = f'{os.path.basename(file_name)} - 2D Array Heatmap'
    else:  # arr.ndim == 3
        data_to_plot = arr[0]
        title = f'{os.path.basename(file_name)} - First 2D Slice of 3D Array [0,:,:]'
    
    # Create heatmap
    plt.figure(figsize=(10, 8))
    plt.imshow(data_to_plot, cmap='viridis', aspect='auto', interpolation='nearest')
    plt.colorbar(label='Value')
    plt.title(title)
    plt.xlabel('Column Index')
    plt.ylabel('Row Index')
    plt.tight_layout()
    
    # Save to temporary file
    temp_path = '/tmp/npy_preview.png'
    plt.savefig(temp_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    # Display with chafa
    try:
        subprocess.run(['chafa', temp_path], check=True)
    except subprocess.CalledProcessError:
        print(f"Error: Could not display image with chafa. Image saved at {temp_path}")
    except FileNotFoundError:
        print(f"Error: chafa not found. Please install chafa. Image saved at {temp_path}")
else:
    # Print array for 1D or 4D+ arrays
    print(arr)
