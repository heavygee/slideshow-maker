#!/usr/bin/env python3
"""
Audio processing for the VRChat Slideshow Maker
"""

import os
import glob
from .config import AUDIO_EXTENSIONS, AUDIO_OUTPUT, AUDIO_BITRATE, AUDIO_CODEC
from .utils import run_command, get_audio_duration


def find_audio_files(directory):
    """Find ALL audio files in the directory (stable sort by name)."""
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(glob.glob(os.path.join(directory, ext)))
    audio_files = sorted(audio_files)
    # Exclude previously merged output to avoid recursive concat and codec mismatches
    audio_files = [p for p in audio_files if os.path.basename(p) != AUDIO_OUTPUT]
    return audio_files


def merge_audio(audio_files, output_file):
    """Merge multiple audio files"""
    if len(audio_files) == 0:
        print("No audio files found!")
        return False

    if len(audio_files) == 1:
        # Single audio file - just copy/convert
        cmd = f'ffmpeg -y -i "{audio_files[0]}" -c:a {AUDIO_CODEC} -b:a {AUDIO_BITRATE} "{output_file}"'
        return run_command(cmd, f"Processing single audio file: {os.path.basename(audio_files[0])}")

    # Multiple audio files - concatenate
    concat_file = "audio_concat.txt"
    with open(concat_file, 'w') as f:
        for audio in audio_files:
            f.write(f"file '{audio}'\n")

    cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c:a {AUDIO_CODEC} -b:a {AUDIO_BITRATE} "{output_file}"'
    success = run_command(cmd, f"Merging {len(audio_files)} audio files")

    # Clean up
    try:
        os.remove(concat_file)
    except Exception:
        pass

    return success


def combine_video_audio(video_file, audio_file, output_file):
    """Combine video and audio"""
    # Get audio duration
    audio_duration = get_audio_duration(audio_file)
    if audio_duration == 0:
        print("Could not get audio duration")
        return False

    # Loop video to match audio duration. Re-encode video to avoid timestamp/DTS issues with copy + stream_loop.
    # Copy audio to keep original quality.
    cmd = (
        f'ffmpeg -y -stream_loop -1 -i "{video_file}" -i "{audio_file}" '
        f'-map 0:v:0 -map 1:a:0 '
        f'-c:v libx264 -r 25 -crf 23 -preset ultrafast -pix_fmt yuv420p '
        f'-c:a aac -b:a {AUDIO_BITRATE} -shortest "{output_file}"'
    )
    return run_command(cmd, f"Combining video and audio (duration: {audio_duration:.1f}s)", timeout_seconds=600)


def get_total_audio_duration(audio_files):
    """Calculate total duration from multiple audio files"""
    total_duration = 0
    for audio_file in audio_files:
        duration = get_audio_duration(audio_file)
        total_duration += duration
    return total_duration
