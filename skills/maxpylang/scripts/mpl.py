"""
mpl.py - thin safety layer over MaxPyLang (pip install maxpylang).

Copy this file next to your build script and `import mpl` (it imports maxpylang for you, and stands
in for maxpylang's optional deps when installed offline). It fixes/avoids known MaxPyLang quirks:

  patch()                      new empty patch (mpl.mp is the maxpylang module if you need it)

  at(patch, text, x, y)        place ONE object at exact (x, y); raises on typos with suggestions;
                               expands s/r/i/f/del/v abbreviations; falls back to a raw box when
                               maxpylang's arg checker wrongly rejects valid Max text (metro 4n, expr ...)
  comment(patch, text, x, y)   comment box (maxpylang puts the word "comment" into the text)
  message(patch, text, x, y)   message box with verbatim text ($1, commas, semicolons OK)
  ui(patch, cls, x, y)         UI box missing from maxpylang's db (live.dial, live.menu, ...)
  extern(patch, text, x, y, ins, outs)   any object box with declared I/O (externals, p, ...)
  wire(patch, (a, 0, b, 0), ...)          connect with bounds checks + readable errors
  chain(patch, a, b, c)                   a:0 -> b:0 -> c:0
  live_param(obj, "Cutoff", ...)          make a live.* UI object an automatable M4L parameter
  present(obj, x, y) / face(*objs)       put controls on a Max for Live device's face (presentation view)
  autolayout(patch)                       arrange boxes top-to-bottom by signal flow (skips comments)
  poly(patch, "voice", 8, x, y)           poly~ box with I/O read from ./voice.maxpat
  gen(patch, "out1 = in1 * 0.5;", x, y)   gen~ box with an embedded GenExpr codebox
  js(patch, "name.js", code, x, y)        write a js file next to the patch and place its box
  load(path) / find(p, name) / replace(p, id, text) / delete(p, *ids)   edit existing patches quietly
  save(patch, path, device_type=None)     quiet save + structural validation

Coordinates are the object's top-left corner in patcher pixels; y grows downward.
"""
from __future__ import annotations

import contextlib
import copy
import difflib
import io
from io import StringIO
import json
import re
import sys
import warnings


def _shim_optional_deps():
    """maxpylang imports tabulate (error tables) and numpy (import_objs only) at import time.
    When they're missing (offline install with --no-deps), stand in for them."""
    import types
    try:
        import tabulate  # noqa: F401
    except ImportError:
        tab = types.ModuleType("tabulate")

        def tabulate(rows, headers=(), **_):
            rows = [list(map(str, r)) for r in rows]
            return "\n".join(["  ".join(map(str, headers))] + ["  ".join(r) for r in rows])
        tab.tabulate = tabulate
        sys.modules["tabulate"] = tab
    try:
        import numpy  # noqa: F401
    except ImportError:
        sys.modules["numpy"] = types.ModuleType("numpy")


_shim_optional_deps()
import maxpylang as mp  # noqa: E402

try:
    from maxpylang.exceptions import UnknownObjectWarning
except Exception:  # older maxpylang
    UnknownObjectWarning = UserWarning

# Abbreviations Max accepts but maxpylang's database does not.
ABBREV = {"s": "send", "r": "receive", "i": "int", "f": "float", "del": "delay",
          "v": "value", "s~": "send~", "r~": "receive~"}

# (inlets, outlets) for objects whose maxpylang arg-checker rejects valid text.
FALLBACK_IO = {"noteout": (3, 0), "bendin": (1, 2), "pgmin": (1, 2), "bendout": (2, 0),
               "pgmout": (2, 0), "touchin": (1, 2), "touchout": (2, 0), "biquad~": (6, 1)}


def _nargs(args, default):
    try:
        return int(float(args[0])) if args else default
    except ValueError:
        return default


# Objects whose I/O maxpylang computes wrongly (or crashes on): name -> f(args) -> (ins, outs)
IO_FIX = {
    "send": lambda a: (1, 0),
    "value": lambda a: (1, 1),
    "pv": lambda a: (1, 1),
    "switch": lambda a: (_nargs(a, 2) + 1, 1),
    "selector~": lambda a: (_nargs(a, 1) + 1, 1),
    "dac~": lambda a: (len([x for x in a if not x.startswith("@")]) or 2, 0),
    "join": lambda a: (_nargs(a, 2), 1),
    "mc.pack~": lambda a: (_nargs(a, 2), 1),
}

