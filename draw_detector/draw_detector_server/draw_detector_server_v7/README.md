# draw_detector_server_v7

Tablet draws → **Detect** saves a snapshot → `send_data2robot_arm` queues a
job → job is compared against the robot's last committed state → only the
diff (`erase`/`draw`) is sent to the robot.

## Run

```bash
source /path/to/environment/bin/activate
cd draw_detector_server_v7
python -m pip install -r requirements.txt
python main.py
```

Tablet: `http://littledaisy.local:8000`
Raspberry Pi preview window: `LIVE TABLET | LAST DETECTED | ROBOT JOB`

## Structure

```text
draw_detector_server_v7/
├── main.py            # starts server, preview, terminal console
├── server.py           # FastAPI routes, WebSocket, /detect endpoint
├── processor.py         # coordinate conversion + point filtering
├── robot_jobs.py         # diff, FIFO queue, robot job management
├── native_preview.py      # OpenCV 3-panel preview
├── preview_state.py        # shared runtime state
├── json_preview.py          # standalone JSON preview tool
├── config.py                 # all settings
├── static/                    # tablet web UI
├── output/                     # Detect snapshots (drawing_<ts>.json)
├── comparison_state/            # robot's last committed drawing
├── robot_jobs/
│   ├── jobs/                      # one file per executable job
│   └── latest_job.json             # queue manifest (no point data)
└── tests/
```

## Coordinates

Normalized, bottom-left origin: `x, y ∈ [0,1]`, +X right, +Y up. Canvas
top-left Y is flipped once at Detect: `y_output = 1 - y_canvas`.

## Detect

`Detect & Save` writes the current canvas as `output/drawing_<timestamp>.json`.
It only saves — no comparison, no robot job yet. Only a snapshot from the
*current* program run can be sent to the robot.

## Filtering (`config.py`)

```
PROCESSING_MODE = "raw"        # "raw" = pass tablet points through unchanged. "filtered" = apply the 4 settings below.
SMOOTHING_PASSES = 0           # number of 3-point moving-average passes to blend out jitter.
SIMPLIFY_EPSILON = 0.0002      # Douglas-Peucker tolerance (fraction of canvas width); larger = fewer points, less detail.
MIN_STROKE_POINTS = 1          # strokes with fewer points than this are dropped entirely.
MIN_STROKE_LENGTH = 0.0        # strokes shorter than this (fraction of canvas width) are dropped entirely.
```

## Sending to the robot

`send_data2robot_arm` queues a job referencing the latest Detect snapshot.
Comparison is delayed until the job reaches the front of the FIFO queue, so
it's always diffed against the state committed by the previously *completed*
job:

- old stroke gone in new drawing → `erase`
- new stroke not in old drawing → `draw`
- same id + same geometry → `same` (no-op, preview only)
- geometry changed → `erase` old + `draw` new
- stroke split by pixel-eraser → surviving fragment kept as `same`, only the
  removed gap is `erase`d (matched by point geometry, not by stroke id —
  fixes a bug where partially-erased strokes were fully redrawn)

`set_mode difference` (default) does the above. `set_mode full_redraw` does
`erase_all` + draw everything. `send_full_erase` queues just `{"erase_all"}`.

Job statuses: `pending → processing → completed` (commits to
`comparison_state/robot_committed_state.json`) or `→ failed` (no commit).

`SIMULATE_ROBOT_ACK = True` — no physical robot is connected yet; real
transport goes in `RobotJobManager._send_to_transport()`.

## Job file shape

```json
{
  "mode": "difference",
  "coordinate_system": "normalized_bottom_left_origin",
  "actions": [
    {"type": "erase", "stroke_id": "...", "points": [[x,y], ...]},
    {"type": "draw",  "stroke_id": "...", "points": [[x,y], ...]},
    {"type": "same",  "stroke_id": "...", "points": [[x,y], ...]}
  ]
}
```
Robot consumes `erase`/`draw` in order, skips `same`.
`latest_job.json` only lists job files + status, no point data.

## Startup (`config.py`)

```
STARTUP_OUTPUT_ERASE_ENABLED = True     # clear old output/ snapshots on start
RESET_COMPARISON_STATE_ON_START = True  # forget committed robot state
RESET_ROBOT_JOBS_ON_START = True        # clear old queue/jobs
STARTUP_FULL_ERASE_ENABLED = True       # queue an erase_all job at start
```

## Terminal commands

```
send_data2robot_arm
send_full_erase
set_mode difference | set_mode full_redraw
show_state
show_queue
help
```

## Tests

```bash
python -m unittest discover -s tests -v
```
Covers coordinate conversion, diff/erase/draw behavior (including the pixel-
eraser geometry-matching fix), startup cleanup, FIFO queue processing, and
full-erase-before-drawing-jobs safety.