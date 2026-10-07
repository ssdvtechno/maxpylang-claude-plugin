"""Max for Live stereo chorus: two LFO-modulated short delays (90 deg apart), wet/dry mix."""
import os
import sys

# mpl.py lives in the skill; normally it is copied next to the build script
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "maxpylang", "scripts"))
import mpl  # noqa: E402

BASE_MS = 15.0
p = mpl.patch()

mpl.comment(p, "=== STEREO CHORUS ===", 30, 5)
src = mpl.at(p, "plugin~", 30, 30)
out = mpl.at(p, "plugout~", 30, 420)

rate = mpl.ui(p, "live.dial", 440, 30)
mpl.live_param(rate, "Rate", mmin=0.05, mmax=5., initial=0.6, unitstyle="hz", exponent=2.)
depth = mpl.ui(p, "live.dial", 500, 30)
mpl.live_param(depth, "Depth", mmin=0., mmax=8., initial=3., unitstyle="ms")
mix = mpl.ui(p, "live.dial", 560, 30)
mpl.live_param(mix, "Mix", mmin=0., mmax=1., initial=0.5, unitstyle="float")
mpl.face(rate, depth, mix)                        # the three dials are the device's face in Live

for ch in (0, 1):
    x = 30 + ch * 200
    lfo  = mpl.at(p, "cycle~ 0.6", x + 100, 100)
    dep  = mpl.at(p, "*~ 3.", x + 100, 140)
    off  = mpl.at(p, f"+~ {BASE_MS}", x + 100, 180)
    tin  = mpl.at(p, "tapin~ 50", x, 140)
    tout = mpl.at(p, f"tapout~ {BASE_MS}", x, 220)
    wet  = mpl.at(p, "*~ 0.5", x, 260)
    clip = mpl.at(p, "clip~ -1. 1.", x, 340)
    if ch == 1:                                   # right LFO a quarter cycle ahead
        ph = mpl.at(p, "loadmess 0.25", x + 100, 60)
        mpl.wire(p, (ph, 0, lfo, 1))
    mpl.wire(p,
        (src, ch, tin, 0), (tin, 0, tout, 0),
        (lfo, 0, dep, 0), (dep, 0, off, 0), (off, 0, tout, 0),   # signal delay time
        (tout, 0, wet, 0), (wet, 0, clip, 0), (src, ch, clip, 0),
        (clip, 0, out, ch),
        (rate, 0, lfo, 0), (depth, 0, dep, 1), (mix, 0, wet, 1),
    )

mpl.save(p, "chorus.amxd", device_type="audio_effect")
