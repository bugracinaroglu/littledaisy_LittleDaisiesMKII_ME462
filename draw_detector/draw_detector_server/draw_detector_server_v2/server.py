"""FastAPI server for the LittleDaisy tablet drawing application.

The tablet opens GET / and sends live drawing snapshots through /ws/preview.
The Raspberry Pi preview is a native OpenCV window managed by main.py.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import processor
from preview_state import preview_state


class Stroke(BaseModel):
    points: List[List[float]]


class DetectRequest(BaseModel):
    canvas_size_px: int
    strokes: List[Stroke]


app = FastAPI(title="LittleDaisy Draw Server")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.websocket("/ws/preview")
async def preview_socket(websocket: WebSocket) -> None:
    """Receive live tablet snapshots and place them in native preview state."""
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "raw_preview":
                strokes = message.get("strokes", [])
                if not isinstance(strokes, list):
                    continue
                preview_state.update_raw(
                    strokes,
                    canvas_size_px=int(message.get("canvas_size_px", 0) or 0),
                )
            elif message_type == "clear":
                preview_state.clear()

    except WebSocketDisconnect:
        pass
    except Exception as error:
        print(f"[preview websocket] {error}")


@app.get("/api/drawings")
def list_drawings() -> Dict[str, List[str]]:
    files = [
        filename
        for filename in os.listdir(config.OUTPUT_DIR)
        if filename.startswith("drawing_") and filename.endswith(".json")
    ]
    files.sort(reverse=True)
    return {"files": files}


@app.get("/api/drawings/{filename}")
def get_drawing(filename: str) -> JSONResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    if not filename.endswith(".json"):
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)

    with open(path, encoding="utf-8") as file:
        return JSONResponse(json.load(file))


@app.post("/detect")
async def detect(req: DetectRequest) -> JSONResponse:
    raw_strokes: List[Dict[str, Any]] = [
        stroke.model_dump() for stroke in req.strokes
    ]
    processed_strokes = processor.process_strokes(raw_strokes)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"drawing_{timestamp}.json"
    output_path = os.path.join(config.OUTPUT_DIR, filename)

    payload: Dict[str, Any] = {
        "timestamp": timestamp,
        "canvas_size_px": req.canvas_size_px,
        "canvas_aspect": [1, 1],
        "coordinate_system": "normalized_top_left_origin",
        "processing_mode": config.PROCESSING_MODE,
        "processed_strokes": processed_strokes,
    }
    if config.SAVE_RAW_STROKES:
        payload["raw_strokes"] = raw_strokes

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    preview_state.update_detected(
        raw_strokes=raw_strokes,
        processed_strokes=processed_strokes,
        saved_to=filename,
        canvas_size_px=req.canvas_size_px,
    )

    raw_points = sum(len(stroke.get("points", [])) for stroke in raw_strokes)
    processed_points = sum(
        len(stroke.get("points", [])) for stroke in processed_strokes
    )
    print(
        f"[detect] {len(raw_strokes)} strokes, "
        f"{raw_points} raw points -> {processed_points} output points -> "
        f"{output_path}"
    )

    return JSONResponse(
        {
            "processed_strokes": processed_strokes,
            "saved_to": filename,
            "raw_count": len(raw_strokes),
            "processed_count": len(processed_strokes),
            "raw_point_count": raw_points,
            "processed_point_count": processed_points,
            "processing_mode": config.PROCESSING_MODE,
        }
    )
