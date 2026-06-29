# LittleDaisies MKII – ME462

This repository contains the software development versions and experiments for the **LittleDaisies MKII** robot project. It includes fisheye camera calibration, drawing detection and processing, robot drawing-job generation, and robot head vision and control.

## Camera Calibration

ChArUco-based tools for calibrating the fisheye camera and correcting image distortion.

* **Calibration V1:** Captures calibration images first and generates the calibration file afterward.
* **Calibration V2:** Performs calibration directly from the live camera feed.
* **Preview Test:** Compares calibration files and undistortion settings.

## Drawing Detector

Contains both camera-based drawing detection and a tablet drawing server.

### Camera-Based Versions

* **V1:** Detects the drawing surface, corrects its perspective, and extracts dark strokes.
* **V2:** Improves surface detection using stronger white-area and dark-frame validation.

### Tablet Server Versions

* **V1:** Basic tablet drawing interface and JSON export.
* **V2:** Adds a native Raspberry Pi preview and raw-point processing.
* **V3:** Adds bottom-left coordinates, stroke IDs, comparison, and robot-job generation.
* **V4:** Adds startup reset, full-erase handling, and old-snapshot protection.
* **V5:** Adds configurable cleanup of runtime files and states.
* **V6:** Adds timestamped FIFO robot jobs, queue tracking, and delayed drawing comparison. This is the current main drawing-server version.

## Robot Head Project

Contains the computer/Raspberry Pi vision system and RP2350 microcontroller software for tracking, gestures, facial expressions, servo control, LCD faces, and IMU-based behaviors.

* **V1:** Initial modular computer-side tracking and behavior system.
* **V2:** Adds RP2350 control, serial communication, face fallback, and open-palm detection.
* **V3:** Adds IMU motion detection, running and dizzy behaviors, and arm animations.
* **V4:** Adds OpenCV/Picamera2 support, fisheye correction modes, and head-mounted camera control.
* **V5:** Uses Picamera2 with fisheye correction and head-mounted tracking defaults, with lighter processing settings. This is the latest robot-head version.

Detailed setup and usage information is available in the README file inside each main project folder.
