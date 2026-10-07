# maxpylang-claude-plugin

> **Unofficial.** A community Claude Code plugin built on top of
> [MaxPyLang](https://github.com/Barnard-PL-Labs/MaxPyLang). Not affiliated with or endorsed by
> Barnard PL Labs, Cycling '74 or Ableton.

Lets Claude build, edit and lint **Max/MSP/Jitter patches** (`.maxpat`) and **Max for Live devices**
(`.amxd`) by writing Python with MaxPyLang. Ask for "a granular delay as an M4L audio effect" or
"a 16-step sequencer patch" and Claude writes a build script, runs it, lints the result and hands you the file.

## Install

```bash
claude plugin marketplace add ssdvtechno/maxpylang-claude-plugin
```

```bash
claude plugin install maxpylang@maxpylang-tools
```

Restart Claude Code. The skill triggers on Max/MSP/Max for Live requests, or call it directly with
`/maxpylang:maxpylang`.

Needs Python 3.9+. Claude installs MaxPyLang from GitHub into the project's venv when it's missing
(the PyPI release is older but also works; offline, it installs the bundled copy). Max is only needed to
open the results. Optional: `matplotlib` for PNG previews, `playwright` for the audio check.

Update later with `claude plugin marketplace update maxpylang-tools && claude plugin update maxpylang@maxpylang-tools`.

## Contents

```
.claude-plugin/plugin.json        plugin manifest
.claude-plugin/marketplace.json   makes this repo a one-plugin marketplace
skills/maxpylang/
  SKILL.md                        workflow, Max semantics, layout rules, quirks
  scripts/mpl.py                  safety layer over MaxPyLang (copied next to build scripts)
  scripts/maxref.py               object lookup / search / typo check (stdlib only)
  scripts/inspect_patch.py        .maxpat/.amxd summary + linter, incl. Max for Live device faces (stdlib only)
  scripts/render_patch.py         draw a patch or device face as PNG (matplotlib) or SVG (stdlib)
  scripts/audio_check.py          render audio in MaxPyLang's browser engine (playwright) / share a listen link
  references/recipes.md           15 tested build scripts (synths, poly~, gen~, js, Jitter GL, M4L, Live API, editing)
  references/m4l.md               Max for Live rules, device faces, live.* parameters and I/O
  references/api.md               raw MaxPyLang API + known bugs
  data/objects.json               1068 objects: I/O counts, args, inlet/outlet docs, domains
  data/web_engine.json            objects the browser engine implements (for audio_check)
  vendor/                         MaxPyLang wheel (GitHub 0a171e1, MIT) for installs without network
examples/                         two patches built by the plugin, with their build scripts
tests/run_all.py                  builds and checks every recipe and example (used by CI)
evals/                            `claude plugin eval` cases: does Claude use the skill well?
```

The scripts also work without Claude:

```bash
python3 skills/maxpylang/scripts/maxref.py -s lowpass
```

```bash
python3 skills/maxpylang/scripts/inspect_patch.py examples/chorus.amxd
```

```bash
python3 skills/maxpylang/scripts/render_patch.py examples/chorus.amxd --presentation
```

```bash
python3 skills/maxpylang/scripts/audio_check.py examples/chorus.amxd
```

## What gets checked

- **CI** (`.github/workflows/ci.yml`): every recipe and example is built on Python 3.10 and 3.12 against both
  MaxPyLang releases (PyPI and GitHub main, also weekly), linted and rendered; patches that should make
  sound are rendered in the browser engine; the manifest is validated.
- **Evals** (`evals/`): five prompts graded by an LLM judge, including one where the skill must stay out of
  the way. Run them with
  `claude plugin eval . --trust-plugin --allow-tools Bash Write Edit --runs 1`.
- **Audio check limits**: the browser engine's offline render runs no control messages (loadbang, metro,
  notes, UI), so the check covers the fixed signal path. The engine implements ~330 of Max's objects; the
  check lists the others.
- **Not checked**: opening files in Max/Live. `live.*` inlet/outlet counts were verified against real
  Max-saved patches on GitHub; generated `gen~` boxes and device faces have not been opened in Max yet.
  Please open an issue if something misbehaves.

## What `mpl.py` works around in MaxPyLang

| MaxPyLang behaviour | mpl |
|---|---|
| `comment` text includes the word "comment" | `mpl.comment` writes verbatim text |
| unknown objects share one JSON dict (duplicate ids) | `mpl.at` raises with suggestions |
| `maxpylang.objects` stubs are singletons | refuses to place one twice |
| rejects valid text: `metro 4n`, `expr`, `noteout` ... | falls back to a raw box with correct I/O |
| wrong I/O: `send`, `switch N` (crash), `selector~ N`, `dac~ 1 2 3 4`, `join N` | corrected I/O table |
| `s r i f del v` abbreviations unknown | expanded |
| no `live.*` UI objects | `mpl.ui` + `mpl.live_param` |
| grid placement offsets x by +80 | exact coordinates |
| `load_file` crashes on Max-saved patches with UI boxes | `mpl.load` |
| PyPI 0.1.1 has no `.amxd` save | `mpl.save` writes `.amxd` itself |
| no presentation view for devices | `mpl.face` / `mpl.present` |
| `poly~`, `gen~`, `js` I/O unknown | `mpl.poly`, `mpl.gen`, `mpl.js` |
| noisy stdout on every call | silenced |

## Developing

Claude Code runs a cached copy of an installed plugin. To try local changes, start Claude with
`claude --plugin-dir /path/to/maxpylang-claude-plugin`. Before pushing, run `python tests/run_all.py --render`
(add `--audio` with playwright installed). To release, bump `version` in both `.claude-plugin/plugin.json`
and `.claude-plugin/marketplace.json`.

## Credits and license

MIT (see `LICENSE`). MaxPyLang is by Ranger Liu and contributors (Barnard PL Labs), MIT.
`data/objects.json` is derived from MaxPyLang's object data; its short object and inlet/outlet descriptions
originate from the Max reference documentation. Max, MSP, Jitter, Max for Live and Ableton Live are
trademarks of their respective owners.
