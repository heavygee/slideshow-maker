#!/usr/bin/env python3
"""
Minimal CLI entry to exercise Phase 1: detect beats and select cut times.

Usage examples:
  python3 -m slideshow_maker.cli.beatslides input.mp3 --period 5 10 --target 7.5 \
      --grace 0.5 --min-gap 2.05 --duration 1.0 --audio-end 180
"""
from __future__ import annotations

import argparse
import sys
import json
import os
from typing import List

from ..beat_detection import detect_beats
from ..beat_selection import select_beats
from ..video import create_slideshow_with_durations
from .. import audio as audio_mod
from ..config import AUDIO_OUTPUT
from ..utils import get_audio_duration


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description="Beat-aligned planning (Phase 2 minimal)")
    p.add_argument("audio", help="Path to audio file, a directory of audio files, or 'auto' to use images_dir audio")
    p.add_argument("images_dir", help="Directory of images")
    p.add_argument("--period", nargs=2, type=float, metavar=("MIN", "MAX"), default=[5.0, 10.0])
    p.add_argument("--target", type=float, default=7.5)
    p.add_argument("--grace", type=float, default=0.5)
    p.add_argument("--min-gap", type=float, default=2.05, help="Min cut gap safety (>= 2*xfade+0.05)")
    p.add_argument("--phase", type=float, default=-0.03)
    p.add_argument("--strict", action="store_true", default=False)
    p.add_argument("--audio-end", type=float, default=None, help="Audio length in seconds (optional)")
    p.add_argument("--transition", type=str, default="fade", help="xfade transition type (CPU)")
    p.add_argument("--xfade", type=float, default=0.6, help="Transition duration seconds")
    p.add_argument("--align", type=str, choices=["end","midpoint"], default="midpoint", help="Align transition end or midpoint to beat")
    p.add_argument("--hardcuts", action="store_true", default=False, help="Render without transitions (durations only)")
    p.add_argument("--no-audio", action="store_true", default=False, help="Skip muxing audio into the output")
    p.add_argument("--debug", action="store_true", default=False, help="Print detected beats and selected cuts; visualize cut markers")
    p.add_argument("--mark-beats", action="store_true", default=False, help="Render markers on every detected beat (hardcuts only)")
    p.add_argument("--all-beats", action="store_true", default=False, help="Use every detected beat as a transition boundary")
    p.add_argument("--max-seconds", type=float, default=None, help="Limit output plan to first N seconds of audio")
    p.add_argument("--pulse", action="store_true", default=False, help="Apply subtle saturation/brightness pulse on each beat")
    p.add_argument("--pulse-sat", type=float, default=1.25, help="Pulse saturation multiplier (>1 = boost)")
    p.add_argument("--pulse-bright", type=float, default=0.00, help="Pulse brightness delta (-1..1)")
    p.add_argument("--pulse-dur", type=float, default=0.08, help="Pulse duration seconds per beat")
    p.add_argument("--bloom", action="store_true", default=False, help="Add subtle gaussian bloom pulse on each beat")
    p.add_argument("--bloom-sigma", type=float, default=8.0, help="Bloom blur sigma (higher is softer)" )
    p.add_argument("--bloom-dur", type=float, default=0.08, help="Bloom pulse duration seconds per beat")
    p.add_argument("--counter", action="store_true", default=False, help="Show numeric counter at each beat")
    p.add_argument("--counter-size", type=int, default=36, help="Beat counter font size")
    p.add_argument("--counter-pos", type=str, choices=["tr","tl","br","bl"], default="tr", help="Beat counter position")
    p.add_argument("--preset", type=str, choices=["music-video","hypercut","slow-cinematic","documentary","edm-strobe"], help="Preset of sensible defaults")
    p.add_argument("--beat-mult", type=int, default=1, help="Overlay beat multiplier (1=every beat, 2=every other, etc.)")
    p.add_argument("--overlay-phase", type=float, default=0.0, help="Overlay phase offset seconds (advance/retard overlays)")
    p.add_argument("--cut-markers", action="store_true", default=False, help="Draw red tick marks at transition landings")
    p.add_argument("--overlay-guard", type=float, default=0.0, help="Do not pulse/tick within N seconds of a transition")
    p.add_argument("--frame-quantize", type=str, choices=["nearest","floor","ceil"], default="nearest", help="Quantize segment durations to frame grid")
    p.add_argument("--plan-out", type=str, default=None, help="Write planning JSON to this path")
    p.add_argument("--plan-in", type=str, default=None, help="Read planning JSON and render from it (skips detection/selection)")
    p.add_argument("--xfade-min", type=float, default=0.25, help="Minimum effective xfade seconds; shorter boundaries hardcut")
    p.add_argument("--fallback-style", type=str, choices=["none","pulse","bloom","whitepop","blackflash"], default="none", help="Effect to apply on too-short boundaries")
    p.add_argument("--fallback-dur", type=float, default=0.06, help="Duration of per-boundary fallback effect")
    p.add_argument("--mask-scope", type=str, choices=["none","foreground","background"], default="none", help="Restrict pulse/bloom to foreground or background using rembg mask")
    p.add_argument("--per-audio", action="store_true", default=False, help="Render one video per audio file (when audio is a dir or 'auto')")
    args = p.parse_args(argv)

    # Apply preset defaults early (without clobbering explicit overrides)
    def _apply_preset(preset_name: str):
        # Parser defaults snapshot
        DEF_ALIGN = "midpoint"
        DEF_XFADE = 0.6
        DEF_PHASE = -0.03
        DEF_PERIOD = [5.0, 10.0]
        DEF_TARGET = 7.5
        DEF_MIN_GAP = 2.05
        DEF_QUANT = "nearest"
        DEF_ALL_BEATS = False

        PRESETS = {
            "music-video": {
                "align": "midpoint",
                "xfade": 0.6,
                "phase": -0.03,
                "period": [5.0, 10.0],
                "target": 7.5,
                "quantize": "nearest",
            },
            "hypercut": {
                # Aggressive, near-every-beat style
                "align": "end",
                "xfade": 0.25,
                "phase": -0.01,
                "period": [0.7, 2.0],
                "target": 1.2,
                "quantize": "floor",
                "all_beats": True,
            },
            "slow-cinematic": {
                # Long holds with soft transitions
                "align": "midpoint",
                "xfade": 1.2,
                "phase": -0.01,
                "period": [8.0, 16.0],
                "target": 12.0,
                "quantize": "nearest",
            },
            "documentary": {
                # Moderate holds, subtle fades, keep cuts slightly early
                "align": "end",
                "xfade": 0.3,
                "phase": 0.0,
                "period": [6.0, 12.0],
                "target": 9.0,
                "quantize": "floor",
            },
            "edm-strobe": {
                # Fast, beat-driven with short xfades or hardcuts
                "align": "midpoint",
                "xfade": 0.3,
                "phase": -0.02,
                "period": [0.5, 1.2],
                "target": 0.75,
                "quantize": "nearest",
                "all_beats": True,
            },
        }

        spec = PRESETS.get(preset_name)
        if not spec:
            return

        # Only set when user left parser defaults
        args.align = args.align if args.align != DEF_ALIGN else spec.get("align", DEF_ALIGN)
        args.xfade = float(args.xfade) if args.xfade != DEF_XFADE else float(spec.get("xfade", DEF_XFADE))
        args.phase = float(args.phase) if args.phase != DEF_PHASE else float(spec.get("phase", DEF_PHASE))
        args.period = args.period if list(args.period) != DEF_PERIOD else list(spec.get("period", DEF_PERIOD))
        args.target = float(args.target) if args.target != DEF_TARGET else float(spec.get("target", DEF_TARGET))
        # Quantize applies to renderer; set when default
        args.frame_quantize = (
            args.frame_quantize if args.frame_quantize != DEF_QUANT else str(spec.get("quantize", DEF_QUANT))
        )
        # Optional all-beats for hypercut/edm; set only if user didn't ask otherwise
        if spec.get("all_beats") and args.all_beats == DEF_ALL_BEATS:
            args.all_beats = True

        # Ensure min-gap is safe for the chosen xfade (>= 2*xfade + 0.05)
        try:
            args.min_gap = max(float(args.min_gap if hasattr(args, "min_gap") else DEF_MIN_GAP), 2.0 * float(args.xfade) + 0.05)
        except Exception:
            args.min_gap = 2.0 * float(args.xfade) + 0.05

    if args.preset:
        _apply_preset(args.preset)

    plan = None
    if args.plan_in:
        try:
            with open(args.plan_in, "r") as f:
                plan = json.load(f)
        except Exception as e:
            print(f"Failed to read plan JSON: {e}", file=sys.stderr)
            return 10

    def _render_for_audio(one_audio_path: str) -> int:
        nonlocal args, plan
        if plan is not None:
            beats = plan.get("beats", [])
            cuts = plan.get("cuts", [])
            durations = plan.get("durations", [])
            if args.debug:
                print(f"Loaded plan: beats={len(beats)} cuts={len(cuts)} durations={len(durations)}")
        else:
            beats = detect_beats(one_audio_path)
            if not beats:
                print("No beats detected", file=sys.stderr)
                return 1
            if args.debug:
                print(f"Detected beats ({len(beats)}):")
                print(", ".join(f"{b:.3f}" for b in beats[:50]) + ("..." if len(beats) > 50 else ""))
            if args.audio_end is None:
                audio_end = get_audio_duration(one_audio_path) or (beats[-1] + args.target)
            else:
                audio_end = float(args.audio_end)
            if args.max_seconds is not None:
                audio_end = min(audio_end, float(args.max_seconds))
            period_min, period_max = float(args.period[0]), float(args.period[1])
            if args.all_beats:
                cuts = [b for b in beats if b <= audio_end]
            else:
                cuts = select_beats(
                    beats,
                    audio_end=audio_end,
                    period_min=period_min,
                    period_max=period_max,
                    target_period=args.target,
                    strict=bool(args.strict),
                    grace=float(args.grace),
                    min_cut_gap=float(args.min_gap),
                    phase=float(args.phase),
                    strategy="nearest",
                )
        # Compute durations from cuts relative to start
        if not cuts:
            print("No cuts selected", file=sys.stderr)
            return 2

        if args.debug:
            print(f"Selected cuts ({len(cuts)}):")
            print(", ".join(f"{c:.3f}" for c in cuts[:50]) + ("..." if len(cuts) > 50 else ""))

        # Build absolute segment durations from t=0 to each cut unless plan provides them
        if not plan or not durations:
            durations = []
            if cuts:
                last = 0.0
                for c in cuts:
                    if c <= last:
                        continue
                    durations.append(max(0.05, c - last))
                    last = c
                # Add a short tail (half target) to close the video
                durations.append(max(0.2, args.target * 0.5))

        # Map images
        import glob
        exts = ["*.png", "*.jpg", "*.jpeg"]
        images = []
        plan_images = (plan.get("images") if plan else None) or []
        if plan_images:
            images = [p for p in plan_images if os.path.exists(p)]
        if not images:
            for e in exts:
                images.extend(glob.glob(os.path.join(args.images_dir, e)))
            images = sorted(images)
        if not images:
            print("No images found", file=sys.stderr)
            return 3

        # Loop images if fewer than segments
        if len(images) < len(durations):
            reps = (len(durations) + len(images) - 1) // len(images)
            images = (images * reps)[: len(durations)]
        else:
            images = images[: len(durations)]

        out_file = "beat_aligned.mp4"
        if args.hardcuts:
            beat_markers = beats if args.mark_beats else None
            pulse_beats = beats if args.pulse else None
            ok = create_slideshow_with_durations(
                images,
                durations,
                out_file,
                quantize=args.frame_quantize,
                visualize_cuts=args.debug,
                beat_markers=beat_markers,
                pulse_beats=pulse_beats,
                pulse_duration=float(args.pulse_dur),
                pulse_saturation=float(args.pulse_sat),
                pulse_brightness=float(args.pulse_bright),
                pulse_bloom=bool(args.bloom),
                pulse_bloom_sigma=float(args.bloom_sigma),
                pulse_bloom_duration=float(args.bloom_dur),
                counter_beats=beats if args.counter else None,
                counter_fontsize=int(args.counter_size),
                counter_position=str(args.counter_pos),
                mask_scope=str(args.mask_scope),
            )
        else:
            try:
                from ..video import create_beat_aligned_with_transitions
            except Exception as e:
                print(f"Transitions renderer unavailable: {e}", file=sys.stderr)
                return 4
            ok = create_beat_aligned_with_transitions(
                images,
                durations,
                out_file,
                quantize=args.frame_quantize,
                transition_type=args.transition,
                transition_duration=float(args.xfade),
                min_effective=float(args.xfade_min),
                align=args.align,
                mark_transitions=bool(args.debug or args.mark_beats),
                marker_duration=0.12,
                pulse=bool(args.pulse),
                pulse_duration=float(args.pulse_dur),
                pulse_saturation=float(args.pulse_sat),
                pulse_brightness=float(args.pulse_bright),
                bloom=bool(args.bloom),
                bloom_sigma=float(args.bloom_sigma),
                bloom_duration=float(args.bloom_dur),
                overlay_beats=beats,
                overlay_beat_multiplier=int(args.beat_mult),
                overlay_phase=float(args.overlay_phase),
                overlay_guard_seconds=float(args.overlay_guard),
                mark_cuts=bool(args.cut_markers),
                fallback_style=str(args.fallback_style),
                fallback_duration=float(args.fallback_dur),
                counter_beats=beats if args.counter else None,
                counter_fontsize=int(args.counter_size),
                counter_position=str(args.counter_pos),
                mask_scope=str(args.mask_scope),
            )
            if not ok:
                return 4
            print(f"✅ Created {out_file} with {len(images)} images and {len(durations)} segments")

        # Write planning JSON if requested
        if args.plan_out:
            try:
                plan_payload = {
                    "audio": args.audio,
                    "images_dir": args.images_dir,
                    "images": images,
                    "beats": beats,
                    "cuts": cuts,
                    "durations": durations,
                    "params": {
                        "align": args.align,
                        "xfade": float(args.xfade),
                        "phase": float(args.phase),
                        "period": [float(args.period[0]), float(args.period[1])],
                        "target": float(args.target),
                        "grace": float(args.grace),
                        "min_gap": float(args.min_gap),
                        "hardcuts": bool(args.hardcuts),
                        "transition": args.transition,
                        "quantize": args.frame_quantize,
                    },
                }
                with open(args.plan_out, "w") as f:
                    json.dump(plan_payload, f, indent=2)
                print(f"📝 Wrote plan JSON -> {args.plan_out}")
            except Exception as e:
                print(f"Warning: failed to write plan JSON: {e}", file=sys.stderr)

        if not args.no_audio:
            if not audio_mod.merge_audio([one_audio_path], AUDIO_OUTPUT):
                print("Warning: failed to prepare audio track; leaving video without audio", file=sys.stderr)
                return 0
            final_with_audio = "beat_aligned_with_audio.mp4"
            if not audio_mod.combine_video_audio(out_file, AUDIO_OUTPUT, final_with_audio):
                print("Warning: failed to mux audio; leaving video without audio", file=sys.stderr)
                return 0
            print(f"🎵 Muxed audio -> {final_with_audio}")
        return 0

    # Harmonized default: 'auto' or directory means merge all audio in images_dir; optional --per-audio
    audio_arg = args.audio
    if audio_arg.lower() == 'auto' or os.path.isdir(audio_arg):
        source_dir = args.images_dir if audio_arg.lower() == 'auto' else audio_arg
        audio_files = audio_mod.find_audio_files(source_dir)
        if not audio_files:
            print("No audio files found", file=sys.stderr)
            return 5
        if args.per_audio:
            rc = 0
            for a in audio_files:
                code = _render_for_audio(a)
                if code != 0:
                    rc = code
                else:
                    base = os.path.splitext(os.path.basename(a))[0]
                    try:
                        os.rename("beat_aligned_with_audio.mp4", f"{base}_beat.mp4")
                    except Exception:
                        pass
            return rc
        else:
            if not audio_mod.merge_audio(audio_files, AUDIO_OUTPUT):
                print("Failed to merge audio", file=sys.stderr)
                return 6
            code = _render_for_audio(AUDIO_OUTPUT)
            if code == 0:
                try:
                    os.rename("beat_aligned_with_audio.mp4", "beat_aligned_merged.mp4")
                except Exception:
                    pass
            return code
    else:
        # Single file path
        return _render_for_audio(audio_arg)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))


