#!/bin/bash
# Quick validation of Docker and camera setup
# This checks if everything is ready for deployment

echo "========================================"
echo "Docker Camera Setup Validation"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass=0
fail=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
        ((pass++))
    else
        echo -e "${RED}✗ $1${NC}"
        ((fail++))
    fi
}

echo
echo "Checking prerequisites..."
echo "-------------------------------------------"

# Check Docker
docker --version > /dev/null 2>&1
check "Docker installed"

# Check Docker Compose
docker compose --version > /dev/null 2>&1
check "Docker Compose installed"

# Check camera device
[ -e /dev/video0 ]
check "Camera device /dev/video0 exists"

# Check video group
groups | grep -q video
check "User in video group"

# Check Dockerfile
[ -f Dockerfile ]
check "Dockerfile exists"

# Check docker-compose.yml
[ -f docker-compose.yml ]
check "docker-compose.yml exists"

# Check if camera devices are in docker-compose
grep -q "/dev/video0" docker-compose.yml
check "docker-compose.yml includes /dev/video0"

# Check nvargus-daemon status
echo
echo "Camera status..."
echo "-------------------------------------------"
if systemctl is-active --quiet nvargus-daemon; then
    echo -e "${YELLOW}⚠ nvargus-daemon is running (may need to stop it)${NC}"
else
    echo -e "${GREEN}✓ nvargus-daemon is not running${NC}"
fi

# Quick camera test
echo
echo "Testing camera access..."
echo "-------------------------------------------"
if timeout 2 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=1 ! fakesink 2>&1 | grep -q "busy"; then
    echo -e "${RED}✗ Camera is BUSY${NC}"
    echo "  Solution: Run 'sudo systemctl stop nvargus-daemon'"
    ((fail++))
else
    echo -e "${GREEN}✓ Camera is accessible${NC}"
    ((pass++))
fi

# Summary
echo
echo "========================================"
echo "Validation Summary"
echo "========================================"
echo -e "Passed: ${GREEN}$pass${NC}"
echo -e "Failed: ${RED}$fail${NC}"
echo

if [ $fail -eq 0 ]; then
    echo -e "${GREEN}✓ Ready for deployment!${NC}"
    echo
    echo "Run deployment with:"
    echo "  ./deploy_camera.sh"
    exit 0
else
    echo -e "${RED}✗ Fix the issues above before deploying${NC}"
    exit 1
fi
