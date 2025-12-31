# GenAI Stuff

This is a dumping ground for small genai-related scripts and data
files.

* sui.py - CLI for SwarmUI API; commands are:

    - gen: create an image based on rules, metadata, and options
    - jpg: batch-convert image files to JPG, optionally resizing them
    - rename: batch-rename image files based on --pre|set|seq options
    - params: extract parameters from PNG, JPG, and JSON files
    - prompt: shortcut for `params -p`
    - list-rules: list canned parameter sets (built-in or ~/.sui)
    - list-models: list available base models, loras, or vae
    - status: return server/backend status

Note: to avoid getting into the weeds with EXIF, `PyExifTool` is used,
which requires the [exiftool](https://exiftool.org/) binary be in your
path. Yes, the best way to deal with EXIF in Python is a Perl script.

* dp.py - CLI wrapper to use the popular
  [dynamicprompts](https://github.com/adieyal/dynamicprompts)
  library with image-generation software that doesn't support
  it directly.

* aspect.py - calculate resolutions for arbitrary aspect ratios that
  do not exceed the "standard" pixel count (sidelength squared) for a model.

* waifupaper.py - MacOS wallpaper-rotation script with more
  options than the standard control-panel settings.

* randompeople.yaml - dynamicprompts wildcards converted from a
  [heavily-randomized prompt](https://discord.com/channels/1243166023859961988/1396143088560242708)
  posted to the SwarmUI Discord channel by user Hippotes, with
  some typos corrected and some weights added. Use as `__p/random__`.

## My image-generation workflow

Typically I generate a few hundred prompts with `dp.py`, feed them to
`sui.py gen -j` on STDIN, pick the best ones with my
[deathmatch](https://github.com/jgreely/deathmatch) script, and then
use those files as arguments to `sui.py gen` with refining and
upscaling parameters added.

```
dp.py __prompt/christmas__ | sui.py --pre out/zit --set xmas \
    gen -r zit,1080p -j
deathmatch out
...
sui.py --pre out/zit --set xmas4k \
    gen -r zit,4k -j -u -L sensia out/*-{01,15,19,37,82}.jpg
```
