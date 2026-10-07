---
type: llm
weight: 1
---

Judge the agent's final message. It should report that filter.amxd was created as a Max for Live
**audio effect** and make clear that:
- audio comes in through plugin~ and leaves through plugout~ (not ezdac~/dac~), stereo, with a limiter
  or clip~ before the output
- the filter is a resonant lowpass (lores~, svf~, biquad~/filtercoeff~ or similar)
- Cutoff and Resonance are Live parameters (live.dial or another live.* control) with sensible ranges
- the knobs appear on the device in Live (device face / presentation view)
- the result was checked (linted, and sound-checked or honestly said why not)
- a build script was kept so the device can be regenerated
Score 1.0 if all are clearly stated, lower in proportion to what is missing or wrong; 0 if no .amxd.
