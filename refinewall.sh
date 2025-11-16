#!/usr/bin/env bash

# Refine and upscale PNG images containing SwarmUI metadata. This is
# a quick little hack for the very specific case where images
# generated at 576x1024 or 1024x576 are re-generated with the same
# parameters plus a refining pass, and upscaled 3.75x to native 4K
# monitor resolution (2160x3840) for wallpaper.
#
# Adding -t (tall) or -w (wide) overwrites the original rendering
# size to be 1080x1920 or 1920x1080, and changes the upscaling to
# 2x; for models that can handle the higher initial resolution,
# this reduces the finger/toe defects in the final output.
#
# Since the refining process can create new defects in the image,
# there's also a -v option to add variation seed strength; for most
# models you want to use a very small value like 0.05 to avoid significant
# changes to the source image.
#
# Upscaler used (feel free to edit in your favorite):
#   model-8xNMKDSuperscale_150000G.pth
#   https://civitai.com/models/292030/8xnmkd-superscale150000g
#
# Requires exiftool, jq, jo, curl (version 7.82.0 or newer), wget

HOST=localhost
PORT=7801
UPSCALER=model-8xNMKDSuperscale_150000G.pth
VARIATION=
TALL=
WIDE=
while getopts "h:p:v:wt" opt; do
    case $opt in
    h)
        HOST=$OPTARG
        ;;
    p)
        PORT=$OPTARG
        ;;
    v)
        VARIATION=$OPTARG
        ;;
    t)
        TALL=1
        ;;
    w)
        WIDE=1
        ;;
    \?)
        echo "usage: $0 [-h host] [-p port] [-v variation%] [-t|w] image.png ..."
        exit
        ;;
    esac
done
shift $((OPTIND-1))

BASEURL=http://$HOST:$PORT

CURL() {
    curl -s -S -m 3600 -X POST "$@"
}

# First, get a usable session ID:
#
SESSION_ID=$(CURL --json '{}' $BASEURL/API/GetNewSession |
    jq -r '.session_id')

UPSCALE=3.75
SIZE=()
if [ -n "$TALL" ]; then
    SIZE=(
        width=1080
        height=1920
    )
    UPSCALE=2.0
elif [ -n "$WIDE" ]; then
    SIZE=(
        width=1920
        height=1080
    )
    UPSCALE=2.0
fi

REFINE=(
    ${SIZE[@]}
    refinercontrolpercentage=0.4
    refinermethod=PostApply
    refinerupscale=$UPSCALE
    refinerupscalemethod=$UPSCALER
    refinerdotiling=true
)
if [ -n "$VARIATION" ]; then
    VARY=(
        variationseed=-1
        variationseedstrength=$VARIATION
    )
else
    VARY=()
fi
for SRC in "$@"; do
    # extract parameters from source image, strip out 'images' field
    # (in case it was part of a large batch)
    #
    JSON=$(exiftool -b -parameters "$SRC" |
        jq -c '.sui_image_params|del(.images,.swarm_version)' |
        jo -f - session_id=$SESSION_ID images=1 "${REFINE[@]}" "${VARY[@]}"
    )
    # convert loras & loraweights from arrays into comma-separated strings
    #
    if [ "$(jq .loras <<<"$JSON")" != "null" ]; then
        JSON=$(jq -c '.loras |= join(",")' <<<"$JSON")
        JSON=$(jq -c '.loraweights |= join(",")' <<<"$JSON")
        if [ "$(jq .lorasectionconfinement <<<"$JSON")" != "null" ]; then
            JSON=$(jq -c '.lorasectionconfinement |= join(",")' <<<"$JSON")
        fi
    fi

    OUTPUT=$(CURL --json "$JSON" $BASEURL/API/GenerateText2Image)

    # retrieve new image
    #
    URL=$(jq -r '.images[0]' <<<"$OUTPUT")
    wget --quiet "$BASEURL/$URL"

    # currently assumes success...
    OUTFILE=$(basename "$URL")
    GENTIME=$(exiftool -b -parameters "$OUTFILE" |
        jq -r .sui_extra_data.generation_time)
    # write original filename into EXIF data to preserve the source
    exiftool -q -overwrite_original -DocumentName=$(basename "$SRC") $OUTFILE
    echo $GENTIME $OUTFILE
done
exit
