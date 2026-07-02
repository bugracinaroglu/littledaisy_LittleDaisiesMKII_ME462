from time import ticks_ms, ticks_diff

try:
    from machine import idle
except ImportError:
    def idle():
        pass

import rp2350_touch_lcd_128 as board

from config import *
from face_renderer import FaceRenderer
from serial_parser import SerialParser
from head_controller import HeadController
from head_gesture_controller import HeadGestureController
from arm_controller import ArmController
from imu_motion_detector import IMUMotionDetector


def init_lcd_and_face():
    if not LCD_ENABLED:
        return None, None

    lcd = board.LCD_1inch28()
    lcd.set_bl_pwm(65535)

    face = FaceRenderer(lcd)
    face.set_face(DEFAULT_FACE, transition=False)
    return lcd, face


def init_touch(lcd):
    if not TOUCH_ENABLED or lcd is None:
        return None

    try:
        touch = board.Touch_CST816T(mode=1, LCD=lcd)
        touch.Mode = 1
        touch.Set_Mode(1)
        print("Touch initialized.")
        return touch
    except Exception as exc:
        print("Touch init error:", exc)
        return None


def touch_pressed(touch):
    if touch is None:
        return False

    try:
        if touch.Flag == 1:
            touch.Flag = 0
            return True
    except Exception:
        pass
    return False


def init_head_controller():
    return HeadController(
        pan_pin=HEAD_PAN_SERVO_PIN,
        tilt_pin=HEAD_TILT_SERVO_PIN,
        pan_enabled=HEAD_PAN_SERVO_ENABLED,
        tilt_enabled=HEAD_TILT_SERVO_ENABLED,
        freq=SERVO_FREQ,
        min_us=SERVO_MIN_US,
        max_us=SERVO_MAX_US,
        max_angle=SERVO_MAX_ANGLE,
        pan_head_neutral_angle=HEAD_PAN_HEAD_NEUTRAL_ANGLE,
        pan_command_min_angle=HEAD_PAN_COMMAND_MIN_ANGLE,
        pan_command_max_angle=HEAD_PAN_COMMAND_MAX_ANGLE,
        pan_servo_neutral_angle=HEAD_PAN_SERVO_NEUTRAL_ANGLE,
        pan_min_limit_angle=HEAD_PAN_MIN_LIMIT_ANGLE,
        pan_max_limit_angle=HEAD_PAN_MAX_LIMIT_ANGLE,
        pan_gear_ratio=HEAD_PAN_GEAR_RATIO,
        pan_gear_reverses_direction=HEAD_PAN_GEAR_REVERSES_DIRECTION,
        pan_step_deg=HEAD_PAN_STEP_DEG,
        pan_move_interval_ms=HEAD_PAN_MOTION_UPDATE_INTERVAL_MS,
        pan_max_speed_deg_s=HEAD_PAN_MAX_SPEED_DEG_S,
        pan_acceleration_deg_s2=HEAD_PAN_ACCEL_DEG_S2,
        pan_target_tolerance_deg=HEAD_PAN_TARGET_TOLERANCE_DEG,
        pan_min_command_change_deg=HEAD_PAN_MIN_COMMAND_CHANGE_DEG,
        tilt_neutral_angle=HEAD_TILT_NEUTRAL_ANGLE,
        tilt_min_limit_angle=HEAD_TILT_MIN_LIMIT_ANGLE,
        tilt_max_limit_angle=HEAD_TILT_MAX_LIMIT_ANGLE,
        tilt_step_deg=HEAD_TILT_STEP_DEG,
        tilt_move_interval_ms=HEAD_TILT_MOTION_UPDATE_INTERVAL_MS,
        tilt_max_speed_deg_s=HEAD_TILT_MAX_SPEED_DEG_S,
        tilt_acceleration_deg_s2=HEAD_TILT_ACCEL_DEG_S2,
        tilt_down_max_speed_deg_s=HEAD_TILT_DOWN_MAX_SPEED_DEG_S,
        tilt_down_acceleration_deg_s2=HEAD_TILT_DOWN_ACCEL_DEG_S2,
        tilt_target_tolerance_deg=HEAD_TILT_TARGET_TOLERANCE_DEG,
        tilt_min_command_change_deg=HEAD_TILT_MIN_COMMAND_CHANGE_DEG,
    )


