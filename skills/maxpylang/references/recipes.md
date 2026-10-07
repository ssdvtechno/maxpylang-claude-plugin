# Recipes

Every script below runs as-is with `mpl.py` copied next to it, and lints clean with `inspect_patch.py`.
Adapt them; don't paste blindly. Check unfamiliar objects with `maxref.py` first.

Contents: 1 MIDI keyboard synth · 2 step sequencer · 3 additive synth (loops) · 4 abstraction ·
5 Jitter noise · 6 M4L stereo delay · 7 M4L transposer · 8 M4L instrument · 9 editing a patch ·
10 random/generative patch · 11 polyphonic synth (poly~) · 12 gen~ waveshaper · 13 js note picker ·
14 M4L tempo-synced tremolo (Live API) · 15 Jitter OpenGL torus

## 1. Keyboard synth with ADSR

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== KEYBOARD SYNTH: click ezdac~, play the keys ===", 30, 10)

kb   = mpl.at(p, "kslider", 30, 40)
mtof = mpl.at(p, "mtof", 30, 110)
vel  = mpl.at(p, "/ 127.", 200, 110)          # velocity 0..1, 0 = note off -> release
osc  = mpl.at(p, "saw~", 30, 150)
filt = mpl.at(p, "lores~ 1200 0.6", 30, 190)
env  = mpl.at(p, "adsr~ 10 150 0.6 400", 200, 150)
vca  = mpl.at(p, "*~", 30, 240)
vol  = mpl.at(p, "*~ 0.2", 30, 280)
dac  = mpl.at(p, "ezdac~", 30, 320)

mpl.wire(p,
    (kb, 1, vel, 0), (kb, 0, mtof, 0),
    (mtof, 0, osc, 0), (osc, 0, filt, 0), (filt, 0, vca, 0),
    (vel, 0, env, 0), (env, 0, vca, 1),
    (vca, 0, vol, 0), (vol, 0, dac, 0), (vol, 0, dac, 1),
)
mpl.save(p, "keyboard_synth.maxpat")
```

## 2. Step sequencer from a Python list

```python
import mpl

NOTES = [48, 55, 58, 60, 63, 60, 58, 55]          # edit in Python, regenerate

p = mpl.patch()
mpl.comment(p, "=== 8-STEP SEQUENCER: toggle to run ===", 30, 10)
tog   = mpl.at(p, "toggle", 30, 40)
clock = mpl.at(p, "metro 150", 30, 80)
step  = mpl.at(p, "counter 0 %d" % (len(NOTES) - 1), 30, 120)
look  = mpl.at(p, "zl.lookup", 30, 160)
init  = mpl.at(p, "loadmess " + " ".join(map(str, NOTES)), 200, 120)
num   = mpl.at(p, "number", 30, 200)
mtof  = mpl.at(p, "mtof", 30, 240)
osc   = mpl.at(p, "tri~", 30, 280)
trig  = mpl.at(p, "t b", 200, 240)
ramp  = mpl.message(p, "1 5 0 120", 200, 280)     # line~ pairs: go to 1 in 5 ms, then 0 in 120 ms
env   = mpl.at(p, "line~", 200, 320)
vca   = mpl.at(p, "*~", 30, 360)
vol   = mpl.at(p, "*~ 0.25", 30, 400)
dac   = mpl.at(p, "ezdac~", 30, 440)

mpl.chain(p, tog, clock, step, look, num, mtof, osc, vca, vol, dac)
mpl.wire(p,
    (init, 0, look, 1),                      # cold inlet: the note list
    (num, 0, trig, 0), (trig, 0, ramp, 0), (ramp, 0, env, 0), (env, 0, vca, 1),
    (vol, 0, dac, 1),
)
mpl.save(p, "step_sequencer.maxpat")
```

## 3. Additive synth: N partials generated in a loop

```python
import mpl

N, F0, COL = 8, 110, 90
p = mpl.patch()
mpl.comment(p, f"=== ADDITIVE: {N} partials of {F0} Hz ===", 30, 10)

mix = mpl.at(p, "*~ %.3f" % (0.5 / N), 30, 200)
for k in range(1, N + 1):
    x = 30 + (k - 1) * COL
    osc = mpl.at(p, f"cycle~ {F0 * k}", x, 60)
    amp = mpl.at(p, "*~ %.3f" % (1.0 / k), x, 110)   # 1/k amplitude -> saw-like spectrum
    mpl.wire(p, (osc, 0, amp, 0), (amp, 0, mix, 0))   # signals into one inlet sum
