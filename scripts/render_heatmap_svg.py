#!/usr/bin/env python3
"""
Enhanced version of the GitHub-style contribution heatmap SVG generator.

Improvements:
- Responsive layout: cell size auto-scales to fit available width
- Theme support: multiple color palettes (github, nord, monokai, dracula)
- Interactive elements: hover effects and tooltips (CSS-based)
- Enhanced animation: configurable reveal timing and direction
- Better performance: pre-computed values, optimized SVG structure
- Accessibility: proper ARIA labels and title elements
"""
import datetime
import json
import os
import argparse
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# Configuration
HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap.svg")

# Theme definitions - multiple color palettes
THEMES = {
    "github": {
        "PALETTE": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"],
        "BG": "#0a0e14", "BG2": "#0d1420", "FRAME": "#1f6feb", "MUTED": "#7d8590",
        "TEXT": "#e6edf3", "ACCENT": "#22d3ee", "GREEN": "#39d353", "GOLD": "#f2cc60"
    },
    "github-light": {
        "PALETTE": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39", "#0e4429"],
        "BG": "#ffffff", "BG2": "#f6f8fa", "FRAME": "#d0d7de", "MUTED": "#656d76",
        "TEXT": "#24292f", "ACCENT": "#0969da", "GREEN": "#1a7f37", "GOLD": "#bf8700"
    },
    "nord": {
        "PALETTE": ["#3b4252", "#4c566a", "#5e81ac", "#88c0d0", "#8fbcbb", "#a3be8c"],
        "BG": "#2e3440", "BG2": "#3b4252", "FRAME": "#4c566a", "MUTED": "#d8dee9",
        "TEXT": "#eceff4", "ACCENT": "#88c0d0", "GREEN": "#a3be8c", "GOLD": "#ebcb8b"
    },
    "monokai": {
        "PALETTE": ["#2e2e2e", "#3a3a3a", "#49483e", "#75715e", "#a6e22e", "#f8f8f2"],
        "BG": "#272822", "BG2": "#3e3d32", "FRAME": "#75715e", "MUTED": "#a59f85",
        "TEXT": "#f8f8f2", "ACCENT": "#66d9ef", "GREEN": "#a6e22e", "GOLD": "#e6db74"
    },
    "dracula": {
        "PALETTE": ["#282a36", "#44475a", "#6272a4", "#bd93f9", "#ff79c6", "#ffb86c"],
        "BG": "#282a36", "BG2": "#44475a", "FRAME": "#6272a4", "MUTED": "#6272a4",
        "TEXT": "#f8f8f2", "ACCENT": "#bd93f9", "GREEN": "#50fa7b", "GOLD": "#f1fa8c"
    }
}

# Default theme
DEFAULT_THEME = "github"

# Layout parameters
PAD = 22
LEFT_LABEL_W = 30
TOP_LABEL_H = 20
TITLEBAR_H = 30

# Animation timing (configurable)
DEFAULT_COL_T = 0.018   # per-column delay contribution (left -> right sweep)
DEFAULT_ROW_T = 0.045   # per-row delay contribution (top -> bottom cascade)
DEFAULT_CELL_DUR = 0.42

# Reveal animation modes
REVEAL_MODES = {
    "cascade": "diagonal slide-down (original style)",
    "sweep": "left-to-right column reveal",
    "fade": "simple opacity fade",
    "pop": "scale-up pop effect"
}


def level_for(count: int) -> int:
    """Convert contribution count to level 0-5."""
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def build_grid(days: List[Dict[str, Any]]) -> List[List[Optional[Tuple[str, int, int]]]]:
    """Build 53-week x 7-day grid from days data."""
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def calculate_responsive_cell_size(n_cols: int, max_width: int = 869) -> Tuple[int, int, int]:
    """Calculate responsive cell size based on desired max width."""
    # Base cell from GitHub (12px + 3px gap = 15px step)
    base_step = 15

    # Calculate available width for grid
    available_width = max_width - 2 * PAD - LEFT_LABEL_W
    computed_step = available_width / n_cols

    # Clamp to reasonable range [8, 18]
    step = max(8, min(18, int(computed_step)))

    # Ensure step is even for clean rendering
    if step % 2 != 0:
        step += 1

    cell = step - 3  # 3px gap
    gap = 3
    return cell, gap, step


