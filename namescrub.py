#!/usr/bin/env python
"""
Scrub special characters from file and directory names in
either STDIN or arguments. Turns out my archive of downloaded
pictures is full of garbage names.
"""

import os
import sys
import re

def multi_replace(text, replacements):
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags = re.DOTALL)
    return text


debug = False
if len(sys.argv) > 1 and sys.argv[1] == '-d':
    debug = True
    sys.argv.pop(1)
if len(sys.argv) > 1:
    files = sys.argv[1:]
else:
    files = [x.rstrip() for x in sys.stdin]

for file in files:
    if os.path.exists(file) and re.search(r'[-% &():#!\[\]]+', file):
        newfile = multi_replace(file, [
            ( r'%[0-9A-F][0-9A-F]', '' ),
            ( r'^-', '' ),
            ( r' +', '-' ),
            ( r'[&():#!\[\]]+', '-' ),
            ( r'-+', '-' ),
            ( r'\.-', '-' ),
            ( r'\.+', '.' ),
            ( r'-\.', '.' )
        ])
        if (file != newfile):
            print(file, " -> ", newfile)
            if not debug:
                os.rename(file, newfile)
