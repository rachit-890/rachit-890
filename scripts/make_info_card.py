#!/usr/bin/env python3
"""
Build a neofetch-style info card SVG (Andrew6rant style) to sit to the RIGHT of
the ASCII portrait: colored key/value rows for work experience, tech stack, and
highlights -- NOT GitHub stats (the contribution graph covers those).

Enhanced version with:
- Theme support (github-dark, github-light, nord, monokai, dracula)
- Command-line arguments for customization
- Data-driven content from contributions.json
- Animation toggle via STATIC env var
"""
import html
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Default paths
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "info-card.svg")
DATA_PATH = os.path.join(HERE, "..", "data", "contributions.json")
STATIC = bool(os.environ.get("STATIC"))

# Dimensions
W, H = 480, 376
PAD = 20
TITLEBAR_H = 30
KEY_X = PAD
VAL_X = PAD + 92
LINE_H = 20.5

# Theme definitions - easily extensible
THEMES = {
    "github-dark": {
        "BG": "#0d1117", "BG2": "#111722", "FRAME": "#30363d",
        "MUTED": "#7d8590", "INK": "#c9d1d9", "KEY": "#ffa657",
        "SECTION": "#58a6ff", "GREEN": "#3fb950", "ACCENT": "#22d3ee"
    },
    "github-light": {
        "BG": "#ffffff", "BG2": "#f6f8fa", "FRAME": "#d0d7de",
        "MUTED": "#656d76", "INK": "#24292f", "KEY": "#d73a49",
        "SECTION": "#0075ca", "GREEN": "#28a745", "ACCENT": "#207de5"
    },
    "nord": {
        "BG": "#2e3440", "BG2": "#3b4252", "FRAME": "#4c566a",
        "MUTED": "#d8dee9", "INK": "#eceff4", "KEY": "#81a1c1",
        "SECTION": "#81a1c1", "GREEN": "#a3be8c", "ACCENT": "#88c0d0"
    },
    "monokai": {
        "BG": "#272822", "BG2": "#3e3d32", "FRAME": "#75715e",
        "MUTED": "#a59f85", "INK": "#f8f8f2", "KEY": "#e6db74",
        "SECTION": "#66d9ef", "GREEN": "#66d9ef", "ACCENT": "#cf977d"
    },
    "dracula": {
        "BG": "#282a36", "BG2": "#44475a", "FRAME": "#6272a4",
        "MUTED": "#6272a4", "INK": "#f8f8f2", "KEY": "#ff79c6",
        "SECTION": "#6272a4", "GREEN": "#50fa7b", "ACCENT": "#79c6ff"
    }
}

# Default theme colors
def get_theme_colors(theme_name: str = "github-dark") -> Dict[str, str]:
    """Get theme colors, with fallback to github-dark."""
    return THEMES.get(theme_name, THEMES["github-dark"]).copy()


# Content model: tuples describing each row
# ("host",)                    -> "avi@github" + rule
# ("kv", key, value)           -> orange key + light value
# ("sec", title)               -> blue "— title —" rule
# ("bul", text)                -> green dot + light text
# ("gap",)                     -> vertical space
# ("stat", label, value, unit) -> highlighted stat display

def build_rows_from_data(contributions_data: Dict[str, Any], stats_data: Dict[str, Any] = None) -> List[Tuple]:
    """Build ROWS content from contributions.json data."""
    rows = [
        ("host",),
        ("kv", "Now", "Student & Backend Developer"),
        ("kv", "Edu", "B.Tech CSE, KIET (2023–2027)"),
        ("kv", "Focus", "Microservices & Spring Boot"),
        ("gap",),
        ("sec", "Stack"),
        ("kv", "Languages", "Java, Python, SQL, JS/TS"),
        ("kv", "Frameworks", "Spring Boot, Cloud, Hibernate, React"),
        ("kv", "Data/Msg", "Apache Kafka, Redis, SQL, MongoDB"),
        ("kv", "Auth/Tools", "JWT, OAuth2, Keycloak, Docker"),
        ("gap",),
        ("sec", "Highlights"),
        ("bul", "Advanced Java Certified — GeeksforGeeks"),
        ("bul", "20+ backend repositories on GitHub"),
        ("bul", "150+ DSA problems on LeetCode & Codeforces"),
    ]

    # Add dynamic stats if contribution data is available
    if contributions_data:
        total = contributions_data.get("total_contributions", 0)
        streak = contributions_data.get("current_streak", {}).get("length", 0)
        longest = contributions_data.get("longest_streak", {}).get("length", 0)

        rows.extend([
            ("gap",),
            ("stat", "Contributions", f"{total:,}", "commits"),
            ("stat", "Current Streak", f"{streak} days", ""),
            ("stat", "Longest Streak", f"{longest} days", ""),
        ])

    return rows


def esc(s: str) -> str:
    """Escape HTML entities in text."""
    return html.escape(str(s)) if s else ""


def rise(inner: str, i: int, static: bool = False) -> str:
    """fade + slight upward slide, staggered by row index; freezes visible."""
    if static:
        return f"<g>{inner}</g>"
    delay = 0.15 + i * 0.06
    return (f'<g opacity="0" transform="translate(0,5)">{inner}'
            f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 5" to="0 0" '
            f'begin="{delay:.2f}s" dur="0.4s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/></g>')


