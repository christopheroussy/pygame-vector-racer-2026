#!/usr/bin/env python3
import os
os.environ['SDL_RENDER_SCALE_QUALITY'] = '2' # Blending, blur.
#os.environ['SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR'] = '1'

import pygame
import math
import random
import sys

vec2 = pygame.Vector2
draw_poly = pygame.draw.polygon
draw_line = pygame.draw.line
draw_circle = pygame.draw.circle

# --- CONFIGURATION ---
INTERNAL_RES_W = 512
INTERNAL_RES_H = 288
HALF_WIDTH = INTERNAL_RES_W / 2
HALF_HEIGHT = INTERNAL_RES_H / 2

FULLSCREEN_MODE = True

MOTION_BLUR_EFFECT = True

pygame.init()
pygame.mixer.init()
pygame.joystick.init()

# --- PRE-CALCULATED MATH (LUT) ---
ALT_RES = 3600
SIN_LUT_DEG = [math.sin(math.radians(i / 10.0)) for i in range(ALT_RES)]
COS_LUT_DEG = [math.cos(math.radians(i / 10.0)) for i in range(ALT_RES)]
def get_sin_deg(deg):
    return SIN_LUT_DEG[int(deg * 10) % ALT_RES]
def get_cos_deg(deg):
    return COS_LUT_DEG[int(deg * 10) % ALT_RES]
    
SIN_LUT_RAD = [math.sin(i * (2 * math.pi / ALT_RES)) for i in range(ALT_RES)]
COS_LUT_RAD = [math.cos(i * (2 * math.pi / ALT_RES)) for i in range(ALT_RES)]
def get_sin_rad(rad):
    # Normalize angle to [0, 2PI), convert to index, and wrap using modulo
    idx = int((rad % (2 * math.pi)) * (ALT_RES / (2 * math.pi)))
    return SIN_LUT_RAD[idx % ALT_RES]

def get_cos_rad(rad):
    idx = int((rad % (2 * math.pi)) * (ALT_RES / (2 * math.pi)))
    return COS_LUT_RAD[idx % ALT_RES]

# Constants
CELL_SIZE = 4096; 
MID = CELL_SIZE // 2; 
ROAD_W = 1000 # Width of roads.

MAX_SPEED = 135.0; 
BOOST_SPEED = 250.0; 
ULTRA_LIMIT = 500.0

BOOST_ACCEL = 4.8; 
GRAVITY = 0.75; 

TURN_SPEED = 2.0
FOV = 280; 
CAMERA_HEIGHT = 160; 
CAM_DIST = 350; 
NEAR_PLANE = 15.0
COLLISION_ALT_THRESHOLD = 500.0; 
VOID_RESET_THRESHOLD = 5.0
INSET = 150; 
WALL_HEIGHT = 2500

SHIP_RADIUS = 60; 

# Pre-calculated values for collision
SHIP_RADIUS_SQ = SHIP_RADIUS ** 2

# Manhattan filter: A circle is always inside a Manhattan diamond of radius 2R
MANHATTAN_FILTER = SHIP_RADIUS * 2

# Culling
CULL_MARGIN = 2500
NEAR_CULL_DIST_SQ = (CELL_SIZE * 1.5) ** 2

# Colors.
BLACK = (0, 0, 0);
CYAN = (0, 255, 255);
DARK_CYAN = (0, 80, 120)
WHITE = (255, 255, 255);
ORANGE = (255, 180, 0)
DECO_YELLOW = (200, 180, 0);
RAMP_PURPLE = (180, 0, 255)
BOOST_PURPLE = (100, 0, 150);
FLOOR_GREY = (30, 30, 40)
SHIP_BODY = (60, 65, 85);
PYRAMID_COL = (120, 130, 150); 
CHECKPOINT_GOLD = (255, 215, 0)
BLOCK_GREY_LIGHT = (100, 105, 115); 
BLOCK_GREY_DARK = (70, 75, 85)
GREEN = (0, 255, 0)

def get_username():
    """
    Return the current username. Fallback to "unknown" if getlogin() fails.
    """
    username = "Player1"
    try:
        username = os.getlogin()
    except OSError:
        # Fallback to os.environ.get('USERNAME') if getlogin() fails (common in Windows)
        username = os.environ.get('USERNAME', "Player1")
    return username
    
def get_highscore_key(track_name, username):
    """
    Generates a consistent, unique key for highscores.
    Uses underscore as a separator and strips whitespace.
    """
    return f"{track_name.strip()}|{username.strip()}"
    
def save_highscore(track_name, score):
    username = get_username()
    scores = load_highscores()
    key = get_highscore_key(track_name, username)
    scores[key] = score
    with open("highscores.txt", "w") as f:
        for key, value in scores.items():
            f.write(key + "=" + str(value) + "\n")
    return scores

def load_highscores():
    try:
        with open("highscores.txt", "r") as f:
            lines = f.readlines()
            scores = {}
            for line in lines:
                key, value = line.strip().split("=")
                scores[key] = int(value)
            return scores
    except FileNotFoundError:
        return {}

# ====================== BIG CURVE SYSTEM ======================
def normalize_big_tiles(track_map):
    if not track_map: return track_map
    h, w = len(track_map), len(track_map[0])

    for gy in range(h - 1):
        for gx in range(w - 1):
            c = track_map[gy][gx]
            if c not in ('5', '6', '7', '8'): continue

            # Check for a full 2x2 block of the same character
            if (track_map[gy][gx+1] == c and
                track_map[gy+1][gx] == c and
                track_map[gy+1][gx+1] == c):

                track_map[gy][gx]     = c + 'a' # Top-Left quadrant
                track_map[gy][gx+1]   = c + 'b' # Top-Right quadrant
                track_map[gy+1][gx]   = c + 'c' # Bottom-Left quadrant
                track_map[gy+1][gx+1] = c + 'd' # Bottom-Right quadrant
    return track_map

def is_big_curve_tile(tile):
    return len(tile) == 2 and tile[0] in '5678' and tile[1] in 'abcd'

