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
(the PyPI release is older but also works). Max is only needed to open the results.

Update later with `claude plugin marketplace update maxpylang-tools && claude plugin update maxpylang@maxpylang-tools`.

## Contents

```
.claude-plugin/plugin.json        plugin manifest
.claude-plugin/marketplace.json   makes this repo a one-plugin marketplace
skills/maxpylang/
  SKILL.md                        workflow, Max semantics, layout rules, quirks
  scripts/mpl.py                  safety layer over MaxPyLang (copied next to build scripts)
  scripts/maxref.py               object lookup / search / typo check (stdlib only)
  scripts/inspect_patch.py        .maxpat/.amxd summary + linter (stdlib only)
  references/recipes.md           10 tested build scripts (synths, sequencer, Jitter, M4L, editing)
  references/m4l.md               Max for Live rules and live.* parameters
  references/api.md               raw MaxPyLang API + known bugs
  data/objects.json               1063 objects: I/O counts, args, inlet/outlet docs, domains
examples/                         two patches built by the plugin, with their build scripts
```

The scripts also work without Claude:

```bash
python3 skills/maxpylang/scripts/maxref.py -s lowpass
```

```bash
python3 skills/maxpylang/scripts/inspect_patch.py examples/chorus.amxd
```

## Status

- All recipes and examples build and lint clean on MaxPyLang 0.1.1 (PyPI) and the current GitHub main.
- Generated files have not yet been checked across Max/Live versions. The `live.*` UI objects and their
  parameter settings are written by hand (MaxPyLang's database has none); please open an issue if one
  misbehaves in Live.

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
| noisy stdout on every call | silenced |

## Developing

Claude Code runs a cached copy of an installed plugin. To try local changes, start Claude with
`claude --plugin-dir /path/to/maxpylang-claude-plugin`. To release, bump `version` in both
`.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

## Credits and license

MIT (see `LICENSE`). MaxPyLang is by Ranger Liu and contributors (Barnard PL Labs), MIT.
`data/objects.json` is derived from MaxPyLang's object data; its short object and inlet/outlet descriptions
originate from the Max reference documentation. Max, MSP, Jitter, Max for Live and Ableton Live are
trademarks of their respective owners.
