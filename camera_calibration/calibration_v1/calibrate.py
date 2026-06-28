"""
calibrate.py  —  ChArUco + Fisheye kalibrasyon scripti
PC veya Raspberry Pi üzerinde çalıştır.

Kullanım:
    python calibrate.py

Çıktı:
    calibration.json  (K matrisi, D katsayıları, image size)
"""

import cv2
import numpy as np
import json
import os
import sys

# ─────────────────────────────────────────────
# BOARD AYARLARI  ← burası sana göre
# ─────────────────────────────────────────────
SQUARES_X      = 11          # Yatay kare sayısı
SQUARES_Y      = 8           # Dikey kare sayısı
SQUARE_LENGTH  = 16.75       # mm — bir karenin kenar uzunluğu
MARKER_LENGTH  = 12.5        # mm — ArUco marker kenar uzunluğu (~%75 of square)

# Board'u bastırırken hangi dictionary kullandıysan onu seç.
# Seçenekler: DICT_4X4_50, DICT_5X5_50, DICT_5X5_100, DICT_6X6_50, DICT_6X6_250
ARUCO_DICT_ID  = cv2.aruco.DICT_4X4_50
# ─────────────────────────────────────────────

IMAGES_DIR     = "images"
OUTPUT_FILE    = "calibration.json"
MIN_IMAGES     = 10          # Kabul edilebilir minimum fotoğraf sayısı


def build_board():
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    board = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y),
        SQUARE_LENGTH,
        MARKER_LENGTH,
        aruco_dict
    )
    return board, aruco_dict


def detect_corners(image_path, board, aruco_dict, detector):
    """
    Tek bir görüntüde ChArUco köşelerini tespit et.
    Başarılıysa (obj_points, img_points) döner, aksi halde None.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"  HATA: Okunamadı — {image_path}")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Marker'ları tespit et
    marker_corners, marker_ids, _ = detector.detectMarkers(gray)

    if marker_ids is None or len(marker_ids) < 4:
        print(f"  ATLA: Yeterli marker yok ({image_path})")
        return None

    # ChArUco köşelerini interpolate et
    ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        marker_corners, marker_ids, gray, board
    )

    if not ret or charuco_corners is None or len(charuco_corners) < 4:
        print(f"  ATLA: Yeterli ChArUco köşesi yok ({image_path})")
        return None

    # 3D nesne noktaları — board üzerindeki gerçek koordinatlar
    obj_points = board.getChessboardCorners()[charuco_ids.flatten()]

    # Fisheye calibrate için shape: (N, 1, 3) ve (N, 1, 2)
    obj_points = obj_points.reshape(-1, 1, 3).astype(np.float32)
    img_points = charuco_corners.reshape(-1, 1, 2).astype(np.float32)

    print(f"  OK: {len(charuco_corners):2d} köşe — {os.path.basename(image_path)}")
    return obj_points, img_points, gray.shape[::-1]   # (w, h)


def run_calibration(all_obj_points, all_img_points, image_size):
    """
    cv2.fisheye.calibrate çalıştır.
    image_size: (width, height)
    """
    K = np.zeros((3, 3))
    D = np.zeros((4, 1))

    flags = (
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
        cv2.fisheye.CALIB_CHECK_COND           |
        cv2.fisheye.CALIB_FIX_SKEW
    )

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 200, 1e-7)

    rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
        all_obj_points,
        all_img_points,
        image_size,
        K,
        D,
        flags=flags,
        criteria=criteria
    )

    return rms, K, D


def main():
    # ── Fotoğrafları bul ──
    image_files = sorted([
        os.path.join(IMAGES_DIR, f)
        for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if len(image_files) == 0:
        print(f"HATA: '{IMAGES_DIR}/' klasöründe fotoğraf bulunamadı.")
        sys.exit(1)

    print(f"Toplam {len(image_files)} fotoğraf bulundu.")
    print(f"Board: {SQUARES_X}x{SQUARES_Y} squares, {SQUARE_LENGTH}mm, marker {MARKER_LENGTH}mm")
    print()

    # ── Board ve dedektör ──
    board, aruco_dict = build_board()

    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)

    # ── Köşe tespiti ──
    all_obj_points = []
    all_img_points = []
    image_size     = None

    print("Köşe tespiti yapılıyor...")
    for path in image_files:
        result = detect_corners(path, board, aruco_dict, detector)
        if result is not None:
            obj_pts, img_pts, size = result
            all_obj_points.append(obj_pts)
            all_img_points.append(img_pts)
            if image_size is None:
                image_size = size   # (width, height)

    print()
    print(f"Kullanılabilir: {len(all_obj_points)} / {len(image_files)} fotoğraf")

    if len(all_obj_points) < MIN_IMAGES:
        print(f"HATA: En az {MIN_IMAGES} geçerli fotoğraf gerekiyor.")
        print("Daha fazla fotoğraf çek veya farklı açılar dene.")
        sys.exit(1)

    # ── Kalibrasyon ──
    print("Kalibrasyon hesaplanıyor...")
    try:
        rms, K, D = run_calibration(all_obj_points, all_img_points, image_size)
    except cv2.error as e:
        print("HATA: Kalibrasyon başarısız:")
        print(str(e))
        print()
        print("İpucu: Fotoğraflar yeterince çeşitli olmayabilir.")
        print("  • Farklı açılar (eğim, rotasyon) ekle")
        print("  • Board'u görüntünün kenarlarına da taşı")
        print("  • CALIB_CHECK_COND hatasıysa bazı fotoğrafları sil")
        sys.exit(1)

    # ── Sonuçlar ──
    print()
    print("=" * 50)
    print(f"RMS reprojection error : {rms:.4f}  (iyi: < 1.0)")
    print()
    print("Camera Matrix (K):")
    print(K)
    print()
    print("Distortion Coefficients (D) [k1, k2, k3, k4]:")
    print(D.flatten())
    print("=" * 50)
    print()

    if rms > 2.0:
        print("UYARI: RMS hatası yüksek. Fotoğraf kalitesini kontrol et.")

    # ── JSON export ──
    calib_data = {
        "note": "cv2.fisheye model — K ve D, cv2.fisheye.calibrate() ile üretildi.",
        "board": {
            "squares_x": SQUARES_X,
            "squares_y": SQUARES_Y,
            "square_length_mm": SQUARE_LENGTH,
            "marker_length_mm": MARKER_LENGTH
        },
        "image_size": list(image_size),          # [width, height]
        "rms_error": round(float(rms), 5),
        "camera_matrix": K.tolist(),             # 3x3
        "dist_coeffs": D.flatten().tolist()      # [k1, k2, k3, k4]
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(calib_data, f, indent=2)

    print(f"Kalibrasyon kaydedildi: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()