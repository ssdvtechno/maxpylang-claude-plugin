#!/usr/bin/env python3
"""
inspect_patch.py - summarize and lint a .maxpat / .amxd file without opening Max.

Usage:
  inspect_patch.py patch.maxpat            object list + cords + lint report
  inspect_patch.py device.amxd --lint      lint report only
  inspect_patch.py patch.maxpat --graph    signal-flow listing (who feeds whom)

Exit code 1 if any ERROR is found (WARN/INFO do not fail).
Stdlib only. Uses ../data/objects.json for names, I/O and inlet domains.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "data", "objects.json")
AMXD_TYPES = {b"aaaa": "audio_effect", b"mmmm": "midi_effect", b"iiii": "instrument"}


def load(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] == b"ampf":
        dev = AMXD_TYPES.get(data[8:12], data[8:12].decode("latin1"))
        off = 0
        while off + 8 <= len(data):
            tag, size = data[off:off + 4], struct.unpack("<I", data[off + 4:off + 8])[0]
            if tag == b"ptch":
                return json.loads(data[off + 8:off + 8 + size].rstrip(b"\x00")), dev
            off += 8 + size
        raise ValueError("no ptch chunk in .amxd")
    return json.loads(data), None


def load_db():
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
    except OSError:
        return {}, {}
    alias = {a: n for n, e in db.items() for a in e.get("aka", [])}
    alias.update({"s": "send", "r": "receive", "i": "int", "f": "float", "del": "delay", "v": "value"})
    return db, alias


def label(b):
    return b.get("text") if b.get("maxclass") in ("newobj", "message", "comment") else b.get("maxclass")


def name_of(b):
    if b.get("maxclass") == "newobj":
        return (b.get("text") or "").split(" ")[0]
    return b.get("maxclass")


def overlaps(r1, r2):
    x1, y1, w1, h1 = (r1 + [0, 0])[:4]
    x2, y2, w2, h2 = (r2 + [0, 0])[:4]
    return x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1


def lint(d, dev, patch_dir, db, alias):
    out = []
    E = lambda m: out.append(("ERROR", m))
    W = lambda m: out.append(("WARN", m))
    I = lambda m: out.append(("INFO", m))
    boxes = [b["box"] for b in d["patcher"].get("boxes", [])]
    lines = [l["patchline"] for l in d["patcher"].get("lines", [])]
    by_id = {}
    for b in boxes:
        if b["id"] in by_id:
            E(f"duplicate id {b['id']}: [{label(b)}] and [{label(by_id[b['id']])}] (stub reused / unknown-object dict shared)")
        by_id[b["id"]] = b

    names = []
    for b in boxes:
        n = name_of(b)
        names.append(n)
        t = b.get("text", "")
        if b.get("maxclass") == "newobj":
            if t == "UNK" or not t:
                E(f"{b['id']} is an empty/unknown placeholder box")
            elif db and n not in db and n not in alias:
                local = any(os.path.exists(os.path.join(patch_dir, n + ext)) for ext in ("", ".maxpat", ".js"))
                (I if local else W)(f"{b['id']} [{t}]: '{n}' is not a vanilla Max object"
                                     + (" (abstraction found next to patch)" if local else " - external/abstraction or typo?"))
        if b.get("maxclass") == "comment" and t.startswith("comment "):
            W(f"{b['id']} comment text starts with 'comment ' (maxpylang quirk; use mpl.comment)")
        if b.get("maxclass") == "message" and t.startswith(" "):
            I(f"{b['id']} message text has a leading space")
        if b.get("maxclass") == "newobj" and n == "js":
            parts = t.split()
            if len(parts) > 1 and not os.path.exists(os.path.join(patch_dir, parts[1])):
                W(f"{b['id']} [js {parts[1]}]: file not found next to patch")

    sig_in = {}
    for ln in lines:
        (s, so), (t, ti) = ln["source"], ln["destination"]
        if s not in by_id or t not in by_id:
            E(f"cord {s}:{so} -> {t}:{ti} references a missing box")
            continue
        sb, tb = by_id[s], by_id[t]
        if so >= sb.get("numoutlets", 0):
            E(f"cord from [{label(sb)}] outlet {so}, but it has {sb.get('numoutlets', 0)} outlet(s)")
        if ti >= tb.get("numinlets", 0):
            E(f"cord to [{label(tb)}] inlet {ti}, but it has {tb.get('numinlets', 0)} inlet(s)")
        ot = (sb.get("outlettype") or [])
        if so < len(ot) and ot[so] in ("signal", "multichannelsignal"):
            tn = name_of(tb)
            e = db.get(alias.get(tn, tn), {})
            dom = e.get("inT", [])
            if ti < len(dom) and dom[ti] == "control" and not tn.startswith(("snapshot", "number~", "meter~", "scope~", "levelmeter~", "outlet", "send~", "poly~", "pfft~")):
                W(f"signal cord [{label(sb)}]:{so} -> [{label(tb)}] inlet {ti}, which db marks control-only")
            sig_in.setdefault(t, 0)
            sig_in[t] += 1

    connected = {l["source"][0] for l in lines} | {l["destination"][0] for l in lines}
    for b in boxes:
        if b["id"] not in connected and b.get("maxclass") not in ("comment", "panel", "bpatcher") and \
                name_of(b) not in ("loadbang", "send", "receive", "send~", "receive~", "s", "r", "value", "v", "pattrstorage", "autopattr"):
            if (b.get("numinlets", 0) or b.get("numoutlets", 0)):
                I(f"{b['id']} [{label(b)}] has no cords")

    pairs = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if overlaps(boxes[i].get("patching_rect", [0, 0, 0, 0]), boxes[j].get("patching_rect", [0, 0, 0, 0])):
                pairs += 1
                if pairs <= 5:
                    W(f"overlap: [{label(boxes[i])}] and [{label(boxes[j])}]")
    if pairs > 5:
        W(f"... {pairs} overlapping pairs total (use explicit x/y)")

    nset = set(names)
    if dev:
        for bad in ("ezdac~", "dac~", "adc~", "ezadc~"):
            if bad in nset:
                E(f"M4L device uses {bad}; use plugin~/plugout~")
        if dev in ("instrument", "audio_effect") and "plugout~" not in nset:
            E(f"{dev} has no plugout~ (no audio reaches Live)")
        if dev == "audio_effect" and "plugin~" not in nset:
            W("audio_effect has no plugin~ (track audio is ignored)")
        if dev == "instrument" and not ({"notein", "midiin"} & nset):
            W("instrument has no notein/midiin")
        if dev == "midi_effect" and "midiout" not in nset and "noteout" not in nset:
            E("midi_effect has no midiout/noteout")
        if "plugout~" in nset and "clip~" not in nset:
            W("no clip~ -1. 1. before plugout~ (speaker safety)")
        for b in boxes:
            if b.get("maxclass") in ("dial", "slider", "toggle", "number", "flonum", "umenu"):
                I(f"{b['id']} [{b['maxclass']}] is not automatable in Live; consider live.{ {'number': 'numbox', 'flonum': 'numbox', 'umenu': 'menu'}.get(b['maxclass'], b['maxclass']) }")
    else:
        audio = any(n.endswith("~") for n in nset)
        if audio and not ({"ezdac~", "dac~", "out~", "send~", "plugout~", "outlet"} & nset):
            I("audio objects present but no dac~/ezdac~ output")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--lint", action="store_true", help="lint report only")
    ap.add_argument("--graph", action="store_true", help="show cords grouped by source")
    a = ap.parse_args()
    d, dev = load(a.path)
    db, alias = load_db()
    boxes = [b["box"] for b in d["patcher"].get("boxes", [])]
    lines = [l["patchline"] for l in d["patcher"].get("lines", [])]
    by_id = {b["id"]: b for b in boxes}

    print(f"{os.path.basename(a.path)}: {len(boxes)} objects, {len(lines)} cords" + (f", M4L {dev}" if dev else ""))
    if not a.lint:
        print("\nobjects (top-to-bottom):")
        for b in sorted(boxes, key=lambda b: (b.get("patching_rect", [0, 0])[1], b.get("patching_rect", [0, 0])[0])):
            r = b.get("patching_rect", [0, 0])
            print(f"  {b['id']:8} ({r[0]:.0f},{r[1]:.0f})  in{b.get('numinlets', 0)}/out{b.get('numoutlets', 0)}  [{label(b)}]")
        print("\ncords:")
        if a.graph:
            src = {}
            for ln in lines:
                src.setdefault(ln["source"][0], []).append(ln)
            for sid, ls in src.items():
                sb = by_id.get(sid, {})
                tgt = ", ".join(f"{l['source'][1]}->[{label(by_id.get(l['destination'][0], {}))}]:{l['destination'][1]}" for l in ls)
                print(f"  [{label(sb)}] {tgt}")
        else:
            for ln in lines:
                (s, so), (t, ti) = ln["source"], ln["destination"]
                print(f"  [{label(by_id.get(s, {'maxclass': s}))}]:{so} -> [{label(by_id.get(t, {'maxclass': t}))}]:{ti}")

    report = lint(d, dev, os.path.dirname(os.path.abspath(a.path)), db, alias)
    print("\nlint:" if report else "\nlint: clean")
    for lvl, msg in report:
        print(f"  {lvl:5} {msg}")
    return 1 if any(l == "ERROR" for l, _ in report) else 0


if __name__ == "__main__":
    sys.exit(main())
