## Defaults and modes (harmonized)

| Mode | Audio handling | Image handling | Beat effects | Mask usage |
|---|---|---|---|---|
| Default (classic) | Merge all audio files in the folder into one long track | Shuffle-loop all images to fill duration | Not applicable | Background/foreground visual tweaks (e.g., BG blur/BW, FG sharpen/saturate) |
| Option: per-audio | One video per audio file | Shuffle-loop images to match that audio | Not applicable | Same as classic |
| Beat-matched | One audio file (or merged) drives cut plan | Images mapped to planned durations | Pulse/bloom/counters at beats | Mask gates beat effects to FG/BG (alphamerge+overlay); transitions not masked |

Notes:
- Transitions are not masked; masking applies to overlays/effects.
- For beat-matched mode, masking confines beat pulses/bloom to FG/BG only; for classic mode, masking applies stylistic splits (e.g., blur only background).

## Beat-Aligned Slideshow (`beatslides`) - Command Reference

### Synopsis

```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides <audio_file> <images_dir> [options]
```

### Core arguments

- **audio_file**: Path to a single audio file (mp3, m4a, etc.). Used for beat detection and final muxing.
- **images_dir**: Directory containing images (jpg, jpeg, png). Images are sorted and looped as needed.

### Planning options

- **--period MIN MAX** (default: 5.0 10.0)
  - Window-constrained selection. Chooses cuts such that segment length remains within [MIN, MAX] seconds.
  - Practical: these are the acceptable slide lengths; longer tracks feel more cinematic; smaller values feel more frenetic.

- **--target SECONDS** (default: 7.5)
  - Preference for average segment length within the window. Selection aims for the nearest beat to this target.

- **--grace SECONDS** (default: 0.5)
  - Grace expansion when no beat exists in the window; planner widens the search by this amount to find a cut.

- **--min-gap SECONDS** (default: 2.05)
  - Safety margin for transitions (>= 2*xfade + 0.05). For hardcuts, this prevents ultra-short segments.

- **--phase SECONDS** (default: 0.0)
  - Phase/latency compensation applied to beats before selection. Negative leads cuts earlier for punchier sync.

- **--strict**
  - If set, the planner does not widen the window on sparse sections; it will pick the nearest beat inside the strict window only.

- **--all-beats**
  - Bypass selection and cut on every detected beat. Useful for diagnostics or hyper-cut styles.

- **--audio-end SECONDS** (default: auto)
  - Override end time for planning; by default the true audio duration is used.

- **--max-seconds SECONDS**
  - Preview limit. Shorten planned duration for quick demos; omit for full-length output.

### Rendering mode

- **--hardcuts**
  - Render using hard cuts only (no xfade). Recommended for verifying on-beat timing.

- Transitions mode (experimental):
  - **--transition NAME** (default: fade)
  - **--xfade SECONDS** (default: 0.6)
  - **--align end|midpoint** (default: midpoint)
  - Tip: for on-beat perceptual switch, prefer `--align midpoint --xfade 0.5..0.8 --phase -0.03`.
- **--preset NAME**
  - `music-video` (default style): `align=midpoint, xfade=0.6, phase=-0.03, period=5..10, target=7.5, quantize=nearest`
  - `hypercut`: aggressive, near-beat cuts: `align=end, xfade=0.25, phase=-0.01, period=0.7..2.0, target=1.2, quantize=floor, all-beats`
  - `slow-cinematic`: long holds, soft fades: `align=midpoint, xfade=1.2, phase=-0.01, period=8..16, target=12.0, quantize=nearest`
  - `documentary`: moderate holds, subtle fades: `align=end, xfade=0.3, phase=0.0, period=6..12, target=9.0, quantize=floor`
  - `edm-strobe`: fast beat-driven: `align=midpoint, xfade=0.3, phase=-0.02, period=0.5..1.2, target=0.75, quantize=nearest, all-beats`
  - Preset behavior: presets set values only when you left the parser defaults; any explicit flag you provide wins. Min gap is enforced to `>= 2*xfade + 0.05` automatically.

#### Transitions overlays (diagnostics on top of transitions)
- **--beat-mult N** (default: 1)
  - Downsample overlays to every Nth beat (e.g., 2 = every other beat) to reduce visual clutter.
- **--overlay-phase SECONDS** (default: 0.0)
  - Phase offset applied to overlays only (does not change transitions). Useful to test perceived latency.
