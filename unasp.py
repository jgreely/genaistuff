#!/usr/bin/env python
#
# find the closest well-known aspect ratio for a given resolution(s)

import sys

aspects = [
    { "n": "1:1", "d": "square" },
    { "n": "16:15", "d": "256x240, 1024x960, classic NES format" },
    { "n": "17:15", "d": "" },
    { "n": "17:14", "d": "specialized industrial panels" },
    { "n": "5:4", "d": "8x10, 1280x1024, US framed picture size" },
    { "n": "14:11", "d": "11x14, US framed picture size" },
    { "n": "9:7", "d": "1028x800" },
    { "n": "22:17", "d": "8.5x11, US Letter paper" },
    { "n": "4:3", "d": "1024x768" },
    { "n": "18:13", "d": "foldable phones/tablets" },
    { "n": "24:17", "d": "ISO paper 1.414:1" },
    { "n": "19:13", "d": "large photo paper" },
    { "n": "3:2", "d": "2160x1440, 36x24 (35mm film), 4x6, US framed picture size" },
    { "n": "17:11", "d": "US tabloid/ledger paper" },
    { "n": "14:9", "d": "broadcast compromise between 4:3 and 16:9" },
    { "n": "16:10", "d": "8:5, 1920x1200" },
    { "n": "5:3", "d": "index card" },
    { "n": "7:4", "d": "used by Midjourney" },
    { "n": "16:9", "d": "1920x1080, HDTV" },
    { "n": "256:135", "d": "2048x1080, Digital Cinema Initiatives 4K" },
    { "n": "21:11", "d": "car infotainment screens" },
    { "n": "2:1", "d": "" },
    { "n": "40:19", "d": "Playboy centerfold" },
    { "n": "25:11", "d": "Playboy centerfold" },
    { "n": "7:3", "d": "" },
    { "n": "64:27", "d": "2560x1080, professional/gaming" },
    { "n": "12:5", "d": "" },
    { "n": "5:2", "d": "" },
    { "n": "26:9", "d": "" },
    { "n": "3:1", "d": "" },
    { "n": "29:9", "d": "" },
    { "n": "32:9", "d": "3840x1080" },
    { "n": "29:8", "d": "" },
    { "n": "15:4", "d": "" },
    { "n": "31:8", "d": "" },
    { "n": "4:1", "d": "17280×4320, advertising display" },
    { "n": "5:1", "d": "" }
]

for aspect in aspects:
    w, h = [int(x) for x in aspect['n'].split(':')]
    aspect['r1'] = 100 * w / h
    aspect['r2'] = 100 * h / w

sys.argv.pop(0)
for arg in sys.argv:
    w, h = [int(x) for x in arg.split('x')]
    ratio = 100 * w / h
    diff = 9999
    best_aspect = dict()
    is_tall = 'tall'
    for aspect in aspects:
        if abs(ratio - aspect['r1']) < diff:
            best_aspect = aspect
            diff = abs(ratio - aspect['r1'])
            is_tall = 'wide'
        elif abs(ratio - aspect['r2']) < diff:
            best_aspect = aspect
            diff = abs(ratio - aspect['r2'])
            is_tall = 'tall'
    print(f"{arg}: {best_aspect['n']} ({is_tall}, {diff:.2f}%)")
