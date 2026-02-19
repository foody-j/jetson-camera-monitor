"""FastAPI app factory for Jetson1 web dashboard."""

import time
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .mjpeg import mjpeg_stream


def create_app(cameras: Dict[int, object], state: object, config: dict) -> FastAPI:
    app = FastAPI(title="Jetson1 Dashboard", version="1.0")

    base_dir = Path(__file__).resolve().parent
    template_path = base_dir / "templates" / "dashboard.html"
    static_dir = base_dir / "static"

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(template_path))

    @app.get("/mjpeg/cam{cam_id}")
    async def mjpeg(cam_id: int):
        camera = cameras.get(cam_id)
        fps = int(config.get("web_preview_fps", 5))
        return StreamingResponse(
            mjpeg_stream(camera, fps=fps),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/api/status")
    async def status():
        cameras_status = {
            f"cam{i}": cam.stats for i, cam in cameras.items() if cam is not None
        }
        base = state.build_status()
        return JSONResponse(
            {
                "api_timestamp": time.time(),
                "cameras": cameras_status,
                **base,
            }
        )

    @app.get("/api/config")
    async def get_config():
        return JSONResponse(config)

    @app.get("/api/mqtt/log")
    async def mqtt_log():
        try:
            return JSONResponse(list(state.mqtt_message_log))
        except Exception:
            return JSONResponse([])

    @app.post("/api/control/relay")
    async def relay_control(payload: dict = Body(...)):
        action = str(payload.get("action", "")).lower()
        if action == "on":
            state.relay_turn_on()
        elif action == "off":
            state.relay_turn_off()
        return {"ok": True, "action": action}

    @app.post("/api/control/vibration")
    async def vibration_control(payload: dict = Body(...)):
        action = str(payload.get("action", "")).lower()
        if action == "start":
            state.start_vibration_check()
        elif action == "stop":
            state.stop_vibration_check()
        return {"ok": True, "action": action}

    @app.post("/api/control/vibration/status")
    async def vibration_status(payload: dict = Body(...)):
        status = str(payload.get("status", "")).upper()
        if status:
            state.vibration_status = status
        return {"ok": True, "status": status}

    @app.post("/api/control/recording")
    async def recording_control(payload: dict = Body(...)):
        pot = str(payload.get("pot", "")).lower()
        action = str(payload.get("action", "")).lower()
        if pot == "pot1":
            if action == "start":
                state.start_stirfry_pot1_recording()
            elif action == "stop":
                state.stop_stirfry_pot1_recording()
        elif pot == "pot2":
            if action == "start":
                state.start_stirfry_pot2_recording()
            elif action == "stop":
                state.stop_stirfry_pot2_recording()
        return {"ok": True, "pot": pot, "action": action}

    @app.post("/api/control/mode")
    async def mode_control(payload: dict = Body(...)):
        mode = str(payload.get("mode", "")).lower()
        state.set_mode(mode)
        return {"ok": True, "mode": mode}

    @app.post("/api/control/publish")
    async def publish_now():
        try:
            state._publish_mqtt_status()
        except Exception:
            pass
        return {"ok": True}

    @app.post("/api/control/night-summary/publish")
    async def publish_night_summary_now():
        try:
            detected = state.force_publish_next_day_night_result()
            return {"ok": True, "person_detected": bool(detected)}
        except Exception:
            return {"ok": False}

    return app