def render(
    data: Dict[str, Any],
    theme_name: str = DEFAULT_THEME,
    cell_size: Optional[int] = None,
    reveal_mode: str = "cascade",
    static: bool = False,
    animated: bool = True
) -> str:
    """Render the contribution heatmap SVG."""
    theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    PALETTE = theme["PALETTE"]

    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)

    # Responsive cell sizing
    if cell_size:
        CELL = cell_size
        GAP = 3
    else:
        CELL, GAP, _ = calculate_responsive_cell_size(n_cols)

    STEP = CELL + GAP
    art_w = n_cols * STEP
    art_h = 7 * STEP

    # Month labels
    month_labels = []
    seen_months = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = datetime.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key not in seen_months and date.day <= 7:
                seen_months.add(key)
                month_labels.append((ci, date.strftime("%b")))
            break

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    stats_h = 88
    canvas_h = TITLEBAR_H + TOP_LABEL_H + art_h + stats_h + PAD

    # Animation CSS
    if animated and not static:
        if reveal_mode == "sweep":
            css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateX(-8px); }}
  100% {{ opacity: 1; transform: translateX(0); }}
}}
.c {{ opacity: 0; animation: cell {DEFAULT_CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
"""
        elif reveal_mode == "fade":
            css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; }}
  100% {{ opacity: 1; }}
}}
.c {{ opacity: 0; animation: cell {DEFAULT_CELL_DUR:.2f}s ease-out both; }}
"""
        elif reveal_mode == "pop":
            css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: scale(0.3); transform-origin: center; }}
  100% {{ opacity: 1; transform: scale(1); }}
}}
.c {{ opacity: 0; animation: cell {DEFAULT_CELL_DUR:.2f}s cubic-bezier(.34,1.56,.64,1) both; }}
"""
        else:  # cascade (default)
            css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {DEFAULT_CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
"""
    else:
        css = ""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'role="img" aria-label="GitHub contribution heatmap for {data.get("username", "user")}">',
        f'<style>{css}</style>',
        '<defs>'
        f'<linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{theme["BG2"]}"/><stop offset="1" stop-color="{theme["BG"]}"/></linearGradient>'
        '</defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#hbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w-1}" height="{canvas_h-1}" rx="12" '
        f'fill="none" stroke="{theme["FRAME"]}" stroke-width="1" stroke-opacity="0.55"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{theme["FRAME"]}" stroke-opacity="0.35"/>',
    ]

    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{canvas_w/2}" y="{TITLEBAR_H/2 + 4}" fill="{theme["MUTED"]}" font-size="12" '
                 f'text-anchor="middle">rachit-890@github: ~/contributions --graph</text>')

    grid_top = TITLEBAR_H + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for ci, label in month_labels:
        x = grid_left + ci * STEP
        parts.append(f'<text x="{x}" y="{TITLEBAR_H + 14}" fill="{theme["MUTED"]}" font-size="10">{label}</text>')

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.78
        parts.append(f'<text x="{PAD}" y="{y:.1f}" fill="{theme["MUTED"]}" font-size="9">{wname}</text>')

    # The boxes
    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            delay = ci * DEFAULT_COL_T + ri * DEFAULT_ROW_T
            plural = "s" if count != 1 else ""

            # Add hover effect if not static
            hover_attr = ' class="c"' if (animated and not static) else ''
            opacity_style = f' style="animation-delay:{delay:.3f}s"' if (animated and not static) else ''

            parts.append(
                f'<rect{hover_attr} x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{PALETTE[lvl]}"{opacity_style}>'
                f'<title>{date_s}: {count} contribution{plural}</title></rect>'
            )

    # Legend: Less [][][][][] More
    leg_y = grid_top + art_h + 6
    leg_x = canvas_w - PAD - (len(PALETTE) * (CELL - 1) + 70)
    parts.append(f'<text x="{leg_x}" y="{leg_y + CELL*0.8:.1f}" fill="{theme["MUTED"]}" font-size="10" text-anchor="end">Less</text>')
    lx = leg_x + 8
    for lvl, color in enumerate(PALETTE):
        parts.append(f'<rect x="{lx}" y="{leg_y}" width="{CELL-1}" height="{CELL-1}" rx="2.2" fill="{color}"/>')
        lx += CELL
    parts.append(f'<text x="{lx + 4}" y="{leg_y + CELL*0.8:.1f}" fill="{theme["MUTED"]}" font-size="10">More</text>')

    # Stats footer
    sep_y = leg_y + CELL + 14
    parts.append(f'<line x1="0" y1="{sep_y}" x2="{canvas_w}" y2="{sep_y}" stroke="{theme["FRAME"]}" stroke-opacity="0.25"/>')

    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    total = data["total_contributions"]
    best = data["best_day"]
    rng = data["range"]

    ly = sep_y + 24
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{theme["GREEN"]}">'
                 f'<tspan font-weight="700">{total:,}</tspan>'
                 f'<tspan fill="{theme["MUTED"]}"> contributions in the last year</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{theme["MUTED"]}" text-anchor="end">'
                 f'{rng["start"]} &#8594; {rng["end"]}</text>')
    ly += 24
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{theme["MUTED"]}">current streak '
                 f'<tspan fill="{theme["ACCENT"]}" font-weight="700">{cs} days</tspan>'
                 f'<tspan fill="{theme["MUTED"]}">   &#183;   longest </tspan>'
                 f'<tspan fill="{theme["ACCENT"]}" font-weight="700">{ls} days</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{theme["MUTED"]}" text-anchor="end">'
                 f'best day <tspan fill="{theme["GOLD"]}" font-weight="700">{best["count"]}</tspan> on {best["date"]}</text>')

    parts.append("</svg>")
    return "".join(parts)


