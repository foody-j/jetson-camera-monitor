#!/bin/bash
# Installation script for ROBOTCAM - All Dependencies
# Installs everything needed for both headless and GUI versions

echo "Installing ALL dependencies for ROBOTCAM..."
echo "=============================================="

# Update package list
echo "1. Updating package list..."
apt update

# Install system packages
echo "2. Installing system packages..."
apt install -y python3-pip python3-tk

echo "3. Installing Korean fonts..."
apt install -y fonts-nanum fonts-nanum-coding

# Install Python packages
echo "4. Installing ultralytics (YOLO)..."
pip3 install ultralytics

echo "5. Installing paho-mqtt (MQTT communication)..."
pip3 install paho-mqtt

echo "6. Installing Pillow (PIL - image handling for GUI)..."
pip3 install pillow

echo "7. Installing opencv-python (if not included with ultralytics)..."
pip3 install opencv-python

echo ""
echo "=============================================="
echo "✅ All dependencies installed successfully!"
echo ""
echo "You can now run:"
echo ""
echo "  Headless version (no GUI):"
echo "    cd /project/autostart_autodown"
echo "    python3 ROBOTCAM_HEADLESS.py"
echo ""
echo "  Integrated GUI (Jetson #1):"
echo "    cd /project/autostart_autodown"
echo "    python3 JETSON1_INTEGRATED.py"
echo ""
