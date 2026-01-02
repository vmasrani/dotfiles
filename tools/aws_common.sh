#!/bin/zsh
# Shared AWS EC2 management functions and configuration

# Source gum utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../shell/gum_utils.sh"

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
SSH_HOST="vodasafe-aws"
SSH_CONFIG="$HOME/.ssh/config"
VOLUME_ID="vol-0f6433d9d70214a83"
AVAILABILITY_ZONE="ca-central-1"
DEVICE_NAME="/dev/sda1"

# === Functions ===

select_instance() {
    local title="$1"
    local color="${2:-$GUM_COLOR_INFO}"

    gum_box "$title" "$color"

    local instance_type
    instance_type=$(gum_choose --header "Select instance type:" "metal" "compute")

    if [[ -z "$instance_type" ]]; then
        gum_error "No instance selected"
        exit 1
    fi

    INSTANCE_ID="${INSTANCES[$instance_type]}"
    DISPLAY_NAME="${INSTANCE_TYPES[$instance_type]}"

    gum_info "Selected: $instance_type ($DISPLAY_NAME)"
    echo "$instance_type"
}

get_instance_state() {
    local instance_id="$1"
    gum_spin_quick "Checking instance state..." \
        aws ec2 describe-instances --instance-ids "$instance_id" \
        --query "Reservations[0].Instances[0].State.Name" \
        --output text --no-cli-pager
}

wait_for_instance_stopped() {
    local instance_id="$1"
    gum_spin_wait "Waiting for instance to stop..." \
        aws ec2 wait instance-stopped --instance-ids "$instance_id" --no-cli-pager
}

wait_for_instance_running() {
    local instance_id="$1"
    gum_spin_wait "Waiting for instance to start..." \
        aws ec2 wait instance-running --instance-ids "$instance_id" --no-cli-pager
}

wait_for_volume_available() {
    local volume_id="$1"
    gum_spin_wait "Waiting for volume..." \
        aws ec2 wait volume-available --volume-ids "$volume_id" --no-cli-pager
}

wait_for_volume_attached() {
    local volume_id="$1"
    gum_spin_wait "Waiting for volume to attach..." \
        aws ec2 wait volume-in-use --volume-ids "$volume_id" --no-cli-pager
}

stop_instance() {
    local instance_id="$1"
    local state="$2"

    if [[ "$state" = "stopped" ]]; then
        gum_success "Instance is already stopped"
        return 0
    elif [[ "$state" = "running" ]]; then
        gum_warning "Instance is running. Stopping..."
        aws ec2 stop-instances --instance-ids "$instance_id" --no-cli-pager > /dev/null
        wait_for_instance_stopped "$instance_id"
        gum_success "Instance stopped"
    else
        gum_warning "Instance is in state: $state. Waiting for it to stop..."
        wait_for_instance_stopped "$instance_id"
        gum_success "Instance stopped"
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

    gum_spin_quick "Checking current root volume..." \
        aws ec2 describe-instances --instance-ids "$instance_id" \
        --query "Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName=='$device_name'].Ebs.VolumeId" \
        --output text --no-cli-pager
}

update_ssh_config() {
    local new_ip="$1"
    local host_name="$SSH_HOST"
    local config_file="$SSH_CONFIG"

    if [[ ! -f "$config_file" ]]; then
        gum_warning "SSH config file not found at $config_file"
        return 1
    fi

    # Check if the host exists in the config
    if ! rg --quiet "^Host $host_name\$" "$config_file"; then
        gum_warning "Host $host_name not found in SSH config"
        return 1
    fi

    # Update the HostName for this host
    # Use sed to replace the HostName line that follows the Host line
    sed -i.bak "/^Host $host_name\$/,/^Host / s/^\s*HostName\s\+.*/  HostName  $new_ip/" "$config_file"

    gum_success "Updated SSH config: $host_name -> $new_ip"
}

