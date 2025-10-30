#!/bin/bash
# Setup X11 for Docker GUI support
# Run this ONCE on the HOST (outside Docker)

echo "Setting up X11 for Docker containers..."
echo "========================================"

# Allow Docker to connect to X server
echo "1. Allowing Docker X11 access..."
xhost +local:docker

# Create X11 auth file
echo "2. Creating X11 auth file..."
touch /tmp/.docker.xauth
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f /tmp/.docker.xauth nmerge -
chmod 644 /tmp/.docker.xauth

echo ""
echo "✅ X11 setup complete!"
echo ""
echo "Now restart your Docker container:"
echo "  docker-compose down"
echo "  docker-compose up -d"
echo "  docker-compose exec ai-dev bash"
echo ""
echo "Then inside container, run:"
echo "  cd /project/autostart_autodown"
echo "  python3 ROBOTCAM_HEADLESS.py"