dac = mpl.at(p, "ezdac~", 30, 250)
mpl.wire(p, (mix, 0, dac, 0), (mix, 0, dac, 1))
mpl.save(p, "additive.maxpat")
```

## 4. Abstraction: generate a sub-patch, then use it N times

MaxPyLang detects an abstraction's inlets/outlets when `<name>.maxpat` exists in the **current working
directory** at build time. Build the child first, in the same folder as the parent.

```python
import mpl

# child: voice.maxpat  (inlet = MIDI pitch, outlet = signal)
v = mpl.patch()
i  = mpl.at(v, "inlet", 30, 20)
m  = mpl.at(v, "mtof", 30, 60)
o  = mpl.at(v, "rect~", 30, 100)
g  = mpl.at(v, "*~ 0.1", 30, 140)
out = mpl.at(v, "outlet", 30, 180)
mpl.chain(v, i, m, o, g, out)
mpl.save(v, "voice.maxpat")

# parent: a chord of voices
p = mpl.patch()
chord = [60, 64, 67, 71]
dac = mpl.at(p, "ezdac~", 30, 200)
for n, pitch in enumerate(chord):
    x = 30 + n * 110
    lm = mpl.at(p, f"loadmess {pitch}", x, 40)
    vc = mpl.at(p, "voice", x, 100)          # resolved from ./voice.maxpat: 1 in, 1 out
    mpl.wire(p, (lm, 0, vc, 0), (vc, 0, dac, 0), (vc, 0, dac, 1))
mpl.save(p, "chord.maxpat")
```
Ship `voice.maxpat` together with `chord.maxpat`. For `poly~ voice 8` use
`mpl.extern(p, "poly~ voice 8", x, y, ins, outs)` with the counts of `in`/`out~` objects in the voice patch.

## 5. Jitter: animated noise in a window

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== JITTER NOISE: toggle on ===", 30, 10)
tog   = mpl.at(p, "toggle", 30, 40)
clock = mpl.at(p, "qmetro 33", 30, 80)
noise = mpl.at(p, "jit.noise 4 char 64 48", 30, 120)
win   = mpl.at(p, "jit.pwindow", 30, 170)
mpl.chain(p, tog, clock, noise, win)
mpl.save(p, "jitter_noise.maxpat")
```

## 6. Max for Live audio effect: stereo feedback delay

Python loops build both channels identically. See `m4l.md` for parameter details.

```python
import mpl

p = mpl.patch()
src = mpl.at(p, "plugin~", 30, 30)
out = mpl.at(p, "plugout~", 30, 400)

time = mpl.ui(p, "live.dial", 400, 30)
mpl.live_param(time, "Time", mmin=1., mmax=2000., initial=375., unitstyle="ms")
fb = mpl.ui(p, "live.dial", 460, 30)
mpl.live_param(fb, "Feedback", mmin=0., mmax=0.95, initial=0.4, unitstyle="float")
mix = mpl.ui(p, "live.dial", 520, 30)
mpl.live_param(mix, "Mix", mmin=0., mmax=1., initial=0.35, unitstyle="float")
mpl.face(time, fb, mix)                          # what Live shows in the device strip

for ch in (0, 1):
    x = 30 + ch * 180
    tin  = mpl.at(p, "tapin~ 2000", x, 100)
    tout = mpl.at(p, "tapout~ 375", x, 140)
    fbk  = mpl.at(p, "*~ 0.4", x + 90, 180)      # feedback gain
    wet  = mpl.at(p, "*~ 0.35", x, 220)          # wet level
    clip = mpl.at(p, "clip~ -1. 1.", x, 340)
    mpl.wire(p,
        (src, ch, tin, 0), (tin, 0, tout, 0),
        (tout, 0, fbk, 0), (fbk, 0, tin, 0),     # feedback loop through tapin~
        (tout, 0, wet, 0), (wet, 0, clip, 0),
        (src, ch, clip, 0),                      # dry + wet sum in clip~'s inlet
        (clip, 0, out, ch),
        (time, 0, tout, 0), (fb, 0, fbk, 1), (mix, 0, wet, 1),
    )
mpl.save(p, "stereo_delay.amxd", device_type="audio_effect")
```

## 7. Max for Live MIDI effect: transposer