def init_arm_controller():
    return ArmController(
        left_pin=LEFT_ARM_SERVO_PIN,
        right_pin=RIGHT_ARM_SERVO_PIN,
        enabled=ARM_SERVOS_ENABLED,
        freq=SERVO_FREQ,
        min_us=SERVO_MIN_US,
        max_us=SERVO_MAX_US,
        max_angle=SERVO_MAX_ANGLE,
        left_neutral_angle=LEFT_ARM_NEUTRAL_ANGLE,
        right_neutral_angle=RIGHT_ARM_NEUTRAL_ANGLE,
        left_up_angle=LEFT_ARM_UP_ANGLE,
        right_up_angle=RIGHT_ARM_UP_ANGLE,
        left_min_limit_angle=LEFT_ARM_MIN_LIMIT_ANGLE,
        left_max_limit_angle=LEFT_ARM_MAX_LIMIT_ANGLE,
        right_min_limit_angle=RIGHT_ARM_MIN_LIMIT_ANGLE,
        right_max_limit_angle=RIGHT_ARM_MAX_LIMIT_ANGLE,
        step_deg=ARM_STEP_DEG,
        move_interval_ms=ARM_MOVE_INTERVAL_MS,
        wave_amplitude_deg=ARM_WAVE_AMPLITUDE_DEG,
        wave_interval_ms=ARM_WAVE_INTERVAL_MS,
        wave_cycles=ARM_WAVE_CYCLES,
        use_right_arm_for_wave=USE_RIGHT_ARM_FOR_WAVE,
        running_amplitude_deg=RUNNING_ARM_AMPLITUDE_DEG,
        running_interval_ms=RUNNING_ARM_INTERVAL_MS,
        running_use_right_arm=RUNNING_USE_RIGHT_ARM,
        dance_amplitude_deg=ARM_DANCE_AMPLITUDE_DEG,
        dance_interval_ms=ARM_DANCE_INTERVAL_MS,
        dance_beats_per_cycle=ARM_DANCE_BEATS_PER_CYCLE,
    )


def init_head_gesture_controller(head, arms):
    return HeadGestureController(
        head=head,
        arms=arms,
        default_repeat_count=GESTURE_DEFAULT_REPEAT_COUNT,
        max_repeat_count=GESTURE_MAX_REPEAT_COUNT,
        target_tolerance_deg=GESTURE_TARGET_TOLERANCE_DEG,
        center_before_start=GESTURE_CENTER_BEFORE_START,
        center_dwell_ms=GESTURE_CENTER_DWELL_MS,
        nod_up_offset_deg=GESTURE_NOD_UP_OFFSET_DEG,
        nod_down_offset_deg=GESTURE_NOD_DOWN_OFFSET_DEG,
        nod_dwell_ms=GESTURE_NOD_DWELL_MS,
        shake_left_offset_deg=GESTURE_SHAKE_LEFT_OFFSET_DEG,
        shake_right_offset_deg=GESTURE_SHAKE_RIGHT_OFFSET_DEG,
        shake_dwell_ms=GESTURE_SHAKE_DWELL_MS,
        look_around_use_full_range=GESTURE_LOOK_AROUND_USE_FULL_RANGE,
        look_left_offset_deg=GESTURE_LOOK_LEFT_OFFSET_DEG,
        look_right_offset_deg=GESTURE_LOOK_RIGHT_OFFSET_DEG,
        look_dwell_ms=GESTURE_LOOK_DWELL_MS,
        wake_up_tilt_offset_deg=GESTURE_WAKE_UP_TILT_OFFSET_DEG,
        wake_up_dwell_ms=GESTURE_WAKE_UP_DWELL_MS,
        dance_pan_offset_deg=GESTURE_DANCE_PAN_OFFSET_DEG,
        dance_tilt_up_offset_deg=GESTURE_DANCE_TILT_UP_OFFSET_DEG,
        dance_tilt_down_offset_deg=GESTURE_DANCE_TILT_DOWN_OFFSET_DEG,
        dance_dwell_ms=GESTURE_DANCE_DWELL_MS,
        greet_pan_offset_deg=GESTURE_GREET_PAN_OFFSET_DEG,
        greet_nod_up_offset_deg=GESTURE_GREET_NOD_UP_OFFSET_DEG,
        greet_nod_down_offset_deg=GESTURE_GREET_NOD_DOWN_OFFSET_DEG,
        greet_turn_dwell_ms=GESTURE_GREET_TURN_DWELL_MS,
        greet_nod_dwell_ms=GESTURE_GREET_NOD_DWELL_MS,
    )