def get_dist(point, a, b):
    """
    Distance from point to segment AB and the closest point on AB.
    - point, a, b are vec2 (world coords).
    Returns: (dist, closest_point)
    """
    # vector from A to B and A to P
    ab = b - a
    ap = point - a
    ab_len2 = ab.x * ab.x + ab.y * ab.y
    if ab_len2 == 0.0:
        # A and B are the same point
        closest = a
        d = (point - a).length()
        return d, closest
    # projection t of P onto AB, clamped to [0,1]
    t = (ap.x * ab.x + ap.y * ab.y) / ab_len2
    if t < 0.0:
        closest = a
    elif t > 1.0:
        closest = b
    else:
        closest = a + ab * t
    return (point - closest).length(), closest
    
def get_dist_sq(point, a, b):
    """
    Squared distance version. Returns (dist_sq, closest_point).
    Use when comparing to squared thresholds to avoid sqrt.
    """
    ab = b - a
    ap = point - a
    ab_len2 = ab.x * ab.x + ab.y * ab.y
    if ab_len2 == 0.0:
        closest = a
        d2 = (point - a).length_squared()
        return d2, closest
    t = (ap.x * ab.x + ap.y * ab.y) / ab_len2
    if t < 0.0:
        closest = a
    elif t > 1.0:
        closest = b
    else:
        closest = a + ab * t
    return (point - closest).length_squared(), closest

# Initialize Joysticks Safely
joysticks = []
for i in range(pygame.joystick.get_count()):
    try:
        j = pygame.joystick.Joystick(i)
        j.init()
        joysticks.append(j)
    except pygame.error:
        pass

pygame.mouse.set_visible(False)
flags = pygame.SCALED | pygame.DOUBLEBUF
if FULLSCREEN_MODE:
    flags |= pygame.FULLSCREEN
screen = pygame.display.set_mode((INTERNAL_RES_W, INTERNAL_RES_H), flags, vsync=1)
pygame.display.set_caption("PyGame: Vector Racer 2026")
clock = pygame.time.Clock()
hud_font = pygame.font.SysFont("Courier", 18, bold=True)
small_font = pygame.font.SysFont("Courier", 14, bold=True)

# --- UTILS ---
def play_sound(sounds, name):
    if name in sounds:
        sounds[name].stop()
        sounds[name].play()
        
def load_all_sounds():
    sounds = {}
    sounds_path = "sounds"
    if os.path.exists(sounds_path):
        for f in os.listdir(sounds_path):
            if f.endswith(".ogg"):
                name = os.path.splitext(f)[0]
                sounds[name] = pygame.mixer.Sound(os.path.join(sounds_path, f))
    return sounds
    
def get_level_list():
    if not os.path.exists("levels"): os.makedirs("levels")
    files = [f for f in os.listdir("levels") if f.endswith(".txt")]
    files.sort(); return files
    
def load_track_file(filename):
    path = os.path.join("levels", filename)
    with open(path, "r") as f:
        raw_lines = [line.rstrip('\n').rstrip('\r') for line in f.readlines()]
        while raw_lines and not raw_lines[-1].strip():
            raw_lines.pop()
        if not raw_lines:
            return []
        max_w = max(len(line) for line in raw_lines)
        # return list of lists so rows are mutable
        return [list(line.ljust(max_w)) for line in raw_lines]
        
def get_track_data(track_map, tile_type):
    m, w, s = MID, ROAD_W, CELL_SIZE
    walls, arches = [], []
    if tile_type in '-=rc_':
        walls = [(vec2(-100, m-w), vec2(s+100, m-w)),
                 (vec2(-100, m+w), vec2(s+100, m+w))]
        if tile_type in '-=':
            for ox in [s*0.25, s*0.75]: arches.append((vec2(ox, m-w), vec2(ox, m+w)))
        elif tile_type == 'c': arches.append((vec2(s*0.5, m-w), vec2(s*0.5, m+w)))
    elif tile_type in '|tTB':
        # Vertical walls, going south/north
        walls = [(vec2(m-w, -100), vec2(m-w, s+100)), (vec2(m+w, -100), vec2(m+w, s+100))]
        if tile_type not in 'tTB':
            for i in range(3): arches.append((vec2(m-w, s*i/3 + s/6), vec2(m+w, s*i/3 + s/6)))
    elif tile_type == '+': 
        # Cross roads.
        walls = [
            # Left horizontal wall (split)
            (vec2(-100, m-w), vec2(m-w, m-w)),
            (vec2(-100, m+w), vec2(m-w, m+w)),

            # Right horizontal wall (split)
            (vec2(m+w, m-w), vec2(s+100, m-w)),
            (vec2(m+w, m+w), vec2(s+100, m+w)),

            # Top vertical wall (split)
            (vec2(m-w, -100), vec2(m-w, m-w)),
            (vec2(m+w, -100), vec2(m+w, m-w)),

            # Bottom vertical wall (split)
            (vec2(m-w, m+w), vec2(m-w, s+100)),
            (vec2(m+w, m+w), vec2(m+w, s+100)),
        ]

    elif tile_type == '1': add_arc(walls, vec2(s, s), 180, 270)
    elif tile_type == '2': add_arc(walls, vec2(0, s), 270, 360)
    elif tile_type == '3': add_arc(walls, vec2(0, 0), 0, 90)
    elif tile_type == '4': add_arc(walls, vec2(s, 0), 90, 180)
   
    # === BIG CURVE QUADRANTS ===
    elif is_big_curve_tile(tile_type):
        base = tile_type[0]  # '5','6','7','8'
        quad = tile_type[1]  # 'a','b','c','d'
        walls = build_big_curve_walls(base, quad, s, w)
   
    return {"walls": walls, "arches": arches}

# Small arcs, small curves.
def add_arc(walls, pivot, start_angle, end_angle):
    segments = 24
    for i in range(segments):
        a1 = start_angle + (end_angle - start_angle) * (i / segments)
        a2 = start_angle + (end_angle - start_angle) * ((i + 1) / segments)
        c1, s1 = get_cos_deg(a1), get_sin_deg(a1)
        c2, s2 = get_cos_deg(a2), get_sin_deg(a2)
        
        # Use ROAD_W to define the thickness relative to the pivot/centerline
        # For small curves, the centerline is usually MID
        for r in (MID + ROAD_W, MID - ROAD_W):
            walls.append((pivot + vec2(c1, s1) * r, pivot + vec2(c2, s2) * r))

