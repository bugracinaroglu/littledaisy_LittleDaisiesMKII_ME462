# LittleDaisy Drawing Detector

This repository contains camera-based drawing detection experiments and tablet-based drawing server versions.

The current main implementation is:

```text
draw_detector_server/draw_detector_server_v6
```

## Project Structure

```text
draw_detector/
├── draw_detector_balck_frame/
│   ├── draw_detector_balck_frame_v1/
│   └── draw_detector_balck_frame_v2/
└── draw_detector_server/
    ├── draw_detector_server_v1/
    ├── draw_detector_server_v2/
    ├── draw_detector_server_v3/
    ├── draw_detector_server_v4/
    ├── draw_detector_server_v5/
    └── draw_detector_server_v6/    # Current main version
```

## Version Overview

### Camera-Based Detector

Located in `draw_detector_balck_frame/`.

- **v1:** Detects a physical drawing surface from the camera, applies perspective correction, extracts dark strokes and saves the result.
- **v2:** Adds stronger white-surface and dark-frame verification for more reliable surface detection.

A valid `calibration.json` is required.

```bash
cd draw_detector_balck_frame/draw_detector_balck_frame_v2
python main.py
```

### Tablet Drawing Server

- **v1:** Basic FastAPI drawing server, stroke processing and JSON export. Uses normalized top-left coordinates.
- **v2:** Adds a native OpenCV preview on the Raspberry Pi and supports raw-point processing.
- **v3:** Adds normalized bottom-left coordinates, persistent stroke IDs, drawing comparison and robot-job generation.
- **v4:** Adds startup state reset, startup `erase_all` handling and protection against sending old snapshots.
- **v5:** Adds configurable startup cleanup for the `output/`, comparison-state and robot-job folders.
- **v6:** Adds timestamped FIFO robot jobs, `latest_job.json`, queue status tracking and delayed comparison. This is the current main version.

Each version also contains its own README with version-specific details.

# Version 6

Version 6 receives drawings from a tablet, stores Detect snapshots, compares them with the robot's last successfully committed state and creates FIFO robot jobs.

## Version 6 Structure

```text
draw_detector_server_v6/
├── main.py                 # Starts the server, preview and terminal console
├── server.py               # FastAPI routes, WebSocket and Detect endpoint
├── processor.py            # Coordinate conversion and path processing
├── robot_jobs.py           # Comparison, FIFO queue and robot-job management
├── native_preview.py       # Three-panel OpenCV preview
├── preview_state.py        # Shared runtime preview state
├── json_preview.py         # Saved JSON preview utility
├── config.py               # Server, processing, startup and robot settings
├── requirements.txt
├── static/                 # Tablet drawing interface
├── output/                 # Detect snapshots
├── comparison_state/       # Last committed robot drawing
├── robot_jobs/
│   ├── jobs/               # Timestamped executable job files
│   └── latest_job.json     # Queue manifest and statuses
└── tests/                  # Robot-job and queue tests
```

## Environment and Startup

Activate the existing environment:

```bash
source ~/python_envs/drawing_detector_environment/bin/activate
```

Run Version 6:

```bash
cd <project-path>/draw_detector/draw_detector_server/draw_detector_server_v6
python -m pip install -r requirements.txt
python main.py
```

Open the tablet interface from a device on the same network:

```text
http://littledaisy.local:8000
```

The Raspberry Pi opens this preview:

```text
LIVE TABLET | LAST DETECTED | ROBOT JOB
```

## Normal Workflow

1. Start `main.py`.
2. Draw on the tablet.
3. Press **Detect & Save**.
4. Select a robot-job mode if necessary.
5. Run `send_data2robot_arm`.
6. Check the queue with `show_queue`.

**Detect & Save only creates a snapshot. It does not create or send a robot job.**

Only a Detect snapshot created during the current program run can be used by `send_data2robot_arm`.

## Terminal Commands

### `send_data2robot_arm`

Creates a request from the latest Detect snapshot and adds it to the FIFO queue.

```text
Detect snapshot
      ↓
job request
      ↓
latest_job.json
      ↓
queue worker
      ↓
drawing comparison
      ↓
executable robot actions
```

The comparison is performed when the request reaches the front of the queue. This ensures that it is compared with the state committed by the previously completed job.

### `set_mode difference`

Compares the latest drawing with the last committed robot state.

```text
Old stroke exists, new stroke does not  → erase
New stroke exists, old stroke does not  → draw
Same ID and geometry                    → same
Same ID but changed geometry            → erase old + draw new
```

### `set_mode full_redraw`

Creates:

```text
erase_all + draw every stroke in the latest snapshot
```

### `send_full_erase`

Adds a job containing only:

```json
{"type": "erase_all"}
```

The physical full-surface erase path must be implemented by the robot controller.

### `show_state`

Shows the selected mode, latest Detect snapshot, committed drawing state and active job information.

### `show_queue`

Shows pending, processing, completed and failed jobs.

### `help`

Lists all available terminal commands.

## Data and Coordinate System

Detect snapshots, comparison state and robot jobs use normalized bottom-left coordinates:

```text
          +Y
           ↑
           |
(0,0) -----+------→ +X
```

```text
x, y ∈ [0, 1]
```

Main runtime data:

```text
output/
└── drawing_<timestamp>.json

comparison_state/
└── robot_committed_state.json

robot_jobs/
├── jobs/
│   └── job_<timestamp>_<mode>.json
└── latest_job.json
```

Job states follow:

```text
pending → processing → completed
                    ↘ failed
```

## Robot Integration

The current configuration uses simulated acknowledgement:

```python
SIMULATE_ROBOT_ACK = True
```

Therefore, Version 6 currently creates and processes robot jobs but does not control a physical robot arm.

Real ROS, serial or network communication must be implemented in:

```python
RobotJobManager._send_to_transport(job)
```

This function should:

1. Send the executable job to the robot controller.
2. Wait for the robot acknowledgement.
3. Return `True` only after successful execution.

The committed drawing state must only be updated after a successful acknowledgement.

## Startup Settings

The main startup behavior is controlled in `config.py`:

```python
STARTUP_OUTPUT_ERASE_ENABLED
RESET_COMPARISON_STATE_ON_START
RESET_ROBOT_JOBS_ON_START
STARTUP_FULL_ERASE_ENABLED
SIMULATE_ROBOT_ACK
```

These options control old snapshot cleanup, state reset, queue reset and the startup `erase_all` job.

## Tests

```bash
python -m unittest discover -s tests -v
```
