---
type: llm
weight: 1
---

The answer names a real MSP resonant lowpass object (lores~, svf~, reson~ is bandpass so not ideal,
biquad~ with filtercoeff~ also fine) and describes its inlets correctly. For lores~: inlet 0 audio input,
inlet 1 cutoff frequency, inlet 2 resonance (0-1). For svf~: input, cutoff, Q; its outlets give
lowpass/highpass/bandpass/notch. Inlet descriptions must not be invented. Score 1.0 for a correct,
specific answer (inlets may be numbered from 0 or from 1, or called left/middle/right); 0.5 if the object is right but inlet details are vague or partly wrong; 0 if wrong.
