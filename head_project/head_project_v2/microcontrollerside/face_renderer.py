from time import ticks_ms, ticks_diff
import math


class FaceRenderer:
    def __init__(self, lcd):
        self.lcd = lcd

        self.W = 240
        self.H = 240
        self.CX = 120
        self.CY = 120

        # Driver colors
        self.BLACK = lcd.black
        self.WHITE = lcd.white
        self.RED = lcd.red
        self.GREEN = lcd.green
        self.BLUE = lcd.blue
        self.BROWN = lcd.brown

        # Main face color.
        # White is reliable on this LCD driver.
        self.FACE_COLOR = self.WHITE

        self.EFFECT_BLUE = self.BLUE
        self.EFFECT_RED = self.RED
        self.EFFECT_GREEN = self.GREEN

        # Extra colors may look different depending on driver color order.
        self.YELLOW = 0xFFE0
        self.ORANGE = 0xFD20

        self.face = "IDLE"
        self.next_face = "IDLE"

        self.last_draw_ms = 0
        self.draw_interval_ms = 70

        # Blink transition between emotions
        self.transition_active = False
        self.transition_start_ms = 0
        self.transition_duration_ms = 320

        # Auto blink
        self.blink_active = False
        self.blink_start_ms = 0
        self.blink_duration_ms = 150
        self.next_auto_blink_ms = ticks_ms() + 2200

        # Curious gaze
        self.gaze_offset = 0
        self.gaze_dir = 1
        self.last_gaze_ms = ticks_ms()

        self.anim_counter = 0
        self.force_redraw = True

        # During LCD testing this is useful.
        # Later for final robot face, set this to False.
        self.show_label = True

    # =====================================================
    # Public API
    # =====================================================

    def set_face(self, face_name, transition=True):
        face_name = face_name.upper()

        valid_faces = [
            "NEUTRAL",
            "CURIOUS",
            "HAPPY",
            "SAD",
            "ANGRY",
            "SURPRISED",
            "DISGUST",
            "SLEEPING",
            "IDLE",
        ]

        if face_name not in valid_faces:
            face_name = "IDLE"

        if face_name == self.face and not self.transition_active:
            return

        if transition:
            self.next_face = face_name
            self.transition_active = True
            self.transition_start_ms = ticks_ms()
        else:
            self.face = face_name
            self.next_face = face_name
            self.transition_active = False

        self.force_redraw = True

    def trigger_wave_reaction(self):
        self.set_face("HAPPY", transition=True)
        self._start_blink()

    def update(self):
        now = ticks_ms()

        if ticks_diff(now, self.last_draw_ms) < self.draw_interval_ms and not self.force_redraw:
            return

        self.last_draw_ms = now
        self.anim_counter += 1

        self._update_auto_animation(now)

        face_to_draw, blink_amount = self._get_transition_face_and_blink(now)

        self._draw_face(face_to_draw, blink_amount)
        self.lcd.show()

        self.force_redraw = False

    # =====================================================
    # Timing helpers
    # =====================================================

    def _update_auto_animation(self, now):
        # These faces blink naturally.
        if self.face in ("NEUTRAL", "CURIOUS", "HAPPY", "SAD", "IDLE"):
            if ticks_diff(now, self.next_auto_blink_ms) >= 0:
                self._start_blink()
                self.next_auto_blink_ms = now + 2200 + (self.anim_counter % 5) * 250

        if self.face == "CURIOUS":
            if ticks_diff(now, self.last_gaze_ms) > 850:
                self.last_gaze_ms = now
                self.gaze_dir *= -1
                self.gaze_offset = 5 * self.gaze_dir

    def _start_blink(self):
        self.blink_active = True
        self.blink_start_ms = ticks_ms()
        self.force_redraw = True

    def _get_normal_blink_amount(self, now):
        if not self.blink_active:
            return 0.0

        elapsed = ticks_diff(now, self.blink_start_ms)

        if elapsed >= self.blink_duration_ms:
            self.blink_active = False
            return 0.0

        half = self.blink_duration_ms / 2

        if elapsed <= half:
            return elapsed / half

        return 1.0 - ((elapsed - half) / half)

    def _get_transition_face_and_blink(self, now):
        normal_blink = self._get_normal_blink_amount(now)

        if not self.transition_active:
            return self.face, normal_blink

        elapsed = ticks_diff(now, self.transition_start_ms)

        if elapsed >= self.transition_duration_ms:
            self.face = self.next_face
            self.transition_active = False
            return self.face, 0.0

        half = self.transition_duration_ms / 2

        if elapsed <= half:
            blink = elapsed / half
            return self.face, blink

        blink = 1.0 - ((elapsed - half) / half)
        return self.next_face, blink

    # =====================================================
    # Drawing helpers
    # =====================================================

    def _clear(self):
        self.lcd.fill(self.BLACK)

    def _safe_hline(self, x, y, length, color):
        if y < 0 or y >= self.H:
            return

        x1 = max(0, int(x))
        x2 = min(self.W - 1, int(x + length))

        if x2 >= x1:
            self.lcd.hline(x1, int(y), x2 - x1 + 1, color)

    def _thick_line(self, x1, y1, x2, y2, color, t=2):
        for dx in range(-t, t + 1):
            self.lcd.line(x1 + dx, y1, x2 + dx, y2, color)

        for dy in range(-t, t + 1):
            self.lcd.line(x1, y1 + dy, x2, y2 + dy, color)

    def _fill_circle(self, cx, cy, r, color):
        cx = int(cx)
        cy = int(cy)
        r = int(r)

        for y in range(-r, r + 1):
            x = int(math.sqrt(max(r * r - y * y, 0)))
            self._safe_hline(cx - x, cy + y, 2 * x + 1, color)

    def _fill_round_rect(self, x, y, w, h, r, color):
        self.lcd.fill_rect(x + r, y, w - 2 * r, h, color)
        self.lcd.fill_rect(x, y + r, w, h - 2 * r, color)

        self._fill_circle(x + r, y + r, r, color)
        self._fill_circle(x + w - r - 1, y + r, r, color)
        self._fill_circle(x + r, y + h - r - 1, r, color)
        self._fill_circle(x + w - r - 1, y + h - r - 1, r, color)

    def _fill_triangle(self, p1, p2, p3, color):
        pts = sorted([p1, p2, p3], key=lambda p: p[1])

        x1, y1 = pts[0]
        x2, y2 = pts[1]
        x3, y3 = pts[2]

        def interp(y, xa, ya, xb, yb):
            if yb == ya:
                return xa
            return int(xa + (xb - xa) * (y - ya) / (yb - ya))

        for y in range(y1, y3 + 1):
            if y < y2:
                xa = interp(y, x1, y1, x2, y2)
                xb = interp(y, x1, y1, x3, y3)
            else:
                xa = interp(y, x2, y2, x3, y3)
                xb = interp(y, x1, y1, x3, y3)

            if xa > xb:
                xa, xb = xb, xa

            self._safe_hline(xa, y, xb - xa + 1, color)

    def _ellipse_outline(self, cx, cy, rx, ry, color, thickness=2):
        steps = 80

        for t in range(thickness):
            last = None
            rrx = max(1, rx - t)
            rry = max(1, ry - t)

            for i in range(steps + 1):
                a = 2 * math.pi * i / steps

                x = int(cx + rrx * math.cos(a))
                y = int(cy + rry * math.sin(a))

                if last is not None:
                    self.lcd.line(last[0], last[1], x, y, color)

                last = (x, y)

    def _draw_curve(self, cx, cy, width, amp, direction, color, thickness=2):
        """
        direction = +1 -> smile curve
        direction = -1 -> frown / upper curve
        """
        prev_x = None
        prev_y = None

        w2 = width * width

        for x in range(-width, width + 1, 2):
            y = cy + direction * ((amp * (w2 - x * x)) // w2)

            if prev_x is not None:
                self._thick_line(prev_x, prev_y, cx + x, y, color, thickness)

            prev_x = cx + x
            prev_y = y

    def _draw_label(self, text):
        if not self.show_label:
            return

        self.lcd.fill_rect(0, 214, 240, 26, self.BLACK)

        x = int((240 - len(text) * 8) / 2)
        self.lcd.text(text, x, 224, self.FACE_COLOR)

    def _draw_blink_eye(self, left_x, right_x, y, color, thickness=3):
        self._thick_line(left_x, y, right_x, y, color, thickness)

    def _draw_round_eye(self, cx, cy, r, color, blink=0.0, pupil=True, pupil_dx=0, pupil_dy=0):
        if blink > 0.72:
            self._draw_blink_eye(cx - r, cx + r, cy, color, 3)
            return

        effective_r = max(3, int(r * (1.0 - 0.60 * blink)))

        self._fill_circle(cx, cy, effective_r, color)

        if pupil and blink < 0.55 and effective_r > 8:
            pr = max(5, int(effective_r * 0.42))
            self._fill_circle(cx + pupil_dx, cy + pupil_dy, pr, self.BLACK)

    def _draw_capsule_eye(self, x, y, w, h, color, blink=0.0):
        if blink > 0.72:
            self._draw_blink_eye(x, x + w, y + h // 2, color, 3)
            return

        effective_h = max(4, int(h * (1.0 - blink)))

        yy = y + (h - effective_h) // 2

        self._fill_round_rect(x, yy, w, effective_h, min(8, effective_h // 2), color)

    def _draw_flame_pupil(self, cx, cy):
        # Black pupil base
        self._fill_circle(cx, cy, 9, self.BLACK)

        # Small flame inside eye.
        self._fill_triangle(
            (cx - 5, cy + 7),
            (cx + 5, cy + 7),
            (cx, cy - 9),
            self.EFFECT_RED
        )
        self._fill_triangle(
            (cx - 3, cy + 5),
            (cx + 3, cy + 5),
            (cx + 1, cy - 5),
            self.ORANGE
        )

    def _draw_blush(self, cx, cy):
        # Red cheek mark. If red appears strange, replace EFFECT_RED with FACE_COLOR.
        self._fill_circle(cx, cy, 5, self.EFFECT_RED)
        self._fill_circle(cx + 8, cy + 2, 3, self.EFFECT_RED)

    # =====================================================
    # Face router
    # =====================================================

    def _draw_face(self, face, blink):
        self._clear()

        if face == "NEUTRAL":
            self._draw_neutral(blink)

        elif face == "CURIOUS":
            self._draw_curious(blink)

        elif face == "HAPPY":
            self._draw_happy(blink)

        elif face == "SAD":
            self._draw_sad(blink)

        elif face == "ANGRY":
            self._draw_angry(blink)

        elif face == "SURPRISED":
            self._draw_surprised(blink)

        elif face == "DISGUST":
            self._draw_disgust(blink)

        elif face == "SLEEPING":
            self._draw_sleeping(blink)

        else:
            self._draw_idle(blink)

    # =====================================================
    # Individual faces
    # =====================================================

    def _draw_neutral(self, blink):
        c = self.FACE_COLOR

        # Round eyes with pupils
        self._draw_round_eye(82, 94, 20, c, blink, pupil=True)
        self._draw_round_eye(158, 94, 20, c, blink, pupil=True)

        # Slight lip curve, not fully smiling
        self._draw_curve(120, 154, 32, 7, +1, c, 2)
        self.lcd.fill_rect(108, 162, 24, 3, c)

        self._draw_label("NEUTRAL")

    def _draw_idle(self, blink):
        c = self.FACE_COLOR

        self._draw_capsule_eye(60, 92, 42, 15, c, blink)
        self._draw_capsule_eye(138, 92, 42, 15, c, blink)

        self.lcd.fill_rect(102, 160, 36, 4, c)

        self._draw_label("IDLE")

    def _draw_curious(self, blink):
        c = self.FACE_COLOR
        gx = self.gaze_offset

        self._draw_round_eye(82, 94, 22, c, blink, pupil=True, pupil_dx=gx)
        self._draw_round_eye(158, 94, 22, c, blink, pupil=True, pupil_dx=gx)

        # Raised eyebrow and flat eyebrow
        self._thick_line(55, 69, 102, 58, c, 2)
        self._thick_line(138, 66, 185, 66, c, 2)

        # Wider curious mouth
        self._thick_line(90, 160, 108, 168, c, 2)
        self._thick_line(108, 168, 132, 168, c, 2)
        self._thick_line(132, 168, 152, 158, c, 2)

        self._draw_label("CURIOUS")
           
#     def _draw_happy(self, blink):
#         c = self.FACE_COLOR
# 
#         eye_color = c
#         mouth_color = c
#         cheek_color = self.EFFECT_RED
# 
#         # Small breathing animation
#         bounce = (self.anim_counter // 6) % 2
# 
#         # =====================================================
#         # C-shaped happy eyes
#         # =====================================================
#         eye_y = 92 + bounce
# 
#         if blink > 0.72:
#             # During blink, eyes become simple short lines
#             self._draw_blink_eye(58, 106, eye_y, eye_color, 3)
#             self._draw_blink_eye(134, 182, eye_y, eye_color, 3)
#         else:
#             # Left happy eye: like a soft upside-down U / C smile
#             self._draw_curve(82, eye_y, 27, 13, -1, eye_color, 4)
#             self._draw_curve(82, eye_y + 2, 24, 10, -1, eye_color, 2)
# 
#             # Right happy eye
#             self._draw_curve(158, eye_y, 27, 13, -1, eye_color, 4)
#             self._draw_curve(158, eye_y + 2, 24, 10, -1, eye_color, 2)
# 
#             # Tiny end pixels make the C eyes look softer on low resolution
#             self._fill_circle(57, eye_y - 1, 3, eye_color)
#             self._fill_circle(107, eye_y - 1, 3, eye_color)
#             self._fill_circle(133, eye_y - 1, 3, eye_color)
#             self._fill_circle(183, eye_y - 1, 3, eye_color)
# 
#         # =====================================================
#         # Cute cheeks
#         # =====================================================
#         self._fill_circle(55, 132, 5, cheek_color)
#         self._fill_circle(64, 135, 3, cheek_color)
# 
#         self._fill_circle(185, 132, 5, cheek_color)
#         self._fill_circle(176, 135, 3, cheek_color)
# 
#         # =====================================================
#         # Simple but clear happy mouth
#         # =====================================================
#         mouth_y = 145 + bounce
# 
#         # Small U-shaped smile
#         self._draw_curve(120, mouth_y, 35, 20, +1, mouth_color, 4)
#         self._draw_curve(120, mouth_y + 3, 29, 15, +1, mouth_color, 2)
# 
#         # Very small dimples
#         self._fill_circle(85, mouth_y + 1, 3, mouth_color)
#         self._fill_circle(155, mouth_y + 1, 3, mouth_color)
# 
#         # Optional tiny lower lip, makes it look softer
#         self._draw_curve(120, mouth_y + 27, 16, 4, -1, mouth_color, 1)
# 
#         self._draw_label("HAPPY")
#     
    def _draw_happy(self, blink):
        c = self.FACE_COLOR

        eye_color = c
        mouth_color = c

        # Small vertical bounce gives a more alive expression
        bounce = (self.anim_counter // 5) % 2

        # =====================================================
        # Eyes
        # =====================================================
        if blink > 0.72:
            # Cute closed happy eyes during blink
            self._draw_curve(82, 96, 25, 8, +1, eye_color, 3)
            self._draw_curve(158, 96, 25, 8, +1, eye_color, 3)
        else:
            # Big friendly eyes
            self._draw_round_eye(82, 92 + bounce, 24, eye_color, blink, pupil=True)
            self._draw_round_eye(158, 92 + bounce, 24, eye_color, blink, pupil=True)

            # Stronger pupils
            self._fill_circle(82, 92 + bounce, 10, self.BLACK)
            self._fill_circle(158, 92 + bounce, 10, self.BLACK)

            # Eye highlights
            self._fill_circle(74, 82 + bounce, 3, eye_color)
            self._fill_circle(150, 82 + bounce, 3, eye_color)

            # Tiny lower sparkle, makes eyes look happier
            self._fill_circle(90, 100 + bounce, 2, eye_color)
            self._fill_circle(166, 100 + bounce, 2, eye_color)

        # =====================================================
        # Cheeks
        # =====================================================
        # Use red cheeks to make happiness obvious
        self._fill_circle(54, 132, 5, self.EFFECT_RED)
        self._fill_circle(62, 135, 3, self.EFFECT_RED)

        self._fill_circle(186, 132, 5, self.EFFECT_RED)
        self._fill_circle(178, 135, 3, self.EFFECT_RED)

        # =====================================================
        # Mouth
        # =====================================================
        mouth_y = 148 + bounce

        # Clean big smile, not over-filled
        self._draw_curve(120, mouth_y, 54, 30, +1, mouth_color, 4)

        # Second smaller curve makes the smile look thicker and more natural
        self._draw_curve(120, mouth_y + 4, 48, 24, +1, mouth_color, 2)

        # Small curved lip ends / dimples
        self._thick_line(66, mouth_y + 1, 75, mouth_y + 10, mouth_color, 2)
        self._thick_line(174, mouth_y + 10, 183, mouth_y + 1, mouth_color, 2)

        # Tiny lower lip shine, very subtle
        self._draw_curve(120, mouth_y + 34, 24, 5, -1, mouth_color, 1)

        self._draw_label("HAPPY")


#     def _draw_happy(self, blink):
#         c = self.FACE_COLOR
# 
#         eye_color = c
#         mouth_color = c
#         cheek_color = self.EFFECT_RED
# 
#         # Very small breathing motion
#         bounce = (self.anim_counter // 6) % 2
# 
#         # =====================================================
#         # Happy open eyes with visible pupils
#         # =====================================================
#         eye_y = 80 + bounce
# 
#         if blink > 0.72:
#             # Friendly closed blink, not a flat dead line
#             self._draw_curve(82, 98, 25, 8, +1, eye_color, 3)
#             self._draw_curve(158, 98, 25, 8, +1, eye_color, 3)
#         else:
#             # Soft oval/capsule eyes.
#             # These are less neutral than round eyes but still show pupils clearly.
#             self._fill_round_rect(55, eye_y, 54, 36, 17, eye_color)
#             self._fill_round_rect(131, eye_y, 54, 36, 17, eye_color)
# 
#             # Pupils: slightly lower and slightly toward center.
#             # This gives a warm happy look instead of a blank stare.
#             self._fill_circle(86, eye_y + 20, 10, self.BLACK)
#             self._fill_circle(154, eye_y + 20, 10, self.BLACK)
# 
#             # Small highlights inside pupils
#             self._fill_circle(82, eye_y + 15, 3, eye_color)
#             self._fill_circle(150, eye_y + 15, 3, eye_color)
# 
#             # Small black cut at the upper outside corners.
#             # This makes the eyes look a bit smiling/squinted, not just oval.
#             self._fill_circle(58, eye_y + 4, 10, self.BLACK)
#             self._fill_circle(106, eye_y + 4, 10, self.BLACK)
#             self._fill_circle(134, eye_y + 4, 10, self.BLACK)
#             self._fill_circle(182, eye_y + 4, 10, self.BLACK)
# 
#             # Re-soften lower part of eyes after the cuts
#             self._draw_curve(82, eye_y + 28, 21, 5, +1, eye_color, 2)
#             self._draw_curve(158, eye_y + 28, 21, 5, +1, eye_color, 2)
# 
#         # =====================================================
#         # Cheeks
#         # =====================================================
#         # Cheeks are important here because eyes still have pupils.
#         # They help the face read as happy, not surprised/neutral.
#         self._fill_circle(54, 132, 5, cheek_color)
#         self._fill_circle(63, 135, 3, cheek_color)
# 
#         self._fill_circle(186, 132, 5, cheek_color)
#         self._fill_circle(177, 135, 3, cheek_color)
# 
#         # =====================================================
#         # Mouth
#         # =====================================================
#         mouth_y = 145 + bounce
# 
#         # Clean large smile
#         self._draw_curve(120, mouth_y, 50, 29, +1, mouth_color, 4)
# 
#         # Inner smaller curve makes the smile thicker but not blocky
#         self._draw_curve(120, mouth_y + 4, 42, 21, +1, mouth_color, 2)
# 
#         # Dimples at both ends
#         self._fill_circle(70, mouth_y + 2, 3, mouth_color)
#         self._fill_circle(170, mouth_y + 2, 3, mouth_color)
# 
#         # Tiny lower lip shine
#         self._draw_curve(120, mouth_y + 34, 20, 4, -1, mouth_color, 1)
# 
#         self._draw_label("HAPPY")
        
    def _draw_sad(self, blink):
        c = self.FACE_COLOR

        self._draw_round_eye(82, 96, 13, c, blink, pupil=True, pupil_dy=4)
        self._draw_round_eye(158, 96, 13, c, blink, pupil=True, pupil_dy=4)

        # Crying/sad eyebrows:
        # inner parts are raised, outer parts lower.
        self._thick_line(58, 82, 98, 72, c, 2)
        self._thick_line(142, 72, 182, 82, c, 2)

        # frown
        self._draw_curve(120, 164, 48, 25, -1, c, 3)

        # tears from both eyes
        tear_shift = self.anim_counter % 18
        left_tear_y = 116 + tear_shift
        right_tear_y = 116 + ((tear_shift + 8) % 18)

        self._fill_circle(68, left_tear_y, 5, self.EFFECT_BLUE)
        self._fill_circle(172, right_tear_y, 5, self.EFFECT_BLUE)

        # small tear trails
        self._thick_line(68, 110, 68, min(left_tear_y, 135), self.EFFECT_BLUE, 1)
        self._thick_line(172, 110, 172, min(right_tear_y, 135), self.EFFECT_BLUE, 1)

        self._draw_label("SAD")

    def _draw_angry(self, blink):
        c = self.FACE_COLOR
        red = self.EFFECT_RED

        # Red round angry eyes
        self._draw_round_eye(82, 98, 22, red, blink, pupil=False)
        self._draw_round_eye(158, 98, 22, red, blink, pupil=False)

        if blink < 0.55:
            # Fire pupils inside red eyes
            self._draw_flame_pupil(82, 98)
            self._draw_flame_pupil(158, 98)

        # Eyebrows moved clearly above the eyes
        self._thick_line(50, 62, 106, 80, c, 3)
        self._thick_line(190, 62, 134, 80, c, 3)

        # Strong angry mouth
        self._thick_line(86, 164, 108, 154, c, 3)
        self._thick_line(108, 154, 132, 164, c, 3)
        self._thick_line(132, 164, 156, 154, c, 3)

        # small fire/flicker at bottom
        flicker = self.anim_counter % 3
        base_y = 202

        for i, x in enumerate([86, 110, 134, 158]):
            h = 10 + ((i + flicker) % 3) * 4
            self._thick_line(x, base_y, x + 4, base_y - h, self.EFFECT_RED, 1)

        self._draw_label("ANGRY")

    def _draw_surprised(self, blink):
        c = self.FACE_COLOR

        self._draw_round_eye(82, 92, 24, c, blink, pupil=True)
        self._draw_round_eye(158, 92, 24, c, blink, pupil=True)

        # raised eyebrows
        self._thick_line(55, 60, 100, 52, c, 2)
        self._thick_line(140, 52, 185, 60, c, 2)

        # O mouth
        self._fill_circle(120, 160, 28, c)
        self._fill_circle(120, 160, 17, self.BLACK)

        # small ??? bubble
        self._ellipse_outline(120, 35, 37, 17, c, thickness=1)
        self.lcd.text("???", 108, 31, c)

        self._draw_label("SURPRISE")

    def _draw_disgust(self, blink):
        c = self.FACE_COLOR
        green = self.EFFECT_GREEN

        # puky / nauseated eyes
        self._draw_round_eye(82, 95, 15, c, blink, pupil=True, pupil_dx=-3)
        self._draw_capsule_eye(138, 88, 48, 18, c, blink)

        # asymmetric green eyebrows
        self._thick_line(58, 74, 100, 78, green, 2)
        self._thick_line(140, 80, 184, 68, green, 2)

        # wavy puky mouth
        self._thick_line(88, 160, 102, 155, c, 2)
        self._thick_line(102, 155, 118, 164, c, 2)
        self._thick_line(118, 164, 136, 156, c, 2)
        self._thick_line(136, 156, 154, 162, c, 2)

        # green nausea bubbles
        self._fill_circle(188, 142, 4 + (self.anim_counter % 2), green)
        self._ellipse_outline(202, 163, 6, 5, green, thickness=1)
        self._fill_circle(194, 180, 3, green)

        # more visible puke stream, but still small
        if (self.anim_counter % 12) < 7:
            self._thick_line(124, 172, 130, 190, green, 2)
            self._thick_line(132, 174, 138, 188, green, 1)
            self._fill_circle(130, 194, 4, green)
            self._fill_circle(138, 198, 3, green)

        self._draw_label("DISGUST")

    def _draw_sleeping(self, blink):
        c = self.FACE_COLOR

        # Improved sleeping cap:
        # brim + soft hanging triangle + pompom.
        cap_color = self.EFFECT_BLUE

        # cap main body
        self._fill_triangle((70, 64), (150, 66), (113, 28), cap_color)

        # curved-looking brim made from thick lines
        self._thick_line(68, 64, 152, 66, cap_color, 4)
        self._thick_line(72, 70, 148, 72, c, 1)

        # folded cap tail
        self._thick_line(113, 28, 146, 44, cap_color, 4)
        self._fill_circle(151, 45, 7, c)

        # closed sleepy eyes
        self._thick_line(58, 104, 102, 104, c, 3)
        self._thick_line(138, 104, 182, 104, c, 3)

        # small sleeping mouth
        self.lcd.fill_rect(105, 162, 30, 4, c)

        # Zzz animation, unchanged in concept
        shift = self.anim_counter % 18
        self.lcd.text("z", 170, 58 - shift // 3, c)
        self.lcd.text("Z", 186, 43 - shift // 4, c)

        if hasattr(self.lcd, "write_text"):
            self.lcd.write_text("Z", 200, 22 - shift // 6, 2, c)
        else:
            self.lcd.text("Z", 200, 22 - shift // 6, c)

        self._draw_label("SLEEP")