# Max for Live UI objects (not in maxpylang's db): (inlets, outlets, outlettype, [w, h])
LIVE_UI = {
    "live.dial":   (1, 2, ["", "float"], [44, 48]),
    "live.slider": (1, 2, ["", "float"], [39, 48]),
    "live.numbox": (1, 2, ["", "float"], [44, 15]),
    "live.toggle": (1, 1, [""], [15, 15]),
    "live.button": (1, 1, [""], [15, 15]),
    "live.menu":   (1, 3, ["", "", "float"], [100, 15]),
    "live.text":   (1, 2, ["", ""], [44, 15]),
    "live.tab":    (1, 3, ["", "", "float"], [100, 20]),
    "live.gain~":  (2, 5, ["signal", "signal", "", "float", "list"], [48, 136]),
}

# Live API / device objects (object boxes, not in maxpylang's db): (inlets, outlets, outlettype).
# Counts verified against real Max-saved patches on GitHub.
LIVE_OBJ = {
    "live.thisdevice": (1, 3, ["bang", "int", "int"]),
    "live.path":       (1, 3, ["", "", ""]),
    "live.object":     (2, 1, [""]),
    "live.observer":   (2, 2, ["", ""]),
}

DEVICE_HEIGHT = 169  # px of a Max for Live device's face in Live

UNITSTYLE = {"int": 0, "float": 1, "ms": 2, "time": 2, "hz": 3, "db": 4, "%": 5, "percent": 5,
             "pan": 6, "semitones": 7, "midi": 8, "custom": 9, "native": 10}
PTYPE = {"float": 0, "int": 1, "enum": 2}


class MaxPatchError(ValueError):
    pass


def patch(**kwargs):
    """A new, empty MaxPyLang patch (quiet). Build scripts only need `import mpl`."""
    with _quiet():
        return mp.MaxPatch(verbose=False, **kwargs)


@contextlib.contextmanager
def _quiet():
    """Silence maxpylang's debug prints and collect its warnings."""
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("always")
        yield w


def _known_names():
    names = set()
    for objs in mp.MaxObject.known_objs.values():
        names.update(objs)
    return sorted(names | set(ABBREV))


def _db_io(name):
    """Default (inlets, outlets, outlettype) straight from maxpylang's OBJ_INFO json, or None."""
    import os
    folder = mp.MaxObject.obj_info_folder
    try:
        with open(os.path.join(folder, "obj_aliases.json"), encoding="utf-8") as f:
            name = json.load(f).get(name, name)
    except (OSError, ValueError):
        pass
    for pkg in mp.MaxObject.known_objs:
        try:
            with open(os.path.join(folder, pkg, name + ".json"), encoding="utf-8") as f:
                box = json.load(f)["default"]["box"]
            return box.get("numinlets", 0), box.get("numoutlets", 0), box.get("outlettype")
        except (OSError, ValueError, KeyError):
            continue
    return None


def _note(msg):
    print(f"mpl: {msg}", file=sys.stderr)


def _width_for(text, minimum):
    return max(float(minimum), 6.0 * len(text) + 12.0)


def _put(patch, obj, x, y):
    if any(o is obj for o in patch.objs.values()):
        raise MaxPatchError(f"{obj!r} is already in the patch. maxpylang.objects stubs are shared "
                            "singletons: pass a string like 'cycle~' instead of reusing a stub.")
    with _quiet():
        placed = patch.place(obj, spacing_type="custom", spacing=[[float(x), float(y)]])[0]
    rect = placed._dict["box"]["patching_rect"]
    while len(rect) < 4:
        rect.append(22.0)
    return placed