```python
import mpl

p = mpl.patch()
inp   = mpl.at(p, "midiin", 30, 30)
parse = mpl.at(p, "midiparse", 30, 70)
unp   = mpl.at(p, "unpack 0 0", 30, 110)
add   = mpl.at(p, "+ 0", 30, 150)
pk    = mpl.at(p, "pack 0 0", 30, 190)
fmt   = mpl.at(p, "midiformat", 30, 300)
outp  = mpl.at(p, "midiout", 30, 340)
semi  = mpl.ui(p, "live.dial", 300, 30)
mpl.live_param(semi, "Transpose", ptype="int", mmin=-24, mmax=24, initial=0, unitstyle="semitones")
mpl.face(semi)

mpl.wire(p,
    (inp, 0, parse, 0), (parse, 0, unp, 0),
    (unp, 1, pk, 1),                 # velocity -> cold inlet first (right-to-left)
    (unp, 0, add, 0), (add, 0, pk, 0), (pk, 0, fmt, 0),
    (semi, 0, add, 1),
    (fmt, 0, outp, 0),
)
for k in range(1, 6):                # pass poly pressure, CC, program, aftertouch, bend through
    mpl.wire(p, (parse, k, fmt, k))
mpl.save(p, "transposer.amxd", device_type="midi_effect")
```
Note: changing the dial while notes are held can leave hanging notes (note-off gets a different pitch).

## 8. Max for Live instrument: mono synth

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== MIDI ===", 30, 10)
note = mpl.at(p, "notein", 30, 40)
mtof = mpl.at(p, "mtof", 30, 80)
vel  = mpl.at(p, "/ 127.", 160, 80)
mpl.comment(p, "=== VOICE ===", 30, 120)
osc  = mpl.at(p, "saw~", 30, 150)
filt = mpl.at(p, "lores~ 1500 0.5", 30, 190)
env  = mpl.at(p, "adsr~ 5 200 0.5 300", 160, 150)
vca  = mpl.at(p, "*~", 30, 240)
mpl.comment(p, "=== OUT ===", 30, 280)
clip = mpl.at(p, "clip~ -1. 1.", 30, 310)
out  = mpl.at(p, "plugout~", 30, 350)
cut  = mpl.ui(p, "live.dial", 300, 150)
mpl.live_param(cut, "Cutoff", mmin=50., mmax=12000., initial=1500., unitstyle="hz", exponent=3.)
mpl.face(cut)

mpl.wire(p,
    (note, 0, mtof, 0), (note, 1, vel, 0),
    (mtof, 0, osc, 0), (osc, 0, filt, 0), (filt, 0, vca, 0),
    (vel, 0, env, 0), (env, 0, vca, 1),
    (cut, 0, filt, 1),
    (vca, 0, clip, 0), (clip, 0, out, 0), (clip, 0, out, 1),
)
mpl.save(p, "mono_synth.amxd", device_type="instrument")
```

## 9. Edit an existing patch

```python
import mpl

p = mpl.load("keyboard_synth.maxpat")              # ids renumbered obj-1..obj-N
for oid, o in p.objs.items():
    print(oid, o._dict["box"].get("text", o.name))

osc_id, _ = mpl.find(p, "saw~")[0]
mpl.replace(p, osc_id, "rect~")                    # same spot, cords kept
_, dac = mpl.find(p, "ezdac~")[0]
x, y = dac._dict["box"]["patching_rect"][:2]
scope = mpl.at(p, "scope~", x + 120, y)
_, vol = mpl.find(p, "*~", text="0.2")[0]          # the "*~ 0.2" volume stage
mpl.wire(p, (vol, 0, scope, 0))
mpl.save(p, "keyboard_synth_v2.maxpat")
```
Inspect first (`inspect_patch.py file --graph`) to see ids and flow. `replace()` keeps only cords whose
inlet/outlet index exists on the new object. `mpl.delete(p, "obj-4", ...)` removes objects and their cords.

## 10. Random / generative patch

```python
import random
import mpl

random.seed(7)
p = mpl.patch()
dac = mpl.at(p, "ezdac~", 30, 400)
sumr = mpl.at(p, "*~ 0.05", 30, 360)
for k in range(12):
    x, f = 30 + k * 90, random.choice([110, 165, 220, 330, 440, 660])
    lfo = mpl.at(p, "cycle~ %.2f" % random.uniform(0.05, 0.5), x, 60)
    dep = mpl.at(p, "*~ 0.5", x, 100)
    off = mpl.at(p, "+~ 0.5", x, 140)
    osc = mpl.at(p, f"cycle~ {f}", x, 200)
    vca = mpl.at(p, "*~", x, 260)
    mpl.wire(p, (lfo, 0, dep, 0), (dep, 0, off, 0), (off, 0, vca, 1),
                (osc, 0, vca, 0), (vca, 0, sumr, 0))
