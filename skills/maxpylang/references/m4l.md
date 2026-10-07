# Max for Live devices (.amxd)

`.amxd` = the same patcher JSON as `.maxpat` in a small binary wrapper (`ampf` device-type chunk, `meta`,
`ptch` JSON). Save with `mpl.save(p, "name.amxd", device_type=...)`; `device_type` is required.

| device_type | Live track slot | Input | Output |
|---|---|---|---|
| `"instrument"` | MIDI track, instrument slot | `notein` (or `midiin` -> `midiparse`) | `plugout~` |
| `"audio_effect"` | after an instrument / audio track | `plugin~` (2 outlets L/R) | `plugout~` (2 inlets L/R) |
| `"midi_effect"` | before the instrument on a MIDI track | `midiin` -> `midiparse` | `midiformat` -> `midiout` |

## Rules

- No `ezdac~`, `dac~`, `adc~`: Live owns the audio engine. Use `plugin~` / `plugout~`.
- Always `clip~ -1. 1.` right before `plugout~`; connect both `plugout~` inlets.
- No master volume needed (Live's mixer); a wet/dry or output-gain parameter is fine.
- Controls the user should automate/save must be `live.*` objects with `mpl.live_param(...)`.
  Plain `dial`/`slider`/`number` work but are not saved with the Live set and can't be automated.
- Parameter long names must be unique within a device.
- Live's transport: `transport`, `metro 16n @quantize 16n` and `plugsync~` follow Live tempo.
- `live.thisdevice` (outlet 0 bangs when the device is loaded) is the M4L-safe `loadbang`.
- Live API objects (`live.thisdevice`, `live.path`, `live.object`, `live.observer`) aren't in MaxPyLang's
  database; `mpl.at` places them with the I/O counts below. Recipe 14 follows the Set's tempo.

## The device face (presentation view)

Live shows a device as a strip **169 px tall**. What appears there is the patch's *presentation view*;
without one, Live shows the patching layout cropped to that strip (cords and all). So every device needs:

```python
mpl.face(cutoff, reso, mix)          # left to right at y=10, 10 px apart
mpl.present(label, 10, 70)           # or place one box exactly (presentation coordinates)
```

`mpl.save(..., device_type=...)` then turns `openinpresentation` on and sets `devicewidth` to 0 (Live sizes
the device to its face). It warns if nothing is on the face. Check it with
`render_patch.py device.amxd --presentation`; `inspect_patch.py` warns about `live.*` controls left off the
face, boxes below the 169 px line, and overlaps.

## live.* parameters

```python
d = mpl.ui(p, "live.dial", x, y)
mpl.live_param(d, "Cutoff", mmin=20., mmax=18000., initial=1000., unitstyle="hz", exponent=3.)

m = mpl.ui(p, "live.menu", x, y)
mpl.live_param(m, "Shape", enum=["sine", "saw", "square"])        # outlet 0 = index

t = mpl.ui(p, "live.toggle", x, y)
mpl.live_param(t, "Bypass", ptype="int", mmin=0, mmax=1)
```

`live_param` writes `varname`, `parameter_enable: 1` and `saved_attribute_attributes.valueof`
(`parameter_longname`, `_shortname`, `_type` 0 float / 1 int / 2 enum, `_mmin`, `_mmax`, `_initial`,
`_initial_enable`, `_unitstyle`, `_exponent`, `_enum`).

unitstyle names: `int float ms hz db % pan semitones midi custom native`.
Note `%` shows the raw value with a % sign: use a 0-100 range with it, or `float` for 0-1.

I/O of the `live.*` objects. Counts checked against real Max-saved patches on GitHub
(e.g. 52 `live.dial`, 64 `live.toggle`, 26 `live.observer` boxes); `live.slider` follows `live.dial`.

| object | in | out | outlet meaning |
|---|---|---|---|
| live.dial / live.slider / live.numbox | 1 | 2 | value, normalized 0-1 |
| live.toggle / live.button | 1 | 1 | 0/1, bang |
| live.menu / live.tab | 1 | 3 | index, item symbol, normalized |
| live.text | 1 | 2 | value, text |
| live.gain~ | 2 | 5 | L, R signals, then dB value and meter info |
| live.thisdevice | 1 | 3 | bang when ready, device on/off, preview mode |
| live.path | 1 | 3 | id (follows), id (fixed), dumpout |
| live.object | 2 | 1 | results (inlets: get/set/call, object id) |
| live.observer | 2 | 2 | property value, dumpout (inlets: `property <name>`, object id) |

## Signal-flow templates

```
instrument:   notein -> mtof -> osc~ -> vca (*~ env) -> clip~ -1. 1. -> plugout~ L+R
                     \-> velocity / 127. -> adsr~ ---^
audio_effect: plugin~ L/R -> processing per channel (loop in Python) -> clip~ -> plugout~ L/R
midi_effect:  midiin -> midiparse -0-> unpack 0 0 -> (process) -> pack 0 0 -> midiformat -> midiout
                        midiparse outlets 1..5 -> midiformat inlets 1..5 (pass-through)
```

Full working scripts: `recipes.md` sections 6-8 and 14.

## Loading / round-tripping

`mpl.load("device.amxd")` reads the JSON; save again with the same `device_type`. To see a device's
type without Python: `inspect_patch.py device.amxd` prints `M4L <type>`.
