import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh
pairs = mp_face_mesh.FACEMESH_LEFT_IRIS
print("Pairs:", pairs)

# simulate face_landmarks
class Landmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class FaceLandmarks:
    def __init__(self):
        self.landmark = [Landmark(0.5, 0.5) for _ in range(478)]

face_landmarks = FaceLandmarks()

left_iris_pts = [face_landmarks.landmark[idx] for pair in mp_face_mesh.FACEMESH_LEFT_IRIS for idx in pair]
print("Len left_iris_pts:", len(left_iris_pts))
