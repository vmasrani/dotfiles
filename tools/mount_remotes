#!/bin/zsh

# Define the list of servers and their respective paths
# declare -A servers=(
#     ["117"]="10.213.96.117:$HOME/dev"
#     ["116"]="10.213.96.116:$HOME/dev"
#     ["103"]="10.193.241.103:/fastdata/vaden/dev"
#     ["95"]="7.184.9.95:/data/vaden/dev"
#     ["114"]="10.213.96.114:$HOME/dev"
#     ["206"]="10.193.241.206:/data/vaden/dev"
# )

typeset -A servers
servers=(
    117 "10.213.96.117:$HOME/dev"
    116 "10.213.96.116:$HOME/dev"
    103 "10.193.241.103:/fastdata/vaden/dev"
    104 "10.193.241.104:/fastdata/vaden/dev"
    95  "7.184.9.95:/data/vaden/dev"
    114 "10.213.96.114:$HOME/dev"
    206 "10.193.241.206:/data/vaden/dev"
)

# Function to mount all servers
mount_all_servers() {
    # Create the base directory if it doesn't exist
    mkdir -p ~/mounted_servers

    # Iterate through the servers and mount each one
    for key in "${(@k)servers}"; do
        ip_path="${servers[$key]}"
        mount_point="$HOME/mounted_servers/$key"

        # Create the mount point directory if it doesn't exist
        mkdir -p $mount_point

        # Mount the server using sshfs
        sshfs vaden@${ip_path} $mount_point -o follow_symlinks -o idmap=user
    done
}

# Function to unmount all servers
unmount_all_servers() {
    # Iterate through the servers and unmount each one
    for key in "${(@k)servers}"; do
        mount_point="$HOME/mounted_servers/$key"

        # Unmount the server
        fusermount -u $mount_point
    done
}

