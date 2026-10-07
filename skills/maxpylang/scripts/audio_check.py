#!/usr/bin/env python3
"""
audio_check.py - does the patch make sound? Checked without Max, in MaxPyLang's browser engine.

Usage:
  audio_check.py patch.maxpat                 render 1 s offline, report RMS + dominant Hz
  audio_check.py synth.amxd --expect-hz 220   also check the pitch (+-10%, --tol to change)
  audio_check.py patch.maxpat --url           print a link that opens the patch in the browser
                                              player so a person can click and listen

How: the patch travels in the URL fragment (#p=gzip+base64url, never sent to a server) to
MaxPyLang's web engine (https://barnard-pl-labs.github.io/MaxPyLang/app/), whose self-test
renders it through an OfflineAudioContext. That render runs NO control messages (no loadbang,
loadmess, metro, notes or UI), so it checks the fixed signal path: sources with typed-in
arguments through to the output. A copy of the patch is adapted first (--raw skips this):
  oscillators fed only by numbers -> fixed 220 Hz     plugin~ -> cycle~ 220 test tone
  adsr~ / line~ / curve~ fed only by messages -> 1     plugout~ / dac~ -> ezdac~
The engine implements ~330 objects; others are silent stubs and are listed in the output.

Needs: pip install playwright, plus a Chromium-based browser. Uses $MPL_BROWSER, else
Chrome/Brave/Edge/Chromium from /Applications, else Playwright's own Chromium
(`python -m playwright install chromium`). Runs with a fresh temporary browser profile.
Exit code: 0 sound (and pitch ok), 1 silent / wrong pitch, 2 could not run.
"""
import argparse
import base64
import copy
import gzip
import json
import os
import struct
import sys

APP = "https://barnard-pl-labs.github.io/MaxPyLang/app/"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]


def load(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] == b"ampf":
        off = 0
        while off + 8 <= len(data):
            tag, size = data[off:off + 4], struct.unpack("<I", data[off + 4:off + 8])[0]
            if tag == b"ptch":
                return json.loads(data[off + 8:off + 8 + size].rstrip(b"\x00"))
            off += 8 + size
        raise ValueError("no ptch chunk in .amxd")
    return json.loads(data)


OSCS = {"cycle~", "saw~", "rect~", "tri~", "phasor~"}
ENVS = {"adsr~", "line~", "curve~"}


def _name(box):
    return box.get("maxclass") if box.get("maxclass") != "newobj" else (box.get("text") or "").split(" ")[0]


def harness(d):
    """Copy of the patch whose fixed signal path can be rendered. The engine's offline render
    runs no control messages (loadbang, metro, notes, UI), so values that would arrive as
    messages are frozen: see module docstring."""
    d = copy.deepcopy(d)
    pat = d["patcher"]
    boxes, lines = pat.setdefault("boxes", []), pat.setdefault("lines", [])
    by_id = {b["box"]["id"]: b["box"] for b in boxes}
    notes = []

    def is_signal(src_id, outlet):
        ot = by_id.get(src_id, {}).get("outlettype") or []
        return outlet < len(ot) and ot[outlet] in ("signal", "multichannelsignal")

    def drop_control_into(bid, inlet):
        before = len(lines)
        lines[:] = [ln for ln in lines if not (ln["patchline"]["destination"] == [bid, inlet]
                                              and not is_signal(*ln["patchline"]["source"]))]
        return before != len(lines)

    for box in by_id.values():
        name = _name(box)
        args = (box.get("text") or "").split()[1:]
        has_num = bool(args) and args[0].lstrip("-").replace(".", "", 1).isdigit()
        if name in OSCS and not has_num and drop_control_into(box["id"], 0):
            box["text"] = f"{name} 220"
            notes.append(f"{name} frequency frozen at 220 Hz")
        elif name in ENVS and not any(ln["patchline"]["destination"][0] == box["id"]
                                      and is_signal(*ln["patchline"]["source"]) for ln in lines):
            box.update({"text": "sig~ 1", "numinlets": 1, "numoutlets": 1, "outlettype": ["signal"]})
            lines[:] = [ln for ln in lines if ln["patchline"]["destination"][0] != box["id"]
                        and not (ln["patchline"]["source"][0] == box["id"] and ln["patchline"]["source"][1] > 0)]
            notes.append(f"{name} held open")
        elif name == "plugin~":
            box.update({"maxclass": "newobj", "text": "cycle~ 220", "numinlets": 2, "numoutlets": 1,
                        "outlettype": ["signal"]})
            for ln in lines:
                if ln["patchline"]["source"][0] == box["id"]:
                    ln["patchline"]["source"][1] = 0
            notes.append("plugin~ -> cycle~ 220 test tone")
        elif name in ("plugout~", "dac~"):
            box.update({"maxclass": "ezdac~", "numinlets": 2, "numoutlets": 0, "outlettype": []})
            box.pop("text", None)
            for ln in lines:
                if ln["patchline"]["destination"][0] == box["id"]:
                    ln["patchline"]["destination"][1] %= 2
            notes.append(f"{name} -> ezdac~")
    return d, notes


