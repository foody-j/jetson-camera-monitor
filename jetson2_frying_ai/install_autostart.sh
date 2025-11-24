#!/bin/bash
#
# Installation script for Jetson #2 Frying AI Monitoring System
# Auto-starts the AI monitoring system on boot with GMSL camera support
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="jetson2-ai.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"

echo "=========================================="
echo "Jetson #2 AI Monitoring System - Installation"
echo "=========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "⚠️  Warning: This doesn't appear to be a Jetson device."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: Service file not found: $SERVICE_FILE"
    exit 1
fi

# Check if JETSON2_INTEGRATED.py exists
if [ ! -f "$SCRIPT_DIR/JETSON2_INTEGRATED.py" ]; then
    echo "❌ Error: JETSON2_INTEGRATED.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if config file exists
if [ ! -f "$SCRIPT_DIR/config_jetson2.json" ]; then
    echo "❌ Error: config_jetson2.json not found in $SCRIPT_DIR"
    exit 1
fi

echo "📋 Installation Details:"
echo "   Script directory: $SCRIPT_DIR"
echo "   Service file: $SERVICE_FILE"
echo "   User: $USER"
echo ""

# GMSL cameras are always used for Jetson #2
echo "📷 Camera Configuration: GMSL (4 cameras)"
echo ""

# Install v4l-utils for GMSL cameras
echo "🔧 Checking for v4l-utils (required for GMSL cameras)..."
if ! command -v v4l2-ctl &> /dev/null; then
    echo "   Installing v4l-utils..."
    sudo apt update -qq
    sudo apt install -y v4l-utils
    echo "   ✅ v4l-utils installed"
else
    echo "   ✅ v4l-utils already installed"
fi

# Install camera driver auto-load service
echo ""
echo "📷 Setting up GMSL camera driver auto-load..."

CAMERA_AUTOSTART_DIR="$SCRIPT_DIR/camera_autostart"
CAMERA_SERVICE_NAME="sensing-camera.service"

if [ -d "$CAMERA_AUTOSTART_DIR" ]; then
    # Make camera driver script executable
    chmod +x "$CAMERA_AUTOSTART_DIR/camera_driver_autoload.sh"

    # Install camera driver service
    echo "   Installing camera driver service..."
    sudo cp "$CAMERA_AUTOSTART_DIR/$CAMERA_SERVICE_NAME" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable $CAMERA_SERVICE_NAME

    # Check if already running
    if systemctl is-active --quiet $CAMERA_SERVICE_NAME; then
        echo "   ✅ Camera driver service already running"
    else
        echo "   Starting camera driver service..."
        sudo systemctl start $CAMERA_SERVICE_NAME
        sleep 3

        if systemctl is-active --quiet $CAMERA_SERVICE_NAME; then
            echo "   ✅ Camera driver service started"
        else
            echo "   ⚠️  Camera driver service failed to start"
            echo "      Check logs: sudo journalctl -u $CAMERA_SERVICE_NAME"
        fi
    fi

    # Verify camera devices
    echo "   Verifying camera devices..."
    CAMERA_COUNT=$(ls /dev/video* 2>/dev/null | wc -l)
    if [ $CAMERA_COUNT -gt 0 ]; then
        echo "   ✅ Found $CAMERA_COUNT camera device(s)"
        ls /dev/video* 2>/dev/null | sed 's/^/      /'
    else
        echo "   ⚠️  No camera devices found. Driver may need manual loading."
    fi
else
    echo "   ⚠️  Camera autostart directory not found: $CAMERA_AUTOSTART_DIR"
    echo "      Camera drivers will need to be loaded manually"
fi

# Check Python dependencies
echo ""
echo "🐍 Checking Python dependencies..."
REQUIRED_PACKAGES=("cv2" "PIL" "ultralytics" "paho.mqtt.client")
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "   ⚠️  Missing packages: ${MISSING_PACKAGES[*]}"
    echo "   Please install them first"
    read -p "   Continue installation without dependencies? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "   ✅ All required packages installed"
fi

# Make script executable
echo ""
echo "🔧 Setting executable permissions..."
chmod +x "$SCRIPT_DIR/JETSON2_INTEGRATED.py"
echo "   ✅ Permissions set"

# Install systemd service
echo ""
echo "⚙️  Installing systemd service..."

# Stop service if already running
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "   Stopping existing service..."
    sudo systemctl stop $SERVICE_NAME
fi

# Copy service file
echo "   Copying service file to /etc/systemd/system/..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/

# Reload systemd
echo "   Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable service
echo "   Enabling service to start on boot..."
sudo systemctl enable $SERVICE_NAME

echo "   ✅ Service installed and enabled"

# Ask if user wants to start service now
echo ""
read -p "🚀 Start the AI monitoring system now? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "   Starting service..."
    sudo systemctl start $SERVICE_NAME
    sleep 2

    # Check status
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "   ✅ Service started successfully!"
    else
        echo "   ⚠️  Service failed to start. Check status with:"
        echo "      sudo systemctl status $SERVICE_NAME"
        echo "      sudo journalctl -u $SERVICE_NAME -f"
    fi
fi

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "📖 Useful Commands:"
echo "   Check status:    sudo systemctl status $SERVICE_NAME"
echo "   View logs:       sudo journalctl -u $SERVICE_NAME -f"
echo "   Stop service:    sudo systemctl stop $SERVICE_NAME"
echo "   Start service:   sudo systemctl start $SERVICE_NAME"
echo "   Restart service: sudo systemctl restart $SERVICE_NAME"
echo "   Disable service: sudo systemctl disable $SERVICE_NAME"
echo ""
echo "   Camera driver:"
echo "   Check status:    sudo systemctl status $CAMERA_SERVICE_NAME"
echo "   View logs:       sudo journalctl -u $CAMERA_SERVICE_NAME -f"
echo ""
echo "📝 Configuration:"
echo "   Edit settings in: $SCRIPT_DIR/config_jetson2.json"
echo "   After config changes, restart: sudo systemctl restart $SERVICE_NAME"
echo ""
echo "🎯 The AI monitoring system will now start automatically on boot!"
echo ""
