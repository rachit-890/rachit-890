#!/usr/bin/env python3
"""
Prepare a portrait photo for clean ASCII conversion using pure PIL (Pillow) & NumPy.
This script extracts the background color (a light blue/gray studio backdrop)
using a horizontal template of the top 15 rows, computes the Euclidean color distance,
and sets the background to pure white (255) to isolate the subject.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageOps, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
# Both mypic.jpeg and mypicnbg.png have the background, so we use mypic.jpeg
INP = sys.argv[1] if len(sys.argv) > 1 else "/home/fedora/Portfolio/portfolio-website/public/images/mypic.jpeg"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

# 1. Load image and convert to RGB
img = Image.open(INP).convert("RGB")
arr = np.array(img, dtype=np.float32)
h, w, c = arr.shape

# 2. Extract backdrop color template (average of top 15 rows to reduce noise)
bg_template = arr[:15, :, :].mean(axis=0) # shape (w, c)

# 3. Compute Euclidean distance from each pixel to the backdrop color of its column
diff = arr - bg_template[np.newaxis, :, :]
dist = np.linalg.norm(diff, axis=2) # shape (h, w)

# 4. Create a binary mask (0 = background, 255 = subject)
# Threshold of 50 works perfectly to isolate the subject without leaking into the face
mask_arr = np.where(dist < 50, 0, 255).astype(np.uint8)

# 5. Convert to grayscale and apply mask (set background pixels to 255)
gray = img.convert("L")
gray_arr = np.array(gray)
prepped_arr = np.where(mask_arr == 0, 255, gray_arr).astype(np.uint8)

# 6. Enhance contrast of the subject
prepped_img = Image.fromarray(prepped_arr, mode="L")
prepped_img = ImageOps.autocontrast(prepped_img, cutoff=1)
enhancer = ImageEnhance.Contrast(prepped_img)
prepped_img = enhancer.enhance(1.45)

# Save the result
prepped_img.save(OUT)
print(f"Prepped image saved to {OUT} with size {prepped_img.size}")
