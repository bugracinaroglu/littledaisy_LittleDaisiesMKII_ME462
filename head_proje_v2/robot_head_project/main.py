import cv2
import time

from config import *

from camera import Camera
from visualizer import Visualizer

from vision.human_tracker import HumanTracker
from vision.gesture_detector import GestureDetector
from vision.target_selector import TargetSelector

from control.head_angle_mapper import HeadAngleMapper
from control.command_sender import CommandSender

from behavior.behavior_manager import BehaviorManager


def create_emotion_detector():
    if not ENABLE_EMOTION:
        return None

    try:
        from vision.emotion_detector import EmotionDetector

        return EmotionDetector(
            analyze_every_n_frames=EMOTION_ANALYZE_EVERY_N_FRAMES,
            detector_backend=EMOTION_DETECTOR_BACKEND,
            enforce_detection=EMOTION_ENFORCE_DETECTION
        )

    except Exception as e:
        print("[Emotion init error]")
        print(e)
        print("Emotion detector disabled.")
        return None


def main():
    camera = Camera(
        camera_index=CAMERA_INDEX,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
        flip_horizontal=FLIP_FRAME_HORIZONTAL,
        flip_vertical=FLIP_FRAME_VERTICAL
    )

    if not camera.is_opened():
        print("Camera could not be opened. Try CAMERA_INDEX = 1 or 2.")
        return

    visualizer = Visualizer()

    human_tracker = None
    emotion_detector = None
    gesture_detector = None

    if ENABLE_HUMAN_TRACKING:
        human_tracker = HumanTracker(
            detection_confidence=POSE_DETECTION_CONFIDENCE,
            tracking_confidence=POSE_TRACKING_CONFIDENCE,
            strict_torso_validation=STRICT_TORSO_VALIDATION,
            enable_face_fallback=ENABLE_FACE_FALLBACK,
            min_body_height_ratio=MIN_BODY_HEIGHT_RATIO,
            min_body_width_ratio=MIN_BODY_WIDTH_RATIO,
            min_upper_body_height_ratio=MIN_UPPER_BODY_HEIGHT_RATIO,
            min_upper_body_width_ratio=MIN_UPPER_BODY_WIDTH_RATIO,
            min_visible_pose_points=MIN_VISIBLE_POSE_POINTS
        )

    emotion_detector = create_emotion_detector()

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
            hello_cooldown_frames=HELLO_COOLDOWN_FRAMES
        )

    target_selector = TargetSelector()

    head_mapper = HeadAngleMapper(
        camera_mount_mode=CAMERA_MOUNT_MODE,
        frame_width=FRAME_WIDTH,
        horizontal_fov_deg=CAMERA_HORIZONTAL_FOV_DEG,
        center_angle=HEAD_SERVO_CENTER_ANGLE,
        min_angle=HEAD_SERVO_MIN_ANGLE,
        max_angle=HEAD_SERVO_MAX_ANGLE,
        soft_limit_from_center_deg=HEAD_SERVO_SOFT_LIMIT_FROM_CENTER_DEG,
        servo_direction=HEAD_SERVO_DIRECTION,
        control_reverse_x=CONTROL_REVERSE_X,
        deadband_norm=DEADBAND_NORM,
        error_smoothing_alpha=ERROR_SMOOTHING_ALPHA,
        max_target_step_per_update=MAX_TARGET_STEP_PER_SEND
    )

    command_sender = CommandSender(
        enable_serial=ENABLE_SERIAL,
        serial_port=SERIAL_PORT,
        baudrate=BAUDRATE,
        send_interval_sec=SEND_INTERVAL_SEC,
        min_angle_change_to_send=MIN_ANGLE_CHANGE_TO_SEND
    )

    behavior_manager = BehaviorManager(
        enable_head_tracking=ENABLE_HEAD_TRACKING,
        enable_arm_wave=ENABLE_ARM_WAVE,
        enable_lcd_face=ENABLE_LCD_FACE,
        head_servo_enabled=HEAD_SERVO_ENABLED,
        arm_servos_enabled=ARM_SERVOS_ENABLED,
        lcd_enabled=LCD_ENABLED,
        default_face=DEFAULT_FACE,
        no_human_face=NO_HUMAN_FACE,
        no_human_sleep_delay_sec=3.0
    )
    human_result = None
    emotion_result = None
    gesture_result = None
    selected_target = None
    head_mapping_result = None

    previous_time = time.time()

    print("Robot Head PC Controller started.")
    print("Keys:")
    print("q : quit")
    print("c : center head")
    print("s : stop")
    print("a : manual arm wave command")
    print("f : send curious face")
    print("h : toggle horizontal camera flip")
    print("v : toggle vertical camera flip")
    print("d : reverse servo direction")
    print("r : reverse controller x input")

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
            emotion_result=emotion_result
        )

        if ENABLE_HEAD_TRACKING:
            head_mapping_result = head_mapper.update(selected_target)
        else:
            head_mapping_result = None

        behavior_manager.update(
            target=selected_target,
            head_mapping_result=head_mapping_result,
            human_result=human_result,
            emotion_result=emotion_result,
            gesture_result=gesture_result,
            command_sender=command_sender
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
            command_sender.is_connected()
        )

        current_time = time.time()
        fps = 1.0 / max(current_time - previous_time, 1e-6)
        previous_time = current_time

        output = visualizer.draw_fps(output, fps)

        cv2.imshow(WINDOW_NAME, output)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("c"):
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
            head_mapper.toggle_servo_direction()

        elif key == ord("r"):
            head_mapper.toggle_control_reverse_x()

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