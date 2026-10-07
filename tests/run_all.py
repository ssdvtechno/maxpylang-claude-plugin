#!/usr/bin/env python3
"""
Run every recipe, the SKILL.md skeleton and the examples; lint every patch they produce.

  python tests/run_all.py              build + lint (needs maxpylang)
  python tests/run_all.py --render     also draw every patch (matplotlib optional; SVG otherwise)
  python tests/run_all.py --audio      also render audio in the browser engine (needs playwright)
  python tests/run_all.py --keep out/  keep the generated files

Exit code 1 if any script fails, any patch has a lint ERROR, a device has no face,
or (with --audio) a patch expected to sound is silent.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "maxpylang")
SCRIPTS = os.path.join(SKILL, "scripts")

# Patches whose fixed signal path must make sound in the browser engine (see audio_check.py).
EXPECT_SOUND = {"keyboard_synth.maxpat", "additive.maxpat", "drone_field.maxpat", "keyboard_synth_v2.maxpat",
                "stereo_delay.amxd", "mono_synth.amxd", "tempo_tremolo.amxd", "chorus.amxd", "tone.maxpat",
                "arpeggiator.maxpat", "step_sequencer.maxpat"}
FAIL_WARNINGS = ("device has no face", "is not on the device face", "openinpresentation is off")


def code_blocks(path):
    with open(path, encoding="utf-8") as f:
        return re.findall(r"```python\n(.*?)```", f.read(), re.S)


def run(cmd, cwd, env=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--audio", action="store_true")
    ap.add_argument("--keep")
    a = ap.parse_args()

    work = a.keep or tempfile.mkdtemp(prefix="mpl-tests-")
    os.makedirs(work, exist_ok=True)
    shutil.copy(os.path.join(SCRIPTS, "mpl.py"), work)
    env = dict(os.environ, PYTHONPATH=SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", ""))
    py = sys.executable
    failures = []

    scripts = []
    for i, block in enumerate(code_blocks(os.path.join(SKILL, "references", "recipes.md")), 1):
        scripts.append((f"recipe_{i:02d}.py", block))
    skeleton = code_blocks(os.path.join(SKILL, "SKILL.md"))[0]
    scripts.append(("skill_skeleton.py", skeleton))
    for name in sorted(os.listdir(os.path.join(ROOT, "examples"))):
        if name.endswith(".py"):
            with open(os.path.join(ROOT, "examples", name), encoding="utf-8") as f:
                scripts.append((f"example_{name}", f.read()))

    for name, code in scripts:
        with open(os.path.join(work, name), "w", encoding="utf-8") as f:
            f.write(code)
        rc, out = run([py, name], work, env)
        status = "ok" if rc == 0 else "FAIL"
        print(f"[{status:4}] {name}")
        if rc:
            failures.append(name)
            print("       " + "\n       ".join(out.strip().splitlines()[-6:]))

    patches = sorted(f for f in os.listdir(work) if f.endswith((".maxpat", ".amxd")))
    for pfile in patches:
        rc, out = run([py, os.path.join(SCRIPTS, "inspect_patch.py"), pfile, "--lint"], work)
        bad = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("ERROR")
               or any(w in ln for w in FAIL_WARNINGS)]
        print(f"[{'ok' if not bad else 'FAIL':4}] lint {pfile}")
        for b in bad:
            print(f"       {b}")
        if bad:
            failures.append(f"lint {pfile}")
        if a.render:
            rc, out = run([py, os.path.join(SCRIPTS, "render_patch.py"), pfile], work)
            if rc:
                failures.append(f"render {pfile}")
                print(f"[FAIL] render {pfile}\n       {out.strip()[-300:]}")
        if a.audio and pfile in EXPECT_SOUND:
            rc, out = run([py, os.path.join(SCRIPTS, "audio_check.py"), pfile], work)
            print(f"[{'ok' if rc == 0 else 'FAIL':4}] audio {out.strip().splitlines()[0] if out.strip() else pfile}")
            if rc:
                failures.append(f"audio {pfile}")
                print("       " + "\n       ".join(out.strip().splitlines()[1:]))

    print(f"\n{len(scripts)} scripts, {len(patches)} patches, {len(failures)} failure(s)" +
          (f": {', '.join(failures)}" if failures else ""))
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
