"""
This module defines:
- timing helpers (frame timing, draw & wait)
- visual helpers (deg->px, color mapping)
- stimulus constructors (fixation, memory bars, cues, probe bar, feedback)

All stimuli returned here are Expyriment stimuli already positioned in
screen-centered coordinates (0,0 = fixation).
"""

import math
from collections.abc import Iterable

from expyriment import stimuli
from expyriment.misc import constants


########################################
# ========== 1. TIMING HELPERS =========
########################################

# We assume a 60Hz display
FPS = 60
MS_PER_FRAME = 1000.0 / FPS  # ~16.67 ms at 60Hz


def ms_to_frames(ms):
    """
    Convert milliseconds to an integer number of video frames.
    """
    return int(math.ceil(ms / MS_PER_FRAME))


def frames_to_ms(n_frames):
    """
    Convert a frame count back to ms
    """
    return n_frames * MS_PER_FRAME


def _blit_to_backbuffer(exp, stims):
    """
    Internal helper.
    Clear the backbuffer, draw all stims into it (without flipping),
    but do NOT update the screen yet.
    """
    exp.screen.clear()

    if isinstance(stims, Iterable) and not isinstance(stims, (str, bytes)):
        for stim in stims:
            stim.present(clear=False, update=False)
    else:
        stims.present(clear=False, update=False)


def draw_now(exp, stims):
    """
    Draw stimuli to backbuffer and flip once immediately.
    (One frame; no enforced duration.)
    """
    _blit_to_backbuffer(exp, stims)
    exp.screen.update()


def _timed_draw(exp, stims):
    """
    Draw stimuli and flip once, return how long (ms) that draw+flip took.

    We measure because we want to compensate for drawing time when enforcing
    a total presentation duration.
    """
    t0 = exp.clock.time
    _blit_to_backbuffer(exp, stims)
    exp.screen.update()
    elapsed = exp.clock.time - t0  # ms elapsed
    return elapsed


def present_for_ms(exp, stims, duration_ms):
    """
    Present `stims` for approximately `duration_ms` milliseconds:
    - draw everything and flip once
    - then wait the remaining time (duration - draw_time), quantized to frame rate

    If duration_ms == 0, just returns immediately
    """
    if duration_ms <= 0:
        return

    draw_time = _timed_draw(exp, stims)  # how long it took to draw+flip in ms
    remaining = duration_ms - draw_time
    if remaining > 0:
        exp.clock.wait(remaining)


########################################
# ========== 2. VISUAL HELPERS =========
########################################

def calibrate_visual_geometry(exp, screen_width_mm, viewing_distance_mm=600):
    """
    Calibrate degrees→pixels conversion for THIS experiment setup.

    Arguments:
    - exp: your Expyriment Experiment (already initialized)
    - screen_width_mm: visible display width in millimeters (measure with a ruler)
    - viewing_distance_mm: eye-to-screen distance in millimeters
                           default = 600 mm (60 cm), as in the paper

    What this does:
    - Reads the current screen resolution from exp.screen.size
    - Computes pixels-per-degree of visual angle for this setup
    - Stores two convenience things on `exp`:
        exp.PX_PER_DEG  (float)
        exp.deg2px(deg) (callable)
    """

    # 1. Get pixel resolution from Expyriment
    screen_width_px = exp.screen.size[0]  # horizontal resolution in px

    # 2. Compute mm per pixel
    mm_per_px = float(screen_width_mm) / float(screen_width_px)

    # 3. Compute physical length on screen that subtends 1 degree
    #    visual_angle = 2 * atan( size_mm / (2 * distance_mm) )
    #    -> invert for size_mm given visual_angle = 1°
    theta_rad = math.radians(1.0)  # 1 degree in radians
    size_mm_for_one_deg = 2.0 * viewing_distance_mm * math.tan(theta_rad / 2.0)

    # 4. Convert that physical size to pixels
    px_per_deg = size_mm_for_one_deg / mm_per_px

    # 5. Attach results to the experiment so everything else can use it
    exp.PX_PER_DEG = px_per_deg

    def _deg2px(deg):
        return deg * exp.PX_PER_DEG

    exp.deg2px = _deg2px

    return px_per_deg 


def hsv_to_rgb(h, s, v):
    """
    Convert HSV to RGB.
    h in [0, 360)
    s in [0, 1]
    v in [0, 1]

    Returns (r, g, b) with each in [0,255]
    """
    h = float(h) % 360.0
    s = float(s)
    v = float(v)

    c = v * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = v - c

    if h < 60:
        rp, gp, bp = c, x, 0
    elif h < 120:
        rp, gp, bp = x, c, 0
    elif h < 180:
        rp, gp, bp = 0, c, x
    elif h < 240:
        rp, gp, bp = 0, x, c
    elif h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x

    r = int(round((rp + m) * 255))
    g = int(round((gp + m) * 255))
    b = int(round((bp + m) * 255))

    return (r, g, b)


def color_from_wheel(color_deg):
    """
    Map color index (1..360) to an RGB value.

    In the paper, each bar's color is sampled from a 360-step color wheel.
    We'll interpret that as evenly spaced hues at max saturation and brightness.

    Returns an (r,g,b) tuple usable as Expyriment colour.
    """
    return hsv_to_rgb(color_deg, 1.0, 1.0)


########################################
# ========== 3. STIMULUS CREATION =====
########################################

