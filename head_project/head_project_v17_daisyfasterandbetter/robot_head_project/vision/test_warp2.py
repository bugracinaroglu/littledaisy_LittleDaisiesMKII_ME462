import cv2
import numpy as np
from face_warper import warp_face_to_circle

img = np.zeros((240, 240, 3), dtype=np.uint8)
cv2.rectangle(img, (50, 50), (190, 190), (255, 255, 255), -1)

class DummyLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class DummyLandmarks:
    def __init__(self):
        self.landmark = []
        for i in range(478):
            # circle points
            self.landmark.append(DummyLandmark(0.5 + 0.2*np.cos(i), 0.5 + 0.2*np.sin(i)))
        # Make sure nose is at center
        self.landmark[1] = DummyLandmark(0.5, 0.5)

warped = warp_face_to_circle(img, DummyLandmarks())
print("Warped shape:", warped.shape)
print("Max value in warped:", np.max(warped))
