#!/usr/bin/env python3
"""
Chunked slideshow renderer and helpers, extracted from video.py
"""
from __future__ import annotations

import os
import random
import shutil
from typing import List, Optional

from .config import (
    DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION, DEFAULT_WIDTH, DEFAULT_HEIGHT,
    DEFAULT_FPS, DEFAULT_CRF, DEFAULT_PRESET, DEFAULT_CHUNK_SIZE, TEMP_DIR
)
from .utils import run_command, get_image_info, get_available_transitions, print_ffmpeg_capabilities, detect_nvenc_support


def get_encoding_params(nvenc_available: bool, fps: int) -> str:
    if nvenc_available:
        return f"-c:v h264_nvenc -r {fps} -rc vbr -b:v 10M -maxrate 20M -bufsize 20M -preset p5"
    else:
        return f"-c:v libx264 -r {fps} -crf {DEFAULT_CRF} -preset {DEFAULT_PRESET}"


def create_slideshow(images: List[str], output_file: str, min_duration: float = DEFAULT_MIN_DURATION,
                     max_duration: float = DEFAULT_MAX_DURATION, width: int = DEFAULT_WIDTH,
                     height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS, temp_dir: Optional[str] = None) -> bool:
    if len(images) == 0:
        print("No images found!")
        return False

    if len(images) == 1:
        duration = random.uniform(min_duration, max_duration)
        cmd = f'ffmpeg -y -loop 1 -i "{images[0]}" -t {duration:.1f} -vf "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -r {fps} "{output_file}"'
        return run_command(cmd, f"Creating single image video from {images[0]}")

    print(f"🎬 Creating slideshow with {len(images)} images and smooth transitions...")
    return create_slideshow_chunked(images, output_file, min_duration, max_duration, width, height, fps, temp_dir)


