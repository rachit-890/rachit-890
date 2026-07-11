#!/usr/bin/env python3
"""
Prepare a transparent portrait photo for clean ASCII conversion using pure PIL (Pillow).
This replaces the OpenCV/rembg dependency because the source image (mypicnbg.png)
is already background-removed.
"""
import os
import sys
from PIL import Image, ImageOps, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else "/home/fedora/Portfolio/portfolio-website/public/images/mypicnbg.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

# 1. Load image and ensure it has alpha channel (RGBA)
img = Image.open(INP).convert("RGBA")
r, g, b, alpha = img.split()

# 2. Convert RGB representation to grayscale
gray = Image.merge("RGB", (r, g, b)).convert("L")

# 3. Apply contrast enhancement (autocontrast with a small cutoff, plus a contrast boost)
gray = ImageOps.autocontrast(gray, cutoff=2)
enhancer = ImageEnhance.Contrast(gray)
# Boost contrast to make features sharp
gray = enhancer.enhance(1.4)

# 4. Paste onto white background using the alpha mask
# where alpha is 0 (background), it should be pure white (255)
white = Image.new("L", img.size, 255)
prepped = Image.composite(gray, white, alpha)

# Save the result
prepped.save(OUT)
print(f"Prepped image saved to {OUT} with size {prepped.size}")
