"""FastAPI app factory for Jetson2 web dashboard."""

import time
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .mjpeg import mjpeg_stream


def create_app(
    cameras: Dict[int, object],
    frying_workers: Dict[int, object],
    observe_workers: Optional[Dict[int, object]],
    mqtt_client: Optional[object],
    config: dict,
    state: Optional[object] = None,
) -> FastAPI:
    app = FastAPI(title="Jetson2 Dashboard", version="1.0")

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
        frying_status = {
            f"pot{i}": worker.get_result() for i, worker in frying_workers.items()
        }
        observe_status = {}
        if observe_workers:
            observe_status = {
                f"cam{i}": worker.get_result() for i, worker in observe_workers.items()
            }

        mqtt_connected = False
        if mqtt_client is not None:
            try:
                mqtt_connected = mqtt_client.is_connected()
            except Exception:
                mqtt_connected = False

        extra = {}
        if state is not None:
            try:
                extra = {
                    "pots": {
                        "pot1": {"status": state.pot1_status, "food_type": state.pot1_food_type},
                        "pot2": {"status": state.pot2_status, "food_type": state.pot2_food_type},
                    },
                    "observe_state": {
                        "left": state.observe_left_state,
                        "right": state.observe_right_state,
                    },
                    "vibration": {"status": state.vibration_status},
                    "relay": {"enabled": state.relay_enabled},
                    "collection": {
                        "pot1": state.pot1_collecting,
                        "pot2": state.pot2_collecting,
                        "legacy": state.data_collection_active,
                        "pot1_frames": state.pot1_frame_counter,
                        "pot2_frames": state.pot2_frame_counter,
                        "pot1_session": state.pot1_session_id,
                        "pot2_session": state.pot2_session_id,
                    },
                }
            except Exception:
                extra = {}

        return JSONResponse(
            {
                "timestamp": time.time(),
                "cameras": cameras_status,
                "frying": frying_status,
                "observe": observe_status,
                "mqtt": {"connected": mqtt_connected},
                **extra,
            }
        )

    @app.get("/api/config")
    async def get_config():
        return JSONResponse(config)

    if state is not None:
        @app.get("/api/mqtt/log")
        async def mqtt_log():
            try:
                return JSONResponse(list(state.mqtt_message_log))
            except Exception:
                return JSONResponse([])

    if state is not None:
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

        @app.post("/api/control/observe")
        async def observe_control(payload: dict = Body(...)):
            side = str(payload.get("side", "")).lower()
            status = str(payload.get("status", "")).upper()
            if side == "left":
                state.observe_left_state = status
            elif side == "right":
                state.observe_right_state = status
            return {"ok": True, "side": side, "status": status}

        @app.post("/api/control/publish")
        async def publish_now():
            if state.mqtt_client:
                state._publish_mqtt_status()
            return {"ok": True}

    return app
