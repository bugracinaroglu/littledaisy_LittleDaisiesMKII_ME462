import time
import math
import numpy as np
import base64

import cv2

from behavior.behavior_manager import BehaviorManager
from camera import Camera
from config import *



from control.command_sender import CommandSender
from control.control_mode import ControlMode, ControlModeManager
from control.head_pose_mapper import HeadPoseMapper
from control.manual_controller import ManualController
from control.robot_head_interface import RobotHeadInterface
from vision.distance_estimator import TargetDistanceEstimator
from vision.gesture_detector import GestureDetector
from vision.human_tracker import HumanTracker
from vision.target_selector import TargetSelector
from visualizer import Visualizer


import mediapipe as mp


def create_caricature_mediapipe(img):
    """Generate a clean 1-bit caricature sketch using MediaPipe Face Mesh."""
    mp_face_mesh = mp.solutions.face_mesh
    
    # Initialize canvases
    h, w = img.shape[:2]
    img_basic = np.zeros_like(img) # Blank black canvas for 1-bit caricature
    img_tess = img.copy()
    img_cont = img.copy()
    
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    ) as face_mesh:
        results = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        
        if not results.multi_face_landmarks:
            empty_metrics = {
                'm_var': 0, 'fh_var': 0, 'sp_var': 0, 'gt_var': 0, 'lj_var': 0, 'rj_var': 0, 'gl_var': 0,
                'm_mean': 0, 'fh_mean': 0, 'sp_mean': 0, 'gt_mean': 0, 'lj_mean': 0, 'rj_mean': 0, 'gl_mean': 0,
                'm_avg': (0,0,0), 'fh_avg': (0,0,0), 'sp_avg': (0,0,0), 'gt_avg': (0,0,0), 'lj_avg': (0,0,0), 'rj_avg': (0,0,0), 'gl_avg': (0,0,0),
                'm_dist': 0, 'sp_dist': 0, 'gt_dist': 0, 'lj_dist': 0, 'rj_dist': 0, 'gl_dist': 0
            }
            return img_basic, img_tess, img_cont, img.copy(), img.copy(), False, False, False, False, False, False, empty_metrics
            
        face_landmarks = results.multi_face_landmarks[0]
        
        # Function to draw a specific set of connections
        def draw_feature(canvas, connections, color=(0, 255, 0), thickness=2):
            if not connections:
                return
            for connection in connections:
                start_idx = connection[0]
                end_idx = connection[1]
                pt1 = face_landmarks.landmark[start_idx]
                pt2 = face_landmarks.landmark[end_idx]
                x1, y1 = int(pt1.x * w), int(pt1.y * h)
                x2, y2 = int(pt2.x * w), int(pt2.y * h)
                cv2.line(canvas, (x1, y1), (x2, y2), color, thickness)

        # 1. Basic + Iris (Drawn in White for 1-bit Caricature)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_FACE_OVAL, color=(255, 255, 255), thickness=2)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_LEFT_EYE, color=(255, 255, 255), thickness=2)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_RIGHT_EYE, color=(255, 255, 255), thickness=2)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_LIPS, color=(255, 255, 255), thickness=2)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_LEFT_EYEBROW, color=(255, 255, 255), thickness=2)
        draw_feature(img_basic, mp_face_mesh.FACEMESH_RIGHT_EYEBROW, color=(255, 255, 255), thickness=2)
        if hasattr(mp_face_mesh, 'FACEMESH_LEFT_IRIS'):
            left_iris_pts = [face_landmarks.landmark[idx] for pair in mp_face_mesh.FACEMESH_LEFT_IRIS for idx in pair]
            if left_iris_pts:
                cx = int(np.mean([pt.x * w for pt in left_iris_pts]))
                cy = int(np.mean([pt.y * h for pt in left_iris_pts]))
                cv2.circle(img_basic, (cx, cy), 3, (255, 255, 255), -1)
                
            right_iris_pts = [face_landmarks.landmark[idx] for pair in mp_face_mesh.FACEMESH_RIGHT_IRIS for idx in pair]
            if right_iris_pts:
                cx = int(np.mean([pt.x * w for pt in right_iris_pts]))
                cy = int(np.mean([pt.y * h for pt in right_iris_pts]))
                cv2.circle(img_basic, (cx, cy), 3, (255, 255, 255), -1)
        if hasattr(mp_face_mesh, 'FACEMESH_NOSE'):
            draw_feature(img_basic, mp_face_mesh.FACEMESH_NOSE, color=(255, 255, 255), thickness=2)
            
        # 2. Tesselation
        draw_feature(img_tess, mp_face_mesh.FACEMESH_TESSELATION, color=(255, 255, 0), thickness=1)
        
        # --- MUSTACHE DETECTION (POLYGON MESH METHOD WITH BASELINE) ---
        mustache_detected = False
        soul_patch_detected = False
        goatee_detected = False
        left_jaw_detected = False
        right_jaw_detected = False
        glasses_detected = False
        metrics = {'m_var': 0.0, 'fh_var': 0.0, 'sp_var': 0.0, 'gt_var': 0.0, 'lj_var': 0.0, 'rj_var': 0.0, 'gl_var': 0.0,
                   'm_mean': 0.0, 'fh_mean': 0.0, 'sp_mean': 0.0, 'gt_mean': 0.0, 'lj_mean': 0.0, 'rj_mean': 0.0, 'gl_mean': 0.0}
        img_mustache = img.copy()
        
        try:
            # 1. Draw the full Tesselation on the new mustache window (faint yellow)
            draw_feature(img_mustache, mp_face_mesh.FACEMESH_TESSELATION, color=(150, 150, 0), thickness=1)
            
            # 2. Define the Mustache Polygon (User-provided indices)
            mustache_indices = [0, 37, 39, 40, 43, 202, 212, 216, 206, 203, 99, 97, 2, 326, 327, 423, 426, 436, 432, 422, 273, 267, 269, 270]
            poly_points = []
            for idx in mustache_indices:
                lm = face_landmarks.landmark[idx]
                poly_points.append([int(lm.x * w), int(lm.y * h)])
            poly_points = np.array(poly_points, np.int32).reshape((-1, 1, 2))
            
            # 3. Define the Forehead Baseline Polygon (User-provided indices)
            forehead_indices = [54, 104, 69, 108, 151, 337, 299, 333, 298, 251, 284, 332, 297, 338, 10, 109, 67, 103]
            fh_points = []
            for idx in forehead_indices:
                lm = face_landmarks.landmark[idx]
                fh_points.append([int(lm.x * w), int(lm.y * h)])
            fh_points = np.array(fh_points, np.int32).reshape((-1, 1, 2))
            
            # 4. Define the Soul Patch Polygon (User-provided indices)
            soul_patch_indices = [182, 201, 200, 421, 418, 406, 405, 314, 17, 84, 181, 91]
            sp_points = []
            for idx in soul_patch_indices:
                lm = face_landmarks.landmark[idx]
                sp_points.append([int(lm.x * w), int(lm.y * h)])
            sp_points = np.array(sp_points, np.int32).reshape((-1, 1, 2))
            
            # 5. Define the Goatee Polygon (User-provided indices)
            goatee_indices = [149, 176, 148, 152, 377, 400, 378, 395, 431, 262, 428, 199, 208, 32, 211, 170]
            gt_points = []
            for idx in goatee_indices:
                lm = face_landmarks.landmark[idx]
                gt_points.append([int(lm.x * w), int(lm.y * h)])
            gt_points = np.array(gt_points, np.int32).reshape((-1, 1, 2))
            
            # 6. Define the Left Jaw Polygon
            left_jaw_indices = [379, 394, 430, 434, 416, 411, 352, 401, 361, 288, 397, 365]
            lj_points = []
            for idx in left_jaw_indices:
                lm = face_landmarks.landmark[idx]
                lj_points.append([int(lm.x * w), int(lm.y * h)])
            lj_points = np.array(lj_points, np.int32).reshape((-1, 1, 2))
            
            # 7. Define the Right Jaw Polygon
            right_jaw_indices = [150, 170, 211, 210, 214, 187, 123, 177, 215, 58, 172, 136]
            rj_points = []
            for idx in right_jaw_indices:
                lm = face_landmarks.landmark[idx]
                rj_points.append([int(lm.x * w), int(lm.y * h)])
            rj_points = np.array(rj_points, np.int32).reshape((-1, 1, 2))
            
            # 8. Define the Glasses Polygon (Bridge of the nose)
            glasses_indices = [133, 168, 362, 343, 197, 114]
            gl_points = []
            for idx in glasses_indices:
                lm = face_landmarks.landmark[idx]
                gl_points.append([int(lm.x * w), int(lm.y * h)])
            gl_points = np.array(gl_points, np.int32).reshape((-1, 1, 2))
            
            # Draw polygons on the mesh window
            cv2.polylines(img_mustache, [poly_points], isClosed=True, color=(0, 0, 255), thickness=2)    # Mustache = RED
            cv2.polylines(img_mustache, [fh_points], isClosed=True, color=(0, 255, 0), thickness=2)      # Forehead = GREEN
            cv2.polylines(img_mustache, [sp_points], isClosed=True, color=(255, 255, 0), thickness=2)    # Soul Patch = CYAN
            cv2.polylines(img_mustache, [gt_points], isClosed=True, color=(255, 0, 255), thickness=2)    # Goatee = MAGENTA
            cv2.polylines(img_mustache, [lj_points], isClosed=True, color=(0, 128, 255), thickness=2)    # Left Jaw = ORANGE
            cv2.polylines(img_mustache, [rj_points], isClosed=True, color=(200, 0, 200), thickness=2)    # Right Jaw = PURPLE
            cv2.polylines(img_mustache, [gl_points], isClosed=True, color=(255, 255, 255), thickness=2)  # Glasses = WHITE
            
            # Create Binary Masks
            mask_m = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_m, [poly_points], 255)
            
            mask_fh = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_fh, [fh_points], 255)
            
            mask_sp = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_sp, [sp_points], 255)
            
            mask_gt = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_gt, [gt_points], 255)
            
            mask_lj = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_lj, [lj_points], 255)
            
            mask_rj = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_rj, [rj_points], 255)
            
            mask_gl = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_gl, [gl_points], 255)
            
            # Math processing
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
            
            # Extract Pixels
            m_pixels_gray = gray_img[mask_m == 255]
            m_pixels_lap = laplacian[mask_m == 255]
            
            fh_pixels_gray = gray_img[mask_fh == 255]
            fh_pixels_lap = laplacian[mask_fh == 255]
            
            sp_pixels_gray = gray_img[mask_sp == 255]
            sp_pixels_lap = laplacian[mask_sp == 255]
            
            gt_pixels_gray = gray_img[mask_gt == 255]
            gt_pixels_lap = laplacian[mask_gt == 255]
            
            lj_pixels_gray = gray_img[mask_lj == 255]
            lj_pixels_lap = laplacian[mask_lj == 255]
            
            rj_pixels_gray = gray_img[mask_rj == 255]
            rj_pixels_lap = laplacian[mask_rj == 255]
            
            gl_pixels_gray = gray_img[mask_gl == 255]
            gl_pixels_lap = laplacian[mask_gl == 255]
            
            if len(m_pixels_gray) > 0 and len(fh_pixels_gray) > 0 and len(sp_pixels_gray) > 0 and len(gt_pixels_gray) > 0 and len(lj_pixels_gray) > 0 and len(rj_pixels_gray) > 0 and len(gl_pixels_gray) > 0:
                m_var = np.var(m_pixels_lap)
                fh_var = np.var(fh_pixels_lap)
                sp_var = np.var(sp_pixels_lap)
                gt_var = np.var(gt_pixels_lap)
                lj_var = np.var(lj_pixels_lap)
                rj_var = np.var(rj_pixels_lap)
                gl_var = np.var(gl_pixels_lap)
                
                m_mean = np.mean(m_pixels_gray)
                fh_mean = np.mean(fh_pixels_gray)
                sp_mean = np.mean(sp_pixels_gray)
                gt_mean = np.mean(gt_pixels_gray)
                lj_mean = np.mean(lj_pixels_gray)
                rj_mean = np.mean(rj_pixels_gray)
                gl_mean = np.mean(gl_pixels_gray)
                
                def get_mid_color(image, pts):
                    if len(pts) == 0: return (0,0,0)
                    cx = int(np.mean([p[0][0] for p in pts]))
                    cy = int(np.mean([p[0][1] for p in pts]))
                    cy = max(0, min(cy, image.shape[0]-1))
                    cx = max(0, min(cx, image.shape[1]-1))
                    return tuple(map(int, image[cy, cx]))
                    
                m_avg = tuple(map(int, cv2.mean(img, mask=mask_m)[:3]))
                fh_avg = tuple(map(int, cv2.mean(img, mask=mask_fh)[:3]))
                sp_avg = tuple(map(int, cv2.mean(img, mask=mask_sp)[:3]))
                gt_avg = tuple(map(int, cv2.mean(img, mask=mask_gt)[:3]))
                lj_avg = tuple(map(int, cv2.mean(img, mask=mask_lj)[:3]))
                rj_avg = tuple(map(int, cv2.mean(img, mask=mask_rj)[:3]))
                gl_avg = tuple(map(int, cv2.mean(img, mask=mask_gl)[:3]))
                
                m_mid = get_mid_color(img, poly_points)
                fh_mid = get_mid_color(img, fh_points)
                sp_mid = get_mid_color(img, sp_points)
                gt_mid = get_mid_color(img, gt_points)
                lj_mid = get_mid_color(img, lj_points)
                rj_mid = get_mid_color(img, rj_points)
                gl_mid = get_mid_color(img, gl_points)
                
                metrics = {
                    'm_var': m_var, 'fh_var': fh_var, 'sp_var': sp_var, 'gt_var': gt_var, 'lj_var': lj_var, 'rj_var': rj_var, 'gl_var': gl_var,
                    'm_mean': m_mean, 'fh_mean': fh_mean, 'sp_mean': sp_mean, 'gt_mean': gt_mean, 'lj_mean': lj_mean, 'rj_mean': rj_mean, 'gl_mean': gl_mean,
                    'm_avg': m_avg, 'fh_avg': fh_avg, 'sp_avg': sp_avg, 'gt_avg': gt_avg, 'lj_avg': lj_avg, 'rj_avg': rj_avg, 'gl_avg': gl_avg,
                    'm_mid': m_mid, 'fh_mid': fh_mid, 'sp_mid': sp_mid, 'gt_mid': gt_mid, 'lj_mid': lj_mid, 'rj_mid': rj_mid, 'gl_mid': gl_mid
                }
                
                # DETECTION LOGIC (Euclidean Color Distance relative to Forehead)
                def color_distance(c1, c2):
                    return np.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2)
                
                dist_m = color_distance(m_avg, fh_avg)
                dist_sp = color_distance(sp_avg, fh_avg)
                dist_gt = color_distance(gt_avg, fh_avg)
                dist_lj = color_distance(lj_avg, fh_avg)
                dist_rj = color_distance(rj_avg, fh_avg)
                dist_gl = color_distance(gl_avg, fh_avg)
                
                metrics.update({
                    'm_dist': dist_m, 'sp_dist': dist_sp, 'gt_dist': dist_gt,
                    'lj_dist': dist_lj, 'rj_dist': dist_rj, 'gl_dist': dist_gl
                })
                
                COLOR_THRESH = 65.0
                mustache_detected = dist_m > COLOR_THRESH
                soul_patch_detected = dist_sp > COLOR_THRESH
                goatee_detected = dist_gt > COLOR_THRESH
                left_jaw_detected = dist_lj > COLOR_THRESH
                right_jaw_detected = dist_rj > COLOR_THRESH
                glasses_detected = dist_gl > COLOR_THRESH
                
            # --- DEBUG: Draw Landmark IDs on Tesselation Window ---
            img_tess = cv2.resize(img_tess, (w * 3, h * 3))
            for idx, lm in enumerate(face_landmarks.landmark):
                tx, ty = int(lm.x * w * 3), int(lm.y * h * 3)
                cv2.putText(img_tess, str(idx), (tx, ty), cv2.FONT_HERSHEY_PLAIN, 0.8, (255, 255, 255), 1)
                cv2.circle(img_tess, (tx, ty), 2, (0, 0, 255), -1)
            # ------------------------------------------------------
                
            # ----------------------------------------------------
            # WARP THE FINAL IMAGES TO A PERFECT CIRCLE
            # ----------------------------------------------------
            img_warped_oval = np.zeros_like(img)
            try:
                from vision.face_warper import warp_face_to_circle
                img_basic = warp_face_to_circle(img_basic, face_landmarks)
                img_mustache = warp_face_to_circle(img_mustache, face_landmarks)
                
                # Get the fully warped color face
                warped_color = warp_face_to_circle(img, face_landmarks)
                
                # Mask out the background so we ONLY see the face inside the circle
                mask = np.zeros_like(img, dtype=np.uint8)
                center = (int(w/2), int(h/2))
                radius = int(min(w, h) / 2.0 - 5)
                cv2.circle(mask, center, radius, (255, 255, 255), -1)
                
                img_warped_oval = cv2.bitwise_and(warped_color, mask)
                # Draw the white border ring
                cv2.circle(img_warped_oval, center, radius, (255, 255, 255), 2)
                
            except Exception as warp_e:
                print("Warping failed:", warp_e)
                
        except Exception as e:
            print("Mustache poly error:", e)
        # ------------------------------------------------
            
    return img_basic, img_tess, img_cont, img_mustache, img_warped_oval, mustache_detected, soul_patch_detected, goatee_detected, left_jaw_detected, right_jaw_detected, glasses_detected, metrics


