"""MJPEG streaming utilities for FastAPI."""

import asyncio
from typing import AsyncGenerator, Optional


def _frame_chunk(jpg: bytes, boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n".encode("ascii")
        + b"Content-Type: image/jpeg\r\n\r\n"
        + jpg
        + b"\r\n"
    )


async def mjpeg_stream(camera, fps: int = 5, boundary: str = "frame") -> AsyncGenerator[bytes, None]:
    """Yield MJPEG frames from a CameraWorker-like object."""
    if camera is None:
        yield (
            f"--{boundary}\r\nContent-Type: text/plain\r\n\r\nCamera not found\r\n".encode(
                "ascii"
            )
        )
        return

    interval = 1.0 / max(fps, 1)
    while True:
        jpg: Optional[bytes] = camera.get_web_frame()
        if jpg:
            yield _frame_chunk(jpg, boundary)
        await asyncio.sleep(interval)
