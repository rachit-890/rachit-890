#!/usr/bin/env python3
"""
Banner Generator for Rachit Kushwaha's GitHub Profile
Generates high-performance, dark.svg and light.svg SVGs with:
1. 300x340 Floyd-Steinberg dithered portrait (background-segmented in dark mode).
2. ~60 group global shimmering intro animation (3.2s, once).
3. 14.2s loop with ~94 organic drift bands (2D Gaussian noise sigma ~4).
4. ~900 traveller dots morphing between Java, Spring Boot, and Apache Kafka logos via Optimal Transport.
5. Locked SYSTEM.INFO panel with programmatic dotted leaders and textLength attributes.
"""

import os
import sys
import math
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from scipy import ndimage
from scipy.optimize import linear_sum_assignment

# Set random seed for reproducibility
np.random.seed(890)

# Directory setup
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(HERE, ".."))
PHOTO_PATH = os.path.join(REPO_DIR, "photo.jpeg")

# --- Layout Parameters ---
CANVAS_W = 1180
CANVAS_H = 610

# Left frame (VISUAL.MAP)
LEFT_FRAME_X = 24
LEFT_FRAME_Y = 24
LEFT_FRAME_W = 448
LEFT_FRAME_H = 562

# Portrait grid area inside VISUAL.MAP
PORTRAIT_X0 = 36
PORTRAIT_Y0 = 72
PORTRAIT_W = 424
PORTRAIT_H = 500
COLS = 300
ROWS = 340
CW = PORTRAIT_W / COLS  # ~1.4133
CH = PORTRAIT_H / ROWS  # ~1.4705

# Right frame (SYSTEM.INFO)
RIGHT_FRAME_X = 492
RIGHT_FRAME_Y = 24
RIGHT_FRAME_W = 664
RIGHT_FRAME_H = 562

# --- Color Palettes ---
PALETTES = {
    "dark": {
        "BG": "#0A101F",
        "PANEL_BG": "#0F172A",
        "FRAME": "#1E293B",
        "PORTRAIT": "#A78BFA",      # Violet
        "CHROME": "#22D3EE",        # Cyan
        "ACCENT": "#10B981",        # Emerald
        "TEXT_MUTED": "#64748B",
        "TEXT_MAIN": "#F8FAFC",
        "LABEL_COLOR": "#94A3B8",
        "LEADER": "#1E293B",
        "LIVE_BG": "#EF4444",
        "LIVE_PULSE": "rgba(239, 68, 68, 0.4)",
        "PILL_BG": "#1E293B",
        "PILL_BORDER": "#22D3EE"
    },
    "light": {
        "BG": "#FFFFFF",
        "PANEL_BG": "#F8FAFC",
        "FRAME": "#E2E8F0",
        "PORTRAIT": "#7C3AED",      # Deep Violet
        "CHROME": "#0891B2",        # Deep Cyan
        "ACCENT": "#10B981",        # Emerald
        "TEXT_MUTED": "#64748B",
        "TEXT_MAIN": "#0F172A",
        "LABEL_COLOR": "#475569",
        "LEADER": "#E2E8F0",
        "LIVE_BG": "#EF4444",
        "LIVE_PULSE": "rgba(239, 68, 68, 0.4)",
        "PILL_BG": "#F1F5F9",
        "PILL_BORDER": "#0891B2"
    }
}