def estimate_pan_servo_angle(head_pan_angle):
    """Mirror the RP2350 gear conversion for display purposes only."""
    if head_pan_angle is None:
        return None

    direction = -1.0 if STATUS_PAN_GEAR_REVERSES_DIRECTION else 1.0
    head_offset = float(head_pan_angle) - HEAD_PAN_CENTER_ANGLE
    servo_angle = (
        STATUS_PAN_SERVO_NEUTRAL_ANGLE
        + direction * STATUS_PAN_GEAR_RATIO * head_offset
    )
    return max(
        STATUS_PAN_SERVO_MIN_ANGLE,
        min(servo_angle, STATUS_PAN_SERVO_MAX_ANGLE),
    )


def describe_gesture(gesture_result):
    if not gesture_result:
        return "--"
    if gesture_result.get("hello_event", False):
        return "HELLO EVENT"
    if gesture_result.get("waving", False):
        return "WAVE"
    if gesture_result.get("open_palm", False):
        return "OPEN PALM"

    # Check if any hand has a recognized top gesture
    hands = gesture_result.get("hands", [])
    for hand in hands:
        top = hand.get("top_gesture", "None")
        if top != "None":
            return top.upper()

    if gesture_result.get("hand_detected", False):
        return "HAND"
    return "NONE"


