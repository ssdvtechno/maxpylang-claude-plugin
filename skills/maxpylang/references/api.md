# MaxPyLang raw API (and its quirks)

Prefer `mpl` helpers. Use the raw API when you need something `mpl` doesn't wrap. Source:
https://github.com/Barnard-PL-Labs/MaxPyLang · docs https://barnard-pl-labs.github.io/MaxPyLang/

## MaxPatch

```python
import maxpylang as mp
p = mp.MaxPatch(template=None, load_file=None, reorder=True, verbose=True)
```
- `template`: a `.maxpat` to start from (keeps its window size, settings, objects).
- `load_file`: existing `.maxpat`/`.amxd`; `reorder=True` renumbers ids `obj-1..N`. Crashes with
  `KeyError: 'text'` when a UI box has no `text` field, which is every toggle/number/dial/inlet saved by
  Max itself. `mpl.load` patches this.
- Properties: `p.objs` (dict id -> MaxObject), `p.num_objs`, `p.curr_position`, `p.get_json()` (patcher dict).

```python
p.place(*objs, randpick=False, num_objs=1, seed=None, weights=None,
        spacing_type="grid", spacing=[80., 80.], starting_pos=None, verbose=False) -> list[MaxObject]
```
- `objs`: strings (box text) or MaxObjects. Always returns a **list**.
- `num_objs=n`: n copies of each. `spacing_type`: `"grid"` (wraps at canvas width), `"vertical"` (spacing = number),
  `"custom"` (spacing = list of [x, y], one per object), `"random"` (broken, see below).
- Grid/vertical start one step *after* the cursor: `set_position(30, 100)` then a grid place lands at x=110.
  `y == 0` is bumped down one row. Use `"custom"` (what `mpl.at` does) for exact positions.
- `randpick=True` and `spacing_type="random"` are broken (use `np` without importing numpy). Randomize in Python with `random` and place with exact coordinates.
- Prints debug tuples to stdout on every call.

```python
p.connect([outlet, inlet], [outlet, inlet, [[mx, my], ...]], ..., verbose=True)
```
Each connection is a list `[obj.outs[i], obj.ins[j]]`, optional third element = cord midpoints. No type
checking; bad indices raise `IndexError`; duplicates are not detected.

```python
p.replace("obj-3", "saw~ 220", retain=True, **attribs)   # keeps position, common attribs, fitting cords
p.delete(objs=["obj-4"], cords=[[a.outs[0], b.ins[0]]])  # passing an unknown id crashes
p.set_position(x, y)
p.check()                                                # prints unknown / js / abstraction report
p.save("name.maxpat")                                    # appends .maxpat; prints check report
p.save("dev.amxd", device_type="instrument")             # or audio_effect / midi_effect
```

## MaxObject

```python
o = mp.MaxObject("metro 500 @active 1")                    # parsed + validated against the db
o = mp.MaxObject("my_abs", abstraction=True, inlets=2, outlets=1)   # declared abstraction / any box
o.name; o.ins[i]; o.outs[i]; o.notknown(); o._dict["box"]
o.edit(text_add="append" | "replace", text="...", **attribs)
o.move(x, y)
o.link("file.js")                                          # js objects / abstractions (file in cwd)
```
Inlet/Outlet: `.parent`, `.index`, `.types`, `Inlet.sources`, `Outlet.destinations`.

Validation rejects some valid Max text (`metro 4n`, any `expr`, `noteout`, `bendin`, `pgmin`, bare
`biquad~`) and some I/O counts are wrong (`send` has 0 inlets, `switch N` crashes, `selector~ N`,
`dac~ 1 2 3 4`, `join N`, `value`, `pv`). Abbreviations `s r i f del v s~ r~` are unknown. `mpl.at`
corrects all of these.

Unknown objects (typos, externals, `live.*` except via mpl) get 0 inlets/outlets and **share one dict**:
every unknown in a patch saves with the same id and text. Never save a raw patch containing unknowns.

`UnknownObjectWarning` (`maxpylang.exceptions`) is emitted for unknown names / bad args.

## Stubs

`from maxpylang.objects import cycle_tilde, ezdac_tilde, jit_movie, _2d_wave_tilde, in_` -
naming: `~` -> `_tilde`, `.`/`-` -> `_`, leading digit -> `_` prefix, keyword -> `_` suffix.
They are module-level singletons with no arguments; placing the same stub twice corrupts the patch.

## Abstractions and js

- A name with `<name>.maxpat` in the **current working directory** becomes an abstraction; I/O is read from
  its `inlet`/`outlet` objects.
- `js file.js`: if `file.js` is in cwd its `inlets = N` / `outlets = N` declarations set the box I/O.
- Ship these files next to the patch.

## Max for Live helpers

```python
from maxpylang import save_amxd, load_amxd, DEVICE_TYPES
save_amxd(p.get_json(), "dev.amxd", device_type="audio_effect")
d = load_amxd("dev.amxd")   # patcher dict
```

## Object database

- Vanilla max/msp/jit objects (~1000) ship in `maxpylang/data/OBJ_INFO/`. `mp.import_objs()` rebuilds it from a
  local Max install (Max must be open) and can add third-party packages.
- `maxpylang setup-claude` (CLI) drops the project's own CLAUDE.md into the cwd; this skill supersedes it.
- The skill's `data/objects.json` merges that db with refpage digests, inlet/outlet descriptions and domains
  (from the repo's web engine) for `maxref.py` / `inspect_patch.py`.