mpl.wire(p, (sumr, 0, dac, 0), (sumr, 0, dac, 1))
mpl.save(p, "drone_field.maxpat")
```

## 11. Polyphonic synth with poly~

Build the voice first (same folder), then `mpl.poly` reads its `in`/`out~` objects for the I/O.

```python
import mpl

# voice.maxpat: gets "pitch velocity" lists, one voice per note
v = mpl.patch()
inp  = mpl.at(v, "in 1", 30, 20)
unp  = mpl.at(v, "unpack 0 0", 30, 60)
mtof = mpl.at(v, "mtof", 30, 100)
vel  = mpl.at(v, "/ 127.", 160, 100)
osc  = mpl.at(v, "saw~", 30, 140)
filt = mpl.at(v, "lores~ 2000 0.4", 30, 180)
env  = mpl.at(v, "adsr~ 5 150 0.6 400", 160, 140)
vca  = mpl.at(v, "*~", 30, 230)
out  = mpl.at(v, "out~ 1", 30, 270)
busy = mpl.at(v, "thispoly~", 300, 190)        # adsr~ mute outlet frees the voice after release
mpl.wire(v, (inp, 0, unp, 0), (unp, 0, mtof, 0), (unp, 1, vel, 0), (mtof, 0, osc, 0),
            (osc, 0, filt, 0), (filt, 0, vca, 0), (vel, 0, env, 0), (env, 0, vca, 1),
            (env, 2, busy, 0), (vca, 0, out, 0))
mpl.save(v, "polyvoice.maxpat")

# parent: notes from a MIDI keyboard -> 8 voices
p = mpl.patch()
mpl.comment(p, "=== POLY SYNTH: click ezdac~, play a MIDI keyboard ===", 30, 10)
note = mpl.at(p, "notein", 30, 40)
pk   = mpl.at(p, "pack 0 0", 30, 120)
pre  = mpl.at(p, "prepend midinote", 30, 160)
syn  = mpl.poly(p, "polyvoice", 8, 30, 200)     # poly~ polyvoice 8: 1 inlet, 1 signal outlet
vol  = mpl.at(p, "*~ 0.15", 30, 240)
dac  = mpl.at(p, "ezdac~", 30, 280)
mpl.wire(p, (note, 1, pk, 1), (note, 0, pk, 0),          # velocity (cold) first, then pitch
            (pk, 0, pre, 0), (pre, 0, syn, 0), (syn, 0, vol, 0), (vol, 0, dac, 0), (vol, 0, dac, 1))
mpl.save(p, "poly_synth.maxpat")
```
Note-offs (velocity 0) reach the voice playing that pitch, so notes release properly. A `kslider`
only sends note-offs in polyphonic mode (`@mode 1`).

## 12. gen~ waveshaper (GenExpr codebox)

`mpl.gen` embeds the code in a gen~ box; in1..inN / out1..outN in the code set its inlets/outlets.

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== GEN~ WAVESHAPER: drive 0..1 ===", 30, 10)
osc   = mpl.at(p, "cycle~ 110", 30, 40)
drive = mpl.at(p, "flonum", 200, 40)
init  = mpl.at(p, "loadmess 0.4", 300, 40)
shape = mpl.gen(p, "gain = 1 + in2 * 20;\nout1 = tanh(in1 * gain) / tanh(gain);", 30, 90)
vol   = mpl.at(p, "*~ 0.2", 30, 140)
dac   = mpl.at(p, "ezdac~", 30, 180)
mpl.wire(p, (init, 0, drive, 0), (osc, 0, shape, 0), (drive, 0, shape, 1),
            (shape, 0, vol, 0), (vol, 0, dac, 0), (vol, 0, dac, 1))
mpl.save(p, "waveshaper.maxpat")
```

## 13. js: note picker written in JavaScript

`mpl.js` writes the .js file next to the patch; `inlets`/`outlets` in the code set the box I/O.

