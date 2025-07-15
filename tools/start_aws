#!/bin/bash
# shellcheck shell=bash
# ===================================================================
# AWS EC2 Instance Management Script (Improved)
# ===================================================================
# Manages EC2 instance startup with volume attachment
# Usage: ./start_aws.sh
# ===================================================================

read -p "Enter instance type (metal/compute): " INSTANCE_TYPE

if [ "$INSTANCE_TYPE" == "metal" ]; then
    INSTANCE_ID="i-0858d0e3943d34004"
elif [ "$INSTANCE_TYPE" == "compute" ]; then
    INSTANCE_ID="i-06e021e025d37666d"
else
    echo "Invalid instance type. Please enter 'metal' or 'compute'."
    exit 1
fi

KEY_PATH="$HOME/.ssh/vaden-vodasafe-aws.pem"
SSH_USER="vaden"  # Change to ubuntu, admin, etc. as needed
VOLUME_ID="vol-0f6433d9d70214a83"  # Optional: if replacing root volume
AVAILABILITY_ZONE="ca-central-1"
DEVICE_NAME="/dev/sda1"

# Check if instance is running
INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].State.Name" \
  --output text  --no-cli-pager )

if [ "$INSTANCE_STATE" = "running" ]; then
  echo "Instance $INSTANCE_ID is already running. Skipping all operations."
  exit 0
fi

echo "Stopping instance $INSTANCE_ID to prepare for root volume replacement..."
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --no-cli-pager
aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID" --no-cli-pager
echo "Instance stopped."

echo "Checking current root volume..."
CURRENT_ROOT_VOL=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName=='$DEVICE_NAME'].Ebs.VolumeId" \
  --output text --no-cli-pager)

# Check if the desired volume is already attached to the correct instance at the correct device
ATTACHED_INSTANCE=$(aws ec2 describe-volumes \
  --volume-ids "$VOLUME_ID" \
  --query "Volumes[0].Attachments[0].InstanceId" \
  --output text --no-cli-pager)
ATTACHED_DEVICE=$(aws ec2 describe-volumes \
  --volume-ids "$VOLUME_ID" \
  --query "Volumes[0].Attachments[0].Device" \
  --output text --no-cli-pager)

if [ "$ATTACHED_INSTANCE" == "$INSTANCE_ID" ] && [ "$ATTACHED_DEVICE" == "$DEVICE_NAME" ]; then
  echo "Volume $VOLUME_ID is already attached to $INSTANCE_ID at $DEVICE_NAME. Skipping detach/attach."
else
  # If the volume is attached to a different instance, detach it automatically
  if [ "$ATTACHED_INSTANCE" != "None" ] && [ "$ATTACHED_INSTANCE" != "$INSTANCE_ID" ]; then
    echo "Volume $VOLUME_ID is attached to another instance ($ATTACHED_INSTANCE). Detaching..."
    aws ec2 detach-volume --volume-id "$VOLUME_ID" --instance-id "$ATTACHED_INSTANCE" --no-cli-pager
    aws ec2 wait volume-available --volume-ids "$VOLUME_ID" --no-cli-pager
    echo "Detached volume $VOLUME_ID from $ATTACHED_INSTANCE"
  fi

  # Detach current root volume if present and different from desired
  if [ -n "$CURRENT_ROOT_VOL" ] && [ "$CURRENT_ROOT_VOL" != "$VOLUME_ID" ]; then
    echo "Detaching current root volume $CURRENT_ROOT_VOL..."
    aws ec2 detach-volume --volume-id "$CURRENT_ROOT_VOL" --instance-id "$INSTANCE_ID" --device "$DEVICE_NAME" --no-cli-pager
    aws ec2 wait volume-available --volume-ids "$CURRENT_ROOT_VOL" --no-cli-pager
    echo "Detached volume $CURRENT_ROOT_VOL"
  else
    echo "No root volume to detach or already using desired volume."
  fi

  # Attach the desired volume
  echo "Attaching volume $VOLUME_ID to instance $INSTANCE_ID at $DEVICE_NAME..."
  aws ec2 attach-volume \
    --volume-id "$VOLUME_ID" \
    --instance-id "$INSTANCE_ID" \
    --device "$DEVICE_NAME" --no-cli-pager

  # Wait for attachment
  aws ec2 wait volume-in-use --volume-ids "$VOLUME_ID" --no-cli-pager
  echo "Volume attached."