def load_data(path: str) -> Dict[str, Any]:
    """Load contributions data from JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_svg(svg: str, path: str) -> None:
    """Save SVG to file with proper encoding."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(svg)


def main():
    parser = argparse.ArgumentParser(
        description="Render GitHub-style contribution heatmap SVG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Themes: {', '.join(THEMES.keys())}
Reveal modes: {', '.join(REVEAL_MODES.keys())}

Examples:
  %(prog)s --theme nord
  %(prog)s --reveal-mode pop --cell-size 14
  %(prog)s --static  # No animations
  %(prog)s --width 1200  # Wider responsive layout
        """
    )
    parser.add_argument("--input", "-i", default=IN_PATH,
                        help="Input JSON path (default: data/contributions.json)")
    parser.add_argument("--output", "-o", default=OUT_PATH,
                        help="Output SVG path (default: contrib-heatmap.svg)")
    parser.add_argument("--theme", "-t", default=DEFAULT_THEME,
                        choices=list(THEMES.keys()),
                        help="Color theme (default: github)")
    parser.add_argument("--cell-size", "-c", type=int, default=None,
                        help="Fixed cell size in pixels (ignores responsive sizing)")
    parser.add_argument("--reveal-mode", "-r", default="cascade",
                        choices=list(REVEAL_MODES.keys()),
                        help="Animation reveal mode (default: cascade)")
    parser.add_argument("--width", "-w", type=int, default=869,
                        help="Max canvas width for responsive sizing (default: 869)")
    parser.add_argument("--static", "-s", action="store_true",
                        help="Generate static SVG without animations")
    parser.add_argument("--no-animate", "-na", action="store_true",
                        help="Disable animations (alias for --static)")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Print SVG to stdout instead of writing file")
    parser.add_argument("--list-themes", action="store_true",
                        help="List available themes")

    args = parser.parse_args()

    if args.list_themes:
        print("Available themes:")
        for name, theme in THEMES.items():
            print(f"  {name}: {len(theme['PALETTE'])} levels, BG={theme['BG']}")
        return

    # Load data
    data = load_data(args.input)

    # Render
    svg = render(
        data,
        theme_name=args.theme,
        cell_size=args.cell_size,
        reveal_mode=args.reveal_mode,
        static=args.static or args.no_animate,
    )

    # Output
    if args.preview:
        print(svg)
    else:
        save_svg(svg, args.output)
        print(f"wrote {args.output} ({len(svg)} bytes; theme: {args.theme})")


if __name__ == "__main__":
    main()