import time

import cv2

from behavior.behavior_manager import BehaviorManager
from camera import Camera
from config import *
from control.command_sender import CommandSender
from control.head_pose_mapper import HeadPoseMapper
from vision.distance_estimator import TargetDistanceEstimator
from vision.gesture_detector import GestureDetector
from vision.human_tracker import HumanTracker
from vision.target_selector import TargetSelector
from visualizer import Visualizer


def create_emotion_detector():
    if not ENABLE_EMOTION:
        return None

    try:
        from vision.emotion_detector import EmotionDetector

        return EmotionDetector(
            analyze_every_n_frames=EMOTION_ANALYZE_EVERY_N_FRAMES,
            detector_backend=EMOTION_DETECTOR_BACKEND,
            enforce_detection=EMOTION_ENFORCE_DETECTION,
        )
    except Exception as exc:
        print("[Emotion init error]")
        print(exc)
        print("Emotion detector disabled.")
        return None


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
            open_palm_hold_frames=OPEN_PALM_HOLD_FRAMES,
            hello_cooldown_frames=HELLO_COOLDOWN_FRAMES,
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

    human_result = None
    emotion_result = None
    gesture_result = None
    selected_target = None
    head_mapping_result = None
    previous_time = time.time()

    print("Robot Head v6 fixed-camera controller started.")
    print("Keys:")
    print("q: quit | c: center | s: stop | a: arm wave | f: curious face")
    print("h/v: image flip | d: pan servo direction | k: tilt servo direction")
    print("r: reverse X | y: reverse Y | u: enable/disable up-down tracking")

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Frame could not be read.")
                break

            if human_tracker is not None:
                human_result = human_tracker.update(frame)
            if emotion_detector is not None:
                emotion_result = emotion_detector.update(frame)
            if gesture_detector is not None:
                gesture_result = gesture_detector.update(frame)

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

            behavior_manager.update(
                target=selected_target,
                head_mapping_result=head_mapping_result,
                human_result=human_result,
                emotion_result=emotion_result,
                gesture_result=gesture_result,
                command_sender=command_sender,
            )

            output = frame.copy()
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

            cv2.imshow(WINDOW_NAME, output)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == ord("c"):
                head_mapper.reset_center()
                command_sender.send_center()
            elif key == ord("s"):
                command_sender.send_stop()
            elif key == ord("a"):
                command_sender.send_arm_wave()
            elif key == ord("f"):
                command_sender.send_face("CURIOUS")
            elif key == ord("h"):
                camera.toggle_horizontal_flip()
            elif key == ord("v"):
                camera.toggle_vertical_flip()
            elif key == ord("d"):
                head_mapper.toggle_pan_servo_direction()
            elif key == ord("k"):
                head_mapper.toggle_tilt_servo_direction()
            elif key == ord("r"):
                head_mapper.toggle_control_reverse_x()
            elif key == ord("y"):
                head_mapper.toggle_control_reverse_y()
            elif key == ord("u"):
                head_mapper.toggle_tilt_tracking()

    finally:
        command_sender.send_stop()
        if human_tracker is not None:
            human_tracker.close()
        if gesture_detector is not None:
            gesture_detector.close()
        command_sender.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