```python
import mpl

CODE = """inlets = 1;
outlets = 1;
var scale = [0, 2, 4, 7, 9, 12];
function bang() {
    outlet(0, 60 + scale[Math.floor(Math.random() * scale.length)]);
}
"""
p = mpl.patch()
mpl.comment(p, "=== JS NOTE PICKER: click ezdac~, toggle ===", 30, 10)
tog   = mpl.at(p, "toggle", 30, 40)
clock = mpl.at(p, "metro 200", 30, 80)
pick  = mpl.js(p, "pentapick.js", CODE, 30, 120)
mtof  = mpl.at(p, "mtof", 30, 160)
osc   = mpl.at(p, "tri~", 30, 200)
vol   = mpl.at(p, "*~ 0.2", 30, 240)
dac   = mpl.at(p, "ezdac~", 30, 280)
mpl.chain(p, tog, clock, pick, mtof, osc, vol, dac)
mpl.wire(p, (vol, 0, dac, 1))
mpl.save(p, "js_picker.maxpat")
```
Ship `pentapick.js` with the patch.

## 14. Max for Live: tempo-synced tremolo (Live API)

`live.thisdevice` fires when the device is ready; `live.path` finds the Live Set and
`live.observer` reports its tempo whenever it changes. One LFO cycle per beat = tempo / 60 Hz.

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== TEMPO FOLLOW ===", 300, 10)
ready = mpl.at(p, "live.thisdevice", 300, 40)
path  = mpl.message(p, "path live_set", 300, 80)
prop  = mpl.message(p, "property tempo", 450, 80)
lp    = mpl.at(p, "live.path", 300, 120)
obs   = mpl.at(p, "live.observer", 450, 160)
hz    = mpl.at(p, "/ 60.", 450, 200)
mpl.wire(p, (ready, 0, path, 0), (ready, 0, prop, 0), (path, 0, lp, 0),
            (lp, 0, obs, 1), (prop, 0, obs, 0), (obs, 0, hz, 0))

mpl.comment(p, "=== TREMOLO ===", 30, 230)
lfo   = mpl.at(p, "cycle~ 2.", 450, 260)
depth = mpl.ui(p, "live.dial", 600, 230)
mpl.live_param(depth, "Depth", mmin=0., mmax=1., initial=0.5, unitstyle="float")
amt   = mpl.at(p, "*~ 0.25", 450, 300)            # +-depth/2 around 1 - depth/2
half  = mpl.at(p, "* 0.5", 600, 300)
inv   = mpl.at(p, "!- 1.", 600, 340)
off   = mpl.at(p, "+~ 0.75", 450, 340)
scale = mpl.at(p, "* 0.5", 700, 300)
src   = mpl.at(p, "plugin~", 30, 260)
out   = mpl.at(p, "plugout~", 30, 460)
mpl.wire(p, (hz, 0, lfo, 0), (lfo, 0, amt, 0), (amt, 0, off, 0),
            (depth, 0, scale, 0), (scale, 0, amt, 1),
            (depth, 0, half, 0), (half, 0, inv, 0), (inv, 0, off, 1))
for ch in (0, 1):
    x = 30 + ch * 140
    vca  = mpl.at(p, "*~", x, 380)
    clip = mpl.at(p, "clip~ -1. 1.", x, 420)
    mpl.wire(p, (src, ch, vca, 0), (off, 0, vca, 1), (vca, 0, clip, 0), (clip, 0, out, ch))
mpl.face(depth)
mpl.save(p, "tempo_tremolo.amxd", device_type="audio_effect")
```
Gain = 1 - depth/2 + (depth/2) * LFO, so depth 0 is bypass and depth 1 swings 0..1.

## 15. Jitter OpenGL: rotating torus

```python
import mpl

p = mpl.patch()
mpl.comment(p, "=== JITTER GL: toggle on, drag in the window to rotate ===", 30, 10)
tog    = mpl.at(p, "toggle", 30, 40)
world  = mpl.at(p, "jit.world torus @enable 0", 30, 80)
handle = mpl.at(p, "jit.gl.handle torus @auto_rotate 1", 300, 120)
shape  = mpl.at(p, "jit.gl.gridshape torus @shape torus @color 0.3 0.6 1. 1. @lighting_enable 1", 30, 160)
mpl.wire(p, (tog, 0, world, 0), (handle, 0, shape, 0))
mpl.save(p, "gl_torus.maxpat")
```
All three objects share the render context name `torus`; `jit.world` draws them on its own clock.