- **--overlay-guard SECONDS** (default: 0.0)
  - Suppress beat ticks/pulses that occur within N seconds of a transition landing to avoid double flashes.
- **--cut-markers**
  - Draw a red vertical tick at the transition landing time. White ticks are the true beat times.

Notes:
- In `--align midpoint`, the fade starts before the beat and the mid-point of the fade lands on the beat. Red cut markers (if enabled) visualize the transition landing; white ticks visualize actual beat times.
- For strict on-beat hardcuts, use `--hardcuts` (no crossfade) and verify alignment with `--mark-beats`.

### Frame quantization

- **--frame-quantize nearest|floor|ceil** (default: nearest)
  - Quantizes each segment duration to the video frame grid to avoid sub-frame drift.
  - nearest: round to nearest frame (balanced)
  - floor: always shorten to previous frame boundary (keeps cuts early)
  - ceil: always extend to next frame boundary (keeps cuts late)

### Planning I/O

- **--plan-out FILE.json**
  - Write a planning JSON containing beats, selected cuts, derived durations, images used, and key parameters. Useful for reproducible runs and debugging.
- **--plan-in FILE.json**
  - Read a planning JSON and render directly from it (skips detection/selection). If images in the plan are missing, falls back to scanning the images_dir.

### Debug overlays (hardcuts mode)

- **--mark-beats**
  - Draw a white vertical bar for every detected beat.

- **--pulse** (with defaults)
  - Subtle image pulse at each beat.
  - Defaults: `--pulse-sat 1.25 --pulse-bright 0.0 --pulse-dur 0.08`.

- **--bloom** (optional glow)
  - Adds gaussian blur pulse at each beat for a soft bloom.
  - Defaults: `--bloom-sigma 8.0 --bloom-dur 0.08`.

- **--mask-scope none|foreground|background** (requires rembg)
  - Restrict pulse/glow overlays and per-boundary fallback effects to just the subject (foreground) or just the background.
  - Mask sources: the renderer prefers precomputed masks placed next to images as `<name>_mask.png` or in a sibling `masks/<name>_mask.png`. If not present and rembg is available, masks are generated lazily.
  - Pipeline: effects are applied on a split branch, alpha-merged with the (possibly inverted) grayscale mask, and composited back over the unmodified base using `alphamerge` + `overlay`. This preserves full color while guaranteeing no bleed onto the protected region.
  - Mask sync: the mask stream is scaled/padded to match each input and crossfaded in lockstep with the visuals so boundaries stay aligned.
  - Notes: mask generation adds processing time; if rembg is unavailable, scope silently falls back to `none`.

### Safety fallback

- Global fallback: the renderer will fall back to all-hardcuts when every pair is too short for a safe crossfade.
- Per-segment fallback: during rendering, if an individual boundary is too short for the selected xfade, that boundary is concatenated as a hardcut while other boundaries still use crossfades. This prevents broken transitions on rapid cuts without losing crossfades elsewhere.

### Audio options

- **--no-audio**
  - Skip muxing. By default, the final MP4 includes the input audio.
- Test policy: all test movie files must include audio. For smoke demos, prefer muxed outputs; only use `--no-audio` for filter-graph diagnostics.

### Examples

Render a full-length hardcut debug with overlays:
```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images \
  --period 5 10 --target 7.5 --hardcuts --mark-beats --pulse --bloom --counter
```

Every-beat cut diagnostic (short preview):
```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images \
  --all-beats --hardcuts --mark-beats --counter --max-seconds 30
```

Transitions test (perceptual on-beat midpoints):
```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images \
  --transition fade --xfade 0.6 --align midpoint --phase -0.03
```

Transitions with on-beat overlays (every other beat) and guard near transitions:
```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images \
  --transition fade --xfade 0.6 --align midpoint --phase -0.03 \
  --beat-mult 2 --overlay-guard 0.08 --frame-quantize floor --debug
```

Save plan then render from plan:
```bash
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images --preset music-video --plan-out plan.json
PYTHONPATH=src python3 -m slideshow_maker.cli.beatslides song.mp3 ./images --plan-in plan.json --hardcuts --mark-beats --counter
```

### Notes

- If beats feel late/early, adjust `--phase` slightly (e.g., -0.03 .. +0.03).
- For performance, overlays add filter complexity. Use `--hardcuts` for verification, then iterate with transitions.


