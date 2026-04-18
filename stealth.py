#!/usr/bin/env python
"""
Quick standalone hack to extract SwarmUI stealth metadata from the low
bit in WEBP/PNG images, where it is stored in the alpha channel if
present, or else the RGB channels. RGB is annoying to extract because
it only works for *lossless* WEBP, and it's a continuous bitstream of
3 bits per pixel, so it's a separate function to keep things clean.
"""

import sys
from PIL import Image
import gzip

def stealth_bytes_alpha(image, start=0, count=1):
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


def stealth_bytes_rgb(image, start=0, count=1):
    """
    Convert the low bit of each channel in each pixel into bytes,
    where pixel (x,y) through (x,y+2) contain the bits in order, high
    to low, with one leftover to start the next byte. Because this
    is a pain in the ass to decode at arbitrary offsets, it's easier
    to just start from 0 each time and discard the unused bytes.
    """
    count *= 8
    lowbits = list()
    h = image.height
    x = 0
    y = 0
    while len(lowbits) < start * 8 + count:
        r,g,b = image.getpixel((x, y))
        lowbits.append(r&1)
        lowbits.append(g&1)
        lowbits.append(b&1)
        y += 1
        if y == h:
            y = 0
            x += 1
    buf = bytearray()
    # discard leftover bits
    while len(lowbits) % 8:
        lowbits.pop()
    for i in range(0, len(lowbits), 8):
        b = 0
        for j in range(8):
            if i + j < len(lowbits):
                b |= lowbits[i + j] << (7 - j)
        buf.append(b)
    if start > 0:
        return buf[start:]
    return buf


def stealth_bytes(image, start, count):
    if image.mode == 'RGBA':
        return stealth_bytes_alpha(image, start, count)
    else:
        return stealth_bytes_rgb(image, start, count)


def stealth_metadata(file):
    """
    Check the low bits of a WEBP/PNG image to see if it contains
    a JSON metadata structure:
        00-07   "stealth_"
        08-0A   "png" or "rgb" (stored in alpha channel or RGB)
        0B-0E   "comp" or "info" (gzipped or raw)
        0F      (unused)
        10-13   32-bit big-endian integer length of data, in bits
        14-??   data bytes
    If the image has an alpha channel, the low bits of pixels (0,0)
    through (0,7) contain the first byte; otherwise, the low bits
    of each of the RGB channels in pixels (0,0) through (0,2) contain
    the first byte (RGBRGBRG) as well as the high bit of the second
    byte.
    """
    try:
        im = Image.open(file)
    except Exception as e:
        print(e)
        sys.exit()
    if im.format in ['WEBP', 'PNG']:
        magic = stealth_bytes(im, 0, 11).decode(errors='ignore')
        if magic in ['stealth_png', 'stealth_rgb']:
            is_comp = stealth_bytes(im, 11, 4).decode(errors='ignore')
            data_len = 0
            for b in stealth_bytes(im, 15, 4):
                data_len = data_len * 256 + b
            data = stealth_bytes(im, 19, data_len//8)
            if is_comp == 'comp':
                data = gzip.decompress(data)
            params = data.decode(errors='ignore')
            return params
    return None

sys.argv.pop(0)
if len(sys.argv) > 0:
    params = stealth_metadata(sys.argv[0])
    if params:
        print(params)
else:
    print('Usage: stealth.py sui-image.webp')
