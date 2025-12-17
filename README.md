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
