#!/bin/zsh
# Shared AWS EC2 management functions and configuration

# === Configuration ===
typeset -A INSTANCES=(
    ["metal"]="i-0858d0e3943d34004"
    ["compute"]="i-06e021e025d37666d"
)

typeset -A INSTANCE_TYPES=(
    ["metal"]="g4dn.metal"
    ["compute"]="c6i.8xlarge"
)

KEY_PATH="$HOME/.ssh/vaden-vodasafe-aws.pem"
SSH_USER="vaden"
VOLUME_ID="vol-0f6433d9d70214a83"
AVAILABILITY_ZONE="ca-central-1"
DEVICE_NAME="/dev/sda1"

# === Functions ===

select_instance() {
    local title="$1"
    local color="${2:-212}"

    gum style --border rounded --padding "1 2" --border-foreground "$color" "$title"

    local instance_type
    instance_type=$(gum choose --header "Select instance type:" "metal" "compute")

    if [[ -z "$instance_type" ]]; then
        gum style --foreground 196 "✗ No instance selected"
        exit 1
    fi

    INSTANCE_ID="${INSTANCES[$instance_type]}"
    DISPLAY_NAME="${INSTANCE_TYPES[$instance_type]}"

    gum style --foreground "$color" "→ Selected: $instance_type ($DISPLAY_NAME)"
    echo "$instance_type"
}

get_instance_state() {
    local instance_id="$1"
    gum spin --spinner dot --title "Checking instance state..." -- \
        aws ec2 describe-instances --instance-ids "$instance_id" \
        --query "Reservations[0].Instances[0].State.Name" \
        --output text --no-cli-pager
}

wait_for_instance_stopped() {
    local instance_id="$1"
    gum spin --spinner meter --title "Waiting for instance to stop..." -- \
        aws ec2 wait instance-stopped --instance-ids "$instance_id" --no-cli-pager
}

wait_for_instance_running() {
    local instance_id="$1"
    gum spin --spinner meter --title "Waiting for instance to start..." -- \
        aws ec2 wait instance-running --instance-ids "$instance_id" --no-cli-pager
}

wait_for_volume_available() {
    local volume_id="$1"
    gum spin --spinner meter --title "Waiting for volume..." -- \
        aws ec2 wait volume-available --volume-ids "$volume_id" --no-cli-pager
}

wait_for_volume_attached() {
    local volume_id="$1"
    gum spin --spinner meter --title "Waiting for volume to attach..." -- \
        aws ec2 wait volume-in-use --volume-ids "$volume_id" --no-cli-pager
}

stop_instance() {
    local instance_id="$1"
    local state="$2"

    if [[ "$state" = "stopped" ]]; then
        gum style --foreground 46 "✓ Instance is already stopped"
        return 0
    elif [[ "$state" = "running" ]]; then
        gum style --foreground 208 "⚠ Instance is running. Stopping..."
        aws ec2 stop-instances --instance-ids "$instance_id" --no-cli-pager > /dev/null
        wait_for_instance_stopped "$instance_id"
        gum style --foreground 46 "✓ Instance stopped"
    else
        gum style --foreground 208 "⚠ Instance is in state: $state. Waiting for it to stop..."
        wait_for_instance_stopped "$instance_id"
        gum style --foreground 46 "✓ Instance stopped"
    fi
}

get_public_ip() {
    local instance_id="$1"
    aws ec2 describe-instances \
        --instance-ids "$instance_id" \
        --query "Reservations[0].Instances[0].PublicIpAddress" \
        --output text --no-cli-pager
}

get_volume_attachment_info() {
    local volume_id="$1"
    local query="$2"

    aws ec2 describe-volumes \
        --volume-ids "$volume_id" \
        --query "$query" \
        --output text --no-cli-pager 2>/dev/null || echo "None"
}

get_current_root_volume() {
    local instance_id="$1"
    local device_name="$2"

    gum spin --spinner dot --title "Checking current root volume..." -- \
        aws ec2 describe-instances --instance-ids "$instance_id" \
        --query "Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName=='$device_name'].Ebs.VolumeId" \
        --output text --no-cli-pager
}

