"""FastAPI server for the LittleDaisy tablet drawing application."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import processor
from preview_state import preview_state


class Stroke(BaseModel):
    stroke_id: str = Field(min_length=1)
    parent_stroke_id: Optional[str] = None
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
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "raw_preview":
                strokes = message.get("strokes", [])
                if isinstance(strokes, list):
                    preview_state.update_live(
                        strokes,
                        canvas_size_px=int(message.get("canvas_size_px", 0) or 0),
                    )
            elif message_type == "clear":
                # Clear only the live panel. Last Detect and last robot job remain.
                preview_state.clear_live()
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
    # Tablet coordinates are top-left origin. Output and robot coordinates are
    # converted once here to bottom-left origin (+X right, +Y up).
    tablet_strokes: List[Dict[str, Any]] = [stroke.model_dump() for stroke in req.strokes]
    bottom_left_strokes = processor.convert_top_left_to_bottom_left(tablet_strokes)
    output_strokes = processor.process_strokes(bottom_left_strokes)

    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    timestamp_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
    drawing_id = f"drawing_{timestamp_file}"
    filename = f"{drawing_id}.json"
    output_path = os.path.join(config.OUTPUT_DIR, filename)

    payload: Dict[str, Any] = {
        "schema_version": 2,
        "drawing_id": drawing_id,
        "timestamp": timestamp_iso,
        "canvas_size_px": req.canvas_size_px,
        "canvas_aspect": [1, 1],
        "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
        "processing": {
            "mode": config.PROCESSING_MODE,
            "smoothing_passes": config.SMOOTHING_PASSES,
            "simplify_epsilon": config.SIMPLIFY_EPSILON,
        },
        # Only the output/processed representation is archived. In raw mode it
        # contains the same valid points as the tablet input.
        "strokes": output_strokes,
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    preview_state.update_detected(
        detected_strokes=output_strokes,
        saved_to=filename,
        canvas_size_px=req.canvas_size_px,
    )

    point_count = sum(len(stroke.get("points", [])) for stroke in output_strokes)
    print(
        f"[detect] snapshot={filename} strokes={len(output_strokes)} "
        f"points={point_count} origin=bottom-left"
    )
    return JSONResponse({
        "strokes": output_strokes,
        "saved_to": filename,
        "stroke_count": len(output_strokes),
        "point_count": point_count,
        "processing_mode": config.PROCESSING_MODE,
        "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
    })
