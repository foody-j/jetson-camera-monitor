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
                    "system": state.system_info.get_dynamic_info() if state.system_info else {},
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
        def _mqtt_publish(topic: str, payload: str, qos: int | None = None) -> bool:
            if not state.mqtt_client:
                return False
            q = int(config.get("mqtt_qos", 1) if qos is None else qos)
            try:
                state.mqtt_client.client.publish(topic, payload, qos=q)
                try:
                    state._log_mqtt_message(topic, payload)
                except Exception:
                    pass
                return True
            except Exception:
                return False

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

        @app.post("/api/control/vibration/status")
        async def vibration_status(payload: dict = Body(...)):
            status = str(payload.get("status", "")).upper()
            if status:
                state.vibration_status = status
            return {"ok": True, "status": status}

        @app.post("/api/control/collection")
        async def collection_control(payload: dict = Body(...)):
            target = str(payload.get("target", "")).lower()
            action = str(payload.get("action", "")).lower()
            if target == "legacy":
                if action == "start":
                    state.start_data_collection()
                elif action == "stop":
                    state.stop_data_collection()
            elif target == "pot1":
                if action == "start":
                    state.start_pot1_collection()
                elif action == "stop":
                    state.stop_pot1_collection()
            elif target == "pot2":
                if action == "start":
                    state.start_pot2_collection()
                elif action == "stop":
                    state.stop_pot2_collection()
            return {"ok": True, "target": target, "action": action}

        @app.post("/api/control/overlay")
        async def overlay_control(payload: dict = Body(...)):
            enabled = bool(payload.get("enabled", False))
            try:
                state.set_overlay_enabled(enabled)
            except Exception:
                pass
            return {"ok": True, "enabled": enabled}

        @app.get("/api/ai/snapshot")
        async def ai_snapshot(set: int = 1):  # noqa: A002
            try:
                data = state.build_ai_snapshot(set)
            except Exception:
                data = {}
            return JSONResponse(
                {
                    "timestamp": time.time(),
                    "set": set,
                    "cams": data,
                }
            )

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

        @app.post("/api/control/mqtt/publish")
        async def mqtt_publish(payload: dict = Body(...)):
            topic = str(payload.get("topic", "")).strip()
            message = str(payload.get("message", ""))
            qos = payload.get("qos", None)
            if not topic:
                return {"ok": False, "error": "topic_required"}
            ok = _mqtt_publish(topic, message, qos=qos)
            return {"ok": ok, "topic": topic, "message": message}

        @app.post("/api/control/mqtt/quick")
        async def mqtt_quick(payload: dict = Body(...)):
            action = str(payload.get("action", "")).strip().lower()
            qos = int(config.get("mqtt_qos", 1))
            topic_observe = config.get("mqtt_topic_observe", "observe/status")
            topic_frying = config.get("mqtt_topic_frying", "frying/status")
            topic_status = config.get("mqtt_topic_status", "jetson2/status")

            if action not in {
                "observe_input_left",
                "observe_input_right",
                "frying_discharge_left",
                "frying_discharge_right",
            }:
                return {"ok": False, "error": "invalid_action"}

            sent = []
            action_map = {
                "observe_input_left": (topic_observe, "LEFT:투입"),
                "observe_input_right": (topic_observe, "RIGHT:투입"),
                "frying_discharge_left": (topic_frying, "LEFT:DISCHARGE"),
                "frying_discharge_right": (topic_frying, "RIGHT:DISCHARGE"),
            }
            topic, message = action_map[action]
            if _mqtt_publish(topic, message, qos=qos):
                sent.append({"topic": topic, "message": message})

            # Keep state in sync so the same change is visible on jetson2/status.
            try:
                if action == "observe_input_left":
                    state.observe_left_state = "투입"
                elif action == "observe_input_right":
                    state.observe_right_state = "투입"
                elif action == "frying_discharge_left":
                    state.pot1_status = "DISCHARGE"
                elif action == "frying_discharge_right":
                    state.pot2_status = "DISCHARGE"

                state._publish_mqtt_status()
                sent.append({"topic": topic_status, "message": "state_publish"})
            except Exception:
                pass

            return {
                "ok": len(sent) > 0,
                "action": action,
                "sent": sent,
            }

    return app
