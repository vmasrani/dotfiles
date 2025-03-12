#!/bin/bash

# Script to process 'text' fields in a JSON file through a shell command and update the JSON

# Check if input JSON file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_json_file>"
    exit 1
fi

# Input JSON file
INPUT_JSON="$1"
# Temporary files
TEXT_OUTPUT="text_output.txt"
PROCESSED_TEXT="processed_text.txt"
UPDATED_JSON="updated.json"

# Step 1: Extract the 'text' fields from the input JSON
jq '.documents[] | .text' "$INPUT_JSON" > "$TEXT_OUTPUT"

# Step 2: Process each extracted 'text' field using a shell command (example: tr for uppercasing)
# Clean the processed text file first
> "$PROCESSED_TEXT"

while IFS= read -r line; do
    # Replace this command with your desired shell command to process text
    processed=$(aichat --no-stream -r ocrfixer "$line")
    echo $processed
    # Append the processed text to the output file
    echo "$processed" >> "$PROCESSED_TEXT"
done < "$TEXT_OUTPUT"

# Step 3: Merge the processed text back into the original JSON
# Update the 'text' fields with the processed content
jq --slurpfile new_text "$PROCESSED_TEXT" \
   '.documents |= [range(0; length)] | .documents[] |= (.text = $new_text[range(0; length)] | first)' \
   "$INPUT_JSON" > "$UPDATED_JSON"

# Clean up temporary files
rm "$TEXT_OUTPUT" "$PROCESSED_TEXT"

# Notify the user
echo "Updated JSON with processed text has been written to $UPDATED_JSON"


