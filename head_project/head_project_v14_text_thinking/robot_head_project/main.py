import time

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
    if gesture_result.get("hand_detected", False):
        return "HAND"
    return "NONE"


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


def create_ros2_bridge(robot_head, mode_manager):
    if not ENABLE_ROS2_BRIDGE:
        return None

    try:
        from control.ros2_bridge import Ros2CommandBridge

        bridge = Ros2CommandBridge(
            robot_head=robot_head,
            mode_manager=mode_manager,
            node_name=ROS2_NODE_NAME,
        )
        return bridge if bridge.available else None
    except Exception as exc:
        print("ROS2 bridge initialization error:", exc)
        return None


def print_keyboard_help():
    print("Keys (click the OpenCV camera window first):")
    print("1: AUTO mode | 2: MANUAL mode | 3: ROS mode")
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
    ros2_bridge = create_ros2_bridge(robot_head, mode_manager)

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

    print("Robot Head v14 text/thinking controller started.")
    print("Initial control mode:", mode_manager.get_mode())
    if mode_manager.is_mode(ControlMode.ROS) and ros2_bridge is None:
        print("Warning: ROS mode is active but the ROS2 bridge is disabled.")
    print_keyboard_help()

    try:
        while True:
            if ros2_bridge is not None:
                ros2_bridge.spin_once()

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

            active_mode = mode_manager.get_mode()
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

            cv2.imshow(WINDOW_NAME, output)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("1"):
                mode_manager.set_mode(ControlMode.AUTO)
            elif key == ord("2"):
                mode_manager.set_mode(ControlMode.MANUAL)
            elif key == ord("3"):
                mode_manager.set_mode(ControlMode.ROS)
                if ros2_bridge is None:
                    print("ROS mode selected, but ENABLE_ROS2_BRIDGE is False or ROS2 is unavailable.")
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
        if ros2_bridge is not None:
            ros2_bridge.close()
        if human_tracker is not None:
            human_tracker.close()
        if gesture_detector is not None:
            gesture_detector.close()
        command_sender.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
