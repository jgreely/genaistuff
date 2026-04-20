#!/usr/bin/env python
"""
pyshed = py-shuffle-head
    Quick hack to efficiently emulate "shuf | head" for very large
    files, by creating a cache file containing the first byte of each
    line. This cache is stored in .cache-$file, and automatically
    updated if the file is newer than the cache.
"""

import os
import sys
import random
import argparse

parser = argparse.ArgumentParser(
    description='''
        pyshed (py-shuffle-head) - efficiently extract random lines
        from very large files
    ''',
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument('-c', '--count',
    type=int,
    default=10,
    help = 'number of lines to extract'
)
parser.add_argument(
    'files',
    nargs='+',
    help='one or more text files'
)
args=parser.parse_args()

for file in args.files:
    pathname, filename = os.path.split(file)
    if pathname:
        offset_file = os.path.join(pathname, f".cache-{filename}")
    else:
        offset_file = f".cache-{filename}"
    if not os.path.exists(offset_file) or os.path.getmtime(offset_file) < os.path.getmtime(file):
        offset = 0
        with open(offset_file, "w") as output:
            with open(file, "rb") as input:
                for line in input:
                    print(f"{offset:08x}", file=output, end="\r\n")
                    offset += len(line)
    total_lines = os.path.getsize(offset_file) // 10
    with open(offset_file, "r") as cache:
        with open(file, "rb") as input:
            for i in random.sample(range(total_lines), args.count):
                cache.seek(i * 10, 0)
                offset_hex = cache.readline()
                offset = int(offset_hex, base=16)
                input.seek(offset, 0)
                sys.stdout.buffer.write(input.readline())