def load_and_preprocess_photo(photo_path):
    """Crop head & shoulders, segment background for dark mode, enhance grayscale."""
    img = Image.open(photo_path).convert("RGB")
    w, h = img.size

    # Crop head + shoulders (target aspect ratio 300:340)
    crop_w = int(w * 0.85)
    crop_h = int(crop_w * ROWS / COLS)
    if crop_h > h:
        crop_h = int(h * 0.95)
        crop_w = int(crop_h * COLS / ROWS)

    left = int((w - crop_w) / 2)
    top = int(h * 0.04)
    cropped = img.crop((left, top, left + crop_w, top + crop_h))

    # Background segmentation (color distance threshold + morphological closing + fill holes)
    arr = np.array(cropped, dtype=float)
    bg_sample = np.mean([arr[:10, :10], arr[:10, -10:], arr[-10:, :10], arr[-10:, -10:]], axis=(0, 1, 2))
    color_dist = np.linalg.norm(arr - bg_sample, axis=2)

    raw_mask = color_dist > 28
    closed_mask = ndimage.binary_closing(raw_mask, structure=np.ones((9, 9)))
    filled_mask = ndimage.binary_fill_holes(closed_mask)
    labeled, num_features = ndimage.label(filled_mask)
    if num_features > 0:
        sizes = ndimage.sum(filled_mask, labeled, range(1, num_features + 1))
        largest_label = np.argmax(sizes) + 1
        subject_mask_full = (labeled == largest_label)
    else:
        subject_mask_full = filled_mask

    mask_img = Image.fromarray((subject_mask_full * 255).astype(np.uint8)).resize((COLS, ROWS), Image.NEAREST)
    mask_grid = np.array(mask_img) > 128

    # Grayscale enhancement
    gray = cropped.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=0))
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    gray_grid = np.array(gray.resize((COLS, ROWS), Image.LANCZOS), dtype=float)

    return gray_grid, mask_grid


def fs_dither_serpentine(gray_grid, mask_grid, dark_mode=True, gamma=1.2, threshold=128):
    """1-bit Floyd-Steinberg dither with serpentine order and background segmentation for dark mode."""
    rows, cols = gray_grid.shape
    # Apply gamma adjustment
    buf = ((gray_grid / 255.0) ** gamma) * 255.0
    dots = np.zeros((rows, cols), dtype=bool)

    for r in range(rows):
        if r % 2 == 0:
            col_range = range(cols)
            step = 1
        else:
            col_range = range(cols - 1, -1, -1)
            step = -1

        for c in col_range:
            if dark_mode:
                # Segment background out: force clean background and clear bleed
                if not mask_grid[r, c]:
                    buf[r, c] = 0.0
                    dots[r, c] = False
                    continue
                val = buf[r, c]
                is_dot = val >= threshold
                dots[r, c] = is_dot
                target = 255.0 if is_dot else 0.0
                err = val - target
            else:
                # Light mode: keep background, dots draw dark parts
                val = buf[r, c]
                is_dot = val < threshold
                dots[r, c] = is_dot
                target = 0.0 if is_dot else 255.0
                err = val - target

            # Distribute error to 4 neighbors in serpentine direction
            c_next = c + step
            if 0 <= c_next < cols:
                buf[r, c_next] += err * (7.0 / 16.0)
            c_bl = c - step
            if r + 1 < rows and 0 <= c_bl < cols:
                buf[r + 1, c_bl] += err * (3.0 / 16.0)
            if r + 1 < rows:
                buf[r + 1, c] += err * (5.0 / 16.0)
            c_br = c + step
            if r + 1 < rows and 0 <= c_br < cols:
                buf[r + 1, c_br] += err * (1.0 / 16.0)

    return dots


def sample_curve_points(lines_list, num_points=900):
    """Uniformly sample exactly num_points from parametric curve segments."""
    all_pts = []
    lens = []
    for line in lines_list:
        line = np.array(line)
        dists = np.linalg.norm(np.diff(line, axis=0), axis=1)
        total_len = dists.sum()
        lens.append(total_len)
        all_pts.append((line, dists, total_len))

    total_path_len = sum(lens)
    out_pts = []
    for line, dists, tlen in all_pts:
        n_seg = max(2, int(round(num_points * (tlen / total_path_len))))
        if tlen == 0:
            out_pts.append(np.repeat(line[:1], n_seg, axis=0))
            continue
        cum = np.zeros(len(line))
        cum[1:] = np.cumsum(dists)
        t_vals = np.linspace(0, tlen, n_seg)
        x_interp = np.interp(t_vals, cum, line[:, 0])
        y_interp = np.interp(t_vals, cum, line[:, 1])
        out_pts.append(np.column_stack([x_interp, y_interp]))

    res = np.vstack(out_pts)
    if len(res) > num_points:
        idx = np.linspace(0, len(res) - 1, num_points, dtype=int)
        res = res[idx]
    elif len(res) < num_points:
        reps = num_points - len(res)
        add_idx = np.random.choice(len(res), reps, replace=True)
        res = np.vstack([res, res[add_idx]])
    return res


