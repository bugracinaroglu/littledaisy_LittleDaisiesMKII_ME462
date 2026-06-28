"""
capture.py  —  Kalibrasyon fotoğrafı toplama scripti
Raspberry Pi üzerinde çalıştır.

Kullanım:
    python capture.py

Kontroller:
    SPACE   -> Fotoğraf kaydet (sadece yeterli marker varsa)
    Q / ESC -> Çıkış
"""

import cv2
import numpy as np
import os
import time

# ─────────────────────────────────────────────
# AYARLAR
# ─────────────────────────────────────────────
OUTPUT_DIR      = "images"          # Fotoğrafların kaydedileceği klasör
FRAME_WIDTH     = 1296
FRAME_HEIGHT    = 972
TARGET_COUNT    = 30                # Kaç fotoğraf hedefliyoruz
CAMERA_BACKEND  = "picamera2"       # "picamera2" veya "opencv"
CAMERA_INDEX    = 0                 # opencv backend için

# Board ayarları (calibrate.py ile aynı olmalı)
SQUARES_X      = 11
SQUARES_Y      = 8
SQUARE_LENGTH  = 16.75
MARKER_LENGTH  = 12.5
ARUCO_DICT_ID  = cv2.aruco.DICT_4X4_50

MIN_MARKERS    = 6    # En az bu kadar marker görünmeli ki SPACE çalışsın
# ─────────────────────────────────────────────


def build_detector():
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    params     = cv2.aruco.DetectorParameters()
    detector   = cv2.aruco.ArucoDetector(aruco_dict, params)
    board      = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH, MARKER_LENGTH, aruco_dict
    )
    return detector, board


def init_camera():
    if CAMERA_BACKEND == "picamera2":
        from picamera2 import Picamera2
        cam = Picamera2()
        cfg = cam.create_preview_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1.0)
        return ("picamera2", cam)

    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return ("opencv", cap)


def read_frame(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        frame = cam.capture_array()          # RGB888 gelir
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return True, frame
    else:
        return cam.read()


def release_camera(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        cam.stop()
        cam.close()
    else:
        cam.release()


def detect_markers(gray, detector, board):
    """
    Frame'de kaç marker ve kaç ChArUco köşesi var, döndür.
    Marker'ların köşelerini de döndür (çizim için).
    """
    marker_corners, marker_ids, _ = detector.detectMarkers(gray)

    n_markers  = len(marker_ids) if marker_ids is not None else 0
    n_charuco  = 0
    ch_corners = None

    if n_markers >= 4:
        ret, ch_corners, ch_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, gray, board
        )
        if ret and ch_corners is not None:
            n_charuco = len(ch_corners)

    return n_markers, n_charuco, marker_corners, marker_ids, ch_corners


def draw_hud(display, count, n_markers, n_charuco, ready):
    h, w = display.shape[:2]

    # ── Üst sol: kaç fotoğraf kaydedildi ──
    saved_color = (0, 220, 0) if count < TARGET_COUNT else (0, 140, 255)
    cv2.putText(display, f"Kaydedilen: {count} / {TARGET_COUNT}",
                (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4)
    cv2.putText(display, f"Kaydedilen: {count} / {TARGET_COUNT}",
                (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.0, saved_color, 2)

    # ── Üst sağ: marker sayısı ──
    marker_txt   = f"Marker: {n_markers}  Kose: {n_charuco}"
    marker_color = (0, 220, 0) if ready else (0, 80, 220)
    cv2.putText(display, marker_txt,
                (w - 380, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 4)
    cv2.putText(display, marker_txt,
                (w - 380, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, marker_color, 2)

    # ── Orta üst: büyük durum göstergesi ──
    if ready:
        msg   = "HAZIR  ->  SPACE"
        color = (0, 220, 0)
    else:
        msg   = f"Board'u goster (min {MIN_MARKERS} marker)"
        color = (0, 80, 220)

    (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 2)
    tx = (w - tw) // 2
    cv2.putText(display, msg, (tx, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 5)
    cv2.putText(display, msg, (tx, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 2)

    # ── Hedef tamam uyarısı ──
    if count >= TARGET_COUNT:
        done_txt = "HEDEF TAMAM — devam edebilir ya da Q ile cik"
        cv2.putText(display, done_txt,
                    (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 140, 255), 2)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    existing = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".jpg")]
    count    = len(existing)

    print(f"Kamera başlatılıyor ({CAMERA_BACKEND})...")
    backend  = init_camera()
    detector, board = build_detector()
    print("Kamera hazır.")
    print(f"  Hedef: {TARGET_COUNT} fotoğraf  |  Mevcut: {count}")
    print(f"  Min marker: {MIN_MARKERS}  |  SPACE: kaydet  |  Q/ESC: çıkış")
    print()

    cv2.namedWindow("Capture", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Capture", 960, 720)

    # Her N frame'de bir tespit yap (Pi'de CPU tasarrufu)
    DETECT_EVERY = 3
    frame_idx    = 0
    n_markers    = 0
    n_charuco    = 0
    last_mcorners = None
    last_chcorners = None
    last_mids    = None

    while True:
        ret, frame = read_frame(backend)
        if not ret or frame is None:
            continue

        frame_idx += 1
        display = frame.copy()

        # ── Marker tespiti (her DETECT_EVERY frame'de bir) ──
        if frame_idx % DETECT_EVERY == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            n_markers, n_charuco, last_mcorners, last_mids, last_chcorners = \
                detect_markers(gray, detector, board)

        ready = (n_markers >= MIN_MARKERS)

        # ── Tespit edilen marker'ları çiz ──
        if last_mcorners and last_mids is not None:
            cv2.aruco.drawDetectedMarkers(display, last_mcorners, last_mids)

        if last_chcorners is not None:
            cv2.aruco.drawDetectedCornersCharuco(display, last_chcorners,
                                                  cornerColor=(0, 255, 100))

        # ── HUD ──
        draw_hud(display, count, n_markers, n_charuco, ready)

        cv2.imshow("Capture", display)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):
            break

        if key == ord(' '):
            if not ready:
                print(f"  ATLANDI: sadece {n_markers} marker görünüyor (min {MIN_MARKERS})")
            else:
                filename = os.path.join(OUTPUT_DIR, f"calib_{count:03d}.jpg")
                cv2.imwrite(filename, frame)
                count += 1
                print(f"  [{count:02d}/{TARGET_COUNT}] Kaydedildi — "
                      f"{n_markers} marker, {n_charuco} köşe")

                # Flash efekti
                flash = display.copy()
                flash[:] = (255, 255, 255)
                cv2.imshow("Capture", flash)
                cv2.waitKey(100)

    release_camera(backend)
    cv2.destroyAllWindows()
    print(f"\nBitti. Toplam {count} fotoğraf: {OUTPUT_DIR}/")
    if count < 15:
        print("UYARI: 15'ten az fotoğraf kalibrasyon için yetersiz olabilir.")


if __name__ == "__main__":
    main()