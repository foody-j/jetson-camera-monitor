# Camera Deployment Guide for Jetson Orin

This guide explains how to deploy your AI monitoring system with camera support in Docker on Jetson Orin devices.

## Quick Start

```bash
# Make the deployment script executable
chmod +x deploy_camera.sh

# Run the deployment script
./deploy_camera.sh
```

The script will:
1. Check camera availability
2. Handle nvargus-daemon blocking issue
3. Setup X11 for GUI display
4. Build the Docker image
5. Start the container with camera access
6. Verify camera is working

## Manual Deployment

If you prefer to deploy manually:

### 1. Fix Camera Access (if needed)

```bash
# Stop nvargus-daemon that blocks USB camera
sudo systemctl stop nvargus-daemon

# Verify camera is accessible
v4l2-ctl --device=/dev/video0 --all
```

### 2. Setup X11 for GUI

```bash
# Allow Docker to access X server
xhost +local:docker

# Create X11 auth file
touch /tmp/.docker.xauth
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f /tmp/.docker.xauth nmerge -
chmod 644 /tmp/.docker.xauth
```

### 3. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the container
docker-compose up -d

# Enter the container
docker-compose exec ai-dev bash
```

### 4. Test Camera in Container

```bash
# Inside the container, test camera
python3 test_camera_simple.py

# Or run the GUI
python3 camera_monitor/monitor.py
```

## Architecture

### Docker Configuration

**Dockerfile:**
- Based on `nvcr.io/nvidia/l4t-jetpack:r36.4.0`
- Includes OpenCV, V4L2, and GStreamer
- Camera and GPU access configured

**docker-compose.yml:**
- Maps `/dev/video0` and `/dev/video1` into container
- Enables X11 forwarding for GUI
- NVIDIA runtime for GPU access
- Host network mode

### Camera Access

The system uses **V4L2** (Video4Linux2) backend to access USB cameras directly:

```python
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
```

## Troubleshooting

### Camera Busy Error

**Problem:** `Device '/dev/video0' is busy`

**Solution:**
```bash
# Check what's using the camera
sudo fuser -v /dev/video0

# Stop nvargus-daemon
sudo systemctl stop nvargus-daemon
```

### Camera Not Detected in Container

**Problem:** Container can't see `/dev/video0`

**Solution:**
Check `docker-compose.yml` has:
```yaml
devices:
  - /dev/video0:/dev/video0
  - /dev/video1:/dev/video1
group_add:
  - video
```

### GUI Not Showing

**Problem:** `cv2.imshow()` doesn't display window

**Solution:**
```bash
# On host, allow Docker X11 access
xhost +local:docker

# Check DISPLAY variable in container
docker-compose exec ai-dev echo $DISPLAY
# Should show something like :0 or :1
```

### Permission Denied

**Problem:** `Permission denied` when accessing camera

**Solution:**
```bash
# Add user to video group (on host)
sudo usermod -aG video $USER

# Log out and log back in, or reboot
```

## Deployment to Other Jetson Devices

### 1. Export Docker Image

On the development Jetson:
```bash
# Build and save the image
docker-compose build
docker save jp6:jp6 | gzip > jetson-camera-ai.tar.gz
```

### 2. Transfer to Target Jetson

```bash
# Copy to target device
scp jetson-camera-ai.tar.gz user@target-jetson:/tmp/

# Or use USB drive, network share, etc.
```

### 3. Load on Target Jetson

On the target Jetson:
```bash
# Load the image
gunzip -c jetson-camera-ai.tar.gz | docker load

# Copy project files
git clone <your-repo> my_ai_project
cd my_ai_project

# Run deployment
chmod +x deploy_camera.sh
./deploy_camera.sh
```

### Alternative: Use Docker Registry

```bash
# Tag and push to registry
docker tag jp6:jp6 your-registry.com/jetson-camera-ai:latest
docker push your-registry.com/jetson-camera-ai:latest

# On target Jetson, pull and run
docker pull your-registry.com/jetson-camera-ai:latest
docker-compose up -d
```

## Running Your Application

### Interactive Mode

```bash
# Start container and enter bash
docker-compose exec ai-dev bash

# Inside container
cd /project
python3 camera_monitor/monitor.py
```

### Background Mode

```bash
# Run application in background
docker-compose exec -d ai-dev python3 src/monitoring/frying/run_monitor.py

# View logs
docker-compose logs -f
```

### Automatic Start

Edit `docker-compose.yml`:
```yaml
services:
  ai-dev:
    command: python3 /project/src/monitoring/frying/run_monitor.py
    restart: unless-stopped
```

## Important Notes

### nvargus-daemon

- **Purpose:** NVIDIA's camera daemon for CSI cameras
- **Issue:** Can block USB camera access
- **Solution:** Stop it when using USB cameras: `sudo systemctl stop nvargus-daemon`
- **Restore:** Restart it later: `sudo systemctl start nvargus-daemon`

### Camera Device Numbers

- `/dev/video0` - Usually the main camera stream
- `/dev/video1` - Usually camera metadata/control
- Both should be mapped into Docker

### GPU Access

The container has NVIDIA GPU access configured:
- CUDA, cuDNN available
- TensorRT available
- Use `nvidia-smi` in container to verify

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Test camera on host first: `v4l2-ctl --list-devices`
3. Verify container can access device: `docker-compose exec ai-dev ls -l /dev/video0`
