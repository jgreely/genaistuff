#!/usr/bin/env python3
"""

Usage:
    aspect.py -m 64 -p 1328 1:1 17:15 9:7 3:2 5:3 16:9 21:11 26:9 \
        5:2 29:9 4:1 5:4 31:8 15:4 29:8 3:1 12:5 7:4 19:13 18:13 \
        17:14 16:15 5:1 4:3 10:4.75 25:11 | sort -k2n

Written by ChatGPT.
"""

import math

def max_dimensions(aspect_width, aspect_height, total_pixels, multiple=16):
    """
    Calculate the maximum dimensions (width, height) for a given aspect ratio
    that fit within a specified total number of pixels, constrained so that
    both width and height are multiples of `multiple`.
    
    Allows small deviations from the exact aspect ratio in order to maximize
    resolution while staying under the pixel budget.
    
    :param aspect_width: int, the width part of the aspect ratio (e.g. 16 for 16:9)
    :param aspect_height: int, the height part of the aspect ratio (e.g. 9 for 16:9)
    :param total_pixels: int, maximum allowed number of pixels (width * height)
    :param multiple: int, required multiple for both width and height (e.g., 16 or 64)
    :return: (width, height) tuple of maximum dimensions
    """
    # ideal floating-point dimensions before snapping
    scale = math.sqrt(total_pixels / (aspect_width * aspect_height))
    ideal_w = aspect_width * scale
    ideal_h = aspect_height * scale

    # snap down to nearest multiple
    width = int(ideal_w) - (int(ideal_w) % multiple)
    height = int(ideal_h) - (int(ideal_h) % multiple)

    # adjust if snapped values exceed pixel budget
    while width * height > total_pixels and width > 0 and height > 0:
        if width >= height:
            width -= multiple
        else:
            height -= multiple

    return width, height

import argparse
parser = argparse.ArgumentParser(
    prog='aspect',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        small app that calculates largest dimensions for specified
        aspect ratios that do not exceed NxN pixels, plus their
        dimensions scaled down so the long side is 420 pixels.
    """
)
parser.add_argument('-m', '--multiplier',
    type=int,
    default=64,
    help = 'common divisor for dimensions'
)
parser.add_argument('-p', '--pixels',
    type=int,
    default=1024,
    help = 'number of pixels in each dimension'
)
parser.add_argument('aspects',
    nargs = '*',
    help='Aspect ratios to generate'
)
args=parser.parse_args()

total_px = args.pixels * args.pixels
multiple = args.multiplier

for aspect in args.aspects:
    aspect_w, aspect_h = aspect.split(r':')
    w, h = max_dimensions(float(aspect_w), float(aspect_h), total_px, multiple)
    print(f"{aspect_w}:{aspect_h}\t{w} x {h}\t{round(w/h*420)} x 420")
