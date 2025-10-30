"""
This module defines:
- timing helpers (frame timing, draw & wait)
- color helpers (HSV wheel)
- stimulus constructors (fixation, memory bars, cues, probe bar, feedback)

All stimuli returned here are Expyriment stimuli already positioned in
screen-centered coordinates (0,0 = fixation).

IMPORTANT: this version is PIXEL-BASED.
There is no visual-angle / deg->px conversion anymore.
All sizes and positions are assumed to already be in pixels.
"""

import math
from collections.abc import Iterable

from expyriment import stimuli
from expyriment.misc import constants, geometry


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
    Convert a frame count back to ms.
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
    - then wait the remaining time (duration - draw_time)

    If duration_ms <= 0, return immediately.
    """
    if duration_ms <= 0:
        return

    draw_time = _timed_draw(exp, stims)  # ms to draw+flip
    remaining = duration_ms - draw_time
    if remaining > 0:
        exp.clock.wait(remaining)


########################################
# ========== 2. COLOR HELPERS ==========
########################################

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

    Each bar's color is sampled from a 360-step color wheel.
    We treat that as hue=color_deg, full saturation, full value.

    Returns an (r,g,b) tuple usable as Expyriment colour.
    """
    return hsv_to_rgb(color_deg, 1.0, 1.0)


########################################
# ========== 3. STIMULUS CREATION ======
########################################

def make_oriented_colored_bar(
    position_px,
    size_px,
    orientation_deg,
    color_id
):
    """
    One memory item (colored, oriented bar).

    position_px: (x,y) in pixels, relative to screen center
    size_px: (length_px, height_px)
    orientation_deg: orientation of the bar (0-360)
    color_id: hue on the wheel (1-360)
    """
    length_px, height_px = size_px
    rgb = color_from_wheel(color_id)

    bar = stimuli.Rectangle(
        size=(int(round(length_px)), int(round(height_px))),
        colour=rgb,
        position=position_px
    )

    # Expyriment rotation is clockwise
    bar.rotate(orientation_deg)

    return bar


def make_outline_square(
    position_px,
    size_px,
    color=constants.C_BLACK,
    line_width_px=2
):
    """
    Outline square marking the probed item's original location.

    position_px: (x,y) where the square should be drawn
    size_px: (w_px, h_px) of the box we want outlined
    """
    w_px, h_px = size_px
    w_px = int(round(w_px))
    h_px = int(round(h_px))

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


def make_spatial_cue_arrows(target_position_px, color=constants.C_BLACK):
    """
    Make TWO arrows at fixation, both pointing toward the cued item's position.
    We infer which diagonal to point to from the sign of (x,y).

    Returns list of 4 stimuli: [arrow1_rect, arrow1_tri, arrow2_rect, arrow2_tri]
    All of them are positioned near fixation.
    """
    tx, ty = target_position_px

    if tx >= 0 and ty >= 0:
        direction = "top_right"
    elif tx <= 0 and ty >= 0:
        direction = "top_left"
    elif tx <= 0 and ty <= 0:
        direction = "bottom_left"
    else:
        direction = "bottom_right"

    def build_single_arrow(direction='top_left', length=100, width=10,
                           color=color, y_offset_px=0):
        """
        Build one arrow (shaft + head) for a given direction,
        vertically offset so we can draw two stacked arrows.
        """

        # shaft
        rect = stimuli.Rectangle(
            size=(length, width),
            colour=color,
            position=(0, y_offset_px)
        )

        # triangle head
        tri = stimuli.Shape(
            vertex_list=geometry.vertices_regular_polygon(3, 25),
            colour=color,
            position=(0, y_offset_px)
        )

        # Attach point tuning (keeps arrow head touching shaft tip)
        ATTACH = 20  # px

        if direction == 'top_right':
            rect.rotate(45)
            tri_x =  length / 2
            tri_y =  y_offset_px + length / 2
            tri_x -= ATTACH / math.sqrt(2)
            tri_y -= ATTACH / math.sqrt(2)
            tri.position = (tri_x, tri_y)
            tri.rotate(315)  # -45°

        elif direction == 'top_left':
            rect.rotate(135)
            tri_x = -length / 2
            tri_y =  y_offset_px + length / 2
            tri_x += ATTACH / math.sqrt(2)
            tri_y -= ATTACH / math.sqrt(2)
            tri.position = (tri_x, tri_y)
            tri.rotate(45)

        elif direction == 'bottom_left':
            rect.rotate(225)
            tri_x = -length / 2
            tri_y =  y_offset_px - length / 2
            tri_x += ATTACH / math.sqrt(2)
            tri_y += ATTACH / math.sqrt(2)
            tri.position = (tri_x, tri_y)
            tri.rotate(135)

        elif direction == 'bottom_right':
            rect.rotate(315)
            tri_x =  length / 2
            tri_y =  y_offset_px - length / 2
            tri_x -= ATTACH / math.sqrt(2)
            tri_y += ATTACH / math.sqrt(2)
            tri.position = (tri_x, tri_y)
            tri.rotate(225)

        return rect, tri

    GAP = 50  # vertical offset between the two arrows (px)

    arrow1_rect, arrow1_tri = build_single_arrow(
        direction=direction,
        length=100,
        width=10,
        color=color,
        y_offset_px=-GAP/2.0
    )

    arrow2_rect, arrow2_tri = build_single_arrow(
        direction=direction,
        length=100,
        width=10,
        color=color,
        y_offset_px=+GAP/2.0
    )

    return [arrow1_rect, arrow1_tri, arrow2_rect, arrow2_tri]


def make_color_cue_square(
    size_px,
    fill_color_id
):
    """
    Central filled square (feature retro-cue).
    Drawn at fixation (0,0).

    size_px: (w_px, h_px)
    fill_color_id: hue on wheel (1-360)
    """
    w_px, h_px = size_px
    w_px = int(round(w_px))
    h_px = int(round(h_px))

    rgb = color_from_wheel(fill_color_id)

    square = stimuli.Rectangle(
        size=(w_px, h_px),
        colour=rgb,
        position=(0, 0)
    )
    return square


def make_probe_bar(
    position_px,
    size_px,
    orientation_deg,
    color=constants.C_BLACK
):
    """
    Rotatable response bar shown at fixation during report.

    position_px: (x,y)
    size_px: (length_px, height_px)
    orientation_deg: bar angle (0-360)
    """
    length_px, height_px = size_px

    bar = stimuli.Rectangle(
        size=(int(round(length_px)), int(round(height_px))),
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
    Feedback after response, e.g. "Error: 12.3°".
    Displayed at fixation.
    """
    return stimuli.TextLine(
        text=text,
        text_colour=color,
        text_size=font_size,
        position=(0, 0)
    )
