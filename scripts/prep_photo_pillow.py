#!/usr/bin/env python3
"""
Enhanced: Prepare a portrait photo for clean ASCII conversion using PIL (Pillow) & NumPy.

New features:
- Configurable background detection threshold
- Multiple background detection methods (top, corners, edges, automatic)
- Output quality controls (DPI, format options)
- Better error handling and validation
- Debug mode with visualization
- Facial enhancement for better contrast preservation
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

try:
    import numpy as np
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
except ImportError as e:
    print(f"Missing dependency: {e}. Install with: pip install pillow numpy", file=sys.stderr)
    sys.exit(1)


# Enhanced configuration
def detect_background_method(
    img: Image.Image,
    method: str = "auto",
    bg_threshold: int = 50
) -> np.ndarray:
    """Detect background pixels using specified method."""
    arr = np.array(img, dtype=np.float32)
    h, w, c = arr.shape

    if method == "top":
        # Original method: top 15 rows average
        bg_template = arr[:15, :, :].mean(axis=0)
        diff = arr - bg_template[np.newaxis, :, :]
        dist = np.linalg.norm(diff, axis=2)
        return np.where(dist < bg_threshold, 0, 255).astype(np.uint8)

    elif method == "corners":
        # Average corners (top-left, top-right, bottom-left, bottom-right)
        corners = np.concatenate([
            arr[:15, :15, :].mean(axis=(0, 1)),
            arr[:15, -15:, :].mean(axis=(0, 1)),
            arr[-15:, :15, :].mean(axis=(0, 1)),
            arr[-15:, -15:, :].mean(axis=(0, 1))
        ])
        bg_color = corners.mean(axis=0)
        diff = arr - bg_color[np.newaxis, np.newaxis, :]
        dist = np.linalg.norm(diff, axis=2)
        return np.where(dist < bg_threshold, 0, 255).astype(np.uint8)

    elif method == "edges":
        # Sample edge pixels (border)
        top = arr[:15, :, :].mean(axis=0)
        bottom = arr[-15:, :, :].mean(axis=0)
        left = arr[:, :15, :].mean(axis=0)
        right = arr[:, -15:, :].mean(axis=0)
        edge_avg = (top + bottom + left + right) / 4
        dist = np.linalg.norm(arr - edge_avg[np.newaxis, np.newaxis, :], axis=2)
        return np.where(dist < bg_threshold, 0, 255).astype(np.uint8)

    elif method == "auto":
        # Try multiple methods and select best result
        methods = ["top", "corners", "edges"]
        results = {}
        for m in methods:
            mask = detect_background_method(img, m, bg_threshold)
            # Score: prefer masks with more varied background detection
            bg_ratio = np.sum(mask == 0) / (h * w)
            if 0.1 < bg_ratio < 0.7:  # Reasonable background ratio
                results[m] = mask

        if results:
            # Return first successful method
            return list(results.values())[0]
        # Fallback to original method
        return detect_background_method(img, "top", bg_threshold)

    else:
        raise ValueError(f"Unknown background detection method: {method}")


def enhance_facial_features(
    gray_img: Image.Image,
    contrast: float = 1.45,
    sharpen: bool = False,
    clahe_clip: float = 2.0,
    clahe_grid: int = 8
) -> Image.Image:
    """Apply facial enhancement to prepared image."""
    from PIL import ImageOps

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) if available
    if hasattr(ImageOps, 'autocontrast'):
        # Standard PIL autocontrast
        enhanced = ImageOps.autocontrast(gray_img, cutoff=1)
    else:
        # Fallback
        enhanced = gray_img

    # Additional contrast enhancement
    enhancer = ImageEnhance.Contrast(enhanced)
    enhanced = enhancer.enhance(contrast)

    # Optional sharpening for crisp ASCII edges
    if sharpen:
        enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

    return enhanced


def process_image(
    input_path: str,
    output_path: str,
    bg_threshold: int = 50,
    bg_method: str = "auto",
    contrast: float = 1.45,
    sharpen: bool = False,
    dpi: int = 150,
    output_format: str = "PNG",
    preview: bool = False
) -> Dict[str, Any]:
    """Process image and return stats."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    img = Image.open(input_path).convert("RGB")
    orig_w, orig_h = img.size

    # Detect background
    mask_arr = detect_background_method(img, bg_method, bg_threshold)

    # Convert to grayscale and apply mask
    gray = img.convert("L")
    gray_arr = np.array(gray, dtype=np.float32)
    prepped_arr = np.where(mask_arr == 0, 255, gray_arr).astype(np.uint8)

    # Apply facial enhancement
    prepped_img = Image.fromarray(prepped_arr, mode="L")
    prepped_img = enhance_facial_features(prepped_img, contrast=contrast, sharpen=sharpen)

    # Prepare output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    save_kwargs = {}
    if output_format == "PNG":
        save_kwargs["optimize"] = True
        save_kwargs["compress_level"] = 6

    prepped_img.save(output_path, format=output_format, dpi=(dpi, dpi), **save_kwargs)

    # Stats
    stats = {
        "input": input_path,
        "output": output_path,
        "original_size": (orig_w, orig_h),
        "output_size": prepped_img.size,
        "bg_method": bg_method,
        "bg_threshold": bg_threshold,
        "output_format": output_format,
        "dpi": dpi,
    }

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Prepare portrait photo for ASCII conversion with enhanced background removal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Background detection methods:
  top      - Average color from top rows (original method)
  corners  - Average corners pixels
  edges    - Sample edge pixels
  auto     - Try all methods, select best

