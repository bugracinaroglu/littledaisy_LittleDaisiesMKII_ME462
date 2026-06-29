import cv2


class Camera:
    def __init__(
        self,
        camera_index=0,
        width=1280,
        height=720,
        flip_horizontal=True,
        flip_vertical=False
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.flip_horizontal = flip_horizontal
        self.flip_vertical = flip_vertical

        self.cap = cv2.VideoCapture(self.camera_index)

        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def is_opened(self):
        return self.cap.isOpened()

    def read(self):
        ret, frame = self.cap.read()

        if not ret:
            return False, None

        if self.flip_horizontal:
            frame = cv2.flip(frame, 1)

        if self.flip_vertical:
            frame = cv2.flip(frame, 0)

        return True, frame

    def release(self):
        self.cap.release()