#!/usr/bin/env python3
"""
maxref.py - look up Max/MSP/Jitter objects in the bundled MaxPyLang object database.

Usage:
  maxref.py cycle~ metro "pack 0 0"     detailed card per object (inlets, outlets, args, attrs)
  maxref.py -s lowpass filter            search names + descriptions (all terms must match)
  maxref.py -c cycle~ metr0 lores~       check names exist; suggest fixes for typos
  maxref.py --pkg msp                    list every object in a package (max, msp, jit, m4l)

Stdlib only. Data: ../data/objects.json (derived from MaxPyLang's OBJ_INFO + Max refpages).
Inlet/outlet counts are the DEFAULTS for the bare object; objects flagged
"io varies with args" (pack, trigger, gate, route, ...) gain/lose xlets from their arguments.
"""
import argparse
import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "data", "objects.json")


def load_db():
    with open(DB_PATH, encoding="utf-8") as f:
        db = json.load(f)
    alias = {}
    for name, e in db.items():
        for a in e.get("aka", []):
            alias.setdefault(a, name)
    # abbreviations Max accepts that the db lacks (mpl.at() expands these automatically)
    for a, full in {"s": "send", "r": "receive", "i": "int", "f": "float", "del": "delay",
                    "v": "value", "s~": "send~", "r~": "receive~"}.items():
        alias.setdefault(a, full)
    return db, alias


def resolve(name, db, alias):
    if name in db:
        return name
    return alias.get(name)


def suggest(name, db, alias, n=5):
    pool = list(db) + list(alias)
    return difflib.get_close_matches(name, pool, n=n, cutoff=0.6)


def card(name, e):
    lines = []
    kind = f"UI object (maxclass {e['ui']})" if e.get("ui") else "object box (newobj)"
    lines.append(f"## {name}  [{e.get('pkg')}]  {kind}")
    if e.get("digest"):
        lines.append(f"   {e['digest']}")
    if e.get("aka"):
        lines.append(f"   aliases: {', '.join(e['aka'])}")
    if e.get("mp") is False:
        lines.append("   NOT in maxpylang database -> place with mpl.at()/mpl.ui(), not patch.place()")
    if e.get("curated"):
        lines.append("   (curated entry: I/O from typical M4L patches; verify in Max)")
    if e.get("args"):
        lines.append(f"   args: {' '.join(e['args'])}   (? = optional)")
    io = " (io varies with args)" if e.get("io_varies_with_args") else ""
    lines.append(f"   inlets: {e.get('in')}  outlets: {e.get('out')}{io}")
    ins, inT = e.get("inlets", []), e.get("inT", [])
    for i in range(max(len(ins), len(inT))):
        dom = inT[i] if i < len(inT) else "?"
        txt = ins[i] if i < len(ins) else ""
        lines.append(f"     in {i} [{dom}] {txt}")
    outs, outT = e.get("outlets", []), e.get("outT", [])
    for i in range(max(len(outs), len(outT))):
        dom = outT[i] if i < len(outT) else "?"
        txt = outs[i] if i < len(outs) else ""
        lines.append(f"     out {i} [{dom}] {txt}")
    if e.get("attrs"):
        lines.append(f"   @attrs: {', '.join(e['attrs'][:40])}{' ...' if len(e['attrs']) > 40 else ''}")
    if e.get("msgs"):
        lines.append(f"   messages: {', '.join(e['msgs'][:30])}{' ...' if len(e['msgs']) > 30 else ''}")
    return "\n".join(lines)


def search(terms, db, limit):
    terms = [t.lower() for t in terms]
    hits = []
    for name, e in db.items():
        hay = " ".join([name, e.get("digest", ""), " ".join(e.get("inlets", [])), " ".join(e.get("outlets", []))]).lower()
        if all(t in hay for t in terms):
            score = sum(3 if t in name.lower() else (2 if t in e.get("digest", "").lower() else 1) for t in terms)
            hits.append((-score, name))
    hits.sort()
    for _, name in hits[:limit]:
        e = db[name]
        print(f"{name:24} [{e.get('pkg')}] in{e.get('in')}/out{e.get('out')}  {e.get('digest', '')}")
    if len(hits) > limit:
        print(f"... {len(hits) - limit} more (use --limit)")
    if not hits:
        print("no matches")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="object names (or full box text; first word is used)")
    ap.add_argument("-s", "--search", action="store_true", help="search names/descriptions")
    ap.add_argument("-c", "--check", action="store_true", help="only check names exist")
    ap.add_argument("--pkg", help="list all objects in package")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    db, alias = load_db()

    if a.pkg:
        for name in sorted(n for n, e in db.items() if e.get("pkg") == a.pkg):
            print(f"{name:24} {db[name].get('digest', '')}")
        return 0
    if not a.names:
        ap.print_help()
        return 1
    if a.search:
        search(a.names, db, a.limit)
        return 0

    bad = 0
    for raw in a.names:
        name = raw.split()[0]
        real = resolve(name, db, alias)
        if real is None:
            bad += 1
            s = suggest(name, db, alias)
            print(f"UNKNOWN {name!r}" + (f" -> did you mean: {', '.join(s)}" if s else " (not a vanilla Max object; external/abstraction?)"))
            continue
        if a.check:
            note = " (not in maxpylang db: mpl.at() handles it)" if db[real].get("mp") is False else ""
            print(f"ok      {name}" + (f" (= {real})" if real != name else "") + note)
        else:
            print(card(real, db[real]))
            print()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