def create_emotion_detector():
    if not ENABLE_EMOTION:
        return None

    try:
        from vision.emotion_detector import EmotionDetector

        return EmotionDetector(
            model_path=EMOTION_MODEL_PATH,
            analyze_every_n_frames=EMOTION_ANALYZE_EVERY_N_FRAMES,
        )
    except Exception as exc:
        print("[Emotion init error]")
        print(exc)
        print("Emotion detector disabled.")
        return None


def print_keyboard_help():
    print("Keys (click the OpenCV camera window first):")
    print("1: AUTO mode | 2: MANUAL mode")
    print("MANUAL pose: J/L pan | I/K tilt | C center | S stop")
    print("MANUAL faces: F curious | 4 sigma | 5 sunglasses | 9 thinking")
    print("MANUAL LCD text: [ Oopsie Daisy | ] configured general text")
    print("MANUAL gestures: N nod | O sunglasses nod | G sigma nod")
    print("MANUAL gestures: X shake | B look around | M celebrate")
    print("MANUAL: Z sleep | W wake up | 0 cancel active gesture")
    print("E: emergency stop and switch to MANUAL | Q: quit")
    print("H/V: image flip | D: pan servo direction | T: tilt servo direction")
    print("R: reverse X | Y: reverse Y | U: enable/disable up-down tracking")
    print("P: show/hide live status panel")