def at(patch, text, x, y, io=None, **attribs):
    """Place one object box at (x, y). `text` is the Max box text, e.g. "cycle~ 440" or
    "metro 500 @active 1". Pass io=(inlets, outlets) to force a raw box when you know
    better than maxpylang's database. Extra kwargs become box attributes."""
    if not isinstance(text, str):
        return _put(patch, text, x, y)
    text = " ".join(text.split())
    name, _, rest = text.partition(" ")
    if name in ABBREV:
        name = ABBREV[name]
        text = (name + " " + rest).strip()
    if name == "comment":
        return comment(patch, rest, x, y)
    if name in ("message", "msg"):
        return message(patch, rest, x, y)
    if name in LIVE_UI:
        return ui(patch, name, x, y, **attribs)
    if name in LIVE_OBJ:
        ins, outs, ot = LIVE_OBJ[name]
        return extern(patch, text, x, y, ins, outs, outlettype=ot)
    if io is not None:
        return extern(patch, text, x, y, *io)
    if name in IO_FIX:
        return extern(patch, text, x, y, *IO_FIX[name](rest.split()))

    printed = StringIO()
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(printed):
        warnings.simplefilter("always")
        obj = mp.MaxObject(text, **attribs)
    if not obj.notknown():
        placed = _put(patch, obj, x, y)
        if placed._dict["box"].get("maxclass") == "newobj":
            rect = placed._dict["box"]["patching_rect"]
            rect[2] = max(rect[2], _width_for(text, rect[2]))
        return placed

    msgs = " / ".join(str(m.message).split("\n")[0] for m in w) \
        or next((ln.strip() for ln in printed.getvalue().splitlines() if ln.strip()), "unknown")
    # name is real but maxpylang's arg checker refused valid Max text -> raw box
    io_guess = None
    if name == "expr":
        n = max([int(k) for k in re.findall(r"\$[ifs](\d+)", text)] or [1])
        io_guess = (n, 1)
    elif name in FALLBACK_IO:
        io_guess = FALLBACK_IO[name]
    elif name in _known_names():
        with _quiet():
            bare = mp.MaxObject(name)
        io_guess = (len(bare.ins), len(bare.outs)) if not bare.notknown() else _db_io(name)
    otype = io_guess[2] if io_guess and len(io_guess) == 3 else None
    io_guess = io_guess[:2] if io_guess else None
    if io_guess:
        _note(f"maxpylang rejected '{text}' ({msgs}); placed raw box with io={io_guess}. "
              "Pass io=(ins, outs) to override.")
        return extern(patch, text, x, y, *io_guess, outlettype=otype)

    hint = difflib.get_close_matches(name, _known_names(), n=5, cutoff=0.6)
    raise MaxPatchError(
        f"Unknown Max object '{name}' ({msgs})."
        + (f" Did you mean: {', '.join(hint)}?" if hint else "")
        + " If it is a real external/abstraction, use mpl.extern(patch, text, x, y, ins, outs)."
    )


def comment(patch, text, x, y, width=None):
    with _quiet():
        obj = mp.MaxObject("comment")
    placed = _put(patch, obj, x, y)
    box = placed._dict["box"]
    box["text"] = text
    box["patching_rect"][2] = float(width) if width else _width_for(text, 40)
    return placed


def message(patch, text, x, y):
    with _quiet():
        obj = mp.MaxObject("message")
    placed = _put(patch, obj, x, y)
    box = placed._dict["box"]
    box["text"] = text
    box["patching_rect"][2] = _width_for(text, 30)
    return placed


def ui(patch, cls, x, y, ins=None, outs=None, outlettype=None, size=None, **box_attrs):
    """UI object by maxclass. Uses maxpylang if it knows the class, else builds the box JSON."""
    if cls not in LIVE_UI and ins is None:
        with _quiet():
            probe = mp.MaxObject(cls)
        if not probe.notknown():
            return _put(patch, probe, x, y)
    d_in, d_out, d_type, d_size = LIVE_UI.get(cls, (1, 1, [""], [40, 22]))
    ins = d_in if ins is None else ins
    outs = d_out if outs is None else outs
    outlettype = outlettype or (d_type if len(d_type) == outs else [""] * outs)
    w, h = size or d_size
    box = {"id": "obj-0", "maxclass": cls, "numinlets": ins, "numoutlets": outs,
           "outlettype": outlettype, "patching_rect": [float(x), float(y), float(w), float(h)],
           "text": ""}
    if cls.startswith("live."):
        box["parameter_enable"] = 1
    box.update(box_attrs)
    with _quiet():
        obj = mp.MaxObject(copy.deepcopy({"box": box}), from_dict=True)
    obj._dict["box"].pop("text", None)
    return _put(patch, obj, x, y)


