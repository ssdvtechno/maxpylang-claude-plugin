---
name: maxpylang
description: Build, edit and lint Max/MSP/Jitter patches (.maxpat) and Max for Live devices (.amxd) from Python using the MaxPyLang library. Use whenever the user wants a Max patch, an MSP synth or effect, a Jitter video patch, a Max for Live instrument / audio effect / MIDI effect, wants to "vibecode" Max, generate or mass-place/mass-connect Max objects programmatically, modify an existing .maxpat/.amxd, or asks which Max object or inlet does something.
---

# MaxPyLang: Max patches from Python

MaxPyLang (`pip install maxpylang`, MIT, Barnard PL Labs) writes Max's patcher JSON from Python.
You write a short **build script**, run it, lint the output, iterate. The user opens the result in Max
or drops the `.amxd` on a Live track. Max itself is **not** needed to generate patches.

Paths below are relative to this skill's base directory (shown when the skill loads), referred to as `$SKILL`.

| File | Use |
|---|---|
| `$SKILL/scripts/mpl.py` | Safety layer over MaxPyLang. **Copy next to every build script and use it.** |
| `$SKILL/scripts/maxref.py` | Object lookup: inlets/outlets/args/attrs, search by function, typo check. |
| `$SKILL/scripts/inspect_patch.py` | Summarize + lint any `.maxpat`/`.amxd` (also user-supplied ones). |
| `$SKILL/references/recipes.md` | Tested build scripts: synth, sequencer, additive, abstraction, Jitter, M4L devices, editing. |
| `$SKILL/references/m4l.md` | Max for Live rules, `live.*` parameters, device I/O. |
| `$SKILL/references/api.md` | Raw MaxPyLang API + its known bugs (read before using `patch.place` directly). |

## Workflow

1. **Environment.** `python3 -c "import maxpylang"`. If missing, create/use a venv in the project and install
   from GitHub: `pip install "git+https://github.com/Barnard-PL-Labs/MaxPyLang.git"` (Python 3.9+).
   PyPI's `maxpylang` 0.1.1 is older (no `.amxd` save, no stubs, no `abstraction=`); `mpl` works with both,
   the raw-API notes in `references/api.md` assume the GitHub version.
   Ignore its `SyntaxWarning: invalid escape sequence` noise.
2. **Design the signal flow first** in a few lines (source -> processing -> output, control paths, init).
3. **Look up every object you are unsure of** before writing code. Never guess inlet/outlet indices:
   ```bash
   python3 "$SKILL/scripts/maxref.py" lores~ adsr~ "pack 0 0"     # cards
   python3 "$SKILL/scripts/maxref.py" -s reverb                   # find by function
   python3 "$SKILL/scripts/maxref.py" -c cycle~ metro zl.lookup   # typo check
   ```
4. **Write `build_<name>.py`** with `mpl` (skeleton below). Copy `mpl.py` beside it:
   `cp "$SKILL/scripts/mpl.py" .`
5. **Run it, then lint**: `python3 build_<name>.py && python3 "$SKILL/scripts/inspect_patch.py" <out>.maxpat`.
   Fix every ERROR; review WARN (overlaps, signal into control inlet, missing clip~ ...). Repeat.
