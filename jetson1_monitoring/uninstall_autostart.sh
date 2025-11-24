#!/bin/bash
#
# Uninstallation script for Jetson #1 Integrated Monitoring System
#

set -e  # Exit on error

SERVICE_NAME="jetson-monitor.service"

echo "=========================================="
echo "Jetson #1 Monitoring System - Uninstall"
echo "=========================================="
echo ""

read -p "⚠️  This will remove the auto-start service. Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Stop service if running
echo "🛑 Stopping service..."
if systemctl is-active --quiet $SERVICE_NAME; then
    sudo systemctl stop $SERVICE_NAME
    echo "   ✅ Service stopped"
else
    echo "   ℹ️  Service not running"
fi

# Disable service
echo "🔧 Disabling service..."
if systemctl is-enabled --quiet $SERVICE_NAME; then
    sudo systemctl disable $SERVICE_NAME
    echo "   ✅ Service disabled"
else
    echo "   ℹ️  Service not enabled"
fi

# Remove service file
echo "🗑️  Removing service file..."
if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
    sudo rm /etc/systemd/system/$SERVICE_NAME
    echo "   ✅ Service file removed"
else
    echo "   ℹ️  Service file not found"
fi

# Reload systemd
echo "⚙️  Reloading systemd daemon..."
sudo systemctl daemon-reload
sudo systemctl reset-failed
echo "   ✅ Systemd reloaded"

echo ""
echo "=========================================="
echo "✅ Uninstallation Complete!"
echo "=========================================="
echo ""
echo "The monitoring system will no longer start automatically on boot."
echo "You can still run it manually:"
echo "   cd $(dirname "${BASH_SOURCE[0]}")"
echo "   python3 JETSON1_INTEGRATED.py"
echo ""
