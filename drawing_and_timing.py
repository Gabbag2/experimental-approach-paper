"""
drawing_and_timing.py

All the low-level visual stuff for the task:
- drawing bars / cues / probe / feedback
- handling timing of what gets shown on screen

The goal is:
experiment_run.py controls what happens when
this file controls what gets drawn and for how long
"""

import math
import time
from expyriment import stimuli
from expyriment.misc import constants, geometry


# ============================================================
# --- BASIC SCREEN CONTROL HELPERS ---
# ============================================================

def _blit_to_backbuffer(exp, stim_list):
    """
    Draw a list of stimuli to the backbuffer (not yet visible).

    We don't flip here. This lets us prepare the frame first.
    """
    for stim in stim_list:
        stim.present(clear=False, update=False)  # draw but don't flip yet
    # NOTE: We do NOT clear here. Callers are responsible for clearing screen
    # before first blit if needed.


def _timed_flip_and_measure(exp):
    """
    Flip the backbuffer to the screen and return the timestamp (in ms).
    """
    flip_timestamp_ms = exp.clock.time  # time *before* flip call
    exp.screen.update()                 # flip
    return flip_timestamp_ms


def draw_now(exp, stim_list):
    """
    Just draw these stimuli and show them immediately.

    Used for interactive phases (e.g. the response phase where subject
    rotates the probe bar). We don't need a fixed duration there, we just
    want to refresh ASAP.
    """
    exp.screen.clear()
    _blit_to_backbuffer(exp, stim_list)
    _timed_flip_and_measure(exp)


def _timed_draw(exp, stim_list):
    """
    Draw stimuli, flip, and return the actual flip time in ms.

    This is the "one frame shown" part. We don't control how long it stays;
    present_for_ms() does that by waiting after this call.
    """
    exp.screen.clear()
    _blit_to_backbuffer(exp, stim_list)
    flip_t_ms = _timed_flip_and_measure(exp)
    return flip_t_ms


def present_for_ms(exp, stim_list, duration_ms):
    """
    Show a list of stimuli for a specific amount of time (in ms).

    This is our standard "put something on screen for X ms" call.
    - fixation
    - memory array
    - cue
    - blank delays
    - feedback

    How it works:
    1. draw + flip (get the flip timestamp)
    2. busy-wait / sleep until total time on screen reaches duration_ms
    """
    flip_t = _timed_draw(exp, stim_list)
    target_t = flip_t + duration_ms

    # Simple wait loop. We try to sleep in small chunks so timing isn't horrible.
    while True:
        now = exp.clock.time
        remaining = target_t - now
        if remaining <= 0:
            break
        # sleep a little to avoid burning CPU
        time.sleep(min(remaining / 1000.0, 0.001))


# ============================================================
# --- COLOR HELPERS ---
# ============================================================

def hsv_to_rgb(h, s, v):
    """
    Convert HSV in [0,1] to RGB in [0,255].

    We use this to assign each memory item a color on a color wheel.
    """
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6

    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q

    return [int(r * 255), int(g * 255), int(b * 255)]


def color_from_wheel(angle_deg):
    """
    Map an angle in degrees [0..360) to a bright, unique-ish RGB color.

    We basically treat angle as hue on the color wheel.
    Saturation and value are high to make colors pop.
    """
    hue = (angle_deg % 360) / 360.0
    return hsv_to_rgb(hue, 0.9, 0.9)


# ============================================================
# --- STIMULUS BUILDERS ---
# These functions return Expyriment stimuli that we can blit.
# Nothing is presented here. We just *create* them.
# ============================================================

def make_oriented_colored_bar(
    angle_deg,
    color_angle_deg,
    center_xy,
    length_px=60,
    width_px=10
):
    """
    One memory item: a colored bar at a given orientation.

    - angle_deg: the physical orientation (what they actually have to remember)
    - color_angle_deg: used to pick the bar color
    - center_xy: (x,y) on screen in px
    """

    # Color is based on color_angle_deg, not orientation. That's how we bind.
    rgb = color_from_wheel(color_angle_deg)

    # Build a rectangle, then rotate it.
    bar = stimuli.Rectangle(
        size=(length_px, width_px),
        colour=rgb
    )
    bar.rotate(angle_deg)
    bar.position = center_xy
    return bar


def make_outline_square(center_xy, size_px=80, line_width=3, colour=constants.C_WHITE):
    """
    Little square frame used around the probed location during response.
    Just a visual hint: "this is the item you're reporting".
    """
    square = stimuli.Rectangle(
        size=(size_px, size_px),
        colour=colour,          # border color
        line_width=line_width  # >0 means it's an outlined box, not filled
    )
    square.position = center_xy
    return square



def make_spatial_cue_arrows(target_position_px, color=constants.C_BLACK):
    """
    Retro-cue for spatial condition.

    We draw TWO arrows at fixation, both pointing toward the cued item.
    So if the cued item is upper-left, both arrows point upper-left, etc.

    Returns a list of 4 stimuli:
    [arrow1_rect, arrow1_tri, arrow2_rect, arrow2_tri]
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


def make_color_cue_square(rgb_color, size_px=100):
    """
    Retro-cue for color condition.

    Just a filled colored square at fixation.
    """
    sq = stimuli.Rectangle(size=(size_px, size_px), colour=rgb_color)
    sq.position = (0, 0)
    return sq


def make_probe_bar(angle_deg, center_xy, length_px=60, width_px=10, color=constants.C_WHITE):
    """
    The white bar they rotate during response.

    angle_deg: current rotation we're showing to the participant
    center_xy: position of the probed item
    """
    bar = stimuli.Rectangle(size=(length_px, width_px), colour=color)
    bar.rotate(angle_deg)
    bar.position = center_xy
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