def extern(patch, text, x, y, ins, outs, outlettype=None, **box_extra):
    """Raw object box with declared inlet/outlet counts (externals, `p name`, odd args).
    Built from box JSON, so it works on every maxpylang version and keeps `text` verbatim."""
    name = text.split()[0]
    box = {"id": "obj-0", "maxclass": "newobj", "numinlets": ins, "numoutlets": outs,
           "outlettype": outlettype or (["signal"] * outs if name.endswith("~") else [""] * outs),
           "patching_rect": [float(x), float(y), _width_for(text, 30), 22.0], "text": text}
    box.update(box_extra)
    with _quiet():
        obj = mp.MaxObject({"box": box}, from_dict=True)
    if len(obj.ins) != ins or len(obj.outs) != outs:  # abstraction file in cwd overrode the counts
        _note(f"'{text}': using I/O {len(obj.ins)}/{len(obj.outs)} from the file, not {ins}/{outs}")
    return _put(patch, obj, x, y)


def _label(o):
    return f"{o.name} ({o._dict['box'].get('id')})"


def wire(patch, *conns):
    """wire(patch, (src, outlet, dst, inlet), ...) with readable bounds errors.
    Duplicate cords are skipped."""
    for c in conns:
        if len(c) != 4:
            raise MaxPatchError(f"connection must be (src, outlet, dst, inlet), got {c!r}")
        src, o, dst, i = c
        if o >= len(src.outs):
            raise MaxPatchError(f"{_label(src)} has {len(src.outs)} outlet(s); outlet {o} does not exist")
        if i >= len(dst.ins):
            raise MaxPatchError(f"{_label(dst)} has {len(dst.ins)} inlet(s); inlet {i} does not exist")
        if dst.ins[i] in src.outs[o].destinations:
            continue
        with _quiet():
            patch.connect([src.outs[o], dst.ins[i]], verbose=False)


def chain(patch, *objs):
    """Connect outlet 0 -> inlet 0 down a list of objects."""
    wire(patch, *[(a, 0, b, 0) for a, b in zip(objs, objs[1:])])


def live_param(obj, longname, shortname=None, ptype="float", mmin=0.0, mmax=1.0,
               initial=None, unitstyle=None, enum=None, exponent=None):
    """Turn a live.* UI box into a named, automatable, saved M4L parameter."""
    box = obj._dict["box"]
    vo = {"parameter_longname": longname,
          "parameter_shortname": shortname or longname[:8],
          "parameter_type": PTYPE.get(ptype, ptype)}
    if enum:
        vo["parameter_enum"] = list(enum)
        vo["parameter_type"] = 2
        vo["parameter_mmax"] = len(enum) - 1
    else:
        vo["parameter_mmin"] = mmin
        vo["parameter_mmax"] = mmax
    if initial is not None:
        vo["parameter_initial_enable"] = 1
        vo["parameter_initial"] = initial if isinstance(initial, list) else [initial]
    if unitstyle is not None:
        vo["parameter_unitstyle"] = UNITSTYLE.get(str(unitstyle).lower(), unitstyle)
    if exponent is not None:
        vo["parameter_exponent"] = exponent
    box["parameter_enable"] = 1
    box["varname"] = longname
    box.setdefault("saved_attribute_attributes", {})["valueof"] = vo
    return obj


def present(obj, x, y, w=None, h=None):
    """Show `obj` on the presentation view (the face of a Max for Live device) at (x, y).
    The face is DEVICE_HEIGHT (169) px tall; width grows with the controls."""
    box = obj._dict["box"]
    rect = box.get("patching_rect", [0, 0, 40, 22])
    box["presentation"] = 1
    box["presentation_rect"] = [float(x), float(y), float(w or rect[2]), float(h or rect[3])]
    return obj


def face(*objs, x=10, y=10, gap=10, labels=None):
    """Lay `objs` out left to right on the device face. Returns the face width used.
    labels: optional {obj: "text"} comments placed above (live.* dials label themselves)."""
    cx = float(x)
    for o in objs:
        r = o._dict["box"].get("patching_rect", [0, 0, 40, 22])
        present(o, cx, y)
        cx += r[2] + gap
    return cx


