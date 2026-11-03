#!/usr/bin/env python
"""
Given a directory full of clean images each containing one human
figure, analyze the body position and cluster the images by similar
poses. Requires quite a bit of tweaking to find the most useful
value for similarity and number of clusters. Images are copied from
'./in' to sub-directories of './out'.

Written by GenAI, cleaned up by a human.
"""

import os
import cv2
import numpy as np
import urllib.request
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
import shutil
import argparse

IMAGE_FOLDER = "in" 
OUTPUT_FOLDER = "out"
valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')

parser = argparse.ArgumentParser(
    prog='clusterposes',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        Given a directory full of clean images each containing one
        human figure, analyze the body position and cluster the images
        by similar poses. Requires quite a bit of tweaking to find the
        most useful value for similarity and number of clusters.
    """
)
parser.add_argument('-t', '--threshold',
    type=float,
    default=0.05,
    help='confidence level for declaring images similar enough (lower is stricter, default=0.05)')
parser.add_argument('-c', '--clusters',
    type=float,
    default=405,
    help='exact number of clusters to divide images among')
args=parser.parse_args()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "pose_landmarker_heavy.task")
MODEL_URL = "https://googleapis.com"

# Auto-download model file if it doesn't exist locally
if not os.path.exists(MODEL_PATH):
    print("Model file missing. Automatically downloading Heavy Model from Google's servers...")
    print("This may take a moment (approx. 25MB)...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Download complete successfully!\n")
    except Exception as e:
        raise RuntimeError(
            f"Failed to auto-download the model. Error: {e}\n"
            f"Please manually download the file from:\n{MODEL_URL}\n"
            f"And save it exactly to: {MODEL_PATH}"
        )

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE,
    min_pose_detection_confidence=args.threshold,
    min_pose_presence_confidence=args.threshold,
    output_segmentation_masks=False
)
pose_extractor = vision.PoseLandmarker.create_from_options(options)

# Hardcoded indices based on MediaPipe's stable pose topology mapping
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24

def extract_pose_features(image_path):
    """
    Extracts, aligns, and flattens 2D body keypoints from a single image 
    using the modern Tasks API.
    """
    image = cv2.imread(image_path)
    if image is None:
        return None
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
    detection_result = pose_extractor.detect(mp_image)
    if not detection_result.pose_landmarks:
        return None 
    landmarks = detection_result.pose_landmarks[0]
    coords = np.array([[lm.x, lm.y] for lm in landmarks])
    
    # Center the coordinates around the pelvis center (midpoint between hips)
    pelvis_center = (coords[LEFT_HIP] + coords[RIGHT_HIP]) / 2.0
    coords -= pelvis_center
    
    # Normalize scale using the distance between shoulders as a baseline anchor
    shoulder_dist = np.linalg.norm(coords[LEFT_SHOULDER] - coords[RIGHT_SHOULDER])
    if shoulder_dist > 0:
        coords /= shoulder_dist
    return coords.flatten()

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)
    print(f"Created '{IMAGE_FOLDER}' folder. Please place your images there and rerun.")
    exit()

image_paths = [os.path.join(IMAGE_FOLDER, f) for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(valid_extensions)]

if not image_paths:
    print(f"No valid images found in the '{IMAGE_FOLDER}' directory.")
    exit()

features_list = []
tracked_paths = []

print(f"Extracting structural features from {len(image_paths)} images...")
for path in image_paths:
    features = extract_pose_features(path)
    if features is not None:
        features_list.append(features)
        tracked_paths.append(path)
    else:
        print(f"Skipping (no clear pose detected): {os.path.basename(path)}")

if not features_list:
    print("Could not detect poses in any of the provided images.")
    exit()

X = np.array(features_list)

# Scaling features ensures unit variance across the coordinates
X_scaled = StandardScaler().fit_transform(X)

clustering = AgglomerativeClustering(n_clusters=args.clusters,
    metric='euclidean', linkage='ward')
cluster_labels = clustering.fit_predict(X_scaled)

print(f"\nExecution Summary:")
print(f"Total processed images: {len(tracked_paths)}")
print(f"Forced categories / clusters generated: {args.clusters}")
print(f"Unclassified / noise images: 0 (All images sorted)")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

for img_path, label in zip(tracked_paths, cluster_labels):
    cluster_dir = os.path.join(OUTPUT_FOLDER, f"{label:03d}-cluster")
    os.makedirs(cluster_dir, exist_ok=True)
    shutil.copy(img_path, os.path.join(cluster_dir, os.path.basename(img_path)))

print(f"\nSuccess! Copying complete. Check your results folder at: {OUTPUT_FOLDER}")