def make_oriented_colored_bar(
    exp,
    position_px,
    size_deg,
    orientation_deg,
    color_id
):
    """
    One memory item (colored, oriented bar).
    """
    length_deg, height_deg = size_deg
    length_px = int(round(exp.deg2px(length_deg)))
    height_px = int(round(exp.deg2px(height_deg)))

    rgb = color_from_wheel(color_id)

    bar = stimuli.Rectangle(
        size=(length_px, height_px),
        colour=rgb,
        position=position_px
    )

    # Expyriment rotation is clockwise
    bar.rotate(orientation_deg)

    return bar


def make_outline_square(
    exp,
    position_px,
    size_deg,
    color=constants.C_BLACK,
    line_width_px=2
):
    """
    Outline square marking the probed item's original location.
    """
    w_deg, h_deg = size_deg
    w_px = int(round(exp.deg2px(w_deg)))
    h_px = int(round(exp.deg2px(h_deg)))

    canv_w = w_px + line_width_px
    canv_h = h_px + line_width_px

    canv = stimuli.Canvas(
        size=(canv_w, canv_h),
        position=position_px,
        colour=None
    )

    half_w = w_px // 2
    half_h = h_px // 2

    # top
    stimuli.Line(
        start_point=(-half_w, -half_h),
        end_point=(+half_w, -half_h),
        line_width=line_width_px,
        colour=color
    ).plot(canv)

    # bottom
    stimuli.Line(
        start_point=(-half_w, +half_h),
        end_point=(+half_w, +half_h),
        line_width=line_width_px,
        colour=color
    ).plot(canv)

    # left
    stimuli.Line(
        start_point=(-half_w, -half_h),
        end_point=(-half_w, +half_h),
        line_width=line_width_px,
        colour=color
    ).plot(canv)

    # right
    stimuli.Line(
        start_point=(+half_w, -half_h),
        end_point=(+half_w, +half_h),
        line_width=line_width_px,
        colour=color
    ).plot(canv)

    return canv

def make_spatial_cue_arrows(exp, target_position_px, color=constants.C_BLACK):
    """
    Two arrowheads near fixation, both pointing toward the target location.
    Each arrowhead is a triangle. We build them in final (screen-centered)
    coordinates so we don't have to mess with .rotate().
    """

    tx, ty = target_position_px

    # Direction from fixation to target
    angle_rad = math.atan2(ty, tx)

    # Unit direction vector (toward target)
    ux = math.cos(angle_rad)
    uy = math.sin(angle_rad)

    # Perpendicular direction (90° CCW)
    px = -uy
    py = ux

    # Geometry for one arrowhead (triangle), defined along +x before rotation.
    ARROW_LEN = 40.0          # length of the arrowhead
    ARROW_HALF_WIDTH = 12.0   # half the base width

    half_L = ARROW_LEN / 2.0
    tri_local = [
        ( +half_L, 0.0),                          # tip
        ( -half_L, +ARROW_HALF_WIDTH),            # base upper
        ( -half_L, -ARROW_HALF_WIDTH),            # base lower
    ]

    def rotate_and_translate(vertices, center_x, center_y, ang_rad):
        cos_a = math.cos(ang_rad)
        sin_a = math.sin(ang_rad)
        out = []
        for (x, y) in vertices:
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            out.append((rx + center_x, ry + center_y))
        return out

    # Where to place them:
    ARROW_CENTER_DIST = 25.0   # distance from fixation in pointing direction
    ARROW_SEP = 10.0           # spread along perpendicular (so we get two arrows)

    ax = ux * ARROW_CENTER_DIST + px * ARROW_SEP
    ay = uy * ARROW_CENTER_DIST + py * ARROW_SEP

    bx = ux * ARROW_CENTER_DIST - px * ARROW_SEP
    by = uy * ARROW_CENTER_DIST - py * ARROW_SEP

    verts_a = rotate_and_translate(tri_local, ax, ay, angle_rad)
    verts_b = rotate_and_translate(tri_local, bx, by, angle_rad)

    # Build Shape objects (outline polygons)
    arrow_a = stimuli.Shape(
        vertex_list=verts_a,
        colour=color,
        position=(0, 0)
    )
    arrow_b = stimuli.Shape(
        vertex_list=verts_b,
        colour=color,
        position=(0, 0)
    )

    # Make them visually thick enough to be obvious
    arrow_a.line_width = 4
    arrow_b.line_width = 4

    return [arrow_a, arrow_b]


def make_color_cue_square(
    exp,
    size_deg,
    fill_color_id
):
    """
    Central filled square (feature retro-cue).
    """
    w_deg, h_deg = size_deg
    w_px = int(round(exp.deg2px(w_deg)))
    h_px = int(round(exp.deg2px(h_deg)))

    rgb = color_from_wheel(fill_color_id)

    square = stimuli.Rectangle(
        size=(w_px, h_px),
        colour=rgb,
        position=(0, 0)
    )
    return square


def make_probe_bar(
    exp,
    position_px,
    size_deg,
    orientation_deg,
    color=constants.C_BLACK
):
    """
    Rotatable response bar at fixation.
    """
    length_deg, height_deg = size_deg
    length_px = int(round(exp.deg2px(length_deg)))
    height_px = int(round(exp.deg2px(height_deg)))

    bar = stimuli.Rectangle(
        size=(length_px, height_px),
        colour=color,
        position=position_px
    )
    bar.rotate(orientation_deg)
    return bar

def make_feedback_text(
    text,
    color=constants.C_BLACK,
    font_size=24
):
    """
    Feedback after response
    We just render text at fixation like "Error: 12.3°".
    """
    return stimuli.TextLine(
        text=text,
        text_colour=color,
        text_size=font_size,
        position=(0, 0)
    )
