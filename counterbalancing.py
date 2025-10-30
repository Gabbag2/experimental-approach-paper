import itertools
import random

delay = [50 , 200, 350, 500, 650]
exp = ["spatial cue", "Color cue", "No cue"]
n_trials = 28


def counterbalanced(exp, delay):
    all_conditions = list(itertools.product(exp, delay))
    random.shuffle(all_conditions)
    return all_conditions



everything = counterbalanced(exp, delay)
print(f"Total permutations: {len(everything)}")
print(everything)