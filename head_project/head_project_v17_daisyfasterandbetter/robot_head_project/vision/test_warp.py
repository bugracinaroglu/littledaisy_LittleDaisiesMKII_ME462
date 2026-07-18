import cv2
import numpy as np
import mediapipe as mp
from face_warper import warp_face_to_circle

img = np.zeros((240, 240, 3), dtype=np.uint8)
mp_face_mesh = mp.solutions.face_mesh
with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
    # Just pass a dummy image that won't find a face
    # Wait, we need a real face to get landmarks to test it.
    pass
