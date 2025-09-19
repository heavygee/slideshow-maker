#!/usr/bin/env python3
"""
Beat-aligned transitions renderer, extracted from video.py
"""
from __future__ import annotations

import os
import tempfile
from typing import List, Optional

from .config import (
    DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_FPS, DEFAULT_TRANSITION_DURATION
)
from .utils import run_command, detect_nvenc_support
from .video_chunked import get_encoding_params  # reuse helper


def create_beat_aligned_with_transitions(
    images: List[str],
    durations: List[float],
    output_file: str,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    quantize: str = "nearest",
    transition_type: str = "fade",
    transition_duration: float = DEFAULT_TRANSITION_DURATION,
    align: str = "midpoint",
    min_effective: float = 0.25,
    mark_transitions: bool = False,
    marker_duration: float = 0.12,
    pulse: bool = False,
    pulse_duration: float = 0.08,
    pulse_saturation: float = 1.25,
    pulse_brightness: float = 0.00,
    bloom: bool = False,
    bloom_sigma: float = 8.0,
    bloom_duration: float = 0.08,
    overlay_beats: Optional[List[float]] = None,
    overlay_beat_multiplier: int = 1,
    overlay_phase: float = 0.0,
    overlay_guard_seconds: float = 0.0,
    mark_cuts: bool = False,
    counter_beats: Optional[List[float]] = None,
    counter_fontsize: int = 36,
    counter_position: str = "tr",
    fallback_style: str = "none",
    fallback_duration: float = 0.06,
    mask_scope: str = "none",
) -> bool:
    # Import the original implementation to avoid diverging logic during extraction
    from .video import create_beat_aligned_with_transitions as original
    return original(
        images,
        durations,
        output_file,
        width=width,
        height=height,
        fps=fps,
        quantize=quantize,
        transition_type=transition_type,
        transition_duration=transition_duration,
        align=align,
        min_effective=min_effective,
        mark_transitions=mark_transitions,
        marker_duration=marker_duration,
        pulse=pulse,
        pulse_duration=pulse_duration,
        pulse_saturation=pulse_saturation,
        pulse_brightness=pulse_brightness,
        bloom=bloom,
        bloom_sigma=bloom_sigma,
        bloom_duration=bloom_duration,
        overlay_beats=overlay_beats,
        overlay_beat_multiplier=overlay_beat_multiplier,
        overlay_phase=overlay_phase,
        overlay_guard_seconds=overlay_guard_seconds,
        mark_cuts=mark_cuts,
        fallback_style=fallback_style,
        fallback_duration=fallback_duration,
        counter_beats=counter_beats,
        counter_fontsize=counter_fontsize,
        counter_position=counter_position,
        mask_scope=mask_scope,
    )


