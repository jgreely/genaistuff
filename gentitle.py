#!/usr/bin/env python
"""
Use vision model to generate book titles and filenames.

TODO: add uncensoring sysprompt option
"""

import io
import os
import re
import sys
import json
import base64
from openai import OpenAI
from PIL import Image
import argparse

booktitle_prompt='Analyze this image and use its significant elements and themes to compose 8 distinct titles for a genre fiction novel. Output only the titles, one per line, without any number, formatting, or Markdown.'
filename_prompt='Analyze this image and use its significant elements and themes to compose a meaningful file name for the image using only letters, digits, and "-" to separate words; no other characters are permitted. Words MUST be separated by "-". The filename MUST be no longer than 48 characters, and MUST NOT include a date or timestamp. Output only the new filename, with no formatting.'

# convert webp/png to jpg before sending using Image.convert,
# discarding any alpha channel; LM Studio rejected all webp and
# many png
def encode_image_to_base64(image_path, dryrun):
    try:
        im = Image.open(file)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit()
    if im.mode != 'RGB':
        if dryrun:
            print(f"Converting {file} from '{im.mode}' to 'RGB'")
        im = im.convert('RGB')
    if im.width > 1024 or im.height > 1024:
        # LM Studio can choke on larger images
        if dryrun:
            print(f"Scaling {file} down to 1024 from {im.width}x{im.height}")
        if im.width > im.height:
            scale = im.width / 1024
        else:
            scale = im.height / 1024
        im = im.resize((int(im.width / scale), int(im.height / scale)),
            Image.Resampling.LANCZOS)
    f = io.BytesIO()
    im.save(f, 'JPEG', optimize=True, quality=85, progressive=True)
    f.seek(0)
    encoded_string = base64.b64encode(f.getvalue()).decode("utf-8")
    ext = image_path.split(".")[-1].lower()
    mime_type = "image/jpeg"
    return f"data:{mime_type};base64,{encoded_string}"

parser = argparse.ArgumentParser(
    prog='gentitle',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        Call LM Studio via the OpenAI SDK (native SDK locks up on me
        a lot) to create a title/filename for an image.
    """
)
parser.add_argument('-b', '--base-url',
    default='localhost:1234',
    help='host:port to connect to (default: localhost:1234)')
parser.add_argument('-f', '--filename',
    action='store_true',
    help='generate a filename instead of a book title')
parser.add_argument('-c', '--config',
    default=os.path.expanduser('~/.gen'),
    help='config file to read base url & model from, as 'base=...', 'model=...' (default ~/.gen)')
parser.add_argument('-M', '--list-models',
    action='store_true',
    help='list all models available on the server')
parser.add_argument('-m', '--model',
    # qwen/qwen3-vl-4b doesn't make very good filenames
    default="google/gemma-4-31b-qat",
    help='LLM to use for prompt generation (default: google/gemma-4-31b-qat)')
parser.add_argument('-n', '--dryrun',
    action='store_true',
    help='just print the resolved prompt without sending it to the server')
parser.add_argument('--max-tokens',
    default=32768,
    help='max tokens limit')
parser.add_argument('-r', '--reasoning',
    choices=['none', 'low', 'medium', 'high'],
    default='none',
    help='set thinking mode (default: none)')
parser.add_argument('--temperature',
    default=0.6,
    help='LLM temperature parameter (default 0.6)')
parser.add_argument('--verbose',
    action='store_true',
    help='print reasoning content before output')
parser.add_argument('-D', '--debug',
    action='store_true',
    help='print the full JSON response')
parser.add_argument('file',
    nargs='*',
    help='image file to analyze'
)
args=parser.parse_args()

if os.path.exists(args.config):
    with open(args.config) as f:
        for line in f:
            if re.search(r'^#|^ *$', line):
                continue
            if '=' in line:
                var,val = line.strip().split('=', 1)
                if var == 'base':
                    args.base_url = val
                elif var == 'model':
                    args.model = val

if args.list_models:
    client = OpenAI(base_url=f"http://{args.base_url}/v1",
        api_key="lm-studio",
        timeout=60*30)
    models = [x.id for x in client.models.list()]
    models.sort()
    for model in models:
        print(model)
    sys.exit()

model = args.model
if args.filename:
    prompt=filename_prompt
else:
    prompt=booktitle_prompt

if args.dryrun:
    print(f"Connecting to http://{args.base_url}/v1")
    print(f'Using prompt "{prompt}"')
else:
    client = OpenAI(base_url=f"http://{args.base_url}/v1", api_key="lm-studio",
        timeout=60*30)

Image.init() # load all plugins to find supported file extensions
for file in args.file:
    base, ext = os.path.splitext(file)
    if ext.lower() not in Image.EXTENSION.keys():
        print(f"Skipping non-image file '{file}'", file=sys.stderr)
        continue
    base64_image = encode_image_to_base64(file, args.dryrun or args.debug)
    payload = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": base64_image
                    },
                },
            ],
        }
    ]

    if args.dryrun:
        print(f"Sending Base64-encoded version of {file}")
        continue
        
    try:
        response = client.chat.completions.create(
            model=model,
            messages=payload,
            max_tokens=32768,
            temperature=args.temperature,
            timeout=60*30,
            reasoning_effort=args.reasoning,
        )
    except Exception as e:
        print(f"{file}: {e}", file=sys.stderr)
        continue
    if args.reasoning == 'none':
        reasoning_content = {'reasoning': 'disabled'}
    else:
        reasoning_content = response.choices[0].message.reasoning_content
    content = response.choices[0].message.content
    if args.debug:
        print('REQUEST:')
        print(json.dumps(payload, indent=4))
        print('RESPONSE:')
        print(response)
        print('-----')
    if args.verbose:
        print(reasoning_content)
        print('-----')
    if args.filename:
        dir = os.path.dirname(file)
        base, ext = os.path.splitext(file)
        dir = f"{dir}/" if dir else ""
        print(f'mv "{file}" "{dir}{content}{ext.lower()}"', flush=True)
    else:
        print(content, flush=True)
