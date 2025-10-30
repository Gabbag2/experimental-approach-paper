import random
import numpy as np
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
)


########################################
# ========== CONSTANTS =================
########################################

# timing (ms)
FIXATION_DURATION_MS     = 300      # fixation cross
MEMORY_DURATION_MS       = 500      # memory array on screen
FIRST_BLANK_DELAY_MS     = 500      # blank before cue
CUE_DURATION_MS          = 100      # retro-cue on screen
CUE_PROBE_DELAYS_MS      = [50, 200, 350, 500, 650]  # variable delay after cue
PROBE_FEEDBACK_MS        = 1000     # feedback after response

# task structure
N_BARS                   = 4
REPEATS_PER_CONDITION    = 28       # per (cue_type x delay)
CUE_TYPES                = ["spatial", "color", "no_cue"]

# display geometry (now just fixed pixel layout)
# positions are around center (0,0)
BAR_POSITIONS_PX = [
    (-200, +200),   # top-left
    (+200, +200),   # top-right
    (-200, -200),   # bottom-left
    (+200, -200),   # bottom-right
]

# bar drawing parameters for our helper functions
BAR_SIZE_PX              = (110, 40)    # width x height, passed to make_oriented_colored_bar
PROBE_MARKER_SIZE_PX     = (120, 120)   # size for probe box / outline square

# feature sampling constraints
ORI_RANGE_DEG            = (1, 180)
COL_RANGE_DEG            = (1, 360)
ORI_MIN_SEP_DEG          = 30          # bars must differ in orientation by ≥30°
COL_MIN_SEP_DEG          = 60          # bars must differ in color hue by ≥60° on color wheel


########################################
# ========== UTILS =====================
########################################

def circular_distance(a, b, period):
    """Shortest distance on a circular scale (for hue)."""
    diff = abs(a - b) % period
    return min(diff, period - diff)

