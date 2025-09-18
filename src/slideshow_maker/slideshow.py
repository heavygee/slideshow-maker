#!/usr/bin/env python3
"""
Main slideshow orchestrator for the VRChat Slideshow Maker
"""

import os
import sys
import glob
import random
from .config import (
    DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION, MAX_SLIDES_LIMIT,
    AUDIO_OUTPUT, VIDEO_OUTPUT, FINAL_OUTPUT, IMAGE_EXTENSIONS
)
from . import audio as audio_mod
from . import video as video_mod
from .utils import show_progress, print_ffmpeg_capabilities, detect_nvenc_support


def find_images(directory):
    """Find image files in the directory"""
    all_images = []
    for ext in IMAGE_EXTENSIONS:
        pattern = os.path.join(directory, ext)
        all_images.extend(glob.glob(pattern))
    return sorted(all_images)


def calculate_slides_needed(audio_duration, min_duration, max_duration, test_mode=False):
    """Calculate how many slides are needed based on audio duration or test mode"""
    if test_mode:
        # Test mode: 1 minute video
        test_duration = 60  # 1 minute
        slides_needed = int(test_duration / ((min_duration + max_duration) / 2))  # Use average duration
        print(f"🎵 Test mode: creating 1-minute video")
        print(f"⏱️  Slides needed for test: {slides_needed}")
        return slides_needed
    else:
        # Full mode: match audio duration
        avg_duration = (min_duration + max_duration) / 2
        slides_needed = int(audio_duration / avg_duration)
        print(f"🎵 Audio duration: {audio_duration:.1f} seconds")
        print(f"⏱️  Slides needed: {slides_needed} (avg {avg_duration:.1f}s per slide)")

        # Enforce a hard cap to prevent runaway slide counts
        if slides_needed > MAX_SLIDES_LIMIT:
            print(f"⚠️  Limiting slides from {slides_needed} to max {MAX_SLIDES_LIMIT}")
            slides_needed = MAX_SLIDES_LIMIT
        print(f"   Final video will be ~{slides_needed * avg_duration / 60:.1f} minutes")

        return slides_needed


def select_images(all_images, slides_needed, test_mode=False):
    """Select images for the slideshow based on mode and requirements"""
    if len(all_images) == 0:
        return []

    if test_mode:
        # Test mode: just use first N images
        images = all_images[:slides_needed]
        print(f"🎲 Test mode: Using first {len(images)} images")
        return images
    else:
        # Full mode: Use ALL images, then add random repeats to fill duration
        images = all_images.copy()
        remaining = slides_needed - len(images)
        if remaining > 0:
            print(f"🎲 Adding {remaining} random repeats to reach target duration...")
            for i in range(remaining):
                img = random.choice(all_images)
                images.append(img)

                # Show progress for the repeats
                if i % 100 == 0 or i == remaining - 1:
                    current_total = len(all_images) + i + 1
                    show_progress(current_total, slides_needed, img)

        print(f"🎲 Selected {len(images)} images ({len(all_images)} unique + {remaining} repeats)")
        return images