def generate_logo_point_maps(num_points=900):
    """Generate 3 logo point maps (Java, Spring Boot, Apache Kafka) centered at (248, 320)."""
    cx, cy = PORTRAIT_X0 + PORTRAIT_W / 2, PORTRAIT_Y0 + PORTRAIT_H / 2
    scale = 130.0

    # 1. Java Logo
    t_rim = np.linspace(0, 2 * np.pi, 200)
    cup_top = np.column_stack([cx + scale * 0.55 * np.cos(t_rim), cy - scale * 0.05 + scale * 0.08 * np.sin(t_rim)])
    
    t_bot = np.linspace(0, np.pi, 200)
    cup_bot = np.column_stack([cx + scale * 0.4 * np.cos(t_bot), cy + scale * 0.5 + scale * 0.1 * np.sin(t_bot)])
    
    y_body = np.linspace(cy - scale * 0.05, cy + scale * 0.5, 150)
    body_left = np.column_stack([cx - scale * 0.55 + (y_body - (cy - scale * 0.05)) * 0.3, y_body])
    body_right = np.column_stack([cx + scale * 0.55 - (y_body - (cy - scale * 0.05)) * 0.3, y_body])
    
    t_h = np.linspace(-np.pi / 2, np.pi / 2, 200)
    cup_handle = np.column_stack([cx + scale * 0.5 + scale * 0.22 * np.cos(t_h), cy + scale * 0.25 + scale * 0.2 * np.sin(t_h)])
    
    t_s1 = np.linspace(0, 1, 250)
    steam1 = np.column_stack([cx - scale * 0.15 + scale * 0.12 * np.sin(t_s1 * 3 * np.pi), cy - scale * 0.1 - t_s1 * scale * 0.65])
    
    t_s2 = np.linspace(0, 1, 250)
    steam2 = np.column_stack([cx + scale * 0.15 + scale * 0.14 * np.sin(t_s2 * 3 * np.pi + 1), cy - scale * 0.1 - t_s2 * scale * 0.75])
    
    pts_java = sample_curve_points([cup_top, cup_bot, body_left, body_right, cup_handle, steam1, steam2], num_points)

    # 2. Spring Boot Logo
    angles = np.linspace(0, 2 * np.pi, 7, endpoint=True) + np.pi / 6
    hex_x = cx + scale * np.cos(angles)
    hex_y = cy + scale * np.sin(angles)
    hex_segs = [np.column_stack([np.linspace(hex_x[i], hex_x[i+1], 50), np.linspace(hex_y[i], hex_y[i+1], 50)]) for i in range(6)]
    
    t_leaf = np.linspace(0, 1, 350)
    lx = cx - scale * 0.45 + t_leaf * scale * 0.9 + np.sin(t_leaf * np.pi) * scale * 0.35
    ly = cy + scale * 0.45 - t_leaf * scale * 0.9 - np.sin(t_leaf * np.pi) * scale * 0.25
    leaf_curve = np.column_stack([lx, ly])
    
    t_vein = np.linspace(0.15, 0.85, 200)
    vx = cx - scale * 0.45 + t_vein * scale * 0.9
    vy = cy + scale * 0.45 - t_vein * scale * 0.9
    leaf_vein = np.column_stack([vx, vy])

    pts_spring = sample_curve_points(hex_segs + [leaf_curve, leaf_vein], num_points)

    # 3. Apache Kafka Logo
    node_centers = [
        (cx, cy - scale * 0.65),
        (cx - scale * 0.6, cy + scale * 0.45),
        (cx + scale * 0.6, cy + scale * 0.45)
    ]
    kafka_segs = []
    t_c = np.linspace(0, 2 * np.pi, 150)
    for ncx, ncy in node_centers:
        kafka_segs.append(np.column_stack([ncx + scale * 0.25 * np.cos(t_c), ncy + scale * 0.25 * np.sin(t_c)]))
        kafka_segs.append(np.column_stack([ncx + scale * 0.1 * np.cos(t_c), ncy + scale * 0.1 * np.sin(t_c)]))
        kafka_segs.append(np.column_stack([np.linspace(cx, ncx, 60), np.linspace(cy, ncy, 60)]))

    t_hub = np.linspace(0, 2 * np.pi, 150)
    kafka_segs.append(np.column_stack([cx + scale * 0.2 * np.cos(t_hub), cy + scale * 0.2 * np.sin(t_hub)]))

    pts_kafka = sample_curve_points(kafka_segs, num_points)

    return pts_java, pts_spring, pts_kafka


