#!/bin/bash
# Find what's using the camera

echo "========================================"
echo "Finding Camera Users"
echo "========================================"

echo
echo "1. Checking /dev/video0..."
echo "-------------------------------------------"
sudo fuser -v /dev/video0 2>&1

echo
echo "2. Checking /dev/video1..."
echo "-------------------------------------------"
sudo fuser -v /dev/video1 2>&1

echo
echo "3. Listing all processes with 'video' open..."
echo "-------------------------------------------"
sudo lsof | grep -i video 2>&1 | head -20

echo
echo "4. Camera-related processes..."
echo "-------------------------------------------"
ps aux | grep -iE "camera|video|gst|argus|nvargus" | grep -v grep

echo
echo "5. Checking systemd services..."
echo "-------------------------------------------"
systemctl list-units --type=service --state=running | grep -iE "camera|video|argus"

echo
echo "========================================"
echo "Done!"
echo "========================================"
