---
type: llm
weight: 1
---

Judge the agent's final message. It should report an 8-voice polyphonic synth that makes clear:
- it uses poly~ with a separate voice patch, and both files must stay in the same folder
- MIDI comes in through notein and notes reach the voices (e.g. prepend midinote or equivalent)
- each voice has an envelope that releases on note-off, and voices are freed (thispoly~ or equivalent)
- the output goes through a safe gain to the speakers in stereo
- the patch was checked (linted), and it explains how to play it; a build script was kept
Score 1.0 if all are clearly stated, lower in proportion to what is missing or wrong.
