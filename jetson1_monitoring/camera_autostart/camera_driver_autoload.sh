#!/bin/bash
#
# Auto-load SENSING camera drivers at boot
# Non-interactive version for systemd service
#

# Path to manufacturer's driver folder
DRIVER_DIR="/home/dkuyj/jetson-camera-monitor/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3"
KO_DIR="${DRIVER_DIR}/ko"

# ========== CAMERA RESOLUTION CONFIGURATION ==========
# Resolution modes:
#   0 = 1920x1080 (Full HD)
#   1 = 1920x1536 (3:2 aspect ratio)
#   2 = 2880x1860 (High resolution)
#   3 = 3840x2160 (4K)
#   4 = 1280x720  (HD)

# Set desired resolution for all cameras (0-4)
RESOLUTION_MODE=1  # Default: 1920x1536

# Enable/disable automatic resolution configuration
AUTO_CONFIGURE_RESOLUTION=true
# ====================================================

echo "[$(date)] SENSING Camera Driver Auto-load"

# Load MAX96712 GMSL deserializer driver
if [ ! -f "${KO_DIR}/max96712.ko" ]; then
    echo "[ERROR] max96712.ko not found in ${KO_DIR}"
    exit 1
fi

if [ "$(sudo lsmod | grep max96712)" == "" ]; then
    echo "[INFO] Loading max96712.ko..."
    sudo insmod "${KO_DIR}/max96712.ko"
    if [ $? -eq 0 ]; then
        echo "[OK] max96712.ko loaded successfully"
    else
        echo "[ERROR] Failed to load max96712.ko"
        exit 1
    fi
else
    echo "[INFO] max96712 already loaded"
fi

# Load SENSING GMSL2 camera driver
if [ ! -f "${KO_DIR}/sgx-yuv-gmsl2.ko" ]; then
    echo "[ERROR] sgx-yuv-gmsl2.ko not found in ${KO_DIR}"
    exit 1
fi

if [ "$(sudo lsmod | grep gmsl2)" == "" ]; then
    # GMSLMODE settings for 4 cameras
    # Change these values based on your camera types:
    #   0 = GMSL (older)
    #   1 = GMSL2/6G (6Gbps)
    #   2 = GMSL2/3G (3Gbps)

    # Default: All cameras set to GMSL2/6G (mode 1)
    CAM1_TYPE=2
    CAM2_TYPE=2
    CAM3_TYPE=2
    CAM4_TYPE=2

    echo "[INFO] Loading sgx-yuv-gmsl2.ko with GMSLMODE_1=${CAM1_TYPE},${CAM2_TYPE},${CAM3_TYPE},${CAM4_TYPE}..."
    sudo insmod "${KO_DIR}/sgx-yuv-gmsl2.ko" GMSLMODE_1=${CAM1_TYPE},${CAM2_TYPE},${CAM3_TYPE},${CAM4_TYPE}

    if [ $? -eq 0 ]; then
        echo "[OK] sgx-yuv-gmsl2.ko loaded successfully"
    else
        echo "[ERROR] Failed to load sgx-yuv-gmsl2.ko"
        exit 1
    fi
else
    echo "[INFO] sgx-yuv-gmsl2 already loaded"
fi

# Wait for devices to initialize
sleep 2

# Configure NVCSI clock (critical for camera power!)
echo "[INFO] Configuring NVCSI clock..."
if [ -d "/sys/kernel/debug/bpmp/debug/clk/nvcsi" ]; then
    echo 1 > /sys/kernel/debug/bpmp/debug/clk/nvcsi/mrq_rate_locked
    echo 214300000 > /sys/kernel/debug/bpmp/debug/clk/nvcsi/rate
    echo "[OK] NVCSI clock configured to 214.3 MHz"
else
    echo "[ERROR] NVCSI clock interface not found"
    exit 1
fi

# Verify camera devices
echo "[INFO] Checking camera devices..."
for i in 0 1 2 3; do
    if [ -e "/dev/video${i}" ]; then
        echo "[OK] /dev/video${i} exists"
    else
        echo "[WARN] /dev/video${i} not found"
    fi
done

# Configure camera resolutions
if [ "$AUTO_CONFIGURE_RESOLUTION" = true ]; then
    echo "[INFO] Configuring camera resolutions to mode ${RESOLUTION_MODE}..."

    # Check if v4l2-ctl is installed
    if ! command -v v4l2-ctl >/dev/null 2>&1; then
        echo "[WARN] v4l2-ctl not found. Installing v4l-utils..."
        sudo apt update -qq
        sudo apt install -y v4l-utils
    fi

    # Configure each camera
    for i in 0 1 2 3; do
        if [ -e "/dev/video${i}" ]; then
            echo "[INFO] Setting /dev/video${i} to resolution mode ${RESOLUTION_MODE}..."
            v4l2-ctl --set-ctrl bypass_mode=0,sensor_mode=${RESOLUTION_MODE} -d /dev/video${i} 2>/dev/null

            if [ $? -eq 0 ]; then
                echo "[OK] /dev/video${i} configured successfully"
            else
                echo "[WARN] Failed to configure /dev/video${i}"
            fi
        fi
    done

    echo "[INFO] Resolution configuration complete"
else
    echo "[INFO] Auto-configure resolution disabled (set AUTO_CONFIGURE_RESOLUTION=true to enable)"
fi

echo "[$(date)] Camera driver auto-load complete"
