#!/usr/bin/env bash
#
# quick conversion of SwarmUI PNG to JPG, preserving metadata
#
# Requires pngtopnm, cjpeg, exiftool

for PNG in "$@"; do
    echo $PNG
    JPG=$(basename $PNG .png).jpg
    pngtopnm $PNG | cjpeg -q 95 -progressive > $JPG
    exiftool -overwrite_original -b \
        -UserComment="$(exiftool -b -parameters $PNG)" $JPG
done