def init_imu_motion_detector():
    if not IMU_ENABLED:
        return None

    return IMUMotionDetector(
        enabled=IMU_ENABLED,
        sample_interval_ms=IMU_SAMPLE_INTERVAL_MS,
        startup_ignore_ms=IMU_STARTUP_IGNORE_MS,
        delta_mag_threshold=RUNNING_DELTA_MAG_THRESHOLD,
        delta_mag_strong_threshold=RUNNING_DELTA_MAG_STRONG_THRESHOLD,
        start_count_required=RUNNING_START_COUNT,
        stop_count_required=RUNNING_STOP_COUNT,
        direction_scale=RUNNING_FACE_DIRECTION_SCALE,
        reverse_x=RUNNING_FACE_REVERSE_X,
        reverse_y=RUNNING_FACE_REVERSE_Y,
        swap_xy=RUNNING_FACE_SWAP_XY,
        dizzy_gyro_threshold_dps=DIZZY_GYRO_THRESHOLD_DPS,
        dizzy_face_duration_ms=DIZZY_FACE_DURATION_MS,
    )


def _clamp_hold_ms(hold_ms):
    try:
        hold_ms = int(hold_ms)
    except Exception:
        hold_ms = 0
    return max(0, min(hold_ms, FACE_HOLD_MAX_MS))


def set_face_lock(face_state, hold_ms):
    hold_ms = _clamp_hold_ms(hold_ms)
    face_state["lock_started_ms"] = ticks_ms()
    face_state["lock_duration_ms"] = hold_ms


def clear_face_lock(face_state):
    face_state["lock_started_ms"] = ticks_ms()
    face_state["lock_duration_ms"] = 0


def is_face_locked(face_state):
    duration = face_state.get("lock_duration_ms", 0)
    if duration <= 0:
        return False

    elapsed = ticks_diff(ticks_ms(), face_state.get("lock_started_ms", 0))
    if elapsed >= duration:
        clear_face_lock(face_state)
        return False
    return True


def set_base_face(face, face_state, face_name, hold_ms=0):
    face_name = str(face_name).strip().upper()

    # An explicit face command replaces any temporary text overlay.
    if face is not None and hasattr(face, "clear_text"):
        face.clear_text()

    # Intentional project behavior: neutral detection should look curious.
    if face_name == "NEUTRAL":
        face_name = "CURIOUS"

    if face_name not in FACE_LIST:
        print("Unsupported face:", face_name)
        return False

    face_state["base_face"] = face_name
    face_state["special_face"] = None
    set_face_lock(face_state, hold_ms)

    if face is not None:
        face.set_face(face_name, transition=True)
    return True


def apply_special_face(face, face_state, special_face):
    if face is None:
        return
    if special_face == face_state["special_face"]:
        return

    face_state["special_face"] = special_face
    if special_face is not None:
        face.set_face(special_face, transition=True)
    else:
        face.set_face(face_state["base_face"], transition=True)


def gesture_face_name(gesture_name):
    return {
        "SUNGLASSES_NOD": "SUNGLASSES",
        "SIGMA_NOD": "SIGMA",
        "LOOK_AROUND": "CURIOUS",
        "CELEBRATE": "HAPPY",
        "DANCE": "SUNGLASSES",
        "GREET": "SUNGLASSES",
        "DAISY_DANCE": "SUNGLASSES",
        "SLEEP": "SLEEPING",
        "WAKE_UP": "CURIOUS",
    }.get(gesture_name)


