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
- `live.thisdevice` (outlet 0 bangs when the device is loaded) is the M4L-safe `loadbang`; place with
  `mpl.extern(p, "live.thisdevice", x, y, 1, 3)`.
- The Live API (`live.path`, `live.object`, `live.observer`) is outside MaxPyLang's database: use
  `mpl.extern` with the I/O counts from the Max reference.

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

Built-in I/O (curated, verify in Max if a cord fails):

| object | in | out | outlet meaning |
|---|---|---|---|
| live.dial / live.slider / live.numbox | 1 | 2 | value, normalized 0-1 |
| live.toggle / live.button | 1 | 1 | 0/1, bang |
| live.menu | 1 | 3 | index, item symbol, normalized |
| live.text | 1 | 2 | value, text |
| live.gain~ | 2 | 5 | L, R signals, then dB value and meter info |

## Signal-flow templates

```
instrument:   notein -> mtof -> osc~ -> vca (*~ env) -> clip~ -1. 1. -> plugout~ L+R
                     \-> velocity / 127. -> adsr~ ---^
audio_effect: plugin~ L/R -> processing per channel (loop in Python) -> clip~ -> plugout~ L/R
midi_effect:  midiin -> midiparse -0-> unpack 0 0 -> (process) -> pack 0 0 -> midiformat -> midiout
                        midiparse outlets 1..5 -> midiformat inlets 1..5 (pass-through)
```

Full working scripts: `recipes.md` sections 6-8.

## Loading / round-tripping

`mpl.load("device.amxd")` reads the JSON; save again with the same `device_type`. To see a device's
type without Python: `inspect_patch.py device.amxd` prints `M4L <type>`.
