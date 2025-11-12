# GenAI Stuff

This is a dumping ground for small genai-related scripts and data
files.

* sd-dynamic - CLI wrapper to use the popular
  [dynamicprompts](https://github.com/adieyal/dynamicprompts)
  library with image-generation software that doesn't support
  it directly.

* aspect.py - calculate resolutions for arbitrary aspect ratios that
  do not exceed the "standard" (squared) pixel count for a model.

* waifupaper.py - MacOS wallpaper-rotation script with more
  options than the standard control-panel settings.

* refinewall.sh - SwarmUI CLI that re-generates an image with
  refining and upscaling turned on (specifically for 4K wallpaper
  from 1024x576/576x1024). -w/-t options to override the base size
  to 1920x1080/1080x1920 and upscaling to 2x, for better results
  from models that can handle the higher base resolution. -v
  option to generate variations to try to eliminate defects (start
  small, around 0.05).

* swarmui-png2jpg.sh - convert PNG to JPG, preserving SwarmUI metadata.
  uses cjpeg for speed and quality, which requires first converting
  to PPM format.

* randompeople.yaml - dynamicprompts wildcards converted from a
  [heavily-randomized prompt](https://discord.com/channels/1243166023859961988/1396143088560242708)
  posted to the SwarmUI Discord channel by user Hippotes, with
  some typos corrected and some weights added. Use as __p/random__.
