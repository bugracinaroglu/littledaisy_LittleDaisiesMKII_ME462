"""
main.py — Drawing detector pipeline entry point.

Data flow each frame:
    Camera.read()
        -> undistorted BGR frame
    FrameDetector.process(frame)
        -> warped surface + annotated frame
    DrawingDetector.process(warped)
        -> strokes (List[ndarray]) + drawing visualization
    Visualizer.show(...)
        -> three-panel display

Controls:
    S       : save detected strokes to output/drawing_<timestamp>.json
    R       : reset frame detector surface lock (re-scan)
    Q / ESC : quit
"""

import sys
from camera          import Camera
from frame_detector  import FrameDetector
from drawing_detector import DrawingDetector
from visualizer      import Visualizer


def main():
    print("Starting drawing detector pipeline...")

    cam = Camera()
    if not cam.is_opened():
        print("ERROR: Camera could not be opened. Exiting.")
        sys.exit(1)

    fd  = FrameDetector()
    dd  = DrawingDetector()
    vis = Visualizer()

    last_strokes = []

    print("Pipeline running.")
    print("  S : save drawing   R : reset lock   M : manual corners   Q/ESC : quit")

    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            continue

        # ── Stage 1: find and warp the drawing surface ──
        warped, corners, locked, status = fd.process(frame)

        # Annotate the raw frame with the surface outline
        annotated = fd.draw_overlay(frame)

        # ── Stage 2: detect strokes on the flat surface ──
        strokes, drawing_vis = dd.process(warped)
        if strokes:
            last_strokes = strokes

        # ── Display ──────────────────────────────────────
        key = vis.show(annotated, warped, drawing_vis,
                       n_strokes=len(strokes), locked=locked, status=status)

        # ── Key handling ──────────────────────────────────
        if key in (ord('q'), 27):
            break

        elif key == ord('s'):
            if last_strokes:
                dd.save(last_strokes)
            else:
                print("[main] Nothing to save yet.")

        elif key == ord('r'):
            fd.reset()

        elif key == ord('m'):
            fd.start_manual("Drawing Detector")

    cam.release()
    vis.close()
    print("Done.")


if __name__ == "__main__":
    main()