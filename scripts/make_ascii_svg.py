#!/usr/bin/env python3
"""
Enhanced: Convert a portrait photo into a CLEAN, monochrome ASCII-art SVG
with support for custom resolutions, color schemes, progressive animations,
and theme-aware rendering.
"""
import html
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    from PIL import Image, ImageEnhance, ImageOps, ImageFilter
except ImportError:
    print("PIL not installed. Run: pip install pillow numpy", file=sys.stderr)
    sys.exit(1)

# Enhanced: Configuration loading from JSON for themes and presets
THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")
DEFAULT_THEME = "github-dark"

# Ensure themes directory exists
os.makedirs(THEMES_DIR, exist_ok=True)

# Performance boost: Pre-compiled color validation regex
import re
HEX_COLOR_PATTERN = re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$')


def load_theme(theme_name: str) -> Dict[str, str]:
    """Load theme configuration from JSON file."""
    theme_path = os.path.join(THEMES_DIR, f"{theme_name}.json")
    if os.path.exists(theme_path):
        with open(theme_path, 'r') as f:
            return json.load(f)
    return {}


def validate_hex_color(color: str) -> str:
    """Validate and normalize hex color."""
    if not HEX_COLOR_PATTERN.match(color):
        raise ValueError(f"Invalid hex color: {color}")
    return color.upper()


def get_theme_colors(theme_name: str) -> Dict[str, str]:
    """Get complete color palette for a theme."""
    defaults = {
        "github-dark": {
            "BG": "#0d1117",
            "BG2": "#111722",
            "FRAME": "#30363d",
            "TITLE_TEXT": "#7d8590",
            "INK": "#c9d1d9",
            "CURSOR": "#c9d1d9",
        },
        "github-light": {
            "BG": "#ffffff",
            "BG2": "#f6f8fa",
            "FRAME": "#d0d7de",
            "TITLE_TEXT": "#656d76",
            "INK": "#24292f",
            "CURSOR": "#24292f",
        },
        "nord": {
            "BG": "#2e3440",
            "BG2": "#3b4252",
            "FRAME": "#4c566a",
            "TITLE_TEXT": "#d8dee9",
            "INK": "#eceff4",
            "CURSOR": "#88c0d0",
        },
        "monokai": {
            "BG": "#272822",
            "BG2": "#3e3d32",
            "FRAME": "#75715e",
            "TITLE_TEXT": "#a59f85",
            "INK": "#f8f8f2",
            "CURSOR": "#a6e22e",
        },
        "dracula": {
            "BG": "#282a36",
            "BG2": "#44475a",
            "FRAME": "#6272a4",
            "TITLE_TEXT": "#6272a4",
            "INK": "#f8f8f2",
            "CURSOR": "#ff79c6",
        },
    }

    theme = defaults.get(theme_name, defaults["github-dark"])
    custom = load_theme(theme_name)
    return {**theme, **custom}


# Enhanced: Adaptive resolution system
def calculate_optimal_resolution(src_path: str, max_width: int = 1200, max_height: int = 1200) -> Tuple[int, int, int, int]:
    """Calculate optimal COLS, ROWS, CELL_W, CELL_H based on image aspect ratio."""
    try:
        with Image.open(src_path) as im:
            orig_w, orig_h = im.size
    except Exception:
        # Fallback defaults
        return 100, 53, 8, 15

    aspect = orig_w / orig_h

    # Determine base resolution - target 100x53 as standard, scale for high-res
    if max(orig_w, orig_h) > 800:
        scale = 1.5
    else:
        scale = 1.0

    base_cols = int(100 * scale)
    base_rows = int(53 * scale)

    # Adjust to maintain aspect ratio
    if aspect > 1:
        cols = min(base_cols, int(base_rows * aspect))
        rows = base_rows
    else:
        cols = base_cols
        rows = min(base_rows, int(base_cols / aspect))

    # Ensure minimum and maximum bounds
    cols = max(60, min(cols, 200))
    rows = max(30, min(rows, 150))

    # Calculate cell dimensions
    cell_w = max(6, min(12, int(8 * scale)))
    cell_h = max(12, min(20, int(15 * scale)))

    return cols, rows, cell_w, cell_h


# Performance boost: Optimized ramp calculation
RAMP_PRESETS = {
    "standard": " .`:-=+*cs#%@",
    "dense": " .`-_~=+*cba#%@",
    "blocks": " ░▒▓█",
    "blocks2": " ▁▂▃▄▅▆▇█",
    "dots": " ·:;+=xX$&@",
}


