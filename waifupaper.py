#!/usr/bin/env python3
"""
Mac Wallpaper Rotator - Changes wallpapers at fixed intervals

Note: doesn't work if wallpaper is currently set to rotate.

Written by Claude AI (Sonnet 4.5).
"""

import argparse
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict


def get_directory_state(directory):
    """Get the current state of a directory (modification time and file count)."""
    directory = Path(directory)
    try:
        # Get the directory's modification time
        mtime = directory.stat().st_mtime
        # Count image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.heic'}
        file_count = sum(1 for f in directory.iterdir() 
                        if f.is_file() and f.suffix.lower() in image_extensions)
        return (mtime, file_count)
    except Exception:
        return None


def get_image_files(directory):
    """Get all image files from a directory."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.heic'}
    directory = Path(directory)
    
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    images = [
        str(f.resolve()) for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not images:
        print(f"Error: No image files found in '{directory}'", file=sys.stderr)
        sys.exit(1)
    
    return images


def get_display_count():
    """Get the number of connected displays."""
    try:
        # Use system_profiler to get display information
        result = subprocess.run(
            ['system_profiler', 'SPDisplaysDataType'],
            capture_output=True,
            text=True,
            check=True
        )
        # Count occurrences of "Display Type" or "Resolution"
        count = result.stdout.count('Resolution:')
        return max(1, count)  # At least 1 display
    except subprocess.CalledProcessError:
        return 1  # Default to 1 display if command fails


def set_wallpaper(image_path, display_index=0):
    """Set wallpaper for a specific display using AppleScript."""
    # AppleScript to set wallpaper for a specific desktop
    script = f'''
    tell application "System Events"
        tell desktop {display_index + 1}
            set picture to "{image_path}"
        end tell
    end tell
    '''
    
    try:
        subprocess.run(
            ['osascript', '-e', script],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to set wallpaper for display {display_index + 1}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Rotate wallpapers on Mac displays at fixed intervals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s ~/Pictures/Wallpapers
  %(prog)s ~/Pictures/Nature ~/Pictures/Abstract -i 60
  %(prog)s ~/Pictures/Wallpapers -s -i 120
  %(prog)s ~/Pictures/Nature ~/Pictures/Abstract -1 -3
        '''
    )
    
    parser.add_argument(
        'directories',
        nargs='+',
        help='One or more directories containing wallpaper images'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=30,
        help='Interval in seconds between wallpaper changes (default: 30)'
    )
    
    parser.add_argument(
        '-s', '--sort',
        action='store_true',
        help='Sort images instead of shuffling (default: shuffle)'
    )
    
    parser.add_argument(
        '-1', '--display1',
        action='store_true',
        help='Only affect display 1'
    )
    
    parser.add_argument(
        '-2', '--display2',
        action='store_true',
        help='Only affect display 2'
    )
    
    parser.add_argument(
        '-3', '--display3',
        action='store_true',
        help='Only affect display 3'
    )
    
    parser.add_argument(
        '-4', '--display4',
        action='store_true',
        help='Only affect display 4'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='print verbose output'
    )
    
    args = parser.parse_args()
    
    # Determine which displays to affect
    selected_displays = []
    if args.display1:
        selected_displays.append(0)
    if args.display2:
        selected_displays.append(1)
    if args.display3:
        selected_displays.append(2)
    if args.display4:
        selected_displays.append(3)
    
    # If no specific displays selected, affect all displays
    affect_all_displays = len(selected_displays) == 0
    
    # Validate interval
    if args.interval <= 0:
        print("Error: Interval must be a positive number", file=sys.stderr)
        sys.exit(1)
    
    # Get display count
    num_displays = get_display_count()
    if args.verbose:
        print(f"Detected {num_displays} display(s)")
    
    # Validate selected displays
    if not affect_all_displays:
        for display_idx in selected_displays:
            if display_idx >= num_displays:
                print(f"Warning: Display {display_idx + 1} selected but only {num_displays} display(s) detected", 
                      file=sys.stderr)
        # Filter out invalid display indices
        selected_displays = [d for d in selected_displays if d < num_displays]
        
        if not selected_displays:
            print("Error: No valid displays selected", file=sys.stderr)
            sys.exit(1)
    
    # Prepare image lists for each display
    display_images = []
    directory_states = {}  # Track directory modification times
    
    # Determine which displays will be managed
    if affect_all_displays:
        managed_displays = list(range(num_displays))
    else:
        managed_displays = sorted(selected_displays)
    
    if args.verbose:
        print(f"Managing display(s): {', '.join(str(d + 1) for d in managed_displays)}")
    
    for i in managed_displays:
        # Use the corresponding directory, or the last one if we run out
        dir_index = min(managed_displays.index(i), len(args.directories) - 1)
        directory = args.directories[dir_index]
        
        images = get_image_files(directory)
        
        if args.sort:
            images.sort()
        else:
            random.shuffle(images)
        
        display_images.append({
            'images': images,
            'index': 0,
            'directory': directory,
            'display_index': i  # Store the actual display index
        })
        
        # Track initial directory state
        directory_states[directory] = get_directory_state(directory)
        
        if args.verbose:
            print(f"Display {i + 1}: {len(images)} images from '{directory}'")
    
    if args.verbose:
        print(f"\nRotating wallpapers every {args.interval} seconds")
        print("Monitoring directories for changes...")
        print("Press Ctrl+C to stop\n")
    
    try:
        iteration = 0
        while True:
            # Check for directory changes before setting wallpapers
            for display_data in display_images:
                directory = display_data['directory']
                current_state = get_directory_state(directory)
                
                # If directory state changed, reload images
                if current_state != directory_states.get(directory):
                    display_num = display_data['display_index'] + 1
                    if args.verbose:
                        print(f"📁 Directory changed: '{directory}' - reloading images...")
                    
                    new_images = get_image_files(directory)
                    
                    if args.sort:
                        new_images.sort()
                    else:
                        random.shuffle(new_images)
                    
                    display_data['images'] = new_images
                    display_data['index'] = 0
                    directory_states[directory] = current_state
                    
                    if args.verbose:
                        print(f"   Loaded {len(new_images)} images for display {display_num}\n")
            
            # Set wallpaper for each display
            for display_data in display_images:
                images = display_data['images']
                current_index = display_data['index']
                actual_display_idx = display_data['display_index']
                
                image_path = images[current_index]
                image_name = Path(image_path).name
                
                if args.verbose:
                    print(f"Display {actual_display_idx + 1}: {image_name}")
                set_wallpaper(image_path, actual_display_idx)
                
                # Move to next image, wrap around if needed
                display_data['index'] = (current_index + 1) % len(images)
                
                # Reshuffle when we complete a cycle (if not sorting)
                if display_data['index'] == 0 and not args.sort and iteration > 0:
                    random.shuffle(display_data['images'])
                    if args.verbose:
                        print(f"  → Reshuffled images for display {actual_display_idx + 1}")
            
            iteration += 1
            if args.verbose:
                print()
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        if args.verbose:
            print("\n\nWallpaper rotation stopped.")
        sys.exit(0)


if __name__ == '__main__':
    main()