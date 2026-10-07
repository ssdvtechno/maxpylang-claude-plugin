"""Generative arpeggiator: drunk walk over a pentatonic scale, random octave jumps, echo."""
import os
import sys

import maxpylang as mp

# mpl.py lives in the skill; normally it is copied next to the build script
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "maxpylang", "scripts"))
import mpl  # noqa: E402

SCALE = [0, 3, 5, 7, 10, 12, 15, 17]          # minor pentatonic degrees (semitones)
BASE, TEMPO = 48, 150                         # C3, ms per step

p = mp.MaxPatch(verbose=False)

mpl.comment(p, "=== CLOCK: click ezdac~ (bottom), then the toggle ===", 30, 10)
tog   = mpl.at(p, "toggle", 30, 40)
mpl.comment(p, "ms/step", 215, 42)
tempo = mpl.at(p, "number", 160, 40)
init  = mpl.at(p, f"loadmess {TEMPO}", 300, 40)
clock = mpl.at(p, f"metro {TEMPO}", 30, 80)
fork  = mpl.at(p, "t b b", 30, 120)

mpl.comment(p, "=== NOTE: walk the scale, random octave ===", 30, 150)
walk   = mpl.at(p, f"drunk {len(SCALE)} 2", 30, 180)
octave = mpl.at(p, "random 3", 200, 180)
times  = mpl.at(p, "* 12", 200, 220)
scale  = mpl.at(p, "zl.lookup", 30, 220)
notes  = mpl.at(p, "loadmess " + " ".join(map(str, SCALE)), 330, 180)
add_o  = mpl.at(p, "+ 0", 30, 260)
add_b  = mpl.at(p, f"+ {BASE}", 30, 300)
note   = mpl.at(p, "t f b", 30, 340)

mpl.comment(p, "=== VOICE ===", 30, 380)
mtof = mpl.at(p, "mtof", 30, 410)
env_msg = mpl.message(p, "1 3 0 180", 200, 410)
osc  = mpl.at(p, "rect~", 30, 450)
env  = mpl.at(p, "line~", 200, 450)
filt = mpl.at(p, "lores~ 1800 0.5", 30, 490)
vca  = mpl.at(p, "*~", 30, 530)
vol  = mpl.at(p, "*~ 0.2", 30, 570)

mpl.comment(p, "=== ECHO + OUT ===", 30, 610)
tin  = mpl.at(p, "tapin~ 1000", 200, 640)
tout = mpl.at(p, f"tapout~ {TEMPO * 3}", 200, 680)
wet  = mpl.at(p, "*~ 0.35", 200, 720)
dac  = mpl.at(p, "ezdac~", 30, 760)

# clock
mpl.wire(p, (tog, 0, clock, 0), (init, 0, tempo, 0), (tempo, 0, clock, 1), (clock, 0, fork, 0))
# t b b fires right-to-left: octave first (cold inlet of +), then the walk (hot inlet)
mpl.wire(p, (fork, 1, octave, 0), (octave, 0, times, 0), (times, 0, add_o, 1))
mpl.wire(p, (notes, 0, scale, 1), (fork, 0, walk, 0), (walk, 0, scale, 0),
            (scale, 0, add_o, 0), (add_o, 0, add_b, 0), (add_b, 0, note, 0))
# t f b: envelope trigger first, then pitch
mpl.wire(p, (note, 1, env_msg, 0), (env_msg, 0, env, 0), (note, 0, mtof, 0))
mpl.chain(p, mtof, osc, filt, vca, vol)
mpl.wire(p, (env, 0, vca, 1))
# output + echo
mpl.wire(p, (vol, 0, dac, 0), (vol, 0, dac, 1), (vol, 0, tin, 0),
            (tin, 0, tout, 0), (tout, 0, wet, 0), (wet, 0, dac, 0), (wet, 0, dac, 1))

mpl.save(p, "arpeggiator.maxpat")
