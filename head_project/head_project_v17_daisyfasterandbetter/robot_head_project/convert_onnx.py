import os
import subprocess
from deepface.models.demography.Emotion import load_model

print("Building DeepFace Emotion model...")
model = load_model()

print("Saving to SavedModel format...")
saved_model_path = "models/fer2013_saved_model"
model.export(saved_model_path)

print("Converting SavedModel to ONNX...")
output_path = "models/fer2013.onnx"
subprocess.run([
    "/home/deniz/python_envs/papis/bin/python", "-m", "tf2onnx.convert",
    "--saved-model", saved_model_path,
    "--output", output_path,
    "--opset", "13"
])

print(f"Successfully exported ONNX model to {output_path}")
