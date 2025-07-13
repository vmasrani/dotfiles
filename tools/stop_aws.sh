#!/bin/bash

# === Config ===
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
VOLUME_ID="vol-0b96a6d8df56c0f85"  # Optional: if replacing root volume
AVAILABILITY_ZONE="us-west-2c"
DEVICE_NAME="/dev/sda1"

echo "Stopping instance $INSTANCE_ID..."
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" > /dev/null
aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
echo "Instance stopped."

echo "Detaching volume $VOLUME_ID..."
aws ec2 detach-volume \
  --volume-id "$VOLUME_ID" \
  --instance-id "$INSTANCE_ID" \
  --device "$DEVICE_NAME"

aws ec2 wait volume-available --volume-ids "$VOLUME_ID"
echo "Volume $VOLUME_ID detached and available."
