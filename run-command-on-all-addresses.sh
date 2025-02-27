#!/bin/bash

# List of IP addresses
# ips=("7.184.9.95")
# ips=("10.213.96.116" "10.213.96.114" "10.193.241.206")
# ips=("10.209.172.42" "7.184.9.95")
ips=("10.213.96.116" "10.213.96.114" "10.193.241.206" "7.184.9.95")

# SSH username
user="vaden"

# The Python command you want to run (provided as an argument)
my_command="$1"

# Directory to change into on the target machine
target_directory="$HOME/dev/projects/llm-watermarking"


# Tmux session name
session_name="from_117"

for ip in "${ips[@]}"; do
  echo "Running command on $ip..."

  # SSH into the IP and run the tmux command
  ssh "$user@$ip" bash -c "\"
  # Check if the tmux session exists, create it if it doesn't
  tmux has-session -t $session_name 2>/dev/null || tmux new-session -d -s $session_name

  # Change directory on the target machine
  tmux send-keys -t $session_name  \\\"cd $target_directory\\\" C-m

  # Send the Python command to the tmux session
  tmux send-keys -t $session_name \\\"$my_command\\\" C-m
  \""
done

echo "Commands sent to all IPs."