def sample_orientations(n, min_sep, lo, hi):
    """Pick n orientations [lo,hi] such that all are ≥min_sep apart."""
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(abs(cand - prev) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen

def sample_colors(n, min_sep, lo, hi):
    """Pick n hues [lo,hi] on 0-360 wheel, all ≥min_sep circular distance apart."""
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(circular_distance(cand, prev, 360) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen

def create_memory_array():
    """
    Build one memory array = list of 4 dicts:
    {pos:(x,y), ori_deg:θ, color_deg:hue}
    """
    orientations = sample_orientations(
        n=N_BARS,
        min_sep=ORI_MIN_SEP_DEG,
        lo=ORI_RANGE_DEG[0],
        hi=ORI_RANGE_DEG[1]
    )

    colors = sample_colors(
        n=N_BARS,
        min_sep=COL_MIN_SEP_DEG,
        lo=COL_RANGE_DEG[0],
        hi=COL_RANGE_DEG[1]
    )

    bars = []
    for i in range(N_BARS):
        bars.append({
            "pos": BAR_POSITIONS_PX[i],
            "ori_deg": orientations[i],
            "color_deg": colors[i],
        })
    return bars


########################################
# ========== SINGLE TRIAL ==============
########################################

def run_single_trial(exp, cue_type, cue_probe_delay_ms):
    """
    One full trial:
    fixation -> memory array -> blank -> retro-cue -> delay -> probe/response -> feedback

    Returns dict:
        cue_type,
        delay,
        true_orientation,
        reported_orientation,
        offset
    """

    exp.mouse.show_cursor()

    # 1. fixation
    fix_cross = stimuli.FixCross(
        size=(16, 16),
        line_width=2,
        colour=constants.C_BLACK,
        position=(0, 0)
    )
    present_for_ms(exp, fix_cross, FIXATION_DURATION_MS)

    # 2. memory array (4 colored, oriented bars)
    bars = create_memory_array()
    bar_stims = []
    for bar in bars:
        stim = make_oriented_colored_bar(
            position_px=bar["pos"],
            size_px=BAR_SIZE_PX,
            orientation_deg=bar["ori_deg"],
            color_id=bar["color_deg"]
        )
        bar_stims.append(stim)

    present_for_ms(exp, bar_stims, MEMORY_DURATION_MS)

    # 3. first retention delay (blank)
    present_for_ms(exp, [], FIRST_BLANK_DELAY_MS)

    # 4. retro-cue (spatial / color / none)
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
        cue_stim = make_color_cue_square(
            size_px=PROBE_MARKER_SIZE_PX,
            fill_color_id=target_color_deg
        )
        present_for_ms(exp, cue_stim, CUE_DURATION_MS)

    elif cue_type == "no_cue":
        present_for_ms(exp, [], CUE_DURATION_MS)

    else:
        raise ValueError(f"Unknown cue_type: {cue_type}")

    # 5. cue-probe delay (blank screen of variable length)
    present_for_ms(exp, [], cue_probe_delay_ms)

    # 6. probe + orientation report
    #
    # what we display during report:
    #   - an outline square at the target location
    #   - a rotatable bar at fixation (0,0)
    #
    # subject rotates with mouse (left-right) and confirms with left click or SPACE
    current_angle = 90.0  # initial orientation (deg)
    reported_orientation = None

    response_done = False
    last_mouse_x, _ = exp.mouse.position
    SENSITIVITY = 0.4  # deg per horizontal pixel

    while not response_done:
        outline_stim = make_outline_square(
            position_px=target_pos_px,
            size_px=PROBE_MARKER_SIZE_PX,
            color=constants.C_BLACK,
            line_width_px=2
        )

        probe_bar_stim = make_probe_bar(
            position_px=(0, 0),
            size_px=BAR_SIZE_PX,
            orientation_deg=current_angle,
            color=constants.C_BLACK
        )

        draw_now(exp, [outline_stim, probe_bar_stim])

        # mouse-based rotation
        mouse_x, _ = exp.mouse.position
        dx = mouse_x - last_mouse_x
        if dx != 0:
            current_angle = (current_angle + SENSITIVITY * dx) % 360
            last_mouse_x = mouse_x

        # confirm choice
        mouse_left = exp.mouse.check_button_pressed(1)
        space_down = exp.keyboard.check(constants.K_SPACE)
        if mouse_left or space_down:
            reported_orientation = current_angle
            response_done = True

    # 7. compute error
    # bars are symmetric every 180° (a bar at 10° looks like 190°),
    # so error is circular on 0..180 and folded to 0..90.
    def axial_abs_diff(a, b):
        raw = abs(a - b) % 180
        return min(raw, 180 - raw)

    offset = axial_abs_diff(reported_orientation, target_true_ori)

    # 8. feedback
    feedback_msg = make_feedback_text(
        text=f"Error: {offset:.1f}°",
        color=constants.C_BLACK,
        font_size=24
    )
    present_for_ms(exp, feedback_msg, PROBE_FEEDBACK_MS)

    # 9. return trial data
    return {
        "cue_type": cue_type,
        "delay": cue_probe_delay_ms,
        "true_orientation": float(target_true_ori),
        "reported_orientation": float(reported_orientation),
        "offset": float(offset)
    }


########################################
# ========== TRIAL SCHEDULE ============
########################################

def build_trial_list():
    """
    Full design:
    3 cue types × 5 delays × 28 reps = 420 trials
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


########################################
# ========== MAIN EXPERIMENT ==========
########################################

def main():
    GRAY = (128, 128, 128)

    exp = design.Experiment(
        name="retro_cue_task_fixed_layout",
        background_colour=GRAY,
        foreground_colour=constants.C_BLACK
    )

    control.initialize(exp)

    # windowed (dev mode). turn this off for actual data collection.
    #control.set_develop_mode()

    # define data columns
    exp.data_variable_names = [
        "cue_type",
        "cue_probe_delay_ms",
        "true_orientation_deg",
        "reported_orientation_deg",
        "offset_abs_error_deg"
    ]

    # build randomized trial order
    all_trials = build_trial_list()

    # (optional) practice trials before data logging
    # for _ in range(5):
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
