#!/bin/bash

# Usage: ./split_by_size.sh input.mp4 100
# Arguments: $1 = input file, $2 = chunk size in MB

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 input.mp4 chunk_size_in_MB"
    exit 1
fi

INPUT="$1"
CHUNK_MB="$2"
CHUNK_BYTES=$((CHUNK_MB * 1024 * 1024))

# Get duration (seconds) and size (bytes)
DURATION=$(ffprobe -v error -show_entries format=duration \
           -of default=noprint_wrappers=1:nokey=1 "$INPUT")
SIZE=$(ffprobe -v error -show_entries format=size \
        -of default=noprint_wrappers=1:nokey=1 "$INPUT")

# Compute approximate duration per chunk
CHUNK_DURATION=$(echo "scale=2; $DURATION * $CHUNK_BYTES / $SIZE" | bc)

echo "Splitting '$INPUT' into ~${CHUNK_MB}MB chunks (≈ ${CHUNK_DURATION}s each)..."

# Run ffmpeg segmenting
ffmpeg -i "$INPUT" \
  -c copy -map 0 \
  -f segment -segment_time "$CHUNK_DURATION" -reset_timestamps 1 \
  "${INPUT%.*}_chunk_%03d.mp4"