6. **Report**: file path, what it does, how to use it (e.g. "click the ezdac~ to turn audio on, toggle the
   metro"), and anything the user must provide (sample files, js files, abstractions next to the patch).
   Keep the build script: it *is* the source of the patch.

## Skeleton

```python
import maxpylang as mp
import mpl  # copied from $SKILL/scripts/mpl.py

p = mp.MaxPatch(verbose=False)
X, Y, STEP = 30, 30, 40

mpl.comment(p, "=== SOURCE ===", X, Y)
osc  = mpl.at(p, "cycle~ 220", X, Y + 30)
gain = mpl.at(p, "*~ 0.2", X, Y + 30 + STEP)      # never send full-scale to the DAC
dac  = mpl.at(p, "ezdac~", X, Y + 30 + 2 * STEP)  # click to start audio
mpl.chain(p, osc, gain, dac)                       # out0 -> in0 down the list
mpl.wire(p, (gain, 0, dac, 1))                     # (src, outlet, dst, inlet)

mpl.save(p, "tone.maxpat")                         # or device_type="instrument" for .amxd
```

## mpl cheat sheet

| Call | Notes |
|---|---|
| `at(p, "text", x, y)` | One object at exact top-left (x, y). Box text exactly as typed in Max, incl. `@attr val`. Raises on unknown names with suggestions. Auto-handles `s/r/i/f/del/v`, `live.*`, `comment`, `message`, and objects MaxPyLang mis-validates (`metro 4n`, `expr ...`, `switch 3`, `dac~ 1 2 3 4`, `send`, `noteout` ...). `io=(ins, outs)` forces a raw box. |
| `comment(p, text, x, y)` / `message(p, text, x, y)` | Verbatim text (Max dollar args, commas, `;` OK). |
| `ui(p, "live.dial", x, y)` | UI boxes MaxPyLang lacks; builds correct `maxclass` JSON. |
| `extern(p, "text", x, y, ins, outs)` | Third-party externals, `p name` subpatchers, anything with known I/O. |
| `wire(p, (a, o, b, i), ...)` / `chain(p, a, b, c)` | Bounds-checked; duplicate cords skipped. |
| `live_param(obj, "Name", mmin=, mmax=, initial=, unitstyle="hz", enum=[...])` | Makes a `live.*` box a saved, automatable Live parameter. |
| `save(p, path, device_type=None)` | Validates (dup ids, bad xlet indices, placeholders) before writing. |

Objects returned are MaxPyLang `MaxObject`s: `obj.ins[i]`, `obj.outs[i]`, `obj.name`, `obj._dict["box"]`.

## Max semantics you must get right

- **Hot/cold inlets**: only the leftmost inlet triggers output; others just store. Feed cold inlets *before* the hot one.
- **Right-to-left order**: an object with several outlets fires rightmost first. When one value fans out to
  several places and order matters, use `trigger` (`t b f`, `t i i`) instead of fanning a cord.
- **Signal vs control**: `~` objects carry audio. Float into a `*~` right inlet sets the multiplier; a signal
  cord into a control-only inlet is an error (the linter flags it). Use `sig~` to turn numbers into signal,
  `snapshot~` for the reverse, `line~` for click-free ramps.
- Several signal cords into one inlet **sum**. Several control cords do **not** sum.
- **Initialization**: `loadbang` -> messages, or `loadmess <value>`, so the patch starts in a sane state.
- **Audio safety**: put a `*~ 0.1`-`0.3` gain (or `gain~`/`live.gain~`) before output; in M4L always
  `clip~ -1. 1.` before `plugout~`. Connect both DAC channels for stereo.
- **Timing**: `metro <ms>` / `qmetro` (Jitter) for clocks; `counter min max` for steps; `delay`/`pipe` for one-shots.
- **Wireless**: `send name`/`receive name` (control) and `send~`/`receive~` (signal) avoid long cords.
- **Files**: `buffer~ name file.wav`, `js script.js`, abstractions `name.maxpat` must sit next to the patch
  (or in Max's search path). Tell the user.

## Layout conventions

- Explicit coordinates for every object. Flow top-to-bottom (`y` grows down), ~40 px between chained objects,
  80 px between sections, 120-160 px between parallel columns (`x = X0 + i * COL` in loops).
- Section headers via `mpl.comment(p, "=== NAME ===", x, y)`; short labels 20 px above controls.
- `loadbang`/init and UI controls to the right of the main chain; group `wire` calls per section.
- After saving, `inspect_patch.py` reports overlapping boxes; fix them.

## Editing an existing patch

```python
p = mpl.load("in.maxpat")                       # .amxd works too; ids renumbered obj-1..N
for oid, o in p.objs.items():
    print(oid, o._dict["box"].get("text", o.name))
oid, osc = mpl.find(p, "cycle~")[0]             # [(id, obj)] by class and/or text=
mpl.replace(p, oid, "saw~ 220")                 # keeps position and the cords that still fit
mpl.delete(p, "obj-7")                          # also removes its cords
new = mpl.at(p, "lores~ 800 0.5", 300, 200)
mpl.save(p, "out.maxpat")
```
Run `inspect_patch.py in.maxpat --graph` first to understand an unfamiliar patch. Objects MaxPyLang
does not know load as unknowns but keep their JSON and cords, so round-trips are safe.

## Don'ts (MaxPyLang quirks that `mpl` avoids)

- Don't place `maxpylang.objects` stubs (`cycle_tilde` ...) more than once: they are shared singletons,
  the second placement duplicates the box id. Prefer strings.
- Don't use `patch.place("comment ...")`: the text becomes "comment ...". Use `mpl.comment`.
- Don't rely on `patch.place` grid placement: it offsets x by +80 and `y=0` becomes 80.
- Don't `patch.place` unknown objects: all unknowns share one JSON dict (same id + text). `mpl.at` raises instead.
- Don't use `mp.MaxPatch(load_file=...)` on patches saved by Max: it crashes (`KeyError: 'text'`) on UI
  boxes. `mpl.load` works on any `.maxpat`/`.amxd`.
- `place()` always returns a list; raw `connect()` takes `[outlet, inlet]` pairs.

Details and the raw API: `references/api.md`. Max for Live: `references/m4l.md`. Worked examples: `references/recipes.md`.
