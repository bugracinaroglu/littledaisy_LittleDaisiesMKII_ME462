"""
diagnose.py  —  Kaydedilen fotoğraflarda ne algılandığını gösterir.
Hangi fotoğrafın neden reddedildiğini anlamak için kullan.

Kullanım:
    python diagnose.py

Kontroller:
    N / SPACE  -> Sonraki fotoğraf
    P          -> Önceki fotoğraf
    Q / ESC    -> Çıkış
"""

import cv2
import numpy as np
import os
import sys

# ─────────────────────────────────────────────
# AYARLAR  (capture.py ve calibrate.py ile aynı olmalı)
# ─────────────────────────────────────────────
IMAGES_DIR     = "images"
SQUARES_X      = 11
SQUARES_Y      = 8
SQUARE_LENGTH  = 16.75
MARKER_LENGTH  = 12.5
ARUCO_DICT_ID  = cv2.aruco.DICT_4X4_50
# ─────────────────────────────────────────────

# Tüm dictionary'leri dene — hangi birinin marker bulduğunu göster
DICT_CANDIDATES = {
    "4X4_50":   cv2.aruco.DICT_4X4_50,
    "4X4_100":  cv2.aruco.DICT_4X4_100,
    "5X5_50":   cv2.aruco.DICT_5X5_50,
    "5X5_100":  cv2.aruco.DICT_5X5_100,
    "6X6_50":   cv2.aruco.DICT_6X6_50,
}


def try_all_dicts(gray):
    """İlk fotoğrafta hangi dictionary çalışıyor, bul."""
    results = {}
    for name, dict_id in DICT_CANDIDATES.items():
        d = cv2.aruco.getPredefinedDictionary(dict_id)
        det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
        corners, ids, _ = det.detectMarkers(gray)
        n = len(ids) if ids is not None else 0
        results[name] = n
    return results


def detect_on_image(img, aruco_dict, board):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

    mcorners, mids, _ = detector.detectMarkers(gray)
    n_markers = len(mids) if mids is not None else 0

    n_charuco  = 0
    ch_corners = None
    ch_ids     = None

    if n_markers >= 4:
        ret, ch_corners, ch_ids = cv2.aruco.interpolateCornersCharuco(
            mcorners, mids, gray, board
        )
        if ret and ch_corners is not None:
            n_charuco = len(ch_corners)

    return n_markers, n_charuco, mcorners, mids, ch_corners, ch_ids


def render(img, n_markers, n_charuco, mcorners, mids, ch_corners, ch_ids,
           filename, idx, total):
    display = img.copy()

    # Marker ve köşeleri çiz
    if mcorners and mids is not None:
        cv2.aruco.drawDetectedMarkers(display, mcorners, mids)

    if ch_corners is not None:
        cv2.aruco.drawDetectedCornersCharuco(display, ch_corners, ch_ids,
                                              cornerColor=(0, 255, 80))

    h, w = display.shape[:2]

    # Durum rengi
    if n_markers == 0:
        status = "HICBIR MARKER YOK"
        color  = (0, 0, 220)
    elif n_markers < 4:
        status = f"YETERSIZ MARKER: {n_markers}"
        color  = (0, 80, 220)
    elif n_charuco < 6:
        status = f"MARKER OK ({n_markers}) ama ChArUco kose az: {n_charuco}"
        color  = (0, 165, 255)
    else:
        status = f"OK — {n_markers} marker, {n_charuco} kose"
        color  = (0, 210, 0)

    # Overlay kutusu
    cv2.rectangle(display, (0, 0), (w, 90), (0, 0, 0), -1)
    cv2.putText(display, f"[{idx+1}/{total}]  {os.path.basename(filename)}",
                (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (200, 200, 200), 1)
    cv2.putText(display, status,
                (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # Alt kısım: kontroller
    cv2.rectangle(display, (0, h - 40), (w, h), (0, 0, 0), -1)
    cv2.putText(display, "N/SPACE: ileri   P: geri   Q/ESC: cikis",
                (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)

    return display


def main():
    image_files = sorted([
        os.path.join(IMAGES_DIR, f)
        for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if not image_files:
        print(f"HATA: '{IMAGES_DIR}/' içinde fotoğraf yok.")
        sys.exit(1)

    print(f"{len(image_files)} fotoğraf bulundu.")

    # ── İlk fotoğrafda tüm dictionary'leri dene ──
    first_img  = cv2.imread(image_files[0])
    first_gray = cv2.cvtColor(first_img, cv2.COLOR_BGR2GRAY)
    dict_results = try_all_dicts(first_gray)

    print("\nDictionary tarama (ilk fotoğraf):")
    best_dict = None
    best_count = 0
    for name, count in dict_results.items():
        marker = " <-- EN IYI" if count == max(dict_results.values()) and count > 0 else ""
        print(f"  {name:12s}: {count} marker{marker}")
        if count > best_count:
            best_count = count
            best_dict  = name

    if best_count == 0:
        print("\nHICBIR DICTIONARY MARKER BULAMADI.")
        print("Olası sebepler:")
        print("  • Fotoğraf bulanık / aşırı parlak / karanlık")
        print("  • Board yanlış bastırılmış")
        print("  • Kamera çok uzak")
    else:
        print(f"\nÖnerilen dictionary: DICT_{best_dict}")
        print(f"Şu an ayarlı: DICT_{[k for k,v in DICT_CANDIDATES.items() if v == ARUCO_DICT_ID][0]}")

    # ── Görsel inceleme ──
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    board = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH, MARKER_LENGTH, aruco_dict
    )

    cv2.namedWindow("Diagnose", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Diagnose", 1100, 820)

    idx = 0
    while True:
        path = image_files[idx]
        img  = cv2.imread(path)

        n_m, n_c, mcorners, mids, ch_corners, ch_ids = detect_on_image(img, aruco_dict, board)
        display = render(img, n_m, n_c, mcorners, mids, ch_corners, ch_ids,
                         path, idx, len(image_files))

        cv2.imshow("Diagnose", display)
        key = cv2.waitKey(0) & 0xFF

        if key in (ord('q'), 27):
            break
        elif key in (ord('n'), ord(' ')):
            idx = (idx + 1) % len(image_files)
        elif key == ord('p'):
            idx = (idx - 1) % len(image_files)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
