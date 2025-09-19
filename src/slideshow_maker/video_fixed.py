#!/usr/bin/env python3
"""
Fixed-duration slideshow renderer, extracted from video.py
"""
from __future__ import annotations

import os
import shutil
from typing import List, Optional

from .config import DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_FPS
from .utils import run_command


def create_slideshow_with_durations(
    images: List[str],
    durations: List[float],
    output_file: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    temp_dir: Optional[str] = None,
    quantize: str = "nearest",
    visualize_cuts: bool = False,
    marker_duration: float = 0.12,
    beat_markers: Optional[List[float]] = None,
    pulse_beats: Optional[List[float]] = None,
    pulse_duration: float = 0.08,
    pulse_saturation: float = 1.25,
    pulse_brightness: float = 0.00,
    pulse_bloom: bool = False,
    pulse_bloom_sigma: float = 8.0,
    pulse_bloom_duration: float = 0.08,
    counter_beats: Optional[List[float]] = None,
    counter_fontsize: int = 36,
    counter_position: str = "tr",
    cut_markers: Optional[List[float]] = None,
    mask_scope: str = "none",
) -> bool:
    if len(images) == 0:
        print("No images found!")
        return False

    if temp_dir is None:
        temp_dir = ".slideshow_tmp"
    os.makedirs(temp_dir, exist_ok=True)

    count = min(len(images), len(durations))
    images = images[:count]
    durations = durations[:count]

    temp_clips: List[str] = []
    print(f"🎬 Creating fixed-duration clips for {count} images...")

    # Optional foreground/background masks via rembg
    masks: List[str] = []
    use_masks = False
    if mask_scope in ("foreground", "background"):
        import os as _os
        if not _os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                from .background_removal import BackgroundRemover  # type: ignore
                remover = BackgroundRemover()
                if remover.is_available():
                    for img in images:
                        m = remover.create_mask(img, None)
                        masks.append(m)
                    if all(bool(m) for m in masks) and len(masks) == len(images):
                        use_masks = True
            except Exception:
                use_masks = False

    elapsed = 0.0
    for i, (img, dur) in enumerate(zip(images, durations)):
        if quantize == "floor":
            frames = max(1, int(float(dur) * fps))
        elif quantize == "ceil":
            frames = max(1, int((float(dur) * fps) + 0.999999))
        else:
            frames = max(1, int(round(float(dur) * fps)))
        dur = max(1.0 / fps, frames / float(fps))

        clip_path = f"{temp_dir}/clip_{i:04d}.mp4"
        vf_parts = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        ]

        if visualize_cuts and i > 0 and marker_duration > 0:
            vf_parts.append(
                f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=white@1.0:t=fill:enable='between(t,0,{marker_duration:.3f})'"
            )

        if beat_markers:
            try:
                for bt in beat_markers:
                    if bt < elapsed:
                        continue
                    if bt >= elapsed + dur:
                        break
                    rel_t = max(0.0, bt - elapsed)
                    vf_parts.append(
                        f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=white@1.0:t=fill:enable='between(t,{rel_t:.3f},{(rel_t+marker_duration):.3f})'"
                    )
            except Exception:
                pass

        if cut_markers:
            try:
                for ct in cut_markers:
                    if ct <= elapsed:
                        continue
                    if ct > elapsed + dur:
                        break
                    rel_t = max(0.0, ct - elapsed)
                    rel_t = min(max(0.0, rel_t - 0.02), max(0.0, dur - 0.02))
                    vf_parts.append(
                        f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=red@1.0:t=fill:enable='between(t,{rel_t:.3f},{(rel_t+marker_duration):.3f})'"
                    )
            except Exception:
                pass

        if pulse_beats and pulse_duration > 0 and (pulse_saturation > 1.0 or pulse_brightness != 0.0):
            try:
                for bt in pulse_beats:
                    if bt < elapsed:
                        continue
                    if bt >= elapsed + dur:
                        break
                    rel_t = max(0.0, bt - elapsed)
                    vf_parts.append(
                        f"eq=saturation={float(pulse_saturation):.3f}:brightness={float(pulse_brightness):.3f}:enable='between(t,{rel_t:.3f},{(rel_t+pulse_duration):.3f})'"
                    )
            except Exception:
                pass

        if pulse_bloom and pulse_bloom_duration > 0 and pulse_bloom_sigma > 0:
            try:
                beats_for_bloom = pulse_beats or beat_markers or []
                for bt in beats_for_bloom:
                    if bt < elapsed:
                        continue
                    if bt >= elapsed + dur:
                        break
                    rel_t = max(0.0, bt - elapsed)
                    vf_parts.append(
                        f"gblur=sigma={float(pulse_bloom_sigma):.2f}:steps=1:enable='between(t,{rel_t:.3f},{(rel_t+pulse_bloom_duration):.3f})'"
                    )
            except Exception:
                pass

        if counter_beats and counter_fontsize > 0:
            try:
                beats_in_order = list(counter_beats)
                count_before = 0
                first_idx_in_clip = None
                for idx_b, b in enumerate(beats_in_order):
                    if b < elapsed:
                        count_before += 1
                    else:
                        first_idx_in_clip = idx_b
                        break
                if counter_position == "tr":
                    x_expr = "w-tw-20"; y_expr = "20"
                elif counter_position == "tl":
                    x_expr = "20"; y_expr = "20"
                elif counter_position == "br":
                    x_expr = "w-tw-20"; y_expr = "h-th-20"
                else:
                    x_expr = "20"; y_expr = "h-th-20"
                first_rel = None
                if first_idx_in_clip is not None and first_idx_in_clip < len(beats_in_order):
                    first_rel = max(0.0, beats_in_order[first_idx_in_clip] - elapsed)
                if count_before > 0 and first_rel is not None and first_rel > 0:
                    prev_idx = count_before
                    vf_parts.append(
                        "drawtext=fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'"
                        f":text='{prev_idx}':x={x_expr}:y={y_expr}:fontsize={int(counter_fontsize)}:fontcolor=white:"
                        f"bordercolor=black:borderw=2:enable='between(t,0,{first_rel:.3f})'"
                    )
                local_beats: List[float] = []
                for bt in beats_in_order:
                    if bt < elapsed:
                        continue
                    if bt >= elapsed + dur:
                        break
                    local_beats.append(bt)
                for j, bt in enumerate(local_beats):
                    rel_t = max(0.0, bt - elapsed)
                    rel_next = dur if j + 1 >= len(local_beats) else max(0.0, local_beats[j + 1] - elapsed)
                    idx = count_before + j + 1
                    vf_parts.append(
                        "drawtext=fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'"
                        f":text='{idx}':x={x_expr}:y={y_expr}:fontsize={int(counter_fontsize)}:fontcolor=white:"
                        f"bordercolor=black:borderw=2:enable='between(t,{rel_t:.3f},{rel_next:.3f})'"
                    )
            except Exception:
                pass

        if use_masks and masks[i]:
            pre = ",".join([
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "format=yuv420p",
            ])
            # Build effect-only chain on a split branch
            effect_chain_parts: List[str] = []
            if pulse_beats and pulse_duration > 0 and (pulse_saturation > 1.0 or pulse_brightness != 0.0):
                try:
                    for bt in pulse_beats:
                        if bt < elapsed:
                            continue
                        if bt >= elapsed + dur:
                            break
                        rel_t = max(0.0, bt - elapsed)
                        effect_chain_parts.append(
                            f"eq=saturation={float(pulse_saturation):.3f}:brightness={float(pulse_brightness):.3f}:enable='between(t,{rel_t:.3f},{(rel_t+pulse_duration):.3f})'"
                        )
                except Exception:
                    pass
            if pulse_bloom and pulse_bloom_duration > 0 and pulse_bloom_sigma > 0:
                try:
                    beats_for_bloom = pulse_beats or beat_markers or []
                    for bt in beats_for_bloom:
                        if bt < elapsed:
                            continue
                        if bt >= elapsed + dur:
                            break
                        rel_t = max(0.0, bt - elapsed)
                        effect_chain_parts.append(
                            f"gblur=sigma={float(pulse_bloom_sigma):.2f}:steps=1:enable='between(t,{rel_t:.3f},{(rel_t+pulse_bloom_duration):.3f})'"
                        )
                except Exception:
                    pass
            post_chain_parts: List[str] = []
            if visualize_cuts and i > 0 and marker_duration > 0:
                post_chain_parts.append(
                    f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=white@1.0:t=fill:enable='between(t,0,{marker_duration:.3f})'"
                )
            if beat_markers:
                try:
                    for bt in beat_markers:
                        if bt < elapsed:
                            continue
                        if bt >= elapsed + dur:
                            break
                        rel_t = max(0.0, bt - elapsed)
                        post_chain_parts.append(
                            f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=white@1.0:t=fill:enable='between(t,{rel_t:.3f},{(rel_t+marker_duration):.3f})'"
                        )
                except Exception:
                    pass
            if cut_markers:
                try:
                    for ct in cut_markers:
                        if ct <= elapsed:
                            continue
                        if ct > elapsed + dur:
                            break
                        rel_t = max(0.0, ct - elapsed)
                        rel_t = min(max(0.0, rel_t - 0.02), max(0.0, dur - 0.02))
                        post_chain_parts.append(
                            f"drawbox=x=(iw/2-5):y=0:w=10:h=ih:color=red@1.0:t=fill:enable='between(t,{rel_t:.3f},{(rel_t+marker_duration):.3f})'"
                        )
                except Exception:
                    pass
            if counter_beats and counter_fontsize > 0:
                try:
                    beats_in_order = list(counter_beats)
                    count_before = 0
                    first_idx_in_clip = None
                    for idx_b, b in enumerate(beats_in_order):
                        if b < elapsed:
                            count_before += 1
                        else:
                            first_idx_in_clip = idx_b
                            break
                    if counter_position == "tr":
                        x_expr = "w-tw-20"; y_expr = "20"
                    elif counter_position == "tl":
                        x_expr = "20"; y_expr = "20"
                    elif counter_position == "br":
                        x_expr = "w-tw-20"; y_expr = "h-th-20"
                    else:
                        x_expr = "20"; y_expr = "h-th-20"
                    first_rel = None
                    if first_idx_in_clip is not None and first_idx_in_clip < len(beats_in_order):
                        first_rel = max(0.0, beats_in_order[first_idx_in_clip] - elapsed)
                    if count_before > 0 and first_rel is not None and first_rel > 0:
                        prev_idx = count_before
                        post_chain_parts.append(
                            "drawtext=fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'"
                            f":text='{prev_idx}':x={x_expr}:y={y_expr}:fontsize={int(counter_fontsize)}:fontcolor=white:"
                            f"bordercolor=black:borderw=2:enable='between(t,0,{first_rel:.3f})'"
                        )
                    local_beats: List[float] = []
                    for bt in beats_in_order:
                        if bt < elapsed:
                            continue
                        if bt >= elapsed + dur:
                            break
                        local_beats.append(bt)
                    for j2, bt in enumerate(local_beats):
                        rel_t = max(0.0, bt - elapsed)
                        rel_next = dur if j2 + 1 >= len(local_beats) else max(0.0, local_beats[j2 + 1] - elapsed)
                        idx_label = count_before + j2 + 1
                        post_chain_parts.append(
                            "drawtext=fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'"
                            f":text='{idx_label}':x={x_expr}:y={y_expr}:fontsize={int(counter_fontsize)}:fontcolor=white:"
                            f"bordercolor=black:borderw=2:enable='between(t,{rel_t:.3f},{rel_next:.3f})'"
                        )
                except Exception:
                    pass

            eff = ",".join(effect_chain_parts) if effect_chain_parts else None
            post = ",".join(post_chain_parts) if post_chain_parts else None

            mask_process = (
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=gray[m]"
            )
            if mask_scope == "background":
                mask_process = mask_process + ",negate,format=gray[m]"

            fc_parts = [
                f"[0:v]{pre},split=2[b][e]",
                (f"[e]{eff}[ee]" if eff else "[e]copy[ee]"),
                mask_process,
                "[b][ee][m]maskedmerge[mm]",
            ]
            map_label = "[mm]"
            if post:
                fc_parts.append(f"[mm]{post}[vout]")
                map_label = "[vout]"
            filter_complex = ";".join(fc_parts)

            cmd = (
                f'ffmpeg -y -loop 1 -i "{img}" -loop 1 -i "{masks[i]}" -t {float(dur):.3f} '
                f'-filter_complex "{filter_complex}" -map {map_label} -frames:v {frames} '
                f'-c:v libx264 -r {fps} -preset ultrafast -pix_fmt yuv420p "{clip_path}"'
            )
        else:
            vf_filter = ",".join(vf_parts)
            cmd = (
                f'ffmpeg -y -loop 1 -i "{img}" -t {float(dur):.3f} '
                f'-vf "{vf_filter}" -frames:v {frames} -c:v libx264 -r {fps} -preset ultrafast -pix_fmt yuv420p "{clip_path}"'
            )
        if not run_command(cmd, f"Clip {i+1}/{count} ({dur:.2f}s)", timeout_seconds=120):
            return False
        temp_clips.append(clip_path)
        elapsed += float(dur)

    if len(temp_clips) == 1:
        os.rename(temp_clips[0], output_file)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True

    concat_list = f"{temp_dir}/concat.txt"
    with open(concat_list, "w") as f:
        for clip in temp_clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" -c copy "{output_file}"'
    ok = run_command(cmd, "Concatenating fixed-duration clips", timeout_seconds=300)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return ok


