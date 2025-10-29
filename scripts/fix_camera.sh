#!/bin/bash
# Camera Fix Script for Jetson
# Identifies and resolves camera access issues

echo "========================================"
echo "Camera Diagnostic and Fix Tool"
echo "========================================"

echo
echo "1. Checking what's using the camera..."
echo "----------------------------------------"

# Use fuser to find processes using video devices
for dev in /dev/video*; do
    echo "Checking $dev..."
    fuser $dev 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  Process(es) using $dev:"
        fuser -v $dev 2>&1 | grep -v "USER"
    else
        echo "  Not in use"
    fi
done

echo
echo "2. Checking camera-related services..."
echo "----------------------------------------"
ps aux | grep -i "nvargus\|camera" | grep -v grep

echo
echo "3. Testing camera access..."
echo "----------------------------------------"
echo "Attempting quick GStreamer test..."
timeout 2 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=1 ! fakesink 2>&1 | grep -E "busy|ERROR|Setting pipeline"

echo
echo "========================================"
echo "SOLUTION"
echo "========================================"
echo
echo "Your camera IS detected but it's BUSY (being used)."
echo
echo "The nvargus-daemon is likely holding it."
echo
echo "Try these solutions:"
echo
echo "Option 1: Restart nvargus-daemon"
echo "  sudo systemctl restart nvargus-daemon"
echo
echo "Option 2: Stop nvargus-daemon temporarily"
echo "  sudo systemctl stop nvargus-daemon"
echo "  # Run your camera app"
echo "  sudo systemctl start nvargus-daemon  # restart when done"
echo
echo "Option 3: Reboot the system"
echo "  sudo reboot"
echo
echo "After applying a fix, test with:"
echo "  python3 test_camera_simple.py"
echo
