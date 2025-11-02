"""
experiment_run.py

This file decides what happens when in a trial.

Trial structure:
1. fixation
2. memory array (4 bars, each has orientation + color)
3. first blank delay
4. retro-cue (spatial / color / no cue)
5. variable cue/probe delay
6. response phase (subject reports orientation of the cued bar)
7. feedback
8. log trial data
"""

import random
from expyriment import design, control, stimuli
from expyriment.misc import constants

from drawing_and_timing import (
    present_for_ms,
    draw_now,
    make_oriented_colored_bar,
    make_outline_square,
    make_spatial_cue_arrows,
    make_color_cue_square,
    make_probe_bar,
    make_feedback_text,
    color_from_wheel,   # we use this to turn hue (deg) into an RGB square for the color cue
)


# ============================================================
# --- TIMING (in ms) ---
# ============================================================

FIXATION_DURATION_MS      = 300     # fixation cross
MEMORY_DURATION_MS        = 500     # memory array on screen
FIRST_BLANK_DELAY_MS      = 500     # blank before retro-cue
CUE_DURATION_MS           = 100     # retro-cue on screen
CUE_PROBE_DELAYS_MS       = [50, 200, 350, 500, 650]  # variable blank after cue
FEEDBACK_DURATION_MS      = 1000    # how long we show feedback text


# ============================================================
# --- TASK STRUCTURE ---
# ============================================================

N_ITEMS_PER_ARRAY         = 4
REPEATS_PER_CONDITION     = 28      # per (cue_type x delay)
CUE_TYPES                 = ["spatial", "color", "no_cue"]


# ============================================================
# --- DISPLAY GEOMETRY ---
# We place items in 4 fixed locations around the center.
# Screen coordinate system is centered at (0,0).
# ============================================================

ITEM_POSITIONS_PX = [
    (-200, +200),   # top-left
    (+200, +200),   # top-right
    (-200, -200),   # bottom-left
    (+200, -200),   # bottom-right
]

# size of the memory/probe bars
BAR_LENGTH_PX            = 110      # along the bar's main axis
BAR_WIDTH_PX             = 25       # thickness of the bar

# outline square shown during the response phase around the cued item's location
PROBE_MARKER_SIZE_PX     = 120      # side length of the outline square

# mouse sensitivity for rotating the probe bar during response
ROTATION_SENSITIVITY     = 0.4      # deg per horizontal pixel moved


# ============================================================
# --- STIMULUS DRAWING CONSTRAINTS ---
# We want each bar to have:
# 1. a distinct orientation (not too similar)
# 2. a distinct color (not too similar on the hue wheel)
# ============================================================

ORI_RANGE_DEG            = (1, 180)   # allowed orientations (bars are symetrical so 0-180 is enough)
ORI_MIN_SEP_DEG          = 30         # bars differ by at least 30° orientation

COL_RANGE_DEG            = (1, 360)   # allowed hues on color wheel
COL_MIN_SEP_DEG          = 60         # hues differ by at least 60° on the wheel


# ============================================================
# --- COUNTER-BALLANCING ---
# We generate all trials here.
# ============================================================

def build_trial_list():
    """
    Full design:
    3 cue types x 5 delays x REPEATS_PER_CONDITION reps each.

    Example with default params:
    3 * 5 * 28 = 420 trials total
    """
    trials = []
    for cue_type in CUE_TYPES:
        for dly in CUE_PROBE_DELAYS_MS:
            for _ in range(REPEATS_PER_CONDITION):
                trials.append({
                    "cue_type": cue_type,
                    "delay": dly
                })
    random.shuffle(trials)
    return trials

# ============================================================
# --- HELPER FUNCTIONS FOR STIM CREATION ---
# ============================================================

def circular_distance(a, b, period):
    """
    Smallest distance between angles a and b on a circular scale (used for hue)
    """
    diff = abs(a - b) % period
    return min(diff, period - diff)