def autolayout(patch, x0=30, y0=30, row=45, gap=24, comments="keep"):
    """Arrange boxes in rows by signal flow: sources on top, each box one row below its
    deepest input (feedback cords ignored); within a row, ordered by the x of their inputs.
    comments="keep" leaves comment boxes where they are, "drop" deletes them."""
    objs = {oid: o for oid, o in patch.objs.items()}
    movable = {oid for oid, o in objs.items() if o._dict["box"].get("maxclass") != "comment"}
    parents = {oid: [] for oid in movable}
    for oid in movable:
        for inlet in objs[oid].ins:
            for src in inlet.sources:
                pid = src.parent._dict["box"]["id"]
                if pid in movable and pid != oid:
                    parents[oid].append(pid)
    # longest-path layering with cycle protection (DFS marks feedback edges)
    layer, state = {}, {}

    def depth(oid):
        if state.get(oid) == 1:      # on the stack: feedback cord, ignore
            return -1
        if oid in layer:
            return layer[oid]
        state[oid] = 1
        d = 1 + max([depth(p) for p in parents[oid]] or [-1])
        state[oid] = 2
        layer[oid] = max(d, 0)
        return layer[oid]

    for oid in sorted(movable, key=lambda i: int(re.sub(r"\D", "", i) or 0)):
        depth(oid)
    rows = {}
    for oid, d in layer.items():
        rows.setdefault(d, []).append(oid)
    xpos, row_y, y = {}, {}, float(y0)
    for d in sorted(rows):
        row_y[d] = y
        tallest = max(objs[oid]._dict["box"]["patching_rect"][3] for oid in rows[d])
        y += max(row, tallest + row - 22.0)
    for d in sorted(rows):
        def key(oid):
            px = [xpos[p] for p in parents[oid] if p in xpos]
            return (sum(px) / len(px)) if px else objs[oid]._dict["box"]["patching_rect"][0]
        cx = float(x0)
        for oid in sorted(rows[d], key=key):
            box = objs[oid]._dict["box"]
            r = box["patching_rect"]
            want = key(oid) if any(p in xpos for p in parents[oid]) else cx
            nx = max(cx, want)
            r[0], r[1] = nx, row_y[d]
            xpos[oid] = nx
            cx = nx + r[2] + gap
    if comments == "drop":
        ids = [oid for oid in objs if oid not in movable]
        if ids:
            delete(patch, *ids)
    return patch


def poly(patch, voice, n, x, y, extra=""):
    """poly~ box for ./<voice>.maxpat. Inlets/outlets come from the voice's in/in~ and
    out/out~ objects (highest index wins), which maxpylang can't work out itself."""
    import os
    path = voice if voice.endswith(".maxpat") else voice + ".maxpat"
    if not os.path.exists(path):
        raise MaxPatchError(f"{path} not found in {os.getcwd()}: build the voice patch first")
    with open(path, encoding="utf-8") as f:
        boxes = [b["box"] for b in json.load(f)["patcher"]["boxes"]]
    ins = outs = 0
    for b in boxes:
        parts = (b.get("text") or "").split()
        if len(parts) >= 2 and parts[1].isdigit():
            if parts[0] in ("in", "in~"):
                ins = max(ins, int(parts[1]))
            elif parts[0] in ("out", "out~"):
                outs = max(outs, int(parts[1]))
    sig_outs = {int(b["text"].split()[1]) for b in boxes
                if (b.get("text") or "").startswith("out~ ") and b["text"].split()[1].isdigit()}
    otype = ["signal" if i + 1 in sig_outs else "" for i in range(outs)]
    name = os.path.splitext(os.path.basename(path))[0]
    return extern(patch, f"poly~ {name} {n}{(' ' + extra) if extra else ''}", x, y,
                  max(ins, 1), outs, outlettype=otype)


