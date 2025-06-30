#!/bin/bash
# shellcheck shell=bash
# ===================================================================
# AWS EC2 Instance Management Script
# ===================================================================
# Manages EC2 instance startup with volume attachment
# Usage: ./start_aws.sh
# ===================================================================

# === Configuration ===
# INSTANCE_ID="i-0f7a56bf2bb58fab2"
INSTANCE_ID="i-02cdd250f93ade49c"
KEY_PATH="$HOME/.ssh/vaden-vodasafe-aws.pem"
SSH_USER="vaden"  # Change to ubuntu, admin, etc. as needed
VOLUME_ID="vol-0b96a6d8df56c0f85"  # Optional: if replacing root volume
AVAILABILITY_ZONE="us-west-2c"
DEVICE_NAME="/dev/sda1"

# Check if instance is running
INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].State.Name" \
  --output text)

if [ "$INSTANCE_STATE" = "running" ]; then
  echo "Instance $INSTANCE_ID is already running. Skipping all operations."
  exit 0
fi

echo "Stopping instance $INSTANCE_ID to prepare for root volume replacement..."
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" > /dev/null
aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
echo "Instance stopped."

echo "Detaching current root volume (if present)..."
CURRENT_ROOT_VOL=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName=='$DEVICE_NAME'].Ebs.VolumeId" \
  --output text)

if [ -n "$CURRENT_ROOT_VOL" ]; then
  aws ec2 detach-volume --volume-id "$CURRENT_ROOT_VOL" --instance-id "$INSTANCE_ID" --device "$DEVICE_NAME" > /dev/null
  aws ec2 wait volume-available --volume-ids "$CURRENT_ROOT_VOL" > /dev/null
  echo "Detached volume $CURRENT_ROOT_VOL"
else
  echo "No volume attached at $DEVICE_NAME"
fi

echo "Attaching volume $VOLUME_ID to instance $INSTANCE_ID at $DEVICE_NAME..."
aws ec2 attach-volume \
  --volume-id "$VOLUME_ID" \
  --instance-id "$INSTANCE_ID" \
  --device "$DEVICE_NAME" > /dev/null

aws ec2 wait volume-in-use --volume-ids "$VOLUME_ID" > /dev/null
echo "Volume attached."

echo "Starting instance..."
aws ec2 start-instances --instance-ids "$INSTANCE_ID" > /dev/null
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
echo "Instance started."

PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

echo "Connecting to instance at $PUBLIC_IP"
