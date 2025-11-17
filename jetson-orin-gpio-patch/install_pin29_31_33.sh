#!/bin/bash

# Pin 29, 31, 33 GPIO Overlay Installation Script for Jetson Orin Nano

set -e

echo "=========================================="
echo "Pin 29, 31, 33 GPIO Overlay Installation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (sudo)"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DTS_FILE="$SCRIPT_DIR/pin29_31_33_as_gpio.dts"
DTBO_FILE="$SCRIPT_DIR/pin29_31_33_as_gpio.dtbo"

# Check if DTS file exists
if [ ! -f "$DTS_FILE" ]; then
    echo "❌ Error: $DTS_FILE not found"
    exit 1
fi

# Compile DTS to DTBO
echo "🔧 Compiling Device Tree Overlay..."
dtc -I dts -O dtb -o "$DTBO_FILE" "$DTS_FILE"

if [ ! -f "$DTBO_FILE" ]; then
    echo "❌ Error: Compilation failed"
    exit 1
fi

echo "✅ Compilation successful: $DTBO_FILE"

# Copy to /boot
echo "📦 Installing overlay to /boot..."
cp "$DTBO_FILE" /boot/

echo "✅ Overlay installed to /boot/pin29_31_33_as_gpio.dtbo"

# Check if overlay is already in extlinux.conf
if grep -q "pin29_31_33_as_gpio.dtbo" /boot/extlinux/extlinux.conf; then
    echo "✅ Overlay already configured in extlinux.conf"
else
    echo "⚙️  Adding overlay to extlinux.conf..."

    # Backup extlinux.conf
    cp /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.backup.$(date +%Y%m%d_%H%M%S)

    # Add overlay to FDT line
    sed -i '/FDT \/boot\/dtb\/kernel_tegra234-p3767-0000-p3509-a02.dtb/s/$/ \/boot\/pin29_31_33_as_gpio.dtbo/' /boot/extlinux/extlinux.conf

    echo "✅ Overlay added to extlinux.conf"
fi

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "📌 GPIO Pin Mapping:"
echo "   Pin 29 → GPIO 417"
echo "   Pin 31 → GPIO 419"
echo "   Pin 33 → GPIO 391"
echo ""
echo "⚠️  REBOOT REQUIRED to activate GPIO pins"
echo ""
echo "After reboot, verify with:"
echo "   ls /sys/class/gpio/"
echo "   echo 417 > /sys/class/gpio/export"
echo "   echo 419 > /sys/class/gpio/export"
echo "   echo 391 > /sys/class/gpio/export"
echo ""
