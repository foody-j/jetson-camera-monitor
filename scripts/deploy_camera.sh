#!/bin/bash
# ========================================
# Camera-Enabled Docker Deployment Script
# For Jetson Orin with USB Camera
# ========================================

set -e  # Exit on error

echo "========================================"
echo "Camera-Enabled Docker Deployment"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "$1"
}

# ========================================
# Step 1: Check camera availability
# ========================================
echo
print_info "Step 1: Checking camera..."
if [ -e /dev/video0 ]; then
    print_success "Camera device /dev/video0 found"
else
    print_error "Camera device /dev/video0 not found!"
    print_warning "Please connect a USB camera and try again"
    exit 1
fi

# ========================================
# Step 2: Check if nvargus-daemon is blocking
# ========================================
echo
print_info "Step 2: Checking camera availability..."

# Test if camera is busy
if timeout 2 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=1 ! fakesink 2>&1 | grep -q "busy"; then
    print_warning "Camera is BUSY (likely held by nvargus-daemon)"

    print_info ""
    print_info "The nvargus-daemon is blocking camera access."
    print_info "This is common on Jetson devices."
    print_info ""
    print_info "Would you like to stop nvargus-daemon? (y/n)"
    print_warning "Note: This requires sudo password"

    read -p "Stop nvargus-daemon? [y/N]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Stopping nvargus-daemon..."
        sudo systemctl stop nvargus-daemon

        # Wait a moment
        sleep 1

        # Test again
        if timeout 2 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=1 ! fakesink 2>&1 | grep -q "busy"; then
            print_error "Camera still busy after stopping nvargus-daemon"
            print_info "Try rebooting the system or check for other processes using the camera"
            exit 1
        else
            print_success "Camera is now available!"
        fi
    else
        print_warning "Continuing without stopping nvargus-daemon..."
        print_warning "Camera may not work in Docker container"
    fi
else
    print_success "Camera is available and not busy"
fi

# ========================================
# Step 3: Setup X11 for GUI (if needed)
# ========================================
echo
print_info "Step 3: Setting up X11 for GUI display..."

# Allow Docker to connect to X server
xhost +local:docker > /dev/null 2>&1 || print_warning "Could not run xhost (GUI may not work)"

# Create X11 auth file for Docker
if [ ! -f /tmp/.docker.xauth ]; then
    touch /tmp/.docker.xauth
    xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f /tmp/.docker.xauth nmerge - 2>/dev/null || true
    chmod 644 /tmp/.docker.xauth
    print_success "X11 authentication file created"
else
    print_success "X11 authentication file exists"
fi

# ========================================
# Step 4: Build/Update Docker image
# ========================================
echo
print_info "Step 4: Building Docker image (this may take a while)..."

if docker compose build; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

# ========================================
# Step 5: Start Docker container
# ========================================
echo
print_info "Step 5: Starting Docker container..."

# Stop existing container if running
docker compose down 2>/dev/null || true

# Start new container
if docker compose up -d; then
    print_success "Docker container started"
else
    print_error "Failed to start Docker container"
    exit 1
fi

# ========================================
# Step 6: Verify camera in container
# ========================================
echo
print_info "Step 6: Verifying camera access in container..."

sleep 2  # Wait for container to fully start

# Check if video device is accessible in container
if docker compose exec ai-dev ls -l /dev/video0 2>/dev/null | grep -q video0; then
    print_success "Camera device is accessible in container"
else
    print_error "Camera device is NOT accessible in container"
    print_warning "Check docker compose.yml devices configuration"
fi

# ========================================
# Step 7: Test camera with Python
# ========================================
echo
print_info "Step 7: Testing camera with OpenCV..."

# Create a simple test script in the container
docker compose exec ai-dev python3 -c "
import cv2
cap = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
if cap.isOpened():
    ret, frame = cap.read()
    if ret:
        print('SUCCESS: Camera working! Frame shape:', frame.shape)
        exit(0)
    else:
        print('ERROR: Cannot read frames')
        exit(1)
else:
    print('ERROR: Cannot open camera')
    exit(1)
cap.release()
" && print_success "Camera test passed!" || print_error "Camera test failed!"

# ========================================
# Deployment Complete
# ========================================
echo
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo
print_info "Your Docker container is running with camera access."
echo
print_info "To enter the container:"
print_info "  docker compose exec ai-dev bash"
echo
print_info "To run your camera application:"
print_info "  docker compose exec ai-dev python3 camera_monitor/monitor.py"
echo
print_info "To view logs:"
print_info "  docker compose logs -f"
echo
print_info "To stop the container:"
print_info "  docker compose down"
echo
print_warning "Remember: If you stopped nvargus-daemon, restart it after you're done:"
print_warning "  sudo systemctl start nvargus-daemon"
echo
