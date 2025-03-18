#!/bin/bash

# List of IP addresses
IP_ADDRESSES=("10.213.96.116" "10.213.96.114" "10.193.241.206" "10.209.172.42" "7.184.9.95" "10.213.96.117")
USER='vaden'

# Source directory to check
SOURCE_DIR=$1
shift

# Destination directory
DEST_DIR=$1
shift

# Rsync options
RSYNC_OPTIONS="$@"

# Get the local IP address
LOCAL_IP=$(hostname -I | awk '{print $1}')

# Full path to rsync
RSYNC_BIN=$(which rsync)

# Default rsync options from alias
DEFAULT_RSYNC_OPTIONS="-avz --compress --verbose --human-readable --partial --progress"

# Function to check if the source directory exists on the remote server
check_source_dir() {
    local ip=$1
    rsync --dry-run "$USER@$ip:$SOURCE_DIR" "$DEST_DIR" &>/dev/null
}
# Iterate through the list of IP addresses
for ip in "${IP_ADDRESSES[@]}"; do
    if [ "$ip" == "$LOCAL_IP" ]; then
        echo "Skipping local IP address: $ip"
        continue
    fi

    if check_source_dir "$ip"; then
        echo "Source directory found on $ip. Starting rsync..."
        $RSYNC_BIN $DEFAULT_RSYNC_OPTIONS $RSYNC_OPTIONS "$USER@$ip:$SOURCE_DIR" "$DEST_DIR"
        exit 0
    fi
done

echo "Source directory not found on any of the specified IP addresses."
exit 1