def handle_command(
    command_type,
    value,
    head,
    arms,
    face,
    gestures,
    face_state,
    control_state,
):
    if command_type is None:
        return

    if command_type == "MODE":
        requested_mode = str(value).strip().upper()
        if requested_mode not in ("AUTO", "MANUAL", "ROS"):
            print("Unsupported control mode:", requested_mode)
            return

        previous_mode = control_state["mode"]
        control_state["mode"] = requested_mode
        if requested_mode != previous_mode:
            print("Control mode: {} -> {}".format(previous_mode, requested_mode))
            if gestures is not None:
                gestures.cancel(hold_position=True)
            clear_face_lock(face_state)

        if requested_mode != "AUTO":
            if arms is not None:
                arms.set_running_active(False)
            apply_special_face(face, face_state, None)

    elif command_type == "HEAD_POSE":
        # Keep an RP2350 gesture deterministic. Tracking/manual pose commands
        # are ignored until it completes or GESTURE:CANCEL / STOP is received.
        if gestures is not None and gestures.is_active():
            return
        if head is not None:
            pan_angle, tilt_angle = value
            head.set_pose(pan_angle, tilt_angle)

    elif command_type == "HEAD_PAN":
        if gestures is not None and gestures.is_active():
            return
        if head is not None:
            head.set_pan(value)

    elif command_type == "HEAD_TILT":
        if gestures is not None and gestures.is_active():
            return
        if head is not None:
            head.set_tilt(value)

    elif command_type == "FACE":
        face_name, hold_ms = value
        set_base_face(face, face_state, face_name, hold_ms)

    elif command_type == "TEXT":
        text, hold_ms, italic = value
        if face is not None and hasattr(face, "show_text"):
            apply_special_face(face, face_state, None)
            set_face_lock(face_state, hold_ms)
            face.show_text(text, hold_ms=hold_ms, italic=italic)

    elif command_type == "GESTURE":
        gesture_name, count, hold_ms = value
        gesture_name = str(gesture_name).strip().upper()

        selected_face = gesture_face_name(gesture_name)
        if selected_face is not None:
            if not set_base_face(face, face_state, selected_face, hold_ms):
                return
        elif hold_ms > 0:
            set_face_lock(face_state, hold_ms)

        if gestures is not None:
            gestures.start(gesture_name, count)

    elif command_type == "GESTURE_CANCEL":
        if gestures is not None:
            gestures.cancel(hold_position=True)

    elif command_type == "ARM_WAVE":
        if arms is not None:
            arms.start_wave()
        if face is not None and face_state["special_face"] is None:
            face.trigger_wave_reaction()

    elif command_type == "CENTER":
        if gestures is not None:
            gestures.cancel(hold_position=False)
        if head is not None:
            head.center()
        if arms is not None:
            arms.center()
        set_base_face(face, face_state, "CURIOUS", 0)

    elif command_type == "STOP":
        if gestures is not None:
            gestures.cancel(hold_position=False)
        if head is not None:
            head.stop()
        if arms is not None:
            arms.stop()

    elif command_type == "UNKNOWN":
        print("Unknown command:", value)
    elif command_type == "ERROR":
        print("Command parse error:", value)