fi

echo "Starting instance..."
aws ec2 start-instances --instance-ids "$INSTANCE_ID" --no-cli-pager
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --no-cli-pager
echo "Instance started."

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text --no-cli-pager)

echo "Connecting to instance at $PUBLIC_IP"

# ===================================================================
# Original script below (commented out for reference)
# ===================================================================
:
# read -p "Enter instance type (metal/compute): " INSTANCE_TYPE

# if [ "$INSTANCE_TYPE" == "metal" ]; then
#     INSTANCE_ID="i-0858d0e3943d34004"
# elif [ "$INSTANCE_TYPE" == "compute" ]; then
#     INSTANCE_ID="i-06e021e025d37666d"
# else
#     echo "Invalid instance type. Please enter '\''metal'\'' or '\''compute'\''."
#     exit 1
# fi

# KEY_PATH="$HOME/.ssh/vaden-vodasafe-aws.pem"
# SSH_USER="vaden"  # Change to ubuntu, admin, etc. as needed
# VOLUME_ID="vol-0f6433d9d70214a83"  # Optional: if replacing root volume
# AVAILABILITY_ZONE="ca-central-1"
# DEVICE_NAME="/dev/sda1"

# # Check if instance is running
# INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
#   --query "Reservations[0].Instances[0].State.Name" \
#   --output text  --no-cli-pager )

# if [ "$INSTANCE_STATE" = "running" ]; then
#   echo "Instance $INSTANCE_ID is already running. Skipping all operations."
#   exit 0
# fi

# echo "Stopping instance $INSTANCE_ID to prepare for root volume replacement..."
# aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --no-cli-pager
# aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID" --no-cli-pager
# echo "Instance stopped."

# echo "Detaching current root volume (if present)..."
# CURRENT_ROOT_VOL=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
#   --query "Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName=='$DEVICE_NAME'].Ebs.VolumeId" \
#   --output text --no-cli-pager)

# if [ -n "$CURRENT_ROOT_VOL" ]; then
#   aws ec2 detach-volume --volume-id "$CURRENT_ROOT_VOL" --instance-id "$INSTANCE_ID" --device "$DEVICE_NAME" --no-cli-pager
#   aws ec2 wait volume-available --volume-ids "$CURRENT_ROOT_VOL" --no-cli-pager
#   echo "Detached volume $CURRENT_ROOT_VOL"
# else
#   echo "No volume attached at $DEVICE_NAME"
# fi

# echo "Attaching volume $VOLUME_ID to instance $INSTANCE_ID at $DEVICE_NAME..."
# aws ec2 attach-volume \
#   --volume-id "$VOLUME_ID" \
#   --instance-id "$INSTANCE_ID" \
#   --device "$DEVICE_NAME" --no-cli-pager

# aws ec2 wait volume-in-use --volume-ids "$VOLUME_ID" --no-cli-pager
# echo "Volume attached."

# echo "Starting instance..."
# aws ec2 start-instances --instance-ids "$INSTANCE_ID" --no-cli-pager
# aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --no-cli-pager
# echo "Instance started."

# PUBLIC_IP=$(aws ec2 describe-instances \
#   --instance-ids "$INSTANCE_ID" \
#   --query "Reservations[0].Instances[0].PublicIpAddress" \
#   --output text --no-cli-pager)

# echo "Connecting to instance at $PUBLIC_IP"