def gen(patch, code, x, y, ins=None, outs=None):
    """gen~ box containing one GenExpr codebox. I/O counts come from in1..inN / out1..outN in
    `code` unless given. Example: gen(p, "out1 = in1 * in2;", 30, 100)."""
    ins = ins or max([int(k) for k in re.findall(r"\bin(\d+)\b", code)] or [1])
    outs = outs or max([int(k) for k in re.findall(r"\bout(\d+)\b", code)] or [1])
    inner, lines = [], []
    for i in range(ins):
        inner.append({"box": {"id": f"obj-{i + 1}", "maxclass": "newobj", "text": f"in {i + 1}",
                              "numinlets": 0, "numoutlets": 1, "outlettype": [""],
                              "patching_rect": [20.0 + 60 * i, 20.0, 30.0, 22.0]}})
    cb = f"obj-{ins + 1}"
    nlines = code.count("\n") + 1
    inner.append({"box": {"id": cb, "maxclass": "codebox", "code": code, "fontface": 0,
                          "fontname": "Menlo", "fontsize": 12.0, "numinlets": ins, "numoutlets": outs,
                          "outlettype": [""] * outs,
                          "patching_rect": [20.0, 60.0, 400.0, 40.0 + 15 * nlines]}})
    for o in range(outs):
        inner.append({"box": {"id": f"obj-{ins + 2 + o}", "maxclass": "newobj", "text": f"out {o + 1}",
                              "numinlets": 1, "numoutlets": 0,
                              "patching_rect": [20.0 + 60 * o, 120.0 + 15 * nlines, 37.0, 22.0]}})
    for i in range(ins):
        lines.append({"patchline": {"source": [f"obj-{i + 1}", 0], "destination": [cb, i]}})
    for o in range(outs):
        lines.append({"patchline": {"source": [cb, o], "destination": [f"obj-{ins + 2 + o}", 0]}})
    gp = {"fileversion": 1, "appversion": {"major": 8, "minor": 6, "revision": 0, "architecture": "x64",
                                            "modernui": 1},
          "classnamespace": "dsp.gen", "rect": [100.0, 100.0, 600.0, 450.0], "bglocked": 0,
          "openinpresentation": 0, "default_fontsize": 12.0, "default_fontface": 0,
          "default_fontname": "Arial", "gridonopen": 1, "gridsize": [15.0, 15.0], "gridsnaponopen": 1,
          "objectsnaponopen": 1, "statusbarvisible": 2, "toolbarvisible": 1, "boxes": inner, "lines": lines}
    obj = extern(patch, "gen~", x, y, ins, outs, outlettype=["signal"] * outs)
    obj._dict["box"]["patcher"] = gp
    return obj


def js(patch, filename, code, x, y):
    """Write `code` to <filename> in the current directory and place a [js filename] box.
    Declare `inlets = N;` / `outlets = N;` in the code (defaults 1/1)."""
    m_in = re.search(r"^\s*inlets\s*=\s*(\d+)", code, re.M)
    m_out = re.search(r"^\s*outlets\s*=\s*(\d+)", code, re.M)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code if code.endswith("\n") else code + "\n")
    return extern(patch, f"js {filename}", x, y, int(m_in.group(1)) if m_in else 1,
                  int(m_out.group(1)) if m_out else 1,
                  saved_object_attributes={"filename": filename, "parameter_enable": 0})


_NOTEXT = "\x00mpl-notext"
AMXD_TYPES = {"audio_effect": b"aaaa", "midi_effect": b"mmmm", "instrument": b"iiii"}


def write_amxd(patcher, path, device_type):
    """Max for Live wrapper: ampf(type) + meta(4 zero bytes) + ptch(JSON + NUL), little-endian sizes.
    Same format as maxpylang.amxd.save_amxd, but also available on maxpylang versions without it."""
    import struct
    body = json.dumps(patcher, indent=2).encode("utf-8") + b"\x00"
    with open(path, "wb") as f:
        f.write(b"ampf" + struct.pack("<I", 4) + AMXD_TYPES[device_type])
        f.write(b"meta" + struct.pack("<I", 4) + b"\x00" * 4)
        f.write(b"ptch" + struct.pack("<I", len(body)) + body)


def read_amxd(path):
    """Return (patcher dict, device_type) from an .amxd file."""
    import struct
    with open(path, "rb") as f:
        data = f.read()
    kind = {v: k for k, v in AMXD_TYPES.items()}.get(data[8:12])
    off = 0
    while off + 8 <= len(data):
        tag, size = data[off:off + 4], struct.unpack("<I", data[off + 4:off + 8])[0]
        if tag == b"ptch":
            return json.loads(data[off + 8:off + 8 + size].rstrip(b"\x00")), kind
        off += 8 + size
    raise MaxPatchError(f"no ptch chunk in {path}")


def load(path):
    """Load an existing .maxpat/.amxd quietly. Ids are renumbered obj-1..obj-N.
    Works around maxpylang crashing (KeyError 'text') on UI boxes saved by Max without a text field.
    For .amxd, the device type is kept on patch.mpl_device_type."""
    import os
    import tempfile
    kind = None
    if path.endswith(".amxd"):
        d, kind = read_amxd(path)
    else:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    for b in d["patcher"].get("boxes", []):
        b["box"].setdefault("text", _NOTEXT)
    fd, tmp = tempfile.mkstemp(suffix=".maxpat")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f)
        with _quiet():
            patch = mp.MaxPatch(load_file=tmp, verbose=False)
    finally:
        os.remove(tmp)
    for o in patch.objs.values():
        if o._dict["box"].get("text") == _NOTEXT:
            del o._dict["box"]["text"]
    patch.mpl_device_type = kind
    return patch