def run():
    lcd = None
    face = None
    touch = None
    head = None
    arms = None
    gestures = None
    imu_motion = None

    parser = SerialParser()
    face_index = 0
    last_touch_ms = ticks_ms()
    touch_cooldown_ms = 350

    face_state = {
        "base_face": DEFAULT_FACE,
        "special_face": None,
        "lock_started_ms": ticks_ms(),
        "lock_duration_ms": 0,
    }
    control_state = {"mode": STARTUP_CONTROL_MODE}

    try:
        lcd, face = init_lcd_and_face()
        touch = init_touch(lcd)
        head = init_head_controller()
        arms = init_arm_controller()
        gestures = init_head_gesture_controller(head, arms)
        imu_motion = init_imu_motion_detector()

        print("READY")
        print("Control mode:", control_state["mode"])
        print("Pan gear: servo = {:.1f} {} {:.1f} * (head - {:.1f})".format(
            HEAD_PAN_SERVO_NEUTRAL_ANGLE,
            "-" if HEAD_PAN_GEAR_REVERSES_DIRECTION else "+",
            HEAD_PAN_GEAR_RATIO,
            HEAD_PAN_HEAD_NEUTRAL_ANGLE,
        ))
        print("Pan servo limits: {:.1f}..{:.1f}".format(
            HEAD_PAN_MIN_LIMIT_ANGLE,
            HEAD_PAN_MAX_LIMIT_ANGLE,
        ))
        print("Tilt servo limits: {:.1f}..{:.1f}".format(
            HEAD_TILT_MIN_LIMIT_ANGLE,
            HEAD_TILT_MAX_LIMIT_ANGLE,
        ))
        print("Commands:")
        print("MODE:AUTO | MODE:MANUAL | MODE:ROS")
        print("HEAD_POSE:90,90 | HEAD_PAN:90 | HEAD_TILT:90")
        print("FACE:SIGMA,4000 | FACE:SUNGLASSES,4000 | FACE:THINKING,4000")
        print("TEXT:5000,1,Oopsie Daisy | TEXT:4000,0,Hello Daisy")
        print("GESTURE:NOD,3,0")
        print("GESTURE:SUNGLASSES_NOD,3,4000")
        print("GESTURE:SIGMA_NOD,3,4000")
        print("GESTURE:SHAKE,3,0 | GESTURE:LOOK_AROUND,1,0")
        print("GESTURE:CELEBRATE,3,3000")
        print("GESTURE:DANCE,3,7000 | GESTURE:GREET,3,7000")
        print("GESTURE:DAISY_DANCE,3,8000 | GESTURE:CANCEL")
        print("ARM:WAVE | CENTER | STOP")

        while True:
            raw_cmd = parser.read_command()
            if raw_cmd is not None:
                command_type, value = parser.parse(raw_cmd)
                handle_command(
                    command_type,
                    value,
                    head,
                    arms,
                    face,
                    gestures,
                    face_state,
                    control_state,
                )

            gesture_active = gestures is not None and gestures.is_active()

            if (
                control_state["mode"] == "MANUAL"
                and TOUCH_FACE_TEST_ENABLED
                and not gesture_active
                and touch_pressed(touch)
            ):
                now = ticks_ms()
                if ticks_diff(now, last_touch_ms) > touch_cooldown_ms:
                    last_touch_ms = now
                    face_index = (face_index + 1) % len(FACE_LIST)
                    selected_face = FACE_LIST[face_index]
                    print("Touch face:", selected_face)
                    set_base_face(face, face_state, selected_face, 0)

            imu_result = imu_motion.update() if imu_motion is not None else None
            text_active = (
                face is not None
                and hasattr(face, "is_text_active")
                and face.is_text_active()
            )
            face_locked = is_face_locked(face_state) or text_active
            gesture_active = gestures is not None and gestures.is_active()

            if (
                control_state["mode"] == "AUTO"
                and imu_result is not None
                and imu_result.get("ok", False)
            ):
                running_active = imu_result.get("running_active", False)
                running_elapsed_ms = imu_result.get("running_elapsed_ms", 0)
                dizzy_active = imu_result.get("dizzy_active", False)

                if face is not None and hasattr(face, "set_motion_vector"):
                    face.set_motion_vector(
                        imu_result.get("screen_x", 0.0),
                        imu_result.get("screen_y", 0.0),
                    )

                if gesture_active or face_locked:
                    if arms is not None:
                        arms.set_running_active(False)
                    apply_special_face(face, face_state, None)
                else:
                    running_arm_active = (
                        RUNNING_ARM_ENABLE
                        and running_active
                        and running_elapsed_ms >= RUNNING_ARM_MIN_ACTIVE_MS
                    )
                    if arms is not None:
                        arms.set_running_active(running_arm_active)

                    if DIZZY_FACE_ENABLE and dizzy_active:
                        special_face = "DIZZY"
                    elif (
                        RUNNING_FACE_ENABLE
                        and running_active
                        and running_elapsed_ms >= RUNNING_FACE_MIN_ACTIVE_MS
                    ):
                        special_face = "RUNNING"
                    else:
                        special_face = None
                    apply_special_face(face, face_state, special_face)
            else:
                if arms is not None:
                    arms.set_running_active(False)
                apply_special_face(face, face_state, None)

            if gestures is not None:
                gestures.update()
            if head is not None:
                head.update()
            if arms is not None:
                arms.update()
            if face is not None:
                face.update()

            idle()

    finally:
        if head is not None:
            head.deinit()
        if arms is not None:
            arms.deinit()


if __name__ == "__main__":
    run()