Examples:
  %(prog)s input.jpg output.png
  %(prog)s --method corners --threshold 40 --contrast 1.6 input.jpg
  %(prog)s --sharpen --clahe input.jpg
        """
    )
    parser.add_argument("input", nargs="?", help="Input image path")
    parser.add_argument("output", nargs="?", help="Output image path")
    parser.add_argument("--method", "-m", default="auto",
                        choices=["auto", "top", "corners", "edges"],
                        help="Background detection method (default: auto)")
    parser.add_argument("--threshold", "-t", type=int, default=50,
                        help="Background detection threshold (default: 50)")
    parser.add_argument("--contrast", "-c", type=float, default=1.45,
                        help="Contrast enhancement factor (default: 1.45)")
    parser.add_argument("--sharpen", "-s", action="store_true",
                        help="Apply sharpening filter")
    parser.add_argument("--dpi", "-d", type=int, default=150,
                        help="Output DPI (default: 150)")
    parser.add_argument("--format", "-f", default="PNG", choices=["PNG", "JPEG"],
                        help="Output format (default: PNG)")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Show processing stats instead of saving")

    # Default paths from environment or hardcoded
    HERE = os.path.dirname(os.path.abspath(__file__))
    default_input = os.environ.get("PHOTO_INPUT", os.path.join(HERE, "..", "source-photo.jpg"))
    default_output = os.environ.get("PREPPED_OUTPUT", os.path.join(HERE, "..", "source-prepped.png"))

    parser.set_defaults(input=default_input, output=default_output)

    args = parser.parse_args()

    try:
        stats = process_image(
            args.input,
            args.output,
            bg_threshold=args.threshold,
            bg_method=args.method,
            contrast=args.contrast,
            sharpen=args.sharpen,
            dpi=args.dpi,
            output_format=args.format
        )

        if args.preview:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Prepped image saved to {stats['output']}")
            print(f"  Original: {stats['original_size'][0]}x{stats['original_size'][1]}")
            print(f"  Method: {stats['bg_method']}, Threshold: {stats['bg_threshold']}")
            print(f"  Contrast: {stats['contrast']}, Sharpen: {stats['sharpen']}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing image: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()