def build_svg(rows: List[Tuple], theme_colors: Dict[str, str], static: bool = False) -> str:
    """Build the complete SVG with given rows and theme colors."""
    BG = theme_colors["BG"]
    BG2 = theme_colors["BG2"]
    FRAME = theme_colors["FRAME"]
    MUTED = theme_colors["MUTED"]
    INK = theme_colors["INK"]
    KEY = theme_colors["KEY"]
    SECTION = theme_colors["SECTION"]
    GREEN = theme_colors["GREEN"]
    ACCENT = theme_colors["ACCENT"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<defs>'
        f'<linearGradient id="ibg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#ibg)"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]

    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{W/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
                 f'text-anchor="middle">rachit-890@github: ~$ neofetch</text>')

    y = TITLEBAR_H + 30
    for i, row in enumerate(rows):
        kind = row[0]
        if kind == "gap":
            y += LINE_H * 0.5
            continue
        if kind == "host":
            inner = (f'<text x="{KEY_X}" y="{y:.1f}" font-size="14" font-weight="700">'
                     f'<tspan fill="{GREEN}">rachit-890</tspan><tspan fill="{MUTED}">@</tspan>'
                     f'<tspan fill="{ACCENT}">github</tspan></text>'
                     f'<line x1="{KEY_X+155}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                     f'stroke="{FRAME}" stroke-opacity="0.8"/>')
        elif kind == "sec":
            title = esc(row[1])
            inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{SECTION}" font-size="12.5" font-weight="700">'
                     f'&#8212; {title}</text>'
                     f'<line x1="{KEY_X + 12 + len(title)*8}" y1="{y-4:.1f}" x2="{W-PAD}" y2="{y-4:.1f}" '
                     f'stroke="{FRAME}" stroke-opacity="0.8"/>')
        elif kind == "kv":
            key, val = esc(row[1]), esc(row[2])
            inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{KEY}" font-size="12.5" font-weight="700">{key}</text>'
                     f'<text x="{VAL_X}" y="{y:.1f}" fill="{INK}" font-size="12.5">{val}</text>')
        elif kind == "bul":
            txt = esc(row[1])
            inner = (f'<circle cx="{KEY_X+3}" cy="{y-4:.1f}" r="2.5" fill="{GREEN}"/>'
                     f'<text x="{KEY_X+14}" y="{y:.1f}" fill="{INK}" font-size="12.5">{txt}</text>')
        elif kind == "stat":
            label, value, unit = row[1], row[2], row[3]
            inner = (f'<text x="{KEY_X}" y="{y:.1f}" fill="{KEY}" font-size="12.5" font-weight="700">{label}:</text>'
                     f'<tspan fill="{ACCENT}" font-size="14" font-weight="700"> {value}</tspan>'
                     f'<tspan fill="{MUTED}" font-size="10"> {unit}</tspan>')
        else:
            continue
        parts.append(rise(inner, i, static))
        y += LINE_H

    parts.append("</svg>")
    return "".join(parts)


def main():
    global W, H, OUT, STATIC

    parser = argparse.ArgumentParser(
        description="Generate neofetch-style info card SVG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Themes: github-dark, github-light, nord, monokai, dracula
Examples:
  %(prog)s --theme nord
  %(prog)s --width 500 --height 400
  STATIC=1 %(prog)s  # Generate static version for Quick Look preview
        """
    )
    parser.add_argument("--theme", "-t", default=os.environ.get("CARD_THEME", "github-dark"),
                        help="Color theme to use (default: github-dark)")
    parser.add_argument("--width", "-w", type=int, default=480,
                        help="SVG width in pixels (default: 480)")
    parser.add_argument("--height", "-ht", type=int, default=376,
                        help="SVG height in pixels (default: 376)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output SVG path (default: info-card.svg in parent directory)")
    parser.add_argument("--data", "-d", default=DATA_PATH,
                        help="Path to contributions.json (default: data/contributions.json)")
    parser.add_argument("--static", "-s", action="store_true",
                        help="Generate static SVG without animations (overrides STATIC env var)")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Print SVG to stdout instead of writing file")
    parser.add_argument("--list-themes", action="store_true",
                        help="List available themes")

    args = parser.parse_args()

    # Update global dimensions
    W, H = args.width, args.height

    # Handle list-themes
    if args.list_themes:
        print("Available themes:")
        for name in sorted(THEMES.keys()):
            colors = THEMES[name]
            print(f"  {name}: BG={colors['BG']}, INK={colors['INK']}")
        return

    # Update static flag
    if args.static:
        STATIC = True

    # Determine output path
    output_path = args.output or OUT

    # Load contribution data if available
    contributions_data = None
    if os.path.exists(args.data):
        try:
            with open(args.data, 'r') as f:
                contributions_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load contribution data: {e}", file=__import__('sys').stderr)

    # Build rows
    rows = build_rows_from_data(contributions_data or {})

    # Get theme colors
    theme_colors = get_theme_colors(args.theme)

    # Build SVG
    svg = build_svg(rows, theme_colors, static=STATIC)

    # Output
    if args.preview:
        print(svg)
    else:
        with open(output_path, "w") as f:
            f.write(svg)
        print(f"wrote {output_path} ({len(svg)} bytes; {W}x{H})")


if __name__ == "__main__":
    main()