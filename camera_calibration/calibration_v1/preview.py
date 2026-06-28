"""
preview.py  —  Kalibrasyon sonucunu görsel olarak doğrula
calibration.json yüklenir, canlı kameradan orijinal ve düzeltilmiş
görüntü yan yana gösterilir.

Kullanım:
    python preview.py                    # canlı kamera
    python preview.py --image foto.jpg   # tek bir fotoğraf
"""

import cv2
import numpy as np
import json
import sys
import os
import argparse
import time

CALIB_FILE     = "calibration.json"
CAMERA_BACKEND = "picamera2"    # "picamera2" veya "opencv"
CAMERA_INDEX   = 0

# balance=0.0  -> tüm pikseller geçerli (dar görüş, siyah alan yok)
# balance=1.0  -> orijinal FOV korunur (kenar pikseller siyah olabilir)
BALANCE        = 0.0


def load_calibration(path):
    if not os.path.exists(path):
        print(f"HATA: '{path}' bulunamadı. Önce calibrate.py çalıştır.")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    K = np.array(data["camera_matrix"], dtype=np.float64)
    D = np.array(data["dist_coeffs"],   dtype=np.float64).reshape(-1, 1)
    image_size = tuple(data["image_size"])   # (width, height)
    rms = data.get("rms_error", "?")

    print(f"Kalibrasyon yüklendi: {path}")
    print(f"  Image size : {image_size[0]}x{image_size[1]}")
    print(f"  RMS error  : {rms}")
    print(f"  K  =\n{K}")
    print(f"  D  = {D.flatten()}")
    return K, D, image_size


def build_undistort_maps(K, D, image_size, balance):
    """
    Bir kez hesapla, sonra her frame'e uygula (hızlı).
    image_size: (width, height)
    """
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        K, D, image_size, np.eye(3), balance=balance
    )
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, D, np.eye(3), new_K, image_size, cv2.CV_16SC2
    )
    return map1, map2, new_K


def undistort(frame, map1, map2):
    return cv2.remap(
        frame, map1, map2,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT
    )


def side_by_side(original, corrected):
    """İki frame'i yan yana birleştir, etiket ekle."""
    h = max(original.shape[0], corrected.shape[0])

    def pad(img):
        dh = h - img.shape[0]
        if dh > 0:
            img = cv2.copyMakeBorder(img, 0, dh, 0, 0, cv2.BORDER_CONSTANT)
        return img

    left  = pad(original.copy())
    right = pad(corrected.copy())

    # Etiketler
    cv2.putText(left,  "ORIJINAL",   (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 80, 255), 2)
    cv2.putText(right, "DUZELTILMIS", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 200, 60), 2)

    return np.hstack([left, right])


# ─────────────────────────────────────────────
# Tek fotoğraf modu
# ─────────────────────────────────────────────

def run_image_mode(image_path, map1, map2):
    img = cv2.imread(image_path)
    if img is None:
        print(f"HATA: '{image_path}' okunamadı.")
        sys.exit(1)

    fixed = undistort(img, map1, map2)
    combined = side_by_side(img, fixed)

    # Ekrana sığdır
    max_w = 1800
    if combined.shape[1] > max_w:
        scale = max_w / combined.shape[1]
        combined = cv2.resize(combined, None, fx=scale, fy=scale)

    cv2.imshow("Fisheye Calibration Preview", combined)
    print("Herhangi bir tuşa bas...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ─────────────────────────────────────────────
# Canlı kamera modu
# ─────────────────────────────────────────────

def init_camera(width, height):
    if CAMERA_BACKEND == "picamera2":
        from picamera2 import Picamera2
        cam = Picamera2()
        cfg = cam.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1.0)
        return ("picamera2", cam)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return ("opencv", cap)


def read_frame(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        frame = cam.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return True, frame
    else:
        return cam.read()


def release_camera(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        cam.stop(); cam.close()
    else:
        cam.release()


def run_live_mode(map1, map2, image_size):
    width, height = image_size
    print(f"\nCanlı mod başlatılıyor ({CAMERA_BACKEND})...")
    print("Q / ESC : çıkış   |   S : ekran görüntüsü kaydet")

    backend = init_camera(width, height)
    cv2.namedWindow("Fisheye Calibration Preview", cv2.WINDOW_NORMAL)

    # Display boyutunu küçült (yan yana çok geniş olur)
    display_h = 540
    scale = display_h / height
    display_w = int(width * scale * 2)   # iki frame yan yana
    cv2.resizeWindow("Fisheye Calibration Preview", display_w, display_h)

    snap_count = 0

    while True:
        ret, frame = read_frame(backend)
        if not ret or frame is None:
            continue

        fixed    = undistort(frame, map1, map2)
        combined = side_by_side(frame, fixed)

        # FPS için küçük HUD
        cv2.putText(combined, "S: kaydet  Q: cikis",
                    (15, combined.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("Fisheye Calibration Preview", combined)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        if key == ord('s'):
            fname = f"preview_snap_{snap_count:03d}.jpg"
            cv2.imwrite(fname, combined)
            snap_count += 1
            print(f"Kaydedildi: {fname}")

    release_camera(backend)
    cv2.destroyAllWindows()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, default=None,
                        help="Tek fotoğraf modu: --image foto.jpg")
    parser.add_argument("--balance", type=float, default=BALANCE,
                        help="FOV balance: 0.0=tam crop, 1.0=tam FOV (default: 0.0)")
    args = parser.parse_args()

    K, D, image_size = load_calibration(CALIB_FILE)

    print(f"\nUndistortion map'leri oluşturuluyor (balance={args.balance})...")
    map1, map2, new_K = build_undistort_maps(K, D, image_size, args.balance)
    print("Hazır.\n")

    if args.image:
        run_image_mode(args.image, map1, map2)
    else:
        run_live_mode(map1, map2, image_size)


if __name__ == "__main__":
    main()
