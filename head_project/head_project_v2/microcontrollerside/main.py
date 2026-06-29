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
from arm_controller import ArmController


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

    except Exception as e:
        print("Touch init error:", e)
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
        pin=HEAD_SERVO_PIN,
        enabled=HEAD_SERVO_ENABLED,

        freq=SERVO_FREQ,
        min_us=SERVO_MIN_US,
        max_us=SERVO_MAX_US,
        max_angle=SERVO_MAX_ANGLE,

        neutral_angle=HEAD_NEUTRAL_ANGLE,
        min_limit_angle=HEAD_MIN_LIMIT_ANGLE,
        max_limit_angle=HEAD_MAX_LIMIT_ANGLE,

        step_deg=HEAD_STEP_DEG,
        move_interval_ms=HEAD_MOVE_INTERVAL_MS
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

        use_right_arm_for_wave=USE_RIGHT_ARM_FOR_WAVE
    )


def handle_command(command_type, value, head, arms, face):
    if command_type is None:
        return

    if command_type == "HEAD":
        if head is not None:
            head.set_angle(value)

    elif command_type == "FACE":
        if face is not None:
            if value == "NEUTRAL":
                value = "CURIOUS"

            face.set_face(value, transition=True)
            
    elif command_type == "ARM_WAVE":
        if arms is not None:
            arms.start_wave()

        if face is not None:
            face.trigger_wave_reaction()

    elif command_type == "CENTER":
        if head is not None:
            head.center()

        if arms is not None:
            arms.center()

        if face is not None:
            face.set_face("CURIOUS", transition=True)

    elif command_type == "STOP":
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

    parser = SerialParser()

    face_index = 0
    last_touch_ms = ticks_ms()
    touch_cooldown_ms = 350

    try:
        lcd, face = init_lcd_and_face()
        touch = init_touch(lcd)

        head = init_head_controller()
        arms = init_arm_controller()

        print("READY")
        print("Commands:")
        print("HEAD:90")
        print("FACE:HAPPY")
        print("ARM:WAVE")
        print("CENTER")
        print("STOP")

        while True:
            # -----------------------------
            # Serial command handling
            # -----------------------------
            raw_cmd = parser.read_command()

            if raw_cmd is not None:
                command_type, value = parser.parse(raw_cmd)
                handle_command(command_type, value, head, arms, face)

            # -----------------------------
            # Touch face test
            # -----------------------------
            if TOUCH_FACE_TEST_ENABLED and touch_pressed(touch):
                now = ticks_ms()

                if ticks_diff(now, last_touch_ms) > touch_cooldown_ms:
                    last_touch_ms = now

                    face_index = (face_index + 1) % len(FACE_LIST)
                    selected_face = FACE_LIST[face_index]

                    print("Touch face:", selected_face)

                    if face is not None:
                        face.set_face(selected_face, transition=True)

            # -----------------------------
            # Non-blocking updates
            # -----------------------------
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