def sample_orientations(n, min_sep, lo, hi):
    """
    Sample n orientations (integers in [lo, hi]) such that all chosen values
    are at least min_sep apart.

    We retry until we get n that respect spacing.
    """
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(abs(cand - prev) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen


def sample_colors(n, min_sep, lo, hi):
    """
    Sample n hues (integers in [lo, hi]) on a 0-360° color wheel,
    such that circular distance between any two is >= min_sep.

    These hue values later get converted into RGB with color_from_wheel().
    """
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(circular_distance(cand, prev, 360) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen


def create_memory_array():
    """
    Build ONE memory array for a trial.

    Returns a list of 4 dicts, one per item:
    {
        "pos":        (x,y),         # where it goes on screen
        "ori_deg":    θ,             # the true orientation we want them to remember
        "color_deg":  hue_degrees    # used to derive the item's color
    }
    """
    orientations = sample_orientations(
        n=N_ITEMS_PER_ARRAY,
        min_sep=ORI_MIN_SEP_DEG,
        lo=ORI_RANGE_DEG[0],
        hi=ORI_RANGE_DEG[1]
    )

    colors = sample_colors(
        n=N_ITEMS_PER_ARRAY,
        min_sep=COL_MIN_SEP_DEG,
        lo=COL_RANGE_DEG[0],
        hi=COL_RANGE_DEG[1]
    )

    bars = []
    for i in range(N_ITEMS_PER_ARRAY):
        bars.append({
            "pos": ITEM_POSITIONS_PX[i],
            "ori_deg": orientations[i],
            "color_deg": colors[i],
        })
    return bars


# ============================================================
# --- SINGLE TRIAL EXECUTION ---
# This is the core of the task. We run this many times within each block.
# ============================================================

def run_single_trial(exp, cue_type, cue_probe_delay_ms):
    """
    Run ONE full trial with a given cue type and a given cue/probe delay.

    cue_type: "spatial", "color", or "no_cue"
    cue_probe_delay_ms: how long we wait between the cue disappearing and the probe/response appearing

    Returns a dict with response data:
        {
            "cue_type": str,
            "delay": int,
            "true_orientation": float,
            "reported_orientation": float,
            "offset": float   # absolute error in deg (0-180°)
        }
    """

    exp.mouse.show_cursor()  # participant uses mouse to rotate the probe bar

    # --------------------------------------------------------
    # 1. Fixation cross
    # --------------------------------------------------------
    fixation = stimuli.FixCross(
        size=(16, 16),
        line_width=2,
        colour=constants.C_BLACK,
        position=(0, 0)
    )
    present_for_ms(exp, [fixation], FIXATION_DURATION_MS)

    # --------------------------------------------------------
    # 2. Memory array (4 bars: position, orientation, color)
    # --------------------------------------------------------
    bars = create_memory_array()

    bar_stims = []
    for bar in bars:
        stim = make_oriented_colored_bar(
            angle_deg=bar["ori_deg"],
            color_angle_deg=bar["color_deg"],
            center_xy=bar["pos"],
            length_px=BAR_LENGTH_PX,
            width_px=BAR_WIDTH_PX,
        )
        bar_stims.append(stim)

    present_for_ms(exp, bar_stims, MEMORY_DURATION_MS)

    # --------------------------------------------------------
    # 3. First retention delay (blank screen)
    # --------------------------------------------------------
    present_for_ms(exp, [], FIRST_BLANK_DELAY_MS)

    # --------------------------------------------------------
    # 4. Retro-cue
    #
    # We randomly pick which stimulus will be probed later.
    # The cue tells the subject which item from the array matters.
    #
    # spatial cue  = arrows from fixation pointing toward the item's location
    # color cue    = solid square at fixation with that item's color
    # no cue       = nothing (just a blank of the same duration)
    # --------------------------------------------------------
    target_bar = random.choice(bars)
    target_pos_px    = target_bar["pos"]
    target_color_deg = target_bar["color_deg"]
    target_true_ori  = target_bar["ori_deg"]

    if cue_type == "spatial":
        cue_stims = make_spatial_cue_arrows(
            target_position_px=target_pos_px,
            color=constants.C_BLACK
        )
        present_for_ms(exp, cue_stims, CUE_DURATION_MS)

    elif cue_type == "color":
        rgb_for_cue = color_from_wheel(target_color_deg)
        color_cue = make_color_cue_square(
            rgb_color=rgb_for_cue,
            size_px=100
        )
        present_for_ms(exp, [color_cue], CUE_DURATION_MS)

    elif cue_type == "no_cue":
        present_for_ms(exp, [], CUE_DURATION_MS)

    else:
        raise ValueError(f"Unknown cue_type: {cue_type}")

    # --------------------------------------------------------
    # 5. Variable cue/probe delay (blank screen)
    # --------------------------------------------------------
    present_for_ms(exp, [], cue_probe_delay_ms)

    # --------------------------------------------------------
    # 6. Response phase
    #
    # We show:
    # 1. an outline square where the target was
    # 2. a white probe bar at fixation (0,0)
    #
    # Subject rotates the probe bar with left/right mouse movement,
    # and confirms with mouse click.
    #
    # We keep redrawing until they confirm.
    # --------------------------------------------------------
    current_angle = 90.0  # starting orientation of the probe bar (in deg)
    reported_orientation = None

    response_done = False
    last_mouse_x, _ = exp.mouse.position

    while not response_done:
        # outline marks WHICH location is being tested
        outline_stim = make_outline_square(
            center_xy=target_pos_px,
            size_px=PROBE_MARKER_SIZE_PX,
            line_width=2,
            colour=constants.C_BLACK
        )

        # probe bar is what they rotate to report orientation
        probe_bar_stim = make_probe_bar(
            angle_deg=current_angle,
            center_xy=(0, 0),
            length_px=BAR_LENGTH_PX,
            width_px=BAR_WIDTH_PX,
            color=constants.C_BLACK
        )

        draw_now(exp, [outline_stim, probe_bar_stim])

        # update orientation based on horizontal mouse movement
        mouse_x, _ = exp.mouse.position
        dx = mouse_x - last_mouse_x
        if dx != 0:
            current_angle = (current_angle + ROTATION_SENSITIVITY * dx) % 360
            last_mouse_x = mouse_x

        # check confirm (mouse left click OR spacebar)
        mouse_left = exp.mouse.check_button_pressed(0)
        if mouse_left:
            reported_orientation = current_angle
            response_done = True

    # --------------------------------------------------------
    # 7. Compute error
    #
    # Important detail: a bar at 10° looks identical to a bar at 190°.
    # So orientation is axial, not directional. We work modulo 180
    # and then fold into [0,90].
    #
    # offset = absolute error (deg) between their report and truth
    # --------------------------------------------------------
    def axial_abs_diff(a, b):
        raw = abs(a - b) % 180
        return min(raw, 180 - raw)

    offset = axial_abs_diff(reported_orientation, target_true_ori)

    # --------------------------------------------------------
    # 8. Feedback
    # Just tell them their error on that trial.
    # --------------------------------------------------------
    feedback_msg = make_feedback_text(
        text=f"Error: {offset:.1f}°",
        color=constants.C_BLACK,
        font_size=24
    )
    present_for_ms(exp, [feedback_msg], FEEDBACK_DURATION_MS)

    # --------------------------------------------------------
    # 9. Return trial data for logging
    # --------------------------------------------------------
    return {
        "cue_type": cue_type,
        "delay": cue_probe_delay_ms,
        "true_orientation": float(target_true_ori),
        "reported_orientation": float(reported_orientation),
        "offset": float(offset),
    }

# ============================================================
# --- MAIN EXPERIMENT ENTRY POINT ---
# This sets up expyriment, runs all trials, and logs data.
# ============================================================

def main():
    # neutral gray background, black text/stim lines
    BG_GRAY = (128, 128, 128)

    exp = design.Experiment(
        name="retro_cue_task_fixed_layout",
        background_colour=BG_GRAY,
        foreground_colour=constants.C_BLACK
    )

    control.initialize(exp)

    # If you want dev mode (windowed, fast, etc.), uncomment:
    # control.set_develop_mode()

    # define what columns we will save in expyriment's data file
    exp.data_variable_names = [
        "cue_type",
        "cue_probe_delay_ms",
        "true_orientation_deg",
        "reported_orientation_deg",
        "offset_abs_error_deg"
    ]

    # build randomized trial list
    all_trials = build_trial_list()

    # optional: practice trials before we start recording data
    # for _ in range(5): # replace with number of practice trials
    #     t = random.choice(all_trials)
    #     run_single_trial(exp, t["cue_type"], t["delay"])

    control.start(subject_id=1)

    for t in all_trials:
        result = run_single_trial(exp, t["cue_type"], t["delay"])
        exp.data.add([
            result["cue_type"],
            result["delay"],
            result["true_orientation"],
            result["reported_orientation"],
            result["offset"]
        ])

    control.end()


if __name__ == "__main__":
    main()
