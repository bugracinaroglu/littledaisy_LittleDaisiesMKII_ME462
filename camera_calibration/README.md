# Fisheye Camera Calibration

This folder contains ChArUco-based fisheye camera calibration and image undistortion scripts.

## `calibration_v1/` — Image-Based Calibration

A controlled and reusable workflow.

* `capture.py`: Captures calibration images.
* `diagnose.py`: Checks marker and corner detection.
* `calibrate.py`: Creates `calibration.json`.
* `preview.py`: Compares the original and undistorted views.

```bash
cd calibration_v1
python capture.py
python diagnose.py
python calibrate.py
python preview.py
```

## `calibration_v2/` — Live Calibration

Calibrates directly from the live camera feed.

```bash
cd calibration_v2
python live_calibrate.py
```

* `SPACE`: Add the current frame
* `Q` or `ESC`: Finish and save

This version is faster, while `calibration_v1` is easier to inspect and debug.

## `preview_test/` — Result Preview

Place the selected calibration file in this folder as `calibration.json`.

```bash
cd preview_test
python preview.py --balance 0.5
```

* `0.0`: More cropping, fewer black borders
* `0.5`: Balanced result
* `1.0`: Wider field of view

## Important

The ChArUco board parameters must match the printed board.

`live_calibrate.py` uses `MARKER_LENGTH = 13.3`, while the other versions generally use `12.5`.

## Requirements

```bash
pip install numpy opencv-contrib-python
```

Raspberry Pi Camera users also need `picamera2`.