def create_slideshow_chunked(images: List[str], output_file: str, min_duration: float = DEFAULT_MIN_DURATION,
                             max_duration: float = DEFAULT_MAX_DURATION, width: int = DEFAULT_WIDTH,
                             height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS, temp_dir: Optional[str] = None) -> bool:
    if len(images) == 0:
        return False

    chunk_size = DEFAULT_CHUNK_SIZE
    if temp_dir is None:
        temp_dir = TEMP_DIR
    else:
        from .config import get_temp_dir
        temp_dir = get_temp_dir(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    available_transitions, capabilities = get_available_transitions()
    nvenc_available = detect_nvenc_support()

    if not available_transitions:
        print("❌ No transitions available! FFmpeg xfade support not detected.")
        print("   Please install FFmpeg with xfade filter support.")
        return False

    chunk_files: List[str] = []

    print(f"📦 Processing {len(images)} images in chunks of {chunk_size}")
    print(f"🎭 Using {len(available_transitions)} available FFmpeg xfade transition types!")

    import os as _os
    if not _os.environ.get("PYTEST_CURRENT_TEST"):
        print_ffmpeg_capabilities()

    if capabilities['cpu_transitions_supported'] and capabilities['gpu_transitions_supported']:
        print("✨ Both CPU and GPU transitions available - maximum variety!")
    elif capabilities['cpu_transitions_supported']:
        print("💻 Using CPU transitions only (GPU not available)")
    elif capabilities['gpu_transitions_supported']:
        print("🎮 Using GPU transitions only (CPU fallback not available)")

    for chunk_idx, chunk_start in enumerate(range(0, len(images), chunk_size)):
        chunk = images[chunk_start:chunk_start + chunk_size]
        chunk_file = f"{temp_dir}/chunk_{chunk_idx:03d}.mp4"

        if os.path.exists(chunk_file):
            print(f"  ⏭️  Chunk {chunk_idx + 1}/{(len(images) + chunk_size - 1) // chunk_size} already exists - skipping")
            chunk_files.append(chunk_file)
            continue

        print(f"  🔄 Processing chunk {chunk_idx + 1}/{(len(images) + chunk_size - 1) // chunk_size}")
        temp_clips: List[str] = []

        for i, img in enumerate(chunk):
            temp_clip = f"{temp_dir}/temp_{chunk_idx}_{i}.mp4"
            duration = random.uniform(min_duration, max_duration)

            if i % 2 == 0 or i == len(chunk) - 1:
                image_info = get_image_info(img)
                print(f"  📸 Processing: {image_info} ({duration:.1f}s)")

            vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            encoding_params = get_encoding_params(nvenc_available, fps)
            cmd = f'ffmpeg -y -loop 1 -i "{img}" -t {duration:.1f} -vf "{vf_filter}" {encoding_params} "{temp_clip}"'
            ok = run_command(cmd, f"    Creating image {i+1}/{len(chunk)}", show_output=False, timeout_seconds=30)
            if not ok and nvenc_available:
                # Retry once with CPU encoding fallback
                cpu_params = get_encoding_params(False, fps)
                cpu_cmd = f'ffmpeg -y -loop 1 -i "{img}" -t {duration:.1f} -vf "{vf_filter}" {cpu_params} "{temp_clip}"'
                ok = run_command(cpu_cmd, f"    Creating image {i+1}/{len(chunk)} (CPU fallback)", show_output=False, timeout_seconds=30)
            if not ok:
                print(f"    ⚠️  Skipping problematic image: {os.path.basename(img)}")
                continue
            temp_clips.append(temp_clip)

        if len(temp_clips) == 0:
            print(f"    ⚠️  No valid images in chunk {chunk_idx + 1} - skipping")
            continue

        if len(temp_clips) == 1:
            shutil.move(temp_clips[0], chunk_file)
        else:
            print(f"    🎭 Creating VARIED smooth transitions between {len(temp_clips)} images...")
            print(f"      ✨ Creating REAL VARIED transitions")
            transition_clips: List[str] = []

            for j in range(len(temp_clips)):
                if j == 0:
                    transition_clips.append(temp_clips[j])
                else:
                    prev_clip = temp_clips[j-1]
                    curr_clip = temp_clips[j]
                    transition_file = f"{temp_dir}/transition_{chunk_idx}_{j}.mp4"
                    # Choose a transition that is supported by current ffmpeg (probe once)
                    candidates = available_transitions[:]
                    random.shuffle(candidates)
                    transition_type = None
                    for cand in candidates:
                        test_cmd = f'ffmpeg -v error -f lavfi -i "color=red:size=320x240:duration=2" -f lavfi -i "color=blue:size=320x240:duration=2" -filter_complex "[0:v][1:v]xfade=transition={cand}:duration=1.0:offset=1.0" -t 1 -f null -'
                        if run_command(test_cmd, f"    Probe transition {cand}", show_output=False):
                            transition_type = cand
                            break
                    if transition_type is None:
                        # Fallback to a safe transition
                        transition_type = 'fade'
                    if capabilities['gpu_transitions_supported']:
                        cmd = f'ffmpeg -y -init_hw_device opencl=ocl:0.0 -filter_hw_device ocl -i "{prev_clip}" -i "{curr_clip}" -filter_complex "[0:v]format=rgba,hwupload=extra_hw_frames=16[0hw];[1:v]format=rgba,hwupload=extra_hw_frames=16[1hw];[0hw][1hw]xfade_opencl=transition={transition_type}:duration={DEFAULT_TRANSITION_DURATION}:offset={duration-DEFAULT_TRANSITION_DURATION:.1f},hwdownload,format=yuv420p" -c:v libx264 -r {fps} -crf {DEFAULT_CRF} -preset {DEFAULT_PRESET} -t {duration:.1f} "{transition_file}"'
                    else:
                        encoding_params = get_encoding_params(nvenc_available, fps)
                        cmd = f'ffmpeg -y -i "{prev_clip}" -i "{curr_clip}" -filter_complex "[0:v][1:v]xfade=transition={transition_type}:duration={DEFAULT_TRANSITION_DURATION}:offset={duration-DEFAULT_TRANSITION_DURATION:.1f}" {encoding_params} -t {duration:.1f} "{transition_file}"'

                    print(f"      🔄 {transition_type.upper()} transition command: {cmd}")
                    ok_t = run_command(cmd, f"    {transition_type.upper()} transition {j}/{len(temp_clips)-1}", show_output=True)
                    if ok_t:
                        transition_clips.append(transition_file)
                        print(f"      ✅ {transition_type.upper()} transition {j} SUCCESS")
                    else:
                        if capabilities['gpu_transitions_supported'] and capabilities['cpu_transitions_supported']:
                            print(f"      ⚠️ OpenCL transition failed, trying CPU fallback...")
                            encoding_params = get_encoding_params(nvenc_available, fps)
                            cpu_cmd = f'ffmpeg -y -i "{prev_clip}" -i "{curr_clip}" -filter_complex "[0:v][1:v]xfade=transition={transition_type}:duration={DEFAULT_TRANSITION_DURATION}:offset={duration-DEFAULT_TRANSITION_DURATION:.1f}" {encoding_params} -t {duration:.1f} "{transition_file}"'
                            ok_cpu = run_command(cpu_cmd, f"    CPU fallback {transition_type.upper()} transition {j}/{len(temp_clips)-1}", show_output=True)
                            if not ok_cpu and nvenc_available:
                                # Try forced libx264 if NVENC path in encoding_params failed
                                cpu_params2 = get_encoding_params(False, fps)
                                cpu_cmd2 = f'ffmpeg -y -i "{prev_clip}" -i "{curr_clip}" -filter_complex "[0:v][1:v]xfade=transition={transition_type}:duration={DEFAULT_TRANSITION_DURATION}:offset={duration-DEFAULT_TRANSITION_DURATION:.1f}" {cpu_params2} -t {duration:.1f} "{transition_file}"'
                                ok_cpu = run_command(cpu_cmd2, f"    CPU fallback-2 {transition_type.upper()} transition {j}/{len(temp_clips)-1}", show_output=True)
                            if ok_cpu:
                                transition_clips.append(transition_file)
                                print(f"      ✅ CPU fallback {transition_type.upper()} transition {j} SUCCESS")
                            else:
                                print(f"      ❌ Both OpenCL and CPU transitions failed - using original clip")
                                transition_clips.append(curr_clip)
                        else:
                            print(f"      ❌ {transition_type.upper()} transition {j} FAILED - using original clip")
                            transition_clips.append(curr_clip)

            if len(transition_clips) == 1:
                os.rename(transition_clips[0], chunk_file)
            else:
                concat_file = f"{temp_dir}/final_concat_{chunk_idx}.txt"
                with open(concat_file, 'w') as f:
                    for clip in transition_clips:
                        f.write(f"file '{os.path.abspath(clip)}'\n")
                cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c:v libx264 -c:a aac -r {fps} -crf {DEFAULT_CRF} -preset {DEFAULT_PRESET} "{chunk_file}"'
                if not run_command(cmd, f"    Finalizing chunk {chunk_idx + 1} (re-encoding to preserve transitions)", show_output=False):
                    return False
                for clip in transition_clips[1:]:
                    try:
                        os.remove(clip)
                    except:
                        pass
                os.remove(concat_file)

            for clip in temp_clips:
                try:
                    os.remove(clip)
                except:
                    pass

        chunk_files.append(chunk_file)

        completed = chunk_idx + 1
        total_chunks = (len(images) + chunk_size - 1) // chunk_size
        percentage = (completed / total_chunks) * 100
        print(f"  ✅ Chunk {completed}/{total_chunks} completed ({percentage:.1f}%)")

    print("\n🎬 Final concatenation...")
    if len(chunk_files) == 1:
        shutil.move(chunk_files[0], output_file)
        success = True
    else:
        print("  ✨ Smooth transitions already applied within each chunk")
        final_concat = f"{temp_dir}/final_concat.txt"
        with open(final_concat, 'w') as f:
            for chunk_file in chunk_files:
                f.write(f"file '{os.path.abspath(chunk_file)}'\n")
        timeout_seconds = max(60, len(chunk_files) * 30)
        print(f"  ⏱️  Using {timeout_seconds}s timeout for {len(chunk_files)} chunks")
        cmd = f'ffmpeg -y -f concat -safe 0 -i "{final_concat}" -c copy "{output_file}"'
        success = run_command(cmd, "Creating final slideshow with smooth transitions", timeout_seconds=timeout_seconds)

    if success:
        shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        print(f"⚠️  Final concatenation failed - temp files preserved in {temp_dir}")
    return success