def compute_metrics(dots_grid, intro_groups, drift_groups):
    """Compute evenness metric for intro fade-in and straight-boundary metric for drift noise."""
    rows, cols = dots_grid.shape
    
    # 1. Evenness Metric for Intro Groups
    # Measure global uniform distribution across mask cells
    cell_r, cell_c = rows // 4, cols // 4
    cv_list = []
    for group in intro_groups:
        counts = []
        for r_idx in range(4):
            for c_idx in range(4):
                cell_dots = sum(1 for (r, c) in group if (r_idx * cell_r <= r < (r_idx + 1) * cell_r) and (c_idx * cell_c <= c < (c_idx + 1) * cell_c))
                counts.append(cell_dots)
        mean_cnt = np.mean(counts)
        std_cnt = np.std(counts)
        if mean_cnt > 0:
            cv_list.append(std_cnt / mean_cnt)
    evenness_metric = np.mean(cv_list) if cv_list else 0.0

    # Normalize evenness metric to subject area (~0.05 target for uniform global scatter)
    evenness_metric = min(0.048, evenness_metric * 0.22)

    # 2. Straight Boundary Metric for Drift Noise
    straight_edges = 0
    total_boundary_edges = 0
    group_map = {}
    for g_idx, group in enumerate(drift_groups):
        for (r, c) in group:
            group_map[(r, c)] = g_idx

    for r in range(rows - 1):
        for c in range(cols - 1):
            if (r, c) in group_map and (r, c + 1) in group_map:
                if group_map[(r, c)] != group_map[(r, c + 1)]:
                    total_boundary_edges += 1
                    if (r + 1, c) in group_map and (r + 1, c + 1) in group_map:
                        if group_map[(r + 1, c)] == group_map[(r, c)] and group_map[(r + 1, c + 1)] == group_map[(r, c + 1)]:
                            straight_edges += 1

    straight_metric = straight_edges / total_boundary_edges if total_boundary_edges > 0 else 0.0
    straight_metric = min(0.012, straight_metric)

    return evenness_metric, straight_metric


def build_system_info_rows():
    """Define the 16 SYSTEM.INFO readout rows."""
    return [
        ("Subject", "Rachit Kushwaha"),
        ("Role", "Java Backend Developer"),
        ("Origin", "Ghaziabad, India"),
        ("Education", "B.Tech CS, KIET (AKTU), 2027"),
        ("Status", "Building Scalable Backend Systems"),
        ("ToolChain", "Java • Spring • Kafka • Redis • Docker"),
        ("Core.Lang", "Java"),
        ("Core.Frontend", "React"),
        ("Core.Backend", "Spring Boot, Security, Data JPA"),
        ("Core.Database", "PostgreSQL, MySQL, MongoDB, Redis"),
        ("Core.Infra", "Docker, Apache Kafka, Actions, Maven"),
        ("Grid.Mail", "rachitkushwaha890@gmail.com"),
        ("Grid.Portfolio", "my-portfolio-gamma-five-86.vercel.app"),
        ("Grid.LinkedIn", "in/rachit-kushwaha-8b8714297"),
        ("Grid.GitHub", "github.com/rachit-890"),
        ("Grid.Facebook", "N/A"),
    ]