# Big arcs, big curves.
def build_big_curve_walls(base_type, quadrant, cell_size=CELL_SIZE, road_w=ROAD_W):
    m, w, s = MID, ROAD_W, CELL_SIZE
    
    # R_center is the distance from the pivot to the middle of the road
    # To align with straight roads, R_center must be (s + m)
    R_center = s + m 
    R_inner = R_center - road_w
    R_outer = R_center + road_w
    
    # 1. Pivot Points (The "Center" of the circle arc)
    # Relative to the 2x2 block's top-left (0,0)
    centers = {
        '5': (2 * s, 2 * s), # Pivot: Bottom-Right
        '6': (0, 2 * s),     # Pivot: Bottom-Left
        '7': (0, 0),         # Pivot: Top-Left     (Vertical flip of 6)
        '8': (2 * s, 0)      # Pivot: Top-Right    (Vertical flip of 5)
    }
    
    # 2. Angle Mapping for Pygame 
    # (0=Right, 90=Down, 180=Left, 270=Up)
    base_angles = {
        '5': (180, 270), # Arcs from Left to Up
        '6': (270, 360), # Arcs from Up to Right
        '7': (0, 90),    # Arcs from Right to Down (Flipped 6)
        '8': (90, 180)   # Arcs from Down to Left  (Flipped 5)
    }
    
    # 3. Quadrant logic (don't change this, it's standard grid math)
    quad_pos = {
        'a': (0, 0), 'b': (s, 0),
        'c': (0, s), 'd': (s, s)
    }
    
    cx, cy = centers[base_type]
    qx, qy = quad_pos[quadrant]
    
    # Calculate pivot relative to the specific 1x1 tile's origin
    pivot_x, pivot_y = cx - qx, cy - qy
    start_deg, end_deg = base_angles[base_type]

    walls = []
    segments = 24
    for i in range(segments):
        t1, t2 = i / segments, (i + 1) / segments
        a1 = math.radians(start_deg + (end_deg - start_deg) * t1)
        a2 = math.radians(start_deg + (end_deg - start_deg) * t2)

        for r in (R_inner, R_outer):
            p1 = vec2(pivot_x + get_cos_rad(a1) * r, pivot_y + get_sin_rad(a1) * r)
            p2 = vec2(pivot_x + get_cos_rad(a2) * r, pivot_y + get_sin_rad(a2) * r)
            walls.append((p1, p2))
            
    return walls