def find(patch, name=None, text=None):
    """[(id, obj)] whose class == name and/or whose box text contains `text`, in id order."""
    hits = []
    for oid, o in patch.objs.items():
        t = o._dict["box"].get("text", "")
        if (name is None or o.name == name) and (text is None or text in t):
            hits.append((oid, o))
    return hits


def replace(patch, obj_id, text):
    """Swap an object in place, keeping position and the cords whose xlet indices still exist."""
    if obj_id not in patch.objs:
        raise MaxPatchError(f"{obj_id} not in patch (ids: {', '.join(list(patch.objs)[:20])} ...)")
    name = text.split()[0]
    with _quiet():
        probe = mp.MaxObject(text)
    if probe.notknown():
        hint = difflib.get_close_matches(name, _known_names(), n=5, cutoff=0.6)
        raise MaxPatchError(f"maxpylang can't build '{text}'" + (f"; did you mean {', '.join(hint)}?" if hint else
                            "; delete + mpl.at/extern + wire instead"))
    with _quiet():
        patch.replace(obj_id, probe)
    return patch.objs[obj_id]


def delete(patch, *obj_ids):
    """Delete objects (and their cords) by id."""
    missing = [i for i in obj_ids if i not in patch.objs]
    if missing:
        raise MaxPatchError(f"not in patch: {missing}")
    with _quiet():
        patch.delete(objs=list(obj_ids))


def validate(d):
    """Structural checks on a patcher dict. Returns list of error strings."""
    errs = []
    boxes = d["patcher"]["boxes"]
    seen, io_ = set(), {}
    for b in boxes:
        bid = b["box"]["id"]
        if bid in seen:
            errs.append(f"duplicate box id {bid} (reused stub or unknown object?)")
        seen.add(bid)
        io_[bid] = (b["box"].get("numinlets", 0), b["box"].get("numoutlets", 0), b["box"].get("text", b["box"]["maxclass"]))
        if b["box"].get("text") == "UNK":
            errs.append(f"{bid} is an unknown-object placeholder")
    for ln in d["patcher"]["lines"]:
        (s, so), (t, ti) = ln["patchline"]["source"], ln["patchline"]["destination"]
        if s not in io_ or t not in io_:
            errs.append(f"cord {s}:{so} -> {t}:{ti} references a missing box")
            continue
        if so >= io_[s][1]:
            errs.append(f"cord from [{io_[s][2]}] outlet {so}: box has {io_[s][1]} outlet(s)")
        if ti >= io_[t][0]:
            errs.append(f"cord to [{io_[t][2]}] inlet {ti}: box has {io_[t][0]} inlet(s)")
    return errs


def save(patch, path, device_type=None):
    """Save quietly, validate, print one summary line. Raises MaxPatchError on structural errors."""
    errs = validate(patch.get_json())
    if errs:
        raise MaxPatchError("patch has errors:\n  " + "\n  ".join(errs))
    d = patch.get_json()
    if device_type or path.endswith(".amxd"):
        if device_type not in AMXD_TYPES:
            raise MaxPatchError(f"device_type must be one of {', '.join(AMXD_TYPES)} for .amxd")
        out = path if path.endswith(".amxd") else path.rsplit(".maxpat", 1)[0] + ".amxd"
        presented = [b for b in d["patcher"]["boxes"] if b["box"].get("presentation")]
        d["patcher"]["openinpresentation"] = 1 if presented else 0
        d["patcher"]["devicewidth"] = 0.0  # 0 = Live sizes the device to its face
        if not presented:
            _note("device has no face: Live will show the patch cords. Put controls on it with mpl.face(...)")
        write_amxd(d, out, device_type)
    else:
        out = path if path.endswith(".maxpat") else path + ".maxpat"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    kind = f" (M4L {device_type})" if device_type else ""
    print(f"saved {out}{kind}: {len(d['patcher']['boxes'])} objects, {len(d['patcher']['lines'])} cords")
    return out