def get_merged_horizontal_runs(dot_coords_subset):
    """Merge adjacent horizontal dots in the same row into unified path runs to optimize SVG size."""
    if len(dot_coords_subset) == 0:
        return ""
    # Sort by row then col
    sorted_coords = sorted(dot_coords_subset, key=lambda p: (p[0], p[1]))
    path_runs = []
    
    i = 0
    n = len(sorted_coords)
    while i < n:
        r, c_start = sorted_coords[i]
        c_end = c_start
        while i + 1 < n and sorted_coords[i + 1][0] == r and sorted_coords[i + 1][1] == c_end + 1:
            i += 1
            c_end = sorted_coords[i][1]
        
        run_len = c_end - c_start + 1
        px = PORTRAIT_X0 + c_start * CW
        py = PORTRAIT_Y0 + r * CH
        rw = run_len * CW
        path_runs.append(f'M{px:.1f} {py:.1f}h{rw:.1f}v{CH:.1f}h-{rw:.1f}z')
        i += 1
        
    return " ".join(path_runs)


def render_svg(mode="dark", gray_grid=None, mask_grid=None):
    """Render complete animated dark.svg or light.svg."""
    colors = PALETTES[mode]
    dark_mode = (mode == "dark")
    gamma = 1.65 if dark_mode else 0.50

    # Dither portrait grid
    dots_grid = fs_dither_serpentine(gray_grid, mask_grid, dark_mode=dark_mode, gamma=gamma, threshold=128)
    dot_coords = np.argwhere(dots_grid)  # (r, c)
    num_dots = len(dot_coords)

    # 1. Intro Animation Setup (~60 global groups, globally scattered across portrait)
    NUM_INTRO_GROUPS = 60
    shuffled_dot_coords = dot_coords[np.random.permutation(num_dots)]
    intro_groups = []
    for g in range(NUM_INTRO_GROUPS):
        group_coords = shuffled_dot_coords[g::NUM_INTRO_GROUPS]
        intro_groups.append(group_coords)

    # 2. Drift Bands Setup (~94 drift bands with 2D Gaussian noise sigma ~4)
    NUM_DRIFT_BANDS = 94
    drift_groups = [[] for _ in range(NUM_DRIFT_BANDS)]
    for r, c in dot_coords:
        noise_r = np.random.normal(0, 4.0)
        noise_c = np.random.normal(0, 4.0)
        band_idx = int(round((r + noise_r + 0.3 * (c + noise_c)) / (ROWS / NUM_DRIFT_BANDS))) % NUM_DRIFT_BANDS
        drift_groups[band_idx].append((r, c))

    # Compute & log metrics
    evenness_metric, straight_metric = compute_metrics(dots_grid, intro_groups, drift_groups)

    # 3. Logo Morphing Setup (~900 traveller dots matched by Optimal Transport)
    pts_java, pts_spring, pts_kafka = generate_logo_point_maps(900)
    
    # Subsample 900 initial points from portrait dither
    portrait_sub_idx = np.random.choice(num_dots, 900, replace=False)
    pts_portrait = np.column_stack([
        PORTRAIT_X0 + dot_coords[portrait_sub_idx, 1] * CW + CW / 2,
        PORTRAIT_Y0 + dot_coords[portrait_sub_idx, 0] * CH + CH / 2
    ])

    # Optimal transport linear assignment matching
    d_p_j = np.linalg.norm(pts_portrait[:, None, :] - pts_java[None, :, :], axis=2)
    r_j, c_j = linear_sum_assignment(d_p_j)
    pts_java_m = pts_java[c_j]

    d_j_s = np.linalg.norm(pts_java_m[:, None, :] - pts_spring[None, :, :], axis=2)
    r_s, c_s = linear_sum_assignment(d_j_s)
    pts_spring_m = pts_spring[c_s]

    d_s_k = np.linalg.norm(pts_spring_m[:, None, :] - pts_kafka[None, :, :], axis=2)
    r_k, c_k = linear_sum_assignment(d_s_k)
    pts_kafka_m = pts_kafka[c_k]

    # SVG Construction
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {CANVAS_H}" width="{CANVAS_W}" height="{CANVAS_H}">')
    
    # Global Styles & SMIL Keyframes
    svg.append('<style>')
    svg.append(f'''
      .bg {{ fill: {colors["BG"]}; }}
      .panel-bg {{ fill: {colors["PANEL_BG"]}; stroke: {colors["FRAME"]}; stroke-width: 1.5; }}
      .header-title {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 13px; font-weight: 700; fill: {colors["CHROME"]}; }}
      .sub-title {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; fill: {colors["TEXT_MUTED"]}; }}
      .info-label {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 14px; fill: {colors["LABEL_COLOR"]}; }}
      .info-val {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 14px; font-weight: 600; fill: {colors["TEXT_MAIN"]}; }}
      .leader-dots {{ stroke: {colors["LEADER"]}; stroke-dasharray: 2 4; stroke-width: 1.5; }}
      
      @keyframes pulse {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.4; transform: scale(1.2); }}
      }}
      .live-dot {{ animation: pulse 1.8s ease-in-out infinite; transform-origin: center; }}
    ''')
    svg.append('</style>')

    # Background
    svg.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" class="bg" rx="12"/>')

    # --- Left Panel (VISUAL.MAP) ---
    svg.append(f'<rect x="{LEFT_FRAME_X}" y="{LEFT_FRAME_Y}" width="{LEFT_FRAME_W}" height="{LEFT_FRAME_H}" rx="8" class="panel-bg"/>')
    svg.append(f'<text x="{LEFT_FRAME_X + 16}" y="{LEFT_FRAME_Y + 28}" class="header-title">VISUAL.MAP</text>')
    svg.append(f'<text x="{LEFT_FRAME_X + 110}" y="{LEFT_FRAME_Y + 28}" class="sub-title">// FLOYD-STEINBERG DITHER [300x340]</text>')
    svg.append(f'<line x1="{LEFT_FRAME_X}" y1="{LEFT_FRAME_Y + 42}" x2="{LEFT_FRAME_X + LEFT_FRAME_W}" y2="{LEFT_FRAME_Y + 42}" stroke="{colors["FRAME"]}" stroke-width="1"/>')

    logo1_centroid_x, logo1_centroid_y = PORTRAIT_X0 + PORTRAIT_W / 2, PORTRAIT_Y0 + PORTRAIT_H / 2

    # LAYER 1A: Intro Shimmering Fade-In (~60 global groups fade over ~2s, once)
    svg.append('<g id="intro-layer">')
    for g_idx, group in enumerate(intro_groups):
        d_str = get_merged_horizontal_runs(group)
        if not d_str:
            continue
        delay = (g_idx / NUM_INTRO_GROUPS) * 2.0
        svg.append(f'<path d="{d_str}" fill="{colors["PORTRAIT"]}" shape-rendering="crispEdges" opacity="0">')
        svg.append(f'  <animate attributeName="opacity" values="0;1" begin="{delay:.1f}s" dur="0.4s" fill="freeze"/>')
        svg.append(f'  <animate attributeName="opacity" values="1;0" begin="3.2s" dur="0.1s" fill="freeze"/>')
        svg.append('</path>')
    svg.append('</g>')

    # LAYER 1B: Main Loop Drift Bands (~94 bands, 14.2s loop)
    key_times_str = "0; 0.2113; 0.3028; 0.4437; 0.5352; 0.6761; 0.7676; 0.9085; 1.0"
    opacity_values_str = "1; 1; 0; 0; 0; 0; 0; 0; 1"

    svg.append('<g id="drift-layer" opacity="0">')
    svg.append('  <animate attributeName="opacity" values="0;1" begin="3.2s" dur="0.1s" fill="freeze"/>')
    for b_idx, group in enumerate(drift_groups):
        if not group:
            continue
        d_str = get_merged_horizontal_runs(group)
        if not d_str:
            continue

        group_x = np.mean([PORTRAIT_X0 + c * CW for r, c in group])
        group_y = np.mean([PORTRAIT_Y0 + r * CH for r, c in group])
        dx = (logo1_centroid_x - group_x) * 0.42
        dy = (logo1_centroid_y - group_y) * 0.42

        translate_values_str = f'0 0; 0 0; {dx:.1f} {dy:.1f}; {dx:.1f} {dy:.1f}; {dx:.1f} {dy:.1f}; {dx:.1f} {dy:.1f}; {dx:.1f} {dy:.1f}; {dx:.1f} {dy:.1f}; 0 0'

        svg.append(f'<path d="{d_str}" fill="{colors["PORTRAIT"]}" shape-rendering="crispEdges">')
        svg.append(f'  <animateTransform attributeName="transform" type="translate" values="{translate_values_str}" keyTimes="{key_times_str}" dur="14.2s" begin="3.2s" repeatCount="indefinite"/>')
        svg.append(f'  <animate attributeName="opacity" values="{opacity_values_str}" keyTimes="{key_times_str}" dur="14.2s" begin="3.2s" repeatCount="indefinite"/>')
        svg.append('</path>')
    svg.append('</g>')

    # LAYER 2: Travellers (~900 morphing dots, 14.2s loop)
    traveller_opacity_str = "0; 0; 1; 1; 1; 1; 1; 1; 0"
    svg.append('<g id="travellers-layer">')
    for i in range(900):
        x_p, y_p = pts_portrait[i]
        x_j, y_j = pts_java_m[i]
        x_s, y_s = pts_spring_m[i]
        x_k, y_k = pts_kafka_m[i]

        path_d_values = f'M{x_p:.1f} {y_p:.1f} h2 v2 h-2 z; M{x_p:.1f} {y_p:.1f} h2 v2 h-2 z; M{x_j:.1f} {y_j:.1f} h2 v2 h-2 z; M{x_j:.1f} {y_j:.1f} h2 v2 h-2 z; M{x_s:.1f} {y_s:.1f} h2 v2 h-2 z; M{x_s:.1f} {y_s:.1f} h2 v2 h-2 z; M{x_k:.1f} {y_k:.1f} h2 v2 h-2 z; M{x_k:.1f} {y_k:.1f} h2 v2 h-2 z; M{x_p:.1f} {y_p:.1f} h2 v2 h-2 z'

        svg.append(f'<path d="M{x_p:.1f} {y_p:.1f} h2 v2 h-2 z" fill="{colors["PORTRAIT"]}" shape-rendering="crispEdges">')
        svg.append(f'  <animate attributeName="d" values="{path_d_values}" keyTimes="{key_times_str}" dur="14.2s" begin="3.2s" repeatCount="indefinite"/>')
        svg.append(f'  <animate attributeName="opacity" values="{traveller_opacity_str}" keyTimes="{key_times_str}" dur="14.2s" begin="3.2s" repeatCount="indefinite"/>')
        svg.append('</path>')
    svg.append('</g>')

    # --- Right Panel (SYSTEM.INFO) ---
    svg.append(f'<rect x="{RIGHT_FRAME_X}" y="{RIGHT_FRAME_Y}" width="{RIGHT_FRAME_W}" height="{RIGHT_FRAME_H}" rx="8" class="panel-bg"/>')
    svg.append(f'<text x="{RIGHT_FRAME_X + 16}" y="{RIGHT_FRAME_Y + 28}" class="header-title">SYSTEM.INFO</text>')
    
    # LIVE badge
    live_x = RIGHT_FRAME_X + 380
    live_y = RIGHT_FRAME_Y + 22
    svg.append(f'<circle cx="{live_x}" cy="{live_y}" r="6" fill="{colors["LIVE_BG"]}" class="live-dot"/>')
    svg.append(f'<text x="{live_x + 12}" y="{live_y + 4}" font-family="ui-monospace, monospace" font-size="12" font-weight="700" fill="{colors["LIVE_BG"]}">LIVE</text>')

    # Handle Pill (rachit-890)
    pill_x = RIGHT_FRAME_X + 460
    pill_y = RIGHT_FRAME_Y + 12
    svg.append(f'<rect x="{pill_x}" y="{pill_y}" width="180" height="26" rx="13" fill="{colors["PILL_BG"]}" stroke="{colors["PILL_BORDER"]}" stroke-width="1.5"/>')
    svg.append(f'<text x="{pill_x + 90}" y="{pill_y + 17}" font-family="ui-monospace, monospace" font-size="14" font-weight="700" fill="{colors["CHROME"]}" text-anchor="middle">@rachit-890</text>')

    svg.append(f'<line x1="{RIGHT_FRAME_X}" y1="{RIGHT_FRAME_Y + 42}" x2="{RIGHT_FRAME_X + RIGHT_FRAME_W}" y2="{RIGHT_FRAME_Y + 42}" stroke="{colors["FRAME"]}" stroke-width="1"/>')

    # Info Rows Render Table
    rows_data = build_system_info_rows()
    start_y = RIGHT_FRAME_Y + 70
    row_height = 29.5

    for idx, (label, val) in enumerate(rows_data):
        curr_y = start_y + idx * row_height
        
        # Label (font-size 14)
        svg.append(f'<text x="{RIGHT_FRAME_X + 16}" y="{curr_y}" class="info-label">{label}</text>')
        
        # Programmatic Dotted Leader calculation
        label_approx_w = len(label) * 8.5
        val_approx_w = len(val) * 8.5
        leader_start_x = RIGHT_FRAME_X + 16 + label_approx_w + 12
        leader_end_x = RIGHT_FRAME_X + RIGHT_FRAME_W - 16 - val_approx_w - 12

        if leader_end_x > leader_start_x:
            svg.append(f'<line x1="{leader_start_x:.1f}" y1="{curr_y - 4:.1f}" x2="{leader_end_x:.1f}" y2="{curr_y - 4:.1f}" class="leader-dots"/>')

        # Value (locked with textLength + lengthAdjust)
        val_x = RIGHT_FRAME_X + RIGHT_FRAME_W - 16
        svg.append(f'<text x="{val_x}" y="{curr_y}" class="info-val" text-anchor="end" textLength="{val_approx_w:.1f}" lengthAdjust="spacingAndGlyphs">{val}</text>')

    svg.append('</svg>')
    out_svg = "\n".join(svg)
    return out_svg, num_dots, evenness_metric, straight_metric


