"""
server.py — FastAPI server.

Endpoints:
  GET  /              → serves the drawing page (static/index.html)
  GET  /static/...    → static assets (JS, CSS)
  POST /detect        → receives raw stroke list, returns processed strokes
                        and writes both to output/drawing_TIMESTAMP.json
  GET  /health        → simple liveness check
"""

import json
import os
import time
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import processor


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class Stroke(BaseModel):
    points: List[List[float]]   # [[x, y], [x, y], ...] all in 0..1


class DetectRequest(BaseModel):
    canvas_size_px: int                       # canvas pixel size (1:1 square)
    strokes: List[Stroke]


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="LittleDaisy Draw Server")

app.mount(
    "/static",
    StaticFiles(directory=config.STATIC_DIR),
    name="static",
)


@app.get("/")
def index():
    return FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Preview (test viewer)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/preview")
def preview_page():
    return FileResponse(os.path.join(config.STATIC_DIR, "preview.html"))


@app.get("/api/drawings")
def list_drawings():
    """List saved drawing files, newest first."""
    files = [
        f for f in os.listdir(config.OUTPUT_DIR)
        if f.startswith("drawing_") and f.endswith(".json")
    ]
    files.sort(reverse=True)
    return {"files": files}


@app.get("/api/drawings/{filename}")
def get_drawing(filename: str):
    """Return a saved drawing JSON. Guards against path traversal."""
    if "/" in filename or ".." in filename or not filename.endswith(".json"):
        return JSONResponse({"error": "invalid filename"}, status_code=400)

    path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)

    with open(path) as f:
        return JSONResponse(json.load(f))


@app.post("/detect")
def detect(req: DetectRequest):
    raw_strokes: List[Dict[str, Any]] = [s.model_dump() for s in req.strokes]

    processed = processor.process_strokes(raw_strokes)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path  = os.path.join(config.OUTPUT_DIR, f"drawing_{timestamp}.json")

    payload: Dict[str, Any] = {
        "timestamp":         timestamp,
        "canvas_size_px":    req.canvas_size_px,
        "canvas_aspect":     [1, 1],
        "coordinate_system": "normalized_top_left_origin",
        "processed_strokes": processed,
    }
    if config.SAVE_RAW_STROKES:
        payload["raw_strokes"] = raw_strokes

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[detect] saved {len(raw_strokes)} raw / {len(processed)} processed "
          f"strokes → {out_path}")

    return JSONResponse({
        "processed_strokes": processed,
        "saved_to":          os.path.basename(out_path),
        "raw_count":         len(raw_strokes),
        "processed_count":   len(processed),
    })