def is_on_rotating_track(pos, track_map):
    gx, gy = int(pos.x // CELL_SIZE), int(pos.y // CELL_SIZE)
    h = len(track_map); w = len(track_map[0])
    if not (0 <= gy < h and 0 <= gx < w):
        return False
    char = track_map[gy][gx]
    # quick accept for any non-empty, non-wall track char
    return char in ('~')

def is_on_track(pos, track_map):
    gx, gy = int(pos.x // CELL_SIZE), int(pos.y // CELL_SIZE)
    h = len(track_map); w = len(track_map[0])
    if not (0 <= gy < h and 0 <= gx < w):
        return False
    char = track_map[gy][gx]
    # quick accept for any non-empty, non-wall track char
    return char not in (' ', '0', '#', 'G', '%')
    
def get_rel_coords_opt(pos, cam_pos, cos_a, sin_a, roll_angle, height=0):
    # 1. Translate to camera-relative
    rel_x = pos.x - cam_pos.x
    rel_y = pos.y - cam_pos.y

    # 2. Yaw (Heading rotation) - transforms world to camera-local space
    rx = rel_x * sin_a + rel_y * cos_a
    rz = rel_x * cos_a - rel_y * sin_a
    ry = CAMERA_HEIGHT - height

    # 3. Roll (Rotation around the Z/Forward axis)
    if roll_angle != 0:
        cos_r = get_cos_rad(roll_angle)
        sin_r = get_sin_rad(roll_angle)
        # Rotate the X and Y coordinates on the view plane
        rx_new = rx * cos_r - ry * sin_r
        ry_new = rx * sin_r + ry * cos_r
        return rx_new, rz, ry_new

    return rx, rz, ry

    
def project_raw(rx, rz, ry_custom, bank_angle):

    # Apply tilt only (bank)
    ry = ry_custom + (rx * get_sin_rad(bank_angle))

    # Perspective
    f = FOV / max(rz, 0.1)

    # Horizontal position (NO rotation here)
    x = INTERNAL_RES_W // 2 + int(rx * f)

    # Vertical position (tilt already applied)
    y = INTERNAL_RES_H // 2 + int(ry * f)

    return (x, y), f
  
def project_opt(pos, cam_pos, cos_a, sin_a, bank_angle, roll_angle, height=0):
    rx, rz, ry = get_rel_coords_opt(pos, cam_pos, cos_a, sin_a, roll_angle, height)
    
    # Instead of 'if rz >= NEAR_PLANE else None', we clamp it:
    # This keeps the building visible until it is truly behind the camera
    visible_rz = max(rz, 0.01) 
    
    # We still want to hide things that are actually BEHIND the camera
    # to avoid "mirroring" artifacts
    if rz < 0: 
        return None
        
    return project_raw(rx, visible_rz, ry, bank_angle)


def draw_clipped_3d_line(p1_3d, p2_3d, bank_angle, roll_angle, color, width):
    rx1, rz1, ry1 = p1_3d; rx2, rz2, ry2 = p2_3d
    if rz1 < NEAR_PLANE and rz2 < NEAR_PLANE: return
    if rz1 < NEAR_PLANE or rz2 < NEAR_PLANE:
        t = (NEAR_PLANE - rz1) / (rz2 - rz1 + 1e-6)
        if rz1 < NEAR_PLANE: rx1, rz1, ry1 = rx1 + t*(rx2-rx1), NEAR_PLANE, ry1 + t*(ry2-ry1)
        else: rx2, rz2, ry2 = rx1 + t*(rx2-rx1), NEAR_PLANE, ry1 + t*(ry2-ry1)
    s1, _ = project_raw(rx1, rz1, ry1, bank_angle); 
    s2, _ = project_raw(rx2, rz2, ry2, bank_angle)
    pygame.draw.line(screen, color, s1, s2, width)

  
def draw_clipped_arch(p1_base, p2_base, cam_pos, cos_a, sin_a, bank_angle, roll_angle, color=CYAN):
    l_b = get_rel_coords_opt(p1_base, cam_pos, cos_a, sin_a, roll_angle, 0,)
    l_t = get_rel_coords_opt(p1_base, cam_pos, cos_a, sin_a, roll_angle, 250)
    r_b = get_rel_coords_opt(p2_base, cam_pos, cos_a, sin_a, roll_angle, 0)
    r_t = get_rel_coords_opt(p2_base, cam_pos, cos_a, sin_a, roll_angle, 250)
    draw_clipped_3d_line(l_b, l_t, bank_angle, roll_angle, DARK_CYAN, 2); 
    draw_clipped_3d_line(r_b, r_t, bank_angle, roll_angle, DARK_CYAN, 2)
    prev = l_t
    for i in range(1, 7):
        t = i / 6.0; b_pos = p1_base + (p2_base - p1_base) * t
        curr = get_rel_coords_opt(b_pos, cam_pos, cos_a, sin_a, roll_angle, 250 + get_sin_rad(t * math.pi) * 150)
        draw_clipped_3d_line(prev, curr, bank_angle, roll_angle, color, 2); prev = curr
    
    
def draw_ship(screen, ship_alt, ship_vel, is_boosting, bank, roll_angle):
    sx = INTERNAL_RES_W // 2
    sy = (INTERNAL_RES_H // 2 + 75) - int(ship_alt * 0.5)

    v_l = bank * 80
    sc = 1.0 + (ship_vel.length() / BOOST_SPEED)

    # Base polygon (unrotated)
    pts = [
        (sx + v_l        , sy - 8 * sc),
        (sx + v_l + 25*sc, sy + 4 * sc),
        (sx + v_l + 15*sc, sy + 15 * sc),
        (sx + v_l - 15*sc, sy + 15 * sc),
        (sx + v_l - 25*sc, sy + 4 * sc)
    ]

    # Engine core (unrotated)
    cx = sx + int(v_l)
    cy = sy + 8 + int(5 * sc)

    # --- FAST PATH: no rotation needed ---
    if roll_angle == 0 or abs(roll_angle) < 1e-6:
        rot_pts = pts
        core_pt = (cx, cy)

    else:
        # --- SLOW PATH: rotate points around (sx, sy) ---
        cos_r = get_cos_rad(roll_angle)
        sin_r = get_sin_rad(roll_angle)

        rot_pts = []
        for x, y in pts:
            dx = x - sx
            dy = y - sy
            rx = dx * cos_r - dy * sin_r
            ry = dx * sin_r + dy * cos_r
            rot_pts.append((sx + rx, sy + ry))

        # Rotate engine core
        dx = cx - sx
        dy = cy - sy
        rcx = dx * cos_r - dy * sin_r
        rcy = dx * sin_r + dy * cos_r
        core_pt = (sx + rcx, sy + rcy)

    # Draw ship body
    draw_poly(screen, SHIP_BODY, rot_pts)
    draw_poly(screen, ORANGE, rot_pts, 1)

    # Engine glow
    core_r = max(1, int(10 * (sc - 1)))
    draw_circle(screen, (0, 150, 255), core_pt, core_r)

    # Boost particles
    if is_boosting or ship_vel.length() > 100:
        draw_circle(screen, (200, 240, 255), core_pt, core_r // 2)

        # Emit particle behind the rotated core
        p_x = core_pt[0] + random.randint(-5, 5)
        p_y = core_pt[1] + random.randint(0, 5 + int(sc * 12))
        pygame.draw.circle(screen, CYAN, (int(p_x), int(p_y)), random.randint(2, 4))

            
def draw_geodesic_dome(r, c, t_off, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base=1):

    rings = 6      # Horizontal sections
    segments = 12  # Vertical ribs
    radius = CELL_SIZE // 2
    center_3d = t_off + vec2(MID, MID)
    
    # 1. Generate the grid of projected points
    # We store them in a 2D list: nodes[ring_index][segment_index]
    nodes = []
    for r in range(rings + 1):
        row = []
        # phi goes from 0° (top) to 90° (base)
        phi_deg = 90.0 * (r / rings)

        z_height = get_cos_deg(phi_deg) * radius
        ring_r   = get_sin_deg(phi_deg) * radius

        for s in range(segments):
            theta_deg = 360.0 * (s / segments)

            off_x = get_cos_deg(theta_deg) * ring_r
            off_y = get_sin_deg(theta_deg) * ring_r

            p = project_opt(
                center_3d + vec2(off_x, off_y),
                c_pos, cos_cam, sin_cam, bank, roll_angle, z_height
            )
            row.append(p[0] if p else None)
        nodes.append(row)

    # 2. Draw the Wiremesh
    for r in range(rings + 1):
        for s in range(segments):
            curr = nodes[r][s]
            if not curr: continue
            
            # Draw Longitude (Connecting to the node below)
            if r < rings:
                below = nodes[r+1][s]
                if below:
                    draw_line(screen, (0, 255, 180), curr, below, 1)
            
            # Draw Latitude (Connecting to the next node in the circle)
            nxt_s = (s + 1) % segments
            right = nodes[r][nxt_s]
            if right:
                draw_line(screen, (0, 180, 150), curr, right, 1)
        
def draw_sky_scraper(r, c, t_off, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base=1, sky_scraper_heights={}): 
    # Sky scraper grid. Mesh grid.
    # Square footprint
    CUST_INSET = INSET - CELL_SIZE / 4
    pts_base = [
        t_off + vec2(CUST_INSET, CUST_INSET),
        t_off + vec2(CELL_SIZE - CUST_INSET, CUST_INSET),
        t_off + vec2(CELL_SIZE - CUST_INSET, CELL_SIZE - CUST_INSET),
        t_off + vec2(CUST_INSET, CELL_SIZE - CUST_INSET)
    ]

    # Vertical extent
    key = str(c) + '-' + str(r)
    if key not in sky_scraper_heights:
        H_TOP = 1000 + random.randint(0, 8) * 1000
        sky_scraper_heights[key] = H_TOP
    else:
        H_TOP = sky_scraper_heights[key]

    H_BASE = -8000

    # Mesh density
    FLOORS = 14          # horizontal slices
    VERT_DIV = 4         # vertical divisions per face
    step_h = (H_TOP - H_BASE) / FLOORS

    # --- Precompute vertical face points ---
    # For each face, generate intermediate points between corners
    face_points = []
    for i in range(4):
        a = pts_base[i]
        b = pts_base[(i + 1) % 4]
        row = []
        for v in range(VERT_DIV + 1):
            t = v / VERT_DIV
            row.append(a * (1 - t) + b * t)
        face_points.append(row)

    # --- Draw vertical lines (mesh columns) ---
    for face in face_points:
        for p in face:
            p_bottom = project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, H_BASE)
            p_top    = project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, H_TOP)
            if p_bottom and p_top:
                draw_line(screen, BLOCK_GREY_DARK, p_bottom[0], p_top[0])

    # --- Draw horizontal rings (mesh rows) ---
    for f in range(FLOORS + 1):
        h = H_BASE + f * step_h

        # For each face, draw horizontal segments
        for face in face_points:
            ring = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, h) for p in face]
            ring2d = [r[0] for r in ring if r]

            # Draw horizontal lines across the face
            for i in range(len(ring2d) - 1):
                draw_line(screen, BLOCK_GREY_DARK, ring2d[i], ring2d[i + 1])
                            
