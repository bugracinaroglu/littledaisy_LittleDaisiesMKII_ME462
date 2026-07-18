import numpy as np

FACEMESH_LEFT_IRIS = frozenset({(474, 475), (475, 476), (476, 477), (477, 474)})

class Landmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class FaceLandmarks:
    def __init__(self):
        self.landmark = [Landmark(0.5, 0.5) for _ in range(478)]

face_landmarks = FaceLandmarks()
w = 240
h = 240

left_iris_pts = [face_landmarks.landmark[idx] for pair in FACEMESH_LEFT_IRIS for idx in pair]
if left_iris_pts:
    cx = int(np.mean([pt.x * w for pt in left_iris_pts]))
    cy = int(np.mean([pt.y * h for pt in left_iris_pts]))
    print(f"Iris center: {cx}, {cy}")
else:
    print("Empty iris pts")