def create_slideshow_with_audio(image_dir, test_mode=False, dry_run=False, min_duration=DEFAULT_MIN_DURATION, 
                               max_duration=DEFAULT_MAX_DURATION):
    """Main function to create a complete slideshow with audio"""
    
    if not os.path.exists(image_dir):
        print(f"Directory not found: {image_dir}")
        return False

    print("🎬 VRChat Slideshow Creator")
    print(f"📁 Working directory: {image_dir}")
    print(f"⚙️  Test mode: {'ON (1-minute video)' if test_mode else 'OFF (full video)'}")
    print(f"⏱️  Image duration range: {min_duration}-{max_duration} seconds")
    
    # Early dry run check - before any heavy processing
    if dry_run:
        print("\n🔍 DRY RUN MODE - No processing will be performed")
        print("="*60)
        
        # Find audio files for duration calculation
        audio_files = audio_mod.find_audio_files(image_dir)
        print(f"🎵 Found {len(audio_files)} audio files: {[os.path.basename(f) for f in audio_files]}")
        
        if len(audio_files) == 0:
            print("❌ No audio files found!")
            return False
        
        # Calculate audio duration
        # Always compute duration from source files for tests/speed
        audio_duration = audio_mod.get_total_audio_duration(audio_files)
        print(f"🎵 Audio duration: {audio_duration:.1f} seconds")
        
        # Find images
        all_images = find_images(image_dir)
        print(f"🖼️  Found {len(all_images)} total images")
        
        # Calculate slides needed
        slides_needed = calculate_slides_needed(audio_duration, min_duration, max_duration, test_mode)
        
        # Calculate estimated total duration
        avg_duration = (min_duration + max_duration) / 2
        estimated_duration = slides_needed * avg_duration
        
        print(f"\n📊 SUMMARY:")
        print(f"  📁 Directory: {image_dir}")
        print(f"  ⏱️  Image duration range: {min_duration}-{max_duration} seconds")
        print(f"  🎬 Total slides needed: {slides_needed}")
        print(f"  ⏱️  Estimated video duration: {estimated_duration/60:.1f} minutes ({estimated_duration:.1f} seconds)")
        print(f"  🎭 Transitions: All available transition types will be used randomly")
        print(f"  🚀 Encoding: Will detect GPU/CPU encoding capabilities")
        print(f"  📁 Output: {FINAL_OUTPUT}")
        print("="*60)
        print("✅ Dry run complete - use without --dry-run to process")
        return True
    
    # Check FFmpeg capabilities
    print("\n" + "="*50)
    print_ffmpeg_capabilities()
    print("="*50)

    # Find audio first (needed for duration calculation)
    audio_files = audio_mod.find_audio_files(image_dir)
    print(f"🎵 Found {len(audio_files)} audio files: {[os.path.basename(f) for f in audio_files]}")

    if len(audio_files) == 0:
        print("❌ No audio files found!")
        return False

    # Calculate audio duration from source files (mockable, fast)
    audio_duration = audio_mod.get_total_audio_duration(audio_files)

    # Find images
    all_images = find_images(image_dir)
    print(f"🖼️  Found {len(all_images)} total images")

    # Calculate slides based on mode
    slides_needed = calculate_slides_needed(audio_duration, min_duration, max_duration, test_mode)

    # Select images based on mode
    images = select_images(all_images, slides_needed, test_mode)
    print(f"🖼️  Final image count: {len(images)}")


    # Process audio
    if not os.path.exists(os.path.join(image_dir, AUDIO_OUTPUT)):
        print("\n🎵 Processing audio...")
        if not audio_mod.merge_audio(audio_files, AUDIO_OUTPUT):
            print("❌ Audio processing failed!")
            return False
    else:
        print(f"\n🎵 Using existing merged audio: {AUDIO_OUTPUT}")

    # Create slideshow with variable durations
    print("\n🎬 Creating slideshow...")
    if not video_mod.create_slideshow(images, VIDEO_OUTPUT, min_duration, max_duration):
        print("❌ Slideshow creation failed!")
        return False

    # Combine video and audio
    print("\n🎞️  Combining video and audio...")
    if not audio_mod.combine_video_audio(VIDEO_OUTPUT, AUDIO_OUTPUT, FINAL_OUTPUT):
        print("❌ Final combination failed!")
        return False

    # Clean up intermediate files (but keep audio for reuse)
    print("\n🧹 Cleaning up intermediate files...")
    try:
        os.remove(VIDEO_OUTPUT)
    except:
        pass
    # DON'T remove AUDIO_OUTPUT - keep it for reuse!

    # Show result (handle mocked environments where file may not exist)
    print("\n✅ SUCCESS!")
    print(f"🎬 Final video: {FINAL_OUTPUT}")
    try:
        file_size = os.path.getsize(FINAL_OUTPUT) / (1024 * 1024)  # MB
        print(f"📏 File size: {file_size:.1f} MB")
    except FileNotFoundError:
        print("📏 File size: (mocked/no file)")
    
    return True
