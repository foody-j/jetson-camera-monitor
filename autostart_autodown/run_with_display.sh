#!/bin/bash
# Run ROBOTCAM with display enabled

echo "Setting up display..."
export DISPLAY=:0

echo "Starting ROBOTCAM with monitoring window..."
echo "Press Ctrl+C to stop"
echo ""

cd /home/dkutest/my_ai_project/autostart_autodown
python3 ROBOTCAM_HEADLESS.py