def engine_gaps(d):
    """Objects in the patch that the browser engine only stubs (they pass nothing through)."""
    try:
        with open(os.path.join(DATA, "web_engine.json"), encoding="utf-8") as f:
            impl = set(json.load(f)["implemented"])
        with open(os.path.join(DATA, "objects.json"), encoding="utf-8") as f:
            db = json.load(f)
    except OSError:
        return []
    alias = {a: n for n, e in db.items() for a in e.get("aka", [])}
    alias.update({"s": "send", "r": "receive", "i": "int", "f": "float", "del": "delay", "v": "value"})
    gaps = set()
    for b in d["patcher"].get("boxes", []):
        box = b["box"]
        name = box.get("maxclass") if box.get("maxclass") != "newobj" else (box.get("text") or "").split(" ")[0]
        if name and name not in impl and alias.get(name) not in impl and name not in ("comment", "panel"):
            gaps.add(name)
    return sorted(gaps)


def permalink(d):
    raw = gzip.compress(json.dumps(d, separators=(",", ":")).encode("utf-8"))
    return APP + "#p=" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def find_browser():
    env = os.environ.get("MPL_BROWSER")
    if env:
        return env
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    return None  # let Playwright use its bundled Chromium


def render(url, timeout_s):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("audio_check: needs `pip install playwright` (and a Chromium-based browser)", file=sys.stderr)
        sys.exit(2)
    exe = find_browser()
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, executable_path=exe) if exe else pw.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            print(f"audio_check: could not start a browser ({e}). Set MPL_BROWSER or run "
                  "`python -m playwright install chromium`.", file=sys.stderr)
            sys.exit(2)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
        page.wait_for_function("() => { const b = document.getElementById('selftest'); return b && !b.disabled; }",
                               timeout=timeout_s * 1000)
        page.wait_for_timeout(500)
        page.click("#selftest")
        page.wait_for_function("() => window.__selftest !== undefined", timeout=timeout_s * 1000)
        result = page.evaluate("() => window.__selftest")
        text = page.evaluate("() => document.body.innerText")
        browser.close()
    stubs = [ln.strip() for ln in text.splitlines()
             if any(k in ln.lower() for k in ("stub", "unsupported", "not yet implemented", "coverage"))]
    return result, stubs[:5]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--url", action="store_true", help="print a browser-player link and exit")
    ap.add_argument("--raw", action="store_true", help="don't adapt the patch (no auto-on toggles etc.)")
    ap.add_argument("--expect-hz", type=float, help="expected dominant frequency")
    ap.add_argument("--tol", type=float, default=0.10, help="relative pitch tolerance (default 0.10)")
    ap.add_argument("--timeout", type=int, default=45, help="seconds")
    a = ap.parse_args()

    d = load(a.path)
    if a.url:
        link = permalink(d)  # unmodified: a person clicks the toggles / ezdac~ themselves
        print(link)
        if len(link) > 8000:
            print(f"(warning: {len(link)}-character link; some chat apps truncate long links)", file=sys.stderr)
        return 0

    notes = []
    if not a.raw:
        d, notes = harness(d)
    result, stubs = render(permalink(d), a.timeout)
    gaps = engine_gaps(d)
    rms, hz = result.get("rms", 0.0), result.get("dominantHz", 0.0)
    loud = rms > 1e-4
    print(f"{os.path.basename(a.path)}: rms={rms:.4f} dominant~{hz:.1f} Hz -> {'SOUND' if loud else 'SILENT'}")
    if notes:
        print("  test harness: " + ", ".join(sorted(set(notes))))
    for s in stubs:
        print(f"  engine: {s}")
    if gaps:
        print("  not implemented in the browser engine (silent there, fine in Max): " + ", ".join(gaps))
    ok = loud
    if loud and a.expect_hz:
        good = abs(hz - a.expect_hz) <= a.expect_hz * a.tol
        print(f"  pitch {'OK' if good else 'OFF'}: expected {a.expect_hz:g} Hz +-{a.tol:.0%}")
        ok = good
    if not loud:
        print("  silent: " + ("likely the unimplemented objects above; " if gaps else "") +
              "or the signal path is broken (a gain stuck at 0, a source never reaching the output)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