def main():
    camera = Camera(
        backend=CAMERA_BACKEND,
        profile=CAMERA_PROFILE,
        camera_index=CAMERA_INDEX,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
        flip_horizontal=FLIP_FRAME_HORIZONTAL,
        flip_vertical=FLIP_FRAME_VERTICAL,
        fisheye_correction_mode=FISHEYE_CORRECTION_MODE,
        calibration_file=CAMERA_CALIBRATION_FILE,
        fisheye_balance=FISHEYE_BALANCE,
        require_calibration=REQUIRE_CALIBRATION,
    )

    if not camera.is_opened():
        print("Camera could not be opened.")
        print("Check CAMERA_BACKEND or the Picamera2 installation.")
        return

    visualizer = Visualizer()

    human_tracker = None
    if ENABLE_HUMAN_TRACKING:
        human_tracker = HumanTracker(
            detection_confidence=POSE_DETECTION_CONFIDENCE,
            tracking_confidence=POSE_TRACKING_CONFIDENCE,
            landmark_visibility=POSE_LANDMARK_VISIBILITY,
            strict_torso_validation=STRICT_TORSO_VALIDATION,
            enable_face_fallback=ENABLE_FACE_FALLBACK,
            min_body_height_ratio=MIN_BODY_HEIGHT_RATIO,
            min_body_width_ratio=MIN_BODY_WIDTH_RATIO,
            min_upper_body_height_ratio=MIN_UPPER_BODY_HEIGHT_RATIO,
            min_upper_body_width_ratio=MIN_UPPER_BODY_WIDTH_RATIO,
            min_visible_pose_points=MIN_VISIBLE_POSE_POINTS,
        )

    emotion_detector = create_emotion_detector()

    gesture_detector = None
    if ENABLE_GESTURE:
        gesture_detector = GestureDetector(
            process_every_n_frames=GESTURE_PROCESS_EVERY_N_FRAMES,
            max_num_hands=MAX_NUM_HANDS,
            detection_confidence=HAND_DETECTION_CONFIDENCE,
            tracking_confidence=HAND_TRACKING_CONFIDENCE,
            wave_history_size=WAVE_HISTORY_SIZE,
            wave_min_x_range=WAVE_MIN_X_RANGE,
            wave_min_direction_changes=WAVE_MIN_DIRECTION_CHANGES,
            wave_min_step=WAVE_MIN_STEP,
            open_palm_enabled=OPEN_PALM_ENABLED,
            open_palm_min_fingers=OPEN_PALM_MIN_FINGERS,
            open_palm_hold_time_sec=OPEN_PALM_HOLD_TIME_SEC,
            hello_cooldown_sec=HELLO_COOLDOWN_SEC,
        )

    target_selector = TargetSelector(
        smoothing_alpha=TARGET_POINT_SMOOTHING_ALPHA
    )

    distance_estimator = TargetDistanceEstimator(
        mode=TARGET_DISTANCE_MODE,
        assumed_shoulder_width_m=ASSUMED_SHOULDER_WIDTH_M,
        assumed_face_width_m=ASSUMED_FACE_WIDTH_M,
        default_distance_m=DEFAULT_TARGET_DISTANCE_M,
        min_distance_m=MIN_TARGET_DISTANCE_M,
        max_distance_m=MAX_TARGET_DISTANCE_M,
        smoothing_alpha=DISTANCE_SMOOTHING_ALPHA,
        max_change_per_frame_m=MAX_DISTANCE_CHANGE_PER_FRAME_M,
        min_shoulder_width_pixels=MIN_SHOULDER_WIDTH_PIXELS,
        min_face_width_pixels=MIN_FACE_WIDTH_PIXELS,
    )

    head_mapper = HeadPoseMapper(
        camera=camera,
        enable_tilt_tracking=ENABLE_UP_DOWN_HUMAN_TRACKING,
        head_pivot_offset_m=(
            HEAD_PIVOT_OFFSET_X_M,
            HEAD_PIVOT_OFFSET_Y_M,
            HEAD_PIVOT_OFFSET_Z_M,
        ),
        camera_to_head_yaw_bias_deg=CAMERA_TO_HEAD_YAW_BIAS_DEG,
        camera_to_head_pitch_bias_deg=CAMERA_TO_HEAD_PITCH_BIAS_DEG,
        pan_center_angle=HEAD_PAN_CENTER_ANGLE,
        pan_min_angle=HEAD_PAN_MIN_ANGLE,
        pan_max_angle=HEAD_PAN_MAX_ANGLE,
        pan_soft_limit_from_center_deg=HEAD_PAN_SOFT_LIMIT_FROM_CENTER_DEG,
        pan_servo_direction=HEAD_PAN_SERVO_DIRECTION,
        control_reverse_x=CONTROL_REVERSE_X,
        tilt_center_angle=HEAD_TILT_CENTER_ANGLE,
        tilt_min_angle=HEAD_TILT_MIN_ANGLE,
        tilt_max_angle=HEAD_TILT_MAX_ANGLE,
        tilt_soft_limit_from_center_deg=HEAD_TILT_SOFT_LIMIT_FROM_CENTER_DEG,
        tilt_servo_direction=HEAD_TILT_SERVO_DIRECTION,
        control_reverse_y=CONTROL_REVERSE_Y,
        pan_angle_deadband_deg=PAN_ANGLE_DEADBAND_DEG,
        tilt_angle_deadband_deg=TILT_ANGLE_DEADBAND_DEG,
        pan_smoothing_alpha=PAN_ERROR_SMOOTHING_ALPHA,
        tilt_smoothing_alpha=TILT_ERROR_SMOOTHING_ALPHA,
        pan_max_step_per_update_deg=PAN_MAX_TARGET_STEP_PER_UPDATE_DEG,
        tilt_max_step_per_update_deg=TILT_MAX_TARGET_STEP_PER_UPDATE_DEG,
    )

    command_sender = CommandSender(
        enable_serial=ENABLE_SERIAL,
        serial_port=SERIAL_PORT,
        baudrate=BAUDRATE,
        send_interval_sec=SEND_INTERVAL_SEC,
        min_pan_change_to_send_deg=MIN_PAN_CHANGE_TO_SEND_DEG,
        min_tilt_change_to_send_deg=MIN_TILT_CHANGE_TO_SEND_DEG,
    )

    mode_manager = ControlModeManager(STARTUP_CONTROL_MODE)
    robot_head = RobotHeadInterface(
        command_sender=command_sender,
        mode_manager=mode_manager,
        supported_faces=SUPPORTED_FACES,
        supported_gestures=SUPPORTED_GESTURES,
        pan_min_angle=HEAD_PAN_MIN_ANGLE,
        pan_max_angle=HEAD_PAN_MAX_ANGLE,
        tilt_min_angle=HEAD_TILT_MIN_ANGLE,
        tilt_max_angle=HEAD_TILT_MAX_ANGLE,
        pan_center_angle=HEAD_PAN_CENTER_ANGLE,
        tilt_center_angle=HEAD_TILT_CENTER_ANGLE,
        default_gesture_count=DEFAULT_GESTURE_COUNT,
        max_gesture_count=MAX_GESTURE_COUNT,
        default_gesture_hold_ms=DEFAULT_GESTURE_HOLD_MS,
    )
    manual_controller = ManualController(
        robot_head=robot_head,
        pan_center_angle=HEAD_PAN_CENTER_ANGLE,
        tilt_center_angle=HEAD_TILT_CENTER_ANGLE,
        pan_step_deg=MANUAL_PAN_STEP_DEG,
        tilt_step_deg=MANUAL_TILT_STEP_DEG,
        gesture_count=MANUAL_GESTURE_COUNT,
        face_hold_ms=MANUAL_FACE_HOLD_MS,
        text_hold_ms=MANUAL_TEXT_HOLD_MS,
        manual_text=MANUAL_TEXT_MESSAGE,
        manual_text_italic=MANUAL_TEXT_ITALIC,
        oopsie_hold_ms=OOPSIE_DAISY_HOLD_MS,
    )

    def on_control_mode_changed(_old_mode, new_mode):
        # Keep the RP2350 local IMU/touch behavior under the same authority.
        command_sender.send_mode(new_mode)

        # Stop any in-progress target from the previous authority before the
        # newly selected controller starts issuing commands.
        robot_head.emergency_stop()
        if new_mode == ControlMode.MANUAL:
            manual_controller.sync_from_robot_status()

    mode_manager.add_listener(on_control_mode_changed)
    command_sender.send_mode(mode_manager.get_mode())

    behavior_manager = BehaviorManager(
        enable_head_tracking=ENABLE_HEAD_TRACKING,
        enable_arm_wave=ENABLE_ARM_WAVE,
        enable_lcd_face=ENABLE_LCD_FACE,
        head_pan_servo_enabled=HEAD_PAN_SERVO_ENABLED,
        head_tilt_servo_enabled=HEAD_TILT_SERVO_ENABLED,
        arm_servos_enabled=ARM_SERVOS_ENABLED,
        lcd_enabled=LCD_ENABLED,
        default_face=DEFAULT_FACE,
        no_human_face=NO_HUMAN_FACE,
        no_human_sleep_delay_sec=3.0,
    )
    mode_manager.add_listener(behavior_manager.on_control_mode_changed)

    human_result = None
    emotion_result = None
    gesture_result = None
    selected_target = None
    head_mapping_result = None
    previous_time = time.time()
    show_status_panel = bool(SHOW_STATUS_PANEL)

    print("Robot Head v16 METU Promotion Day controller started (PC DEBUG MODE).")
    print("Initial control mode:", mode_manager.get_mode())
    print_keyboard_help()

    system_started = False
    face_window_open = False
    captured_face_image = None
    captured_edges_image = None
    captured_tess_image = None
    captured_cont_image = None
    captured_mustache_image = None
    captured_warped_oval = None
    captured_mustache_status = False
    captured_sp_status = False
    captured_gt_status = False
    captured_lj_status = False
    captured_rj_status = False
    captured_gl_status = False
    captured_mustache_metrics = {}
    last_thumb_up = False
    last_thumb_down = False

    print("\n[SYSTEM] Currently in STANDBY mode.")
    print("[SYSTEM] Show a 'Victory' (Peace sign) gesture to start tracking.")
    print("[SYSTEM] Show an 'ILoveYou' (Spider-Man web) gesture to pause tracking.\n")

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Frame could not be read.")
                break

            if gesture_detector is not None:
                gesture_result = gesture_detector.update(frame)

            if gesture_result is not None:
                for hand in gesture_result.get("hands", []):
                    top = hand.get("top_gesture", "None")
                    if top == "Victory" and not system_started:
                        system_started = True
                        print("\n[SYSTEM] START UP COMMAND RECEIVED! (Victory Gesture)")
                        print("[SYSTEM] Starting Human Tracking and Emotion Detection...\n")
                    elif top == "ILoveYou" and system_started:
                        system_started = False
                        print("\n[SYSTEM] STANDBY COMMAND RECEIVED! (ILoveYou Gesture)")
                        print("[SYSTEM] Pausing Human Tracking and Emotion Detection...\n")

            if system_started:
                if human_tracker is not None:
                    human_result = human_tracker.update(frame)
                if emotion_detector is not None:
                    face_box = human_result.get("face_bbox") if human_result else None
                    emotion_result = emotion_detector.update(frame, face_bbox=face_box)

                # --- Face Capture Window Logic ---
                if gesture_result is not None:
                    current_thumb_up = False
                    current_thumb_down = False
                    for hand in gesture_result.get("hands", []):
                        top = hand.get("top_gesture", "None")
                        if top == "Thumb_Up":
                            current_thumb_up = True
                        elif top == "Thumb_Down":
                            current_thumb_down = True
                            
                    # Trigger face capture when thumb goes up
                    if current_thumb_up and not last_thumb_up:
                        points = human_result.get("points", {}) if human_result else {}
                        nose = points.get("nose")
                        left_ear = points.get("left_ear")
                        right_ear = points.get("right_ear")

                        if nose and (left_ear or right_ear):
                            cx, cy = nose
                            if left_ear and right_ear:
                                radius = int(math.hypot(left_ear[0] - right_ear[0], left_ear[1] - right_ear[1]))
                            else:
                                ear = left_ear or right_ear
                                radius = int(math.hypot(nose[0] - ear[0], nose[1] - ear[1]) * 2)
                            
                            h_f, w_f = frame.shape[:2]
                            x1 = max(0, cx - radius)
                            y1 = max(0, cy - radius)
                            x2 = min(w_f, cx + radius)
                            y2 = min(h_f, cy + radius)
                            
                            if x2 > x1 and y2 > y1:
                                crop = frame[y1:y2, x1:x2].copy()
                                
                                # Make it circular by masking
                                mask = np.zeros_like(crop)
                                cv2.circle(mask, (cx - x1, cy - y1), radius, (255, 255, 255), -1)
                                
                                captured_face_image = cv2.bitwise_and(crop, mask)
                                img_basic, img_tess, img_cont, img_mustache, img_warped_oval, has_mustache, has_sp, has_gt, has_lj, has_rj, has_gl, metrics = create_caricature_mediapipe(captured_face_image)
                                captured_edges_image = img_basic
                                captured_tess_image = img_tess
                                captured_cont_image = img_cont
                                captured_mustache_image = img_mustache
                                captured_warped_oval = img_warped_oval
                                captured_mustache_status = has_mustache
                                captured_sp_status = has_sp
                                captured_gt_status = has_gt
                                captured_lj_status = has_lj
                                captured_rj_status = has_rj
                                captured_gl_status = has_gl
                                captured_mustache_metrics = metrics
                                face_window_open = True
                                print(f"[SYSTEM] Circular face captured! Beard: {has_mustache} | Glasses: {has_gl}")
                                
                                edge_resized = cv2.resize(captured_edges_image, (240, 240))
                                gray = cv2.cvtColor(edge_resized, cv2.COLOR_BGR2GRAY)
                                _, binary = cv2.threshold(gray, 127, 1, cv2.THRESH_BINARY)
                                packed = np.packbits(binary)
                                b64 = base64.b64encode(packed).decode('utf-8')
                                command_sender.send_image(b64)
                        else:
                            # Fallback to rectangular if landmarks are missing
                            face_box = None
                            
                            if emotion_result is not None and emotion_result.get("ok", False):
                                region = emotion_result.get("region")
                                if region:
                                    face_box = (region["x"], region["y"], region["x"] + region["w"], region["y"] + region["h"])
                            
                            if face_box is None and human_result is not None:
                                face_box = human_result.get("face_bbox")
    
                            if face_box is not None:
                                x1, y1, x2, y2 = face_box
                                h_f, w_f = frame.shape[:2]
                                x1, y1 = max(0, int(x1)), max(0, int(y1))
                                x2, y2 = min(w_f, int(x2)), min(h_f, int(y2))
                                if x2 > x1 and y2 > y1:
                                    captured_face_image = frame[y1:y2, x1:x2].copy()
                                    img_basic, img_tess, img_cont, img_mustache, img_warped_oval, has_mustache, has_sp, has_gt, has_lj, has_rj, has_gl, metrics = create_caricature_mediapipe(captured_face_image)
                                    captured_edges_image = img_basic
                                    captured_tess_image = img_tess
                                    captured_cont_image = img_cont
                                    captured_mustache_image = img_mustache
                                    captured_warped_oval = img_warped_oval
                                    captured_mustache_status = has_mustache
                                    captured_sp_status = has_sp
                                    captured_gt_status = has_gt
                                    captured_lj_status = has_lj
                                    captured_rj_status = has_rj
                                    captured_gl_status = has_gl
                                    captured_mustache_metrics = metrics
                                    face_window_open = True
                                    print(f"[SYSTEM] Face captured! Beard: {has_mustache} | Glasses: {has_gl}")
                                    
                                    edge_resized = cv2.resize(captured_edges_image, (240, 240))
                                    gray = cv2.cvtColor(edge_resized, cv2.COLOR_BGR2GRAY)
                                    _, binary = cv2.threshold(gray, 127, 1, cv2.THRESH_BINARY)
                                    packed = np.packbits(binary)
                                    b64 = base64.b64encode(packed).decode('utf-8')
                                    command_sender.send_image(b64)
                    
                    # Close window when thumb goes down
                    if current_thumb_down and not last_thumb_down:
                        if face_window_open:
                            face_window_open = False
                            captured_face_image = None
                            captured_edges_image = None
                            captured_tess_image = None
                            captured_cont_image = None
                            captured_mustache_image = None
                            try:
                                if not HEADLESS_MODE:
                                    cv2.destroyWindow("Captured Face")
                                    cv2.destroyWindow("MediaPipe: Basic + Iris")
                                    cv2.destroyWindow("MediaPipe: Tesselation")
                                    cv2.destroyWindow("MediaPipe: Contours")
                                    cv2.destroyWindow("MediaPipe: Mustache Mesh")
                                    cv2.destroyWindow("Facial Features")
                            except Exception:
                                pass
                            print("[SYSTEM] Face window closed.")
                            if command_sender:
                                command_sender.send_mode(mode_manager.get_mode())
                                print("[SYSTEM] Cleared robot screen.")
                            
                    last_thumb_up = current_thumb_up
                    last_thumb_down = current_thumb_down
                # ---------------------------------
            else:
                human_result = None
                emotion_result = None

            selected_target = target_selector.select(
                human_result=human_result,
                emotion_result=emotion_result,
            )

            distance_result = distance_estimator.update(
                human_result=human_result,
                emotion_result=emotion_result,
                camera=camera,
            )
            selected_target.update(distance_result)

            head_mapping_result = (
                head_mapper.update(selected_target)
                if ENABLE_HEAD_TRACKING
                else None
            )

            active_mode = mode_manager.get_mode()
            if not system_started:
                robot_head.show_face("STANDBY", source=active_mode)
                behavior_commands = {}
            else:
                behavior_commands = behavior_manager.update(
                    target=selected_target,
                    head_mapping_result=head_mapping_result,
                    human_result=human_result,
                    emotion_result=emotion_result,
                    gesture_result=gesture_result,
                    robot_head=robot_head,
                    control_mode=active_mode,
                )

            output = frame.copy()
            if not system_started:
                cv2.putText(
                    output,
                    "STANDBY: Make 'Victory' gesture to start",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA
                )

            if human_tracker is not None:
                output = visualizer.draw_human(output, human_result)
            if emotion_detector is not None:
                output = visualizer.draw_emotion(output, emotion_result)
            if gesture_detector is not None:
                output = visualizer.draw_gesture(output, gesture_result)

            output = visualizer.draw_target(output, selected_target)
            output = visualizer.draw_control(
                output,
                head_mapping_result,
                command_sender.is_connected(),
            )

            current_time = time.time()
            fps = 1.0 / max(current_time - previous_time, 1e-6)
            previous_time = current_time
            output = visualizer.draw_fps(output, fps)

            if show_status_panel:
                mapping = head_mapping_result or {}
                target = selected_target or {}
                interface_status = robot_head.get_status()
                dominant_emotion = "--"
                if emotion_result is not None and emotion_result.get("ok", False):
                    dominant_emotion = emotion_result.get("dominant", "--")

                commanded_pan = interface_status.get("last_pan_angle")
                status = {
                    "control_mode": active_mode,
                    "auto_commands_active": behavior_commands.get(
                        "auto_commands_active",
                        False,
                    ),
                    "last_command": interface_status.get("last_command") or "--",
                    "last_source": interface_status.get("last_source") or "--",
                    "features": {
                        "head_tracking": ENABLE_HEAD_TRACKING,
                        "tilt_tracking": mapping.get(
                            "tilt_tracking_enabled",
                            head_mapper.enable_tilt_tracking,
                        ),
                        "emotion": ENABLE_EMOTION,
                        "gesture": ENABLE_GESTURE,
                        "lcd_face": ENABLE_LCD_FACE and LCD_ENABLED,
                        "arm_wave": ENABLE_ARM_WAVE and ARM_SERVOS_ENABLED,
                    },
                    "human_detected": bool(
                        human_result
                        and human_result.get("human_detected", False)
                    ),
                    "target_valid": bool(target.get("valid", False)),
                    "hand_detected": bool(
                        gesture_result
                        and gesture_result.get("hand_detected", False)
                    ),
                    "serial_connected": command_sender.is_connected(),
                    "emotion": dominant_emotion,
                    "face": interface_status.get("last_face") or "--",
                    "auto_face": behavior_commands.get("face") or "--",
                    "decision": mapping.get("decision", "--"),
                    "gesture": (
                        interface_status.get("last_gesture")
                        or describe_gesture(gesture_result)
                    ),
                    "pan_angle": commanded_pan,
                    "pan_servo_angle": estimate_pan_servo_angle(commanded_pan),
                    "tilt_angle": interface_status.get("last_tilt_angle"),
                    "auto_pan_angle": mapping.get("pan_angle"),
                    "auto_tilt_angle": mapping.get("tilt_angle"),
                    "pan_error_deg": mapping.get("pan_error_deg"),
                    "tilt_error_deg": mapping.get("tilt_error_deg"),
                    "target_type": target.get("target_type", "--"),
                    "distance_m": target.get("distance_m"),
                    "distance_source": target.get("distance_source", "--"),
                    "fps": fps,
                }
                output = visualizer.compose_status_panel(
                    output,
                    status,
                    panel_width=STATUS_PANEL_WIDTH,
                )

            if not HEADLESS_MODE:
                cv2.imshow(WINDOW_NAME, output)
                if face_window_open and captured_face_image is not None:
                    # cv2.imshow("Captured Face", captured_face_image) # Omit to save screen space
                    if captured_edges_image is not None:
                        cv2.imshow("MediaPipe: Basic + Iris", captured_edges_image)
                    if captured_tess_image is not None:
                        cv2.imshow("MediaPipe: Tesselation", captured_tess_image)
                    if captured_cont_image is not None:
                        cv2.imshow("MediaPipe: Contours", captured_cont_image)
                    if captured_mustache_image is not None:
                        cv2.imshow("MediaPipe: Mustache Mesh", captured_mustache_image)
                        
                    if captured_warped_oval is not None:
                        cv2.imshow("Warped Face Border", captured_warped_oval)
                        
                    # Create Text Window for Facial Features
                    feature_img = np.zeros((650, 800, 3), dtype=np.uint8)
                    
                    # Logic gates for Facial Hair Style
                    has_lj = captured_lj_status
                    has_rj = captured_rj_status
                    has_gt = captured_gt_status
                    has_m = captured_mustache_status
                    has_gl = captured_gl_status
                    
                    style = "Clean Shaven"
                    if has_lj and has_rj and has_gt:
                        style = "Full Beard"
                    elif has_lj and has_rj and not has_gt:
                        style = "Mutton Chops"
                    elif has_gt and not has_lj and not has_rj:
                        style = "Goatee"
                    elif has_m and not has_gt and not has_lj and not has_rj:
                        style = "Mustache Only"
                    elif has_lj or has_rj or has_gt:
                        style = "Patchy / Abstract Beard"
                        
                    cv2.putText(feature_img, f"STYLE DETECTED: {style}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                    
                    # Glasses Alert
                    glasses_str = "GLASSES DETECTED!" if has_gl else "NO GLASSES"
                    gl_color = (0, 255, 255) if has_gl else (100, 100, 100)
                    cv2.putText(feature_img, glasses_str, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, gl_color, 2)
                    
                    cv2.line(feature_img, (0, 120), (800, 120), (255, 255, 255), 2)
                    
                    # Color Analytics Column
                    cv2.putText(feature_img, "Region", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(feature_img, "Average Color (BGR)", (220, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(feature_img, "Middle Pixel (BGR)", (520, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                    regions = [
                        ("Mustache", 'm'),
                        ("Soul Patch", 'sp'),
                        ("Goatee", 'gt'),
                        ("Left Jaw", 'lj'),
                        ("Right Jaw", 'rj'),
                        ("Glasses", 'gl'),
                        ("Forehead", 'fh')
                    ]
                    
                    y_off = 190
                    for name, prefix in regions:
                        avg_c = metrics.get(f'{prefix}_avg', (0,0,0))
                        mid_c = metrics.get(f'{prefix}_mid', (0,0,0))
                        
                        cv2.putText(feature_img, name, (20, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                        # We print the color values, and tint the text with that exact color for immediate visual feedback!
                        cv2.putText(feature_img, str(avg_c), (220, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.7, avg_c, 2)
                        cv2.putText(feature_img, str(mid_c), (520, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mid_c, 2)
                        y_off += 35
                        
                    # Move Texture and Darkness Columns further down
                    y_t = 460
                    # Distance Metric Column
                    cv2.putText(feature_img, f"Euclidean Color Distance (Threshold > 65):", (20, y_t), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(feature_img, f"  Mustache: {metrics.get('m_dist', 0):.1f}", (20, y_t+30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_mustache_status else (0, 0, 255), 2)
                    cv2.putText(feature_img, f"  Soul Patch: {metrics.get('sp_dist', 0):.1f}", (20, y_t+55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_sp_status else (0, 0, 255), 2)
                    cv2.putText(feature_img, f"  Goatee: {metrics.get('gt_dist', 0):.1f}", (20, y_t+80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_gt_status else (0, 0, 255), 2)
                    cv2.putText(feature_img, f"  Left Jaw: {metrics.get('lj_dist', 0):.1f}", (20, y_t+105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_lj_status else (0, 0, 255), 2)
                    cv2.putText(feature_img, f"  Right Jaw: {metrics.get('rj_dist', 0):.1f}", (20, y_t+130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_rj_status else (0, 0, 255), 2)
                    cv2.putText(feature_img, f"  Glasses: {metrics.get('gl_dist', 0):.1f}", (20, y_t+155), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if captured_gl_status else (0, 0, 255), 2)
                    
                    cv2.imshow("Facial Features", feature_img)
                    
                key = cv2.waitKey(1) & 0xFF
            else:
                key = 255

            if key == ord("q"):
                break

            if key == ord("1"):
                mode_manager.set_mode(ControlMode.AUTO)
            elif key == ord("2"):
                mode_manager.set_mode(ControlMode.MANUAL)
            elif key == ord("e"):
                # Latch autonomous command sources off before stopping.
                mode_manager.set_mode(ControlMode.MANUAL)
                robot_head.emergency_stop()
            elif key == ord("c"):
                if mode_manager.is_mode(ControlMode.MANUAL):
                    head_mapper.reset_center()
                    manual_controller.center()
                else:
                    print(
                        "[Command blocked] CENTER is a MANUAL command; "
                        "press 2 first."
                    )
            elif key == ord("s"):
                robot_head.stop(source=ControlMode.MANUAL)
            elif key == ord("a"):
                robot_head.wave_arm(source=ControlMode.MANUAL)
            elif key == ord("f"):
                robot_head.show_face("CURIOUS", source=ControlMode.MANUAL)
            elif key == ord("4"):
                manual_controller.show_sigma()
            elif key == ord("5"):
                manual_controller.show_sunglasses()
            elif key == ord("9"):
                manual_controller.show_thinking()
            elif key == ord("["):
                manual_controller.show_oopsie_daisy()
            elif key == ord("]"):
                manual_controller.show_manual_text()
            elif key == ord("6"):
                manual_controller.dance()
            elif key == ord("7"):
                manual_controller.greet()
            elif key == ord("8"):
                manual_controller.daisy_dance()
            elif key == ord("n"):
                manual_controller.nod()
            elif key == ord("o"):
                manual_controller.sunglasses_nod()
            elif key == ord("g"):
                manual_controller.sigma_nod()
            elif key == ord("x"):
                manual_controller.shake()
            elif key == ord("b"):
                manual_controller.look_around()
            elif key == ord("m"):
                manual_controller.celebrate()
            elif key == ord("z"):
                manual_controller.sleep()
            elif key == ord("w"):
                manual_controller.wake_up()
            elif key == ord("0"):
                manual_controller.cancel_gesture()
            elif key == ord("j"):
                manual_controller.pan_left()
            elif key == ord("l"):
                manual_controller.pan_right()
            elif key == ord("i"):
                manual_controller.tilt_up()
            elif key == ord("k"):
                manual_controller.tilt_down()
            elif key == ord("h"):
                camera.toggle_horizontal_flip()
            elif key == ord("v"):
                camera.toggle_vertical_flip()
            elif key == ord("d"):
                head_mapper.toggle_pan_servo_direction()
            elif key == ord("t"):
                head_mapper.toggle_tilt_servo_direction()
            elif key == ord("r"):
                head_mapper.toggle_control_reverse_x()
            elif key == ord("y"):
                head_mapper.toggle_control_reverse_y()
            elif key == ord("u"):
                head_mapper.toggle_tilt_tracking()
            elif key == ord("p"):
                show_status_panel = not show_status_panel
                print("Live status panel:", "ON" if show_status_panel else "OFF")

    finally:
        robot_head.emergency_stop()
        if human_tracker is not None:
            human_tracker.close()
        if gesture_detector is not None:
            gesture_detector.close()
        command_sender.close()
        camera.release()
        if not HEADLESS_MODE:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