def format_time(ms):
    s = ms // 1000; m = s // 60; ss = s % 60; mm = (ms % 1000) // 10
    return f"{m:02}:{ss:02}.{mm:02}"
    
def is_top_left_of_big(tile_map, gx, gy):
    c = tile_map[gy][gx]
    if c not in ('5','6','7','8'):
        return False
    w = len(tile_map[0]); h = len(tile_map)
    return gx+1 < w and gy+1 < h and \
           tile_map[gy][gx+1] == c and \
           tile_map[gy+1][gx] == c and \
           tile_map[gy+1][gx+1] == c
    
def main_menu(sounds, selected):
    level_files = get_level_list()
    if not level_files: return None
    options = [f.replace(".txt", "") for f in level_files] + ["Exit"]
    while True:
        screen.fill(BLACK)
        
        menu_title_text = "VECTOR RACER 2026: TRACK SELECT"
        title = hud_font.render(menu_title_text, True, CYAN)
        screen.blit(title, (INTERNAL_RES_W//2 - title.get_width()//2, 25))
       
        for i, opt in enumerate(options):
            color = WHITE if i == selected else (80, 80, 80)
            prefix = "> " if i == selected else " "
            text = hud_font.render(prefix + opt.upper(), True, color)
            screen.blit(text, (40, 70 + i * 25))
           
        pygame.draw.line(screen, (40, 40, 50), (INTERNAL_RES_W // 2 + 20, 70), (INTERNAL_RES_W // 2 + 20, 240), 1)
        instr_x = INTERNAL_RES_W // 2 + 40
        header = small_font.render("CONTROLS", True, DARK_CYAN)
        screen.blit(header, (instr_x, 70))
        ctrls = ["ARROWS/DPAD: NAV", "SPACE/BTN X: BOOST", "CTRL/BTN A: ROLL", "ESC/START: QUIT"]
        for i, line in enumerate(ctrls):
            instr_text = small_font.render(line, True, (140, 140, 140))
            screen.blit(instr_text, (instr_x, 95 + i * 20))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None, None, selected
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(options)
                    play_sound(sounds, "bump")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(options)
                    play_sound(sounds, "bump")
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if options[selected] == "Exit": return None, None, selected
                    return options[selected], load_track_file(level_files[selected]), selected
            if event.type == pygame.JOYHATMOTION:
                if event.value[1] == 1:
                    selected = (selected - 1) % len(options)
                    play_sound(sounds, "bump")
                elif event.value[1] == -1:
                    selected = (selected + 1) % len(options)
                    play_sound(sounds, "bump")
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button == 7 or event.button == 2:
                    if options[selected] == "Exit": return None, None, selected
                    return options[selected], load_track_file(level_files[selected]), selected
        clock.tick(30)
        
def run_game(track_name, track_map, sounds, engine_channel):

    if "engine" in sounds:
        engine_channel.play(sounds["engine"], loops=-1)
        engine_channel.set_volume(0.0)
        
    map_h, map_w = len(track_map), len(track_map[0])
    normalize_big_tiles(track_map)
    
    h_base = 1 # Base height of some objects.
    
    do_roll = False
    is_rolling = False  # Barrel roll.
    roll_angle = 0.0
    roll_angle_target = 0.0
    
    lib = {}
    for r in range(map_h):
        for c in range(map_w):
            t = track_map[r][c]
            if t not in lib and t != ' ':
                lib[t] = get_track_data(track_map, t)
    
    start_pos = vec2(0, 0)
    for r in range(map_h):
        for c in range(map_w):
            if track_map[r][c] in '=':
                start_pos = vec2(c * CELL_SIZE + MID, r * CELL_SIZE + MID)
                break
        else: continue
        break
        
    ship_pos, ship_vel = vec2(start_pos), vec2(0, 0)
    heading, bank, ship_alt, alt_vel, booster_val = 0.0, 0.0, 0.0, 0.0, 0.0
    current_lap_time, best_lap_time = 0, float('inf')
    checkpoint_cleared, race_started = False, False
    sky_scraper_heights = {}
    
    highscores = load_highscores()
    username = get_username()
    highscore_key = get_highscore_key(track_name, username)
    if highscore_key in highscores:
        best_lap_time = highscores[highscore_key]
    
    while True:
        dt = clock.tick(60)
        
        # --- DYNAMIC MOTION BLUR LOGIC ---
        current_spd = ship_vel.length()
        blur_threshold = MAX_SPEED - 5
        if MOTION_BLUR_EFFECT and current_spd > blur_threshold:
            # Scale from 0.0 to 1.0 based on how much we are over the threshold
            # I increased the divisor to 100 to make the transition smoother
            overspeed = min(1.0, (current_spd - blur_threshold) / 100.0)
            
            # ADJUST THESE NUMBERS:
            # 255 is "No Blur"
            # 120 is "Moderate Blur"
            # 200 is "Very Subtle"
            blur_alpha = 255 - int(overspeed * 180) # Changing 250 to 100 reduces the intensity
            
            fade_surf = pygame.Surface((INTERNAL_RES_W, INTERNAL_RES_H))
            fade_surf.set_alpha(blur_alpha)
            fade_surf.fill((0, 0, 0))
            screen.blit(fade_surf, (0, 0))
        else:
            screen.fill((0, 0, 0))
       
        joy = joysticks[0] if joysticks else None
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                engine_channel.stop(); return
            if joy and event.type == pygame.JOYBUTTONDOWN and event.button == 7:
                engine_channel.stop(); return
        keys = pygame.key.get_pressed()
        is_boosting = keys[pygame.K_SPACE] or (joy and joy.get_button(2)) # BUTTON X.
        do_roll = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] or (joy and joy.get_button(0)) # BUTTON A.
       
        turn_dir = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: turn_dir = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: turn_dir = 1
        if joy:
            if joy.get_hat(0)[0] != 0: turn_dir = joy.get_hat(0)[0]
            elif abs(joy.get_axis(0)) > 0.2: turn_dir = 1 if joy.get_axis(0) > 0 else -1

        turn_dir *= math.copysign(1, get_cos_rad(roll_angle))

        if not race_started and (is_boosting or turn_dir != 0): race_started = True
        
        if race_started:
            current_lap_time += dt
            turn_mult = 0.5 if ship_alt > COLLISION_ALT_THRESHOLD else 1.0
            turn_speed_now = TURN_SPEED * 0.5 if ship_alt > 2 else TURN_SPEED
            if turn_dir == -1: heading -= turn_speed_now * turn_mult; target_bank = 0.45
            elif turn_dir == 1: heading += turn_speed_now * turn_mult; target_bank = -0.45
            else: target_bank = 0
            
            if do_roll and not is_rolling and ship_alt > 2 and ship_alt < 35:
                is_rolling = True
                roll_angle = 0.0
                roll_angle_target = 2 * math.pi # Barrel roll.
                
            if is_rolling:
                # Advance the roll animation (full 360° in 2 seconds here)
                roll_duration_sec = 1
                roll_angle += roll_angle_target / roll_duration_sec * (dt / 1000.0)
                # Stop after one full rotation
                if roll_angle >= roll_angle_target:
                    if roll_angle_target % (math.pi * 2) == 0:
                        roll_angle = 0
                    is_rolling = False
            else:
                # Normal banking logic (tilt when turning)
                bank += (target_bank - bank) * 0.1
                
            cos_h, sin_h = get_cos_deg(heading), get_sin_deg(heading)
            if is_boosting:
                ship_vel.x += cos_h * BOOST_ACCEL
                ship_vel.y += sin_h * BOOST_ACCEL
                booster_val = min(1.0, booster_val + 0.1)
            else: booster_val = max(0.0, booster_val - 0.03)
           
            gx, gy = int(ship_pos.x // CELL_SIZE), int(ship_pos.y // CELL_SIZE)
           
            if 0 <= gy < map_h and 0 <= gx < map_w:
                tile = track_map[gy][gx]
                if tile == 'r' and ship_alt < 10.0: 
                    alt_vel = ship_vel.length() * 0.13
                    play_sound(sounds, "jump")
                if tile == '_' and ship_alt < 15.0:
                    ship_vel.x += cos_h * 12.0
                    ship_vel.y += sin_h * 12.0
                    booster_val = 1.5
                if tile == 'c' and not checkpoint_cleared: checkpoint_cleared = True; play_sound(sounds, "checkpoint")
                if tile == '=' and checkpoint_cleared and current_lap_time > 2000:
                    # Convert current time to your specific string format for comparison/storage
                    current_time_str = format_time(current_lap_time)
                    
                    # Check if it's a new high score
                    if current_lap_time < best_lap_time:
                        best_lap_time = current_lap_time
                        save_highscore(track_name, current_lap_time)
                        
                    current_lap_time = 0
                    checkpoint_cleared = False
                    play_sound(sounds, "bump")
    
            if is_boosting:
                # Minimal drag while boosting to allow high top speeds
                ship_vel *= 0.995
            else:
                # Reduce the gliding or sliding when player stops boosting.
                # Higher drag when coasting to "brake" the ship naturally
                # Adjust 0.98 to 0.94 for even faster stopping
                ship_vel *= 0.978
                
            # Hard stop for very low speeds to prevent the "forever crawl"
            if ship_vel.length() < 4.0:
                ship_vel = vec2(0, 0)
                
            cur_spd = ship_vel.length()
            engine_channel.set_volume(min(0.7, (cur_spd / BOOST_SPEED) * 0.7))
            limit = ULTRA_LIMIT if booster_val > 1.0 else BOOST_SPEED
            if cur_spd > limit: ship_vel.scale_to_length(cur_spd * 0.96)
            ship_alt += alt_vel; alt_vel = (alt_vel - GRAVITY) if ship_alt > 0 else 0
            if ship_alt < 0: ship_alt = 0
            vx_s, vy_s = ship_vel.x * 0.25, ship_vel.y * 0.25
            
            for _ in range(4):
                nx, ny = ship_pos.x + vx_s, ship_pos.y + vy_s
                p_pos = vec2(nx, ny)
                if ship_alt < VOID_RESET_THRESHOLD and not is_on_track(p_pos, track_map):
                    race_started = False; ship_pos = vec2(start_pos); ship_vel = vec2(0, 0)
                    heading = 0.0;
                    ship_alt = 0; 
                    current_lap_time = 0; 
                    checkpoint_cleared = False; 
                    roll_angle = 0.0
                    is_rolling = False
                    roll_angle_target = 0.0
                    break
                    
                if is_on_rotating_track(p_pos, track_map):
                    is_rolling = True
                    roll_angle = 0.0
                    roll_angle_target = math.pi # 180 deg, upside-down roll.
                   
                hit = False
                if ship_alt < COLLISION_ALT_THRESHOLD:
                    cgx, cgy = int(nx // CELL_SIZE), int(ny // CELL_SIZE)
                    for ny_off in range(cgy-1, cgy+2):
                        for nx_off in range(cgx-1, cgx+2):
                            if 0 <= ny_off < map_h and 0 <= nx_off < map_w:
                                char = track_map[ny_off][nx_off]
                                if char == ' ':
                                    continue
                                if char in lib:
                                    off = vec2(nx_off * CELL_SIZE, ny_off * CELL_SIZE)
                                    for w1, w2 in lib[char]["walls"]:
                                        d, cl = get_dist(p_pos, w1 + off, w2 + off)
                                        if d < SHIP_RADIUS:
                                            play_sound(sounds, "bump")
                                            df = (p_pos - cl).normalize()
                                            ship_pos = cl + df * (SHIP_RADIUS + 3)
                                            dot = ship_vel.x * df.x + ship_vel.y * df.y
                                            ship_vel.x = (ship_vel.x - 1.5 * dot * df.x) * 0.6
                                            ship_vel.y = (ship_vel.y - 1.5 * dot * df.y) * 0.6
                                            hit = True; break
                        if hit: break
                if not hit: ship_pos.x, ship_pos.y = nx, ny
        cos_h, sin_h = get_cos_deg(heading), get_sin_deg(heading)
        cos_cam, sin_cam = get_cos_deg(-heading), get_sin_deg(-heading)
        c_pos = ship_pos - vec2(cos_h, sin_h) * CAM_DIST
       
        # Robust Culling Check: Manhattan Filter -> Euclidean Precision
        tiles = []
        for r in range(map_h):
            for c in range(map_w):
                char = track_map[r][c]
                if char == ' ':
                    continue
               
                tx = c * CELL_SIZE + MID
                ty = r * CELL_SIZE + MID
                dx = tx - c_pos.x
                dy = ty - c_pos.y
                dist_man = abs(dx) + abs(dy)
                is_near = False
                if dist_man < CELL_SIZE * 3:
                    if dx*dx + dy*dy < NEAR_CULL_DIST_SQ:
                        is_near = True
                is_ahead = (dx * cos_h + dy * sin_h) > -CULL_MARGIN
                if is_near or is_ahead:
                    tiles.append((dx*dx + dy*dy, r, c, char))
        
        tiles.sort(key=lambda x: x[0], reverse=True)
       
        # Draw loop, render loop.
        for _, r, c, char in tiles:
            t_off = vec2(c * CELL_SIZE, r * CELL_SIZE)
            tile_type = track_map[r][c]
           
            if char in '-=|tTrc_~':
               
                if char in '-=rc_~': 
                    # East-west roads.
                    p_pts = [t_off+vec2(0,MID-ROAD_W), t_off+vec2(CELL_SIZE,MID-ROAD_W), t_off+vec2(CELL_SIZE,MID+ROAD_W), t_off+vec2(0,MID+ROAD_W)]
                else:
                    # North-south roads.
                    p_pts = [t_off+vec2(MID-ROAD_W,0), t_off+vec2(MID-ROAD_W,CELL_SIZE), t_off+vec2(MID+ROAD_W,CELL_SIZE), t_off+vec2(MID+ROAD_W,0)]
                    
                p = [project_opt(p_pts[i], c_pos, cos_cam, sin_cam, bank, roll_angle, 150 if char=='r' and i in (1,2) else 0) for i in range(4)]
                v_pts = [x[0] for x in p if x is not None]
                if len(v_pts) >= 3:
                    # Add polygons on road.
                    col = CHECKPOINT_GOLD if char=='c' else RAMP_PURPLE if char=='r' else BOOST_PURPLE if char=='_' else DECO_YELLOW if char=='=' else FLOOR_GREY
                    draw_poly(screen, col, v_pts, 0)
                    #draw_transparent_poly(screen, col, v_pts, 120)
            elif char == '0':
                tip = project_opt(t_off + vec2(MID, MID), c_pos, cos_cam, sin_cam, bank, roll_angle, 1800)
                base = [project_opt(t_off + bp, c_pos, cos_cam, sin_cam, bank, roll_angle, 0) for bp in [vec2(0,0), vec2(CELL_SIZE,0), vec2(CELL_SIZE,CELL_SIZE), vec2(0,CELL_SIZE)]]
                if tip:
                    for i in range(4):
                        if base[i] and base[(i+1)%4]:
                            draw_poly(screen, (120, 130, 150) if i%2==0 else DARK_CYAN, [base[i][0], base[(i+1)%4][0], tip[0]])
            elif char == '#':
                incust = INSET - 500
                pts_b = [
                t_off+vec2(incust,incust), 
                t_off+vec2(CELL_SIZE-incust,incust), 
                t_off+vec2(CELL_SIZE-incust,CELL_SIZE-incust), 
                t_off+vec2(incust,CELL_SIZE-incust)]
                base = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, 0) for p in pts_b]
                top = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, WALL_HEIGHT) for p in pts_b]
                for i in range(4):
                    if base[i] and base[(i+1)%4] and top[i] and top[(i+1)%4]:
                        draw_poly(screen, BLOCK_GREY_DARK, [base[i][0], base[(i+1)%4][0], top[(i+1)%4][0], top[i][0]])
                v_top = [t[0] for t in top if t is not None]
                if len(v_top) >= 3: draw_poly(screen, BLOCK_GREY_LIGHT, v_top)

            elif char == '%':
                draw_sky_scraper(r, c, t_off, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base, sky_scraper_heights)

            elif char == 'G':  # 'G' for Geodesic/Greenhouse
                draw_geodesic_dome(r, c, t_off, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base)
            
            # Additional deco on top of road.
            if char == 't': # Decorative triangle.
                TRI_W = ROAD_W * 2 # width
                TRI_H = TRI_W * 0.625 # vertical height
                # Road is vertical (north-south), so we make the triangle plane east-west:
                # -> all points share the same Y, X varies across the road
                y_mid = t_off.y + MID
                x_left = t_off.x + MID - TRI_W // 2
                x_right = t_off.x + MID + TRI_W // 2
                x_center = t_off.x + MID
                # Heights: base on road, apex up
                h_base = 1
                h_top = h_base + TRI_H
                # 3 points in XY
                left_xy = vec2(x_left, y_mid)
                right_xy = vec2(x_right, y_mid)
                top_xy = vec2(x_center, y_mid)
                # Project with individual heights
                p_left = project_opt(left_xy, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base)
                p_right = project_opt(right_xy, c_pos, cos_cam, sin_cam, bank, roll_angle, h_base)
                p_top = project_opt(top_xy, c_pos, cos_cam, sin_cam, bank, roll_angle, h_top)
                if p_left and p_right and p_top:
                    v_left = p_left[0]
                    v_right = p_right[0]
                    v_top = p_top[0]
                    # Outline only (no fill)
                    draw_line(screen, ORANGE, v_top, v_left, 2)
                    draw_line(screen, ORANGE, v_left, v_right, 2)
                    draw_line(screen, ORANGE, v_right, v_top, 2)
                    
            elif char == 'T': # Decorative tunnel arc
                ARC_RES = 8    # Number of segments to make the curve smooth
                ARC_W = ROAD_W * 2   # Total width across the road
                ARC_H = ARC_W * 0.625 # Peak height of the arch, using golden ratio
                
                y_mid = t_off.y + MID
                x_center = t_off.x + MID
                h_base = 1
                
                previous_p = None
                first_p = None
                
                for i in range(ARC_RES + 1):
                    # Calculate angle: 0 is right side, PI/2 is top, PI is left side
                    angle = (i / ARC_RES) * 3.14159
                    
                    # Calculate offset from center and height using sine/cosine
                    # We use -cos for X so the arc builds from right to left (0 to PI)
                    curr_x = x_center - (ARC_W // 2) * get_cos_rad(angle)
                    curr_h = h_base + ARC_H * get_sin_rad(angle)
                    
                    curr_xy = vec2(curr_x, y_mid)
                    projected = project_opt(curr_xy, c_pos, cos_cam, sin_cam, bank, roll_angle, curr_h)
                    
                    if projected:
                        v_curr = projected[0]
                        if previous_p:
                            # Draw the segment of the arc
                            draw_line(screen, ORANGE, previous_p, v_curr, 3)
                        else:
                            first_p = v_curr
                        previous_p = v_curr
                        
            elif char == 'B':  # Brutalist North-South Tunnel Block
                # 1. Dimensions
                tunnel_half_width = ROAD_W + 100  
                incust = INSET - 500  
                
                # 2. Define the footprint segments (West Pillar and East Pillar)
                # North-South tunnel means pillars are at the left (West) and right (East)
                pillar_W = [
                    t_off + vec2(incust, incust), 
                    t_off + vec2(MID - tunnel_half_width, incust), 
                    t_off + vec2(MID - tunnel_half_width, CELL_SIZE - incust),
                    t_off + vec2(incust, CELL_SIZE - incust)
                ]
                pillar_E = [
                    t_off + vec2(MID + tunnel_half_width, incust), 
                    t_off + vec2(CELL_SIZE - incust, incust), 
                    t_off + vec2(CELL_SIZE - incust, CELL_SIZE - incust),
                    t_off + vec2(MID + tunnel_half_width, CELL_SIZE - incust)
                ]
                
                # Heights - using WALL_HEIGHT as the standard for your '#' blocks
                tunnel_ceiling_h = WALL_HEIGHT * 0.7 
                block_total_h = WALL_HEIGHT 

                for footprint in [pillar_W, pillar_E]:
                    # Project Base and Top
                    base = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, 0) for p in footprint]
                    top = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, block_total_h) for p in footprint]
                    
                    # Draw Pillar Sides (Outer and Inner walls)
                    for i in range(4):
                        if base[i] and base[(i+1)%4] and top[i] and top[(i+1)%4]:
                            # Use Dark Grey for the vertical walls
                            draw_poly(screen, BLOCK_GREY_DARK, [base[i][0], base[(i+1)%4][0], top[(i+1)%4][0], top[i][0]])
                    
                    # Draw Pillar Tops (The concrete slabs on top)
                    v_top = [t[0] for t in top if t is not None]
                    if len(v_top) >= 3: 
                        draw_poly(screen, BLOCK_GREY_LIGHT, v_top)

                # 3. The Roof Slab (The "Bridge" connecting West and East)
                # This spans the entire footprint at a high Z
                roof_footprint = [
                    t_off + vec2(incust, incust),
                    t_off + vec2(CELL_SIZE - incust, incust),
                    t_off + vec2(CELL_SIZE - incust, CELL_SIZE - incust),
                    t_off + vec2(incust, CELL_SIZE - incust)
                ]
                
                # Project the bottom of the slab (the ceiling) and the top of the slab
                ceil_pts = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, tunnel_ceiling_h) for p in roof_footprint]
                roof_pts = [project_opt(p, c_pos, cos_cam, sin_cam, bank, roll_angle, block_total_h) for p in roof_footprint]
                
                # Draw the Ceiling (Underneath) - darker to look like shadow
                v_ceil = [c[0] for c in ceil_pts if c is not None]
                if len(v_ceil) >= 3:
                    draw_poly(screen, (30, 30, 30), v_ceil)
                    
                # Draw the Top Surface of the Tunnel
                v_roof = [r[0] for r in roof_pts if r is not None]
                if len(v_roof) >= 3:
                    draw_poly(screen, BLOCK_GREY_LIGHT, v_roof)

            if char in lib and char not in ('0', '#', 'G', '%'): 
            
                for arc in lib[char].get("arches", []):
                    draw_clipped_arch(arc[0]+t_off, arc[1]+t_off, c_pos, cos_cam, sin_cam, bank, roll_angle, color=CHECKPOINT_GOLD if char=='c' else CYAN)
                    
                for w in lib[char]["walls"]:
                    p0 = get_rel_coords_opt(w[0] + t_off, c_pos, cos_cam, sin_cam, roll_angle)
                    p1 = get_rel_coords_opt(w[1] + t_off, c_pos, cos_cam, sin_cam, roll_angle)
                    # Draw the wall line. Usually road sides.
                    draw_clipped_3d_line(p0, p1, bank, roll_angle, CYAN, 1)
           
        draw_ship(screen, ship_alt, ship_vel, is_boosting, bank, roll_angle)
            
        screen.blit(hud_font.render(f"SPD: {int(ship_vel.length())}", True, WHITE), (20, 20))
        lap_txt = hud_font.render(f"LAP: {format_time(current_lap_time)}", True, WHITE)
        screen.blit(lap_txt, (INTERNAL_RES_W - lap_txt.get_width() - 20, 20))
     
        if best_lap_time != float('inf'):
            best_txt = small_font.render(f"BEST: {format_time(best_lap_time)}", True, CHECKPOINT_GOLD)
            screen.blit(best_txt, (INTERNAL_RES_W - best_txt.get_width() - 20, 45))
            
        if not race_started:
            start_txt = hud_font.render("PRESS ANY KEY", True, CYAN)
            screen.blit(start_txt, (INTERNAL_RES_W//2 - start_txt.get_width()//2, INTERNAL_RES_H//2))
            
        pygame.display.flip()

def main():
    random.seed(42)
    sounds = load_all_sounds()
    engine_channel = pygame.mixer.Channel(1)
    music_path = os.path.join("music", "placeholder.ogg")
    if os.path.exists(music_path):
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.play(-1) # -1 = loop the music.
        pygame.mixer.music.set_volume(0.6)
        #pygame.mixer.music.stop()
    selected = 0
    while True:
        track_name, track_map, selected = main_menu(sounds, selected)
        if track_map is None: break
        run_game(track_name, track_map, sounds, engine_channel)
    pygame.quit()

if __name__ == "__main__":
    main()
