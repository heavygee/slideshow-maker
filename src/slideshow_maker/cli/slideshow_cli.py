#!/usr/bin/env python3
"""
Classic (non beat-matched) slideshow CLI.

Default behavior:
- Merge all audio tracks in the given images directory into one long track
- Create a slideshow for the full audio duration by looping images as needed

Examples:
  PYTHONPATH=src python3 -m slideshow_maker.cli.slideshow_cli /path/to/images
  PYTHONPATH=src python3 -m slideshow_maker.cli.slideshow_cli /path/to/images --test-mode
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from ..slideshow import create_slideshow_with_audio
from ..config import DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Classic slideshow: merge all audio and loop images to full length")
    p.add_argument("images_dir", help="Directory containing images and audio files")
    p.add_argument("--test-mode", action="store_true", default=False, help="Create a 60s test render instead of full length")
    p.add_argument("--dry-run", action="store_true", default=False, help="Print plan and exit without rendering")
    p.add_argument("--min-duration", type=float, default=DEFAULT_MIN_DURATION, help="Minimum image hold seconds")
    p.add_argument("--max-duration", type=float, default=DEFAULT_MAX_DURATION, help="Maximum image hold seconds")
    p.add_argument("--temp-dir", type=str, default=None, help="Temporary directory for intermediate files")
    args = p.parse_args(argv)

    ok = create_slideshow_with_audio(
        args.images_dir,
        test_mode=bool(args.test_mode),
        dry_run=bool(args.dry_run),
        min_duration=float(args.min_duration),
        max_duration=float(args.max_duration),
        temp_dir=args.temp_dir,
    )
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))