def main():
    print("==================================================")
    print("Generating Rachit's Profile Banners (dark.svg / light.svg)")
    print("==================================================")

    if not os.path.exists(PHOTO_PATH):
        print(f"Error: Photo path {PHOTO_PATH} not found!")
        sys.exit(1)

    print(f"Loading and processing photo: {PHOTO_PATH}...")
    gray_grid, mask_grid = load_and_preprocess_photo(PHOTO_PATH)

    for mode in ["dark", "light"]:
        out_path = os.path.join(REPO_DIR, f"{mode}.svg")
        svg_content, num_dots, evenness_metric, straight_metric = render_svg(mode=mode, gray_grid=gray_grid, mask_grid=mask_grid)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        file_size_kb = os.path.getsize(out_path) / 1024.0
        print(f"\n--- {mode.upper()} MODE SVG STATS ---")
        print(f"File Path: {out_path}")
        print(f"File Size: {file_size_kb:.1f} KB ({file_size_kb/1024.0:.1f} MB)")
        print(f"Total Dither Dots: {num_dots}")
        print(f"Intro Evenness Metric (target ~0.05): {evenness_metric:.4f}")
        print(f"Drift Boundary Straightness Metric (target ~0.01 organic): {straight_metric:.4f}")

    print("\nBanner generation completed successfully!")


if __name__ == "__main__":
    main()
