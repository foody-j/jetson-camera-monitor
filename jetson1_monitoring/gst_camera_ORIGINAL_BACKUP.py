#!/usr/bin/env python3
"""
GStreamer Camera Wrapper for GMSL UYVY cameras
Direct GStreamer usage to avoid OpenCV format issues
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
import time

# Initialize GStreamer
Gst.init(None)


class GstCamera:
    """GStreamer-based camera capture for UYVY format"""

    def __init__(self, device_index, width=1920, height=1536, fps=30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.device_path = f"/dev/video{device_index}"

        self.pipeline = None
        self.mainloop = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.is_running = False
        self.thread = None

        print(f"[GstCamera] Creating camera for {self.device_path} @ {width}x{height}")

    def start(self):
        """Start the GStreamer pipeline in a background thread"""
        if self.is_running:
            print(f"[GstCamera] Camera {self.device_index} already running")
            return True

        # Build GStreamer pipeline
        pipeline_str = (
            f"v4l2src device={self.device_path} ! "
            f"video/x-raw, format=UYVY, width={self.width}, height={self.height}, framerate={self.fps}/1 ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=1 drop=true"
        )

        print(f"[GstCamera] Pipeline: {pipeline_str}")

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Get the appsink element
            sink = self.pipeline.get_by_name('sink')
            if not sink:
                print(f"[ERROR] Failed to get appsink from pipeline")
                return False

            # Connect to new-sample signal
            sink.connect('new-sample', self._on_new_sample)

            # Start pipeline in background thread
            self.is_running = True
            self.thread = threading.Thread(target=self._run_pipeline, daemon=True)
            self.thread.start()

            # Wait a bit for pipeline to start
            time.sleep(0.5)

            print(f"[GstCamera] Camera {self.device_index} started successfully")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start camera {self.device_index}: {e}")
            return False

    def _run_pipeline(self):
        """Run GStreamer mainloop in background thread"""
        try:
            # Set pipeline to PLAYING state
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print(f"[ERROR] Failed to set pipeline to PLAYING state")
                self.is_running = False
                return

            print(f"[GstCamera] Pipeline for camera {self.device_index} is PLAYING")

            # Add bus watch for errors (NO mainloop - we'll iterate manually)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message', self._on_bus_message)

            # Instead of blocking mainloop, use GLib context iteration
            context = GLib.MainContext.default()

            # Poll GLib events periodically
            while self.is_running:
                # Process pending events
                while context.pending():
                    context.iteration(False)

                # Small sleep to avoid busy-waiting
                time.sleep(0.001)

        except Exception as e:
            print(f"[ERROR] Pipeline thread error for camera {self.device_index}: {e}")
        finally:
            self.is_running = False

    def _on_bus_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[ERROR] GStreamer error on camera {self.device_index}: {err}, {debug}")
            self.stop()
        elif t == Gst.MessageType.EOS:
            print(f"[INFO] End-of-stream on camera {self.device_index}")
            self.stop()

    def _on_new_sample(self, sink):
        """Callback for new frame from appsink"""
        try:
            # Pull sample from appsink
            sample = sink.emit('pull-sample')
            if not sample:
                return Gst.FlowReturn.ERROR

            # Get buffer from sample
            buf = sample.get_buffer()
            caps = sample.get_caps()

            # Get frame dimensions from caps
            structure = caps.get_structure(0)
            width = structure.get_value('width')
            height = structure.get_value('height')

            # Extract buffer data
            success, map_info = buf.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.ERROR

            # Convert to numpy array (BGR format)
            frame = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )

            # Copy frame to avoid data corruption
            with self.frame_lock:
                self.latest_frame = frame.copy()

            buf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            print(f"[ERROR] Error processing frame from camera {self.device_index}: {e}")
            return Gst.FlowReturn.ERROR

    def read(self):
        """
        Read the latest frame
        Returns: (success, frame) tuple
        """
        if not self.is_running:
            return False, None

        with self.frame_lock:
            if self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def isOpened(self):
        """Check if camera is running"""
        return self.is_running

    def stop(self):
        """Stop the camera"""
        if not self.is_running:
            return

        print(f"[GstCamera] Stopping camera {self.device_index}...")
        self.is_running = False

        # Stop pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        # Wait for thread to finish (only if not called from the same thread)
        if self.thread and self.thread.is_alive():
            if threading.current_thread() != self.thread:
                self.thread.join(timeout=2.0)
            else:
                print(f"[GstCamera] Skipping join (called from same thread)")

        print(f"[GstCamera] Camera {self.device_index} stopped")

    def release(self):
        """Release camera resources"""
        self.stop()


# Test code
if __name__ == "__main__":
    print("Testing GstCamera with camera 0...")

    cam = GstCamera(device_index=0, width=1920, height=1536, fps=30)

    if not cam.start():
        print("Failed to start camera!")
        exit(1)

    print("Camera started, reading frames...")

    for i in range(10):
        time.sleep(0.5)
        ret, frame = cam.read()
        if ret:
            print(f"Frame {i+1}: Shape={frame.shape}, Mean={frame.mean():.1f}")
        else:
            print(f"Frame {i+1}: No frame available yet")

    cam.stop()
    print("Test complete!")
