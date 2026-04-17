#!/usr/bin/env python
"""
quick standalone hack to extract SwarmUI stealth metadata from the
alpha channel of WEBP images, where it's stored in the low bit.
SwarmUI *can* also encode it in the RGB channels, as well as in PNG
images, but the only person I know who's using it is Juan on the
Discord, and he's using WEBP/alpha.
"""

import sys
from PIL import Image
import gzip

def stealth_bytes(image, start=0, count=1):
    """
    Convert the low bit of each pixel in the alpha channel into bytes,
    where pixel (x,y) through (x,y+7) contain the bits in order, high
    to low.
    """
    start *= 8
    count *= 8
    lowbits = list()
    h = image.height
    x = start // h
    y = start % h
    while len(lowbits) < count:
        a = image.getpixel((x, y))[3]
        lowbits.append(a&1)
        y += 1
        if y == h:
            y = 0
            x += 1
    buf = bytearray()
    for i in range(0, len(lowbits), 8):
        b = 0
        for j in range(8):
            if i + j < len(lowbits):
                b |= lowbits[i + j] << (7 - j)
        buf.append(b)
    return buf

def webp_stealth_metadata(file):
    """
    If the file is a WEBP image with an alpha channel, attempt to
    extract SwarmUI stealth metadata from it.
    """
    try:
        im = Image.open(file)
    except Exception as e:
        print(e)
        sys.exit()
    if im.format == 'WEBP' and im.mode == 'RGBA':
        magic = stealth_bytes(im, 0, 11).decode(errors='ignore')
        if magic == 'stealth_png':
            is_comp = stealth_bytes(im, 11, 4).decode(errors='ignore')
            data_len = 0
            for b in stealth_bytes(im, 15, 4):
                data_len = data_len * 256 + b
            data = stealth_bytes(im, 19, data_len/8)
            if is_comp == 'comp':
                data = gzip.decompress(data)
            params = data.decode(errors='ignore')
            return(params)
    return None

sys.argv.pop(0)
if len(sys.argv) > 0:
    params = webp_stealth_metadata(sys.argv[0])
    if params:
        print(params)
else:
    print('Usage: stealth.py sui-image.webp')