def process_image(
    src_path: str,
    cols: int,
    rows: int,
    contrast: float = 1.05,
    brightness: float = 1.0,
    gamma: float = 1.18,
    sharpen: bool = False,
    white_floor: float = 0.80,
    ramp: str = "standard",
    invert: bool = False,
) -> List[str]:
    """Process image into ASCII rows with enhanced options."""
    ramp_chars = RAMP_PRESETS.get(ramp, ramp)

    im = Image.open(src_path).convert("L")
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2))

    im = ImageEnhance.Brightness(im).enhance(brightness)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = im.resize((cols, rows), Image.LANCZOS)
    px = im.load()

    rows_txt = []
    for y in range(rows):
        chars = []
        for x in range(cols):
            lum = px[x, y] / 255.0
            lum = pow(lum, gamma)
            if lum >= white_floor:
                chars.append(" ")
                continue
            idx = int((1.0 - lum) * (len(ramp_chars) - 1) + 0.5)
            idx = max(0, min(len(ramp_chars) - 1, idx))
            char = ramp_chars[idx]
            if invert:
                # Invert: map to opposite end of ramp
                char = ramp_chars[len(ramp_chars) - 1 - idx]
            chars.append(char)
        rows_txt.append("".join(chars))

    return rows_txt


def build_svg(
    rows_txt: List[str],
    cols: int,
    rows: int,
    cell_w: int,
    cell_h: int,
    theme_colors: Dict[str, str],
    animate: bool = True,
    stagger: float = 0.11,
    row_dur: float = 0.11,
    font_family: str = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    cursor_style: str = "block",
) -> str:
    """Build the complete SVG with enhanced animation options."""
    PAD = 20
    TITLEBAR_H = 30
    STATUS_H = 30
    ART_W = cols * cell_w
    ART_H = rows * cell_h
    CANVAS_W = ART_W + PAD * 2
    CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

    BG = theme_colors.get("BG", "#0d1117")
    BG2 = theme_colors.get("BG2", "#111722")
    FRAME = theme_colors.get("FRAME", "#30363d")
    TITLE_TEXT = theme_colors.get("TITLE_TEXT", "#7d8590")
    INK = theme_colors.get("INK", "#c9d1d9")
    CURSOR = theme_colors.get("CURSOR", "#c9d1d9")

    art_top = TITLEBAR_H + PAD * 0.35
    font_size = cell_h * 0.86

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="{font_family}">'
    )
    parts.append('<defs>'
                 f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
                 f'</linearGradient></defs>')
    parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
    parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1}" height="{CANVAS_H-1}" rx="12" '
                 f'fill="none" stroke="{FRAME}" stroke-width="1"/>')
    parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{CANVAS_W/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
                 f'text-anchor="middle">rachit-890@github: ~$ ./portrait.sh</text>')

    # Enhanced: Generate animation keyframes for better performance
    if animate:
        parts.append(f'''
<style>
  @keyframes rowReveal {{
    0% {{ opacity: 0; transform: translateY(4px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes cursorBlink {{
    0%, 50% {{ opacity: 1; }}
    51%, 100% {{ opacity: 0; }}
  }}
  .row {{ animation: rowReveal {row_dur:.2f}s cubic-bezier(0.2, 0.8, 0.2, 1) both; }}
  .cursor {{ animation: cursorBlink 1s infinite; }}
</style>
''')

    STATIC = bool(os.environ.get("STATIC"))

    for ry, line in enumerate(rows_txt):
        y = art_top + ry * cell_h + cell_h * 0.74
        row_y = art_top + ry * cell_h
        delay = ry * stagger
        safe = html.escape(line)
        text = (f'<text class="row" xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
                f'font-size="{font_size:.1f}" textLength="{ART_W}" lengthAdjust="spacing" '
                f'style="animation-delay:{delay:.3f}s">{safe}</text>')

        if STATIC or not animate:
            parts.append(text)
            continue

        # Enhanced: Use CSS animation instead of SMIL for better browser support
        parts.append(text)
        # Cursor element
        cursor_width = cell_w if cursor_style == "block" else 2
        parts.append(
            f'<rect class="cursor" x="{PAD}" y="{row_y+1:.1f}" width="{cursor_width}" '
            f'height="{cell_h-2}" fill="{CURSOR}" style="animation-delay:{delay:.3f}s"/>'
        )

    # Status bar with enhanced cursor
    status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
    status_y = status_line_y + 19
    parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
    parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
                 f'rachit-890@github:~$ whoami <tspan fill="{INK}">Rachit Kushwaha</tspan></text>')
    cursor_x = PAD + 258
    parts.append(f'<rect x="{cursor_x}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}" '
                 f'class="cursor"/>')

    parts.append("</svg>")
    return "".join(parts)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced ASCII portrait SVG generator")
    parser.add_argument("input", nargs="?", help="Input image path")
    parser.add_argument("output", nargs="?", help="Output SVG path")
    parser.add_argument("--theme", "-t", default=os.environ.get("ASCII_THEME", DEFAULT_THEME),
                        help="Color theme (github-dark, github-light, nord, monokai, dracula)")
    parser.add_argument("--cols", type=int, help="Number of columns")
    parser.add_argument("--rows", type=int, help="Number of rows")
    parser.add_argument("--cell-w", type=int, help="Cell width in pixels")
    parser.add_argument("--cell-h", type=int, help="Cell height in pixels")
    parser.add_argument("--contrast", type=float, default=1.05, help="Contrast adjustment")
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness adjustment")
    parser.add_argument("--gamma", type=float, default=1.18, help="Gamma correction")
    parser.add_argument("--sharpen", action="store_true", help="Apply unsharp mask")
    parser.add_argument("--white-floor", type=float, default=0.80, help="White floor threshold")
    parser.add_argument("--ramp", default="standard", choices=list(RAMP_PRESETS.keys()),
                        help="ASCII character ramp")
    parser.add_argument("--invert", action="store_true", help="Invert ASCII density")
    parser.add_argument("--no-animate", action="store_true", help="Disable animations")
    parser.add_argument("--stagger", type=float, default=0.11, help="Row animation stagger (seconds)")
    parser.add_argument("--row-dur", type=float, default=0.11, help="Row animation duration (seconds)")
    parser.add_argument("--cursor", choices=["block", "bar", "underline"], default="block",
                        help="Cursor style")
    parser.add_argument("--font", default="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                        help="Font family")
    parser.add_argument("--auto-res", action="store_true", default=True, help="Auto-calculate resolution from image")
    parser.add_argument("--preview", action="store_true", help="Print SVG to stdout")

    args = parser.parse_args()

    HERE = os.path.dirname(os.path.abspath(__file__))
    SRC = args.input or os.path.join(HERE, "..", "source-prepped.png")
    OUT = args.output or os.path.join(HERE, "..", "rachit-ascii.svg")

    # Auto-resolution calculation
    if args.auto_res and not (args.cols and args.rows and args.cell_w and args.cell_h):
        cols, rows, cell_w, cell_h = calculate_optimal_resolution(SRC)
        if args.cols: cols = args.cols
        if args.rows: rows = args.rows
        if args.cell_w: cell_w = args.cell_w
        if args.cell_h: cell_h = args.cell_h
        print(f"Auto-resolution: {cols}x{rows} cells, {cell_w}x{cell_h}px each")
    else:
        cols = args.cols or 100
        rows = args.rows or 53
        cell_w = args.cell_w or 8
        cell_h = args.cell_h or 15

    # Load theme
    theme_colors = get_theme_colors(args.theme)
    print(f"Using theme: {args.theme}")

    # Process image
    print(f"Processing {SRC} -> {cols}x{rows} ASCII grid...")
    rows_txt = process_image(
        SRC, cols, rows,
        contrast=args.contrast,
        brightness=args.brightness,
        gamma=args.gamma,
        sharpen=args.sharpen,
        white_floor=args.white_floor,
        ramp=args.ramp,
        invert=args.invert,
    )

    # Build SVG
    svg = build_svg(
        rows_txt, cols, rows, cell_w, cell_h, theme_colors,
        animate=not args.no_animate,
        stagger=args.stagger,
        row_dur=args.row_dur,
        font_family=args.font,
        cursor_style=args.cursor,
    )

    if args.preview:
        print(svg)
    else:
        with open(OUT, "w") as f:
            f.write(svg)
        print(f"Wrote {OUT} ({len(svg)} bytes; {cols*cell_w + 40}x{rows*cell_h + 80} canvas)")


if __name__ == "__main__":
    main()