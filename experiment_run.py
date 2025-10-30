import math
import random
import numpy as np

from expyriment import design, control, stimuli
from expyriment.misc import constants

from drawing_and_timing import (
    present_for_ms,
    draw_now,
    calibrate_visual_geometry,
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
FIXATION_DURATION_MS     = 300
MEMORY_DURATION_MS       = 500
FIRST_BLANK_DELAY_MS     = 500
CUE_DURATION_MS          = 100
CUE_PROBE_DELAYS_MS      = [50, 200, 350, 500, 650]
PROBE_FEEDBACK_MS        = 1000  # feedback shown after response

# task structure
N_BARS                   = 4
REPEATS_PER_CONDITION    = 28    # per cue_type x delay
CUE_TYPES                = ["spatial", "color", "no_cue"]

# geometry (visual deg)
ECCENTRICITY_DEG         = 3.0                 # distance from fixation
BAR_SIZE_DEG             = (1.1, 0.4)          # bar length x height
PROBE_MARKER_SIZE_DEG    = (1.2, 1.2)          # probe box size

# sampling constraints
ORI_RANGE                = (1, 180)
COL_RANGE                = (1, 360)
ORI_MIN_SEP_DEG          = 30                  # min spacing between bars (deg)
COL_MIN_SEP_DEG          = 60                  # min spacing on color wheel

# physical screen (must be measured on the actual setup)
VIEWING_DISTANCE_MM      = 600   # 60 cm
SCREEN_WIDTH_MM          = 376   # visible width in mm


########################################
# ========== UTILS =====================
########################################

def circular_distance(a, b, period):
    """Shortest distance between a and b on a circular scale (e.g. color wheel)."""
    diff = abs(a - b) % period
    return min(diff, period - diff)

def sample_orientations(n, min_sep, lo, hi):
    """Pick n orientations that are at least min_sep apart."""
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(abs(cand - prev) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen

def sample_colors(n, min_sep, lo, hi):
    """Pick n hue values that are far apart on a 360° wheel."""
    chosen = []
    while len(chosen) < n:
        cand = random.randint(lo, hi)
        if all(circular_distance(cand, prev, 360) >= min_sep for prev in chosen):
            chosen.append(cand)
    return chosen

def get_bar_positions(exp):
    """
    Return the 4 fixed positions (square around fixation).
    Positions are at ~3° eccentricity.
    """
    e_px = exp.deg2px(ECCENTRICITY_DEG)
    return [
        (-e_px, +e_px),  # top-left
        (+e_px, +e_px),  # top-right
        (-e_px, -e_px),  # bottom-left
        (+e_px, -e_px),  # bottom-right
    ]

def create_memory_array(exp):
    """
    Build one memory display = 4 bars (pos, ori, color).
    """
    orientations = sample_orientations(
        n=N_BARS,
        min_sep=ORI_MIN_SEP_DEG,
        lo=ORI_RANGE[0],
        hi=ORI_RANGE[1]
    )

    colors = sample_colors(
        n=N_BARS,
        min_sep=COL_MIN_SEP_DEG,
        lo=COL_RANGE[0],
        hi=COL_RANGE[1]
    )

    positions = get_bar_positions(exp)

    bars = []
    for i in range(N_BARS):
        bars.append({
            "pos": positions[i],
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

    Returns dict with:
    cue_type, delay, true_orientation, reported_orientation, offset
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
    bars = create_memory_array(exp)

    bar_stims = []
    for bar in bars:
        stim = make_oriented_colored_bar(
            exp=exp,
            position_px=bar["pos"],
            size_deg=BAR_SIZE_DEG,
            orientation_deg=bar["ori_deg"],
            color_id=bar["color_deg"]
        )
        bar_stims.append(stim)

    present_for_ms(exp, bar_stims, MEMORY_DURATION_MS)

    # 3. first retention delay
    present_for_ms(exp, [], FIRST_BLANK_DELAY_MS)

    # 4. retro-cue (spatial / color / none)
    target_bar = random.choice(bars)
    target_pos_px    = target_bar["pos"]
    target_color_deg = target_bar["color_deg"]
    target_true_ori  = target_bar["ori_deg"]

    if cue_type == "spatial":
        cue_stims = make_spatial_cue_arrows(
            exp=exp,
            target_position_px=target_pos_px,
            color=constants.C_BLACK
        )
        present_for_ms(exp, cue_stims, CUE_DURATION_MS)

    elif cue_type == "color":
        cue_stim = make_color_cue_square(
            exp=exp,
            size_deg=PROBE_MARKER_SIZE_DEG,
            fill_color_id=target_color_deg
        )
        present_for_ms(exp, cue_stim, CUE_DURATION_MS)

    elif cue_type == "no_cue":
        present_for_ms(exp, [], CUE_DURATION_MS)

    else:
        raise ValueError(f"Unknown cue_type: {cue_type}")

    # 5. cue-probe delay (varies)
    present_for_ms(exp, [], cue_probe_delay_ms)

    # 6. probe + response
    #
    # what we show:
    #   - an outline square where the target was
    #   - a rotatable bar at fixation
    #
    # participant rotates the bar with the mouse (continuous 0..360),
    # then confirms with click or SPACE
    current_angle = 90.0  # start vertical-ish
    reported_orientation = None

    response_done = False
    last_mouse_x, _ = exp.mouse.position
    SENSITIVITY = 0.4  # deg per horizontal pixel

    while not response_done:
        outline_stim = make_outline_square(
            exp=exp,
            position_px=target_pos_px,
            size_deg=PROBE_MARKER_SIZE_DEG,
            color=constants.C_BLACK,
            line_width_px=2
        )

        probe_bar_stim = make_probe_bar(
            exp=exp,
            position_px=(0, 0),
            size_deg=BAR_SIZE_DEG,
            orientation_deg=current_angle,
            color=constants.C_BLACK
        )

        draw_now(exp, [outline_stim, probe_bar_stim])

        # mouse-based rotation
        mouse_x, mouse_y = exp.mouse.position
        dx = mouse_x - last_mouse_x
        if dx != 0:
            current_angle = (current_angle + SENSITIVITY * dx) % 360
            last_mouse_x = mouse_x

        # confirm
        mouse_left = exp.mouse.check_button_pressed(1)
        space_down = exp.keyboard.check(constants.K_SPACE)
        if mouse_left or space_down:
            reported_orientation = current_angle
            response_done = True

    # 7. error (remember: a bar flipped 180° is visually the same)
    def axial_abs_diff(a, b):
        """
        orientation error, modulo 180.
        range: [0, 90]
        """
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
        name="retro_cue_task",
        background_colour=GRAY,
        foreground_colour=constants.C_BLACK
    )

    control.initialize(exp)

    # dev mode = windowed etc.
    # for real data: set_develop_mode(False)
    control.set_develop_mode()

    # map deg -> px based on THIS monitor setup
    calibrate_visual_geometry(
        exp,
        screen_width_mm=SCREEN_WIDTH_MM,
        viewing_distance_mm=VIEWING_DISTANCE_MM
    )

    # data columns
    exp.data_variable_names = [
        "cue_type",
        "cue_probe_delay_ms",
        "true_orientation_deg",
        "reported_orientation_deg",
        "offset_abs_error_deg"
    ]

    # build trial order
    all_trials = build_trial_list()

    # (optional) practice block before recording data
    # for _ in range(5):
    #     t = random.choice(all_trials)
    #     run_single_trial(exp, t["cue_type"], t["delay"])

    control.start(subject_id=1)

    # run all trials
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
