#!/usr/bin/env python
"""
This is a simple CLI wrapper around the dynamicprompts library,
allowing you make prompts for image-generation software that doesn't
directly support it. I like to generate several hundred at a time and
use them as a SwarmUI wildcard file with Seed Behavior set to 'Index'.

Usage:
    sd-dynamic [--count N] __prompt__ > wildcards.txt

There are additional options for debugging YAML files that may or
may not be useful to anyone but me.

Library source and documentation:
    https://github.com/adieyal/dynamicprompts
"""

import re
import os
import sys
import argparse
import json
import yaml
from pathlib import Path
from dynamicprompts.generators import RandomPromptGenerator
from dynamicprompts.generators import CombinatorialPromptGenerator
from dynamicprompts.wildcards.wildcard_manager import WildcardManager

def multi_replace(text, replacements):
    """
    Perform multiple regex search-and-replace actions in sequence
    on the given text.

    :param text: The input string to modify.
    :param replacements: A list of tuples (pattern, replacement) where:
                         - pattern: regex pattern to search for
                         - replacement: string to replace the matched pattern
    :return: The modified string after all replacements.
    """
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags = re.DOTALL)
    return text


parser = argparse.ArgumentParser(
    prog='sd-dynamic',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        Thin CLI wrapper around dynamicprompts library for
        randomizing SD prompts.
    """
)
parser.add_argument('-w', '--wildcards',
    action = 'store_true',
    help = 'list all wildcard collections containing wildcard references'
)
parser.add_argument('-v', '--verbose',
    action = 'store_true',
    help = 'with -w, lists all valid wildcard collections'
)
parser.add_argument('-c', '--count',
    type = int,
    default = 1,
    help = 'number of prompts to generate'
)
parser.add_argument('-d', '--directory',
    default = '.',
    help = 'directory to load wildcard files from (default ".")'
)
parser.add_argument('-a', '--all',
    action = 'store_true',
    help = 'dump all values for the current wildcard (does not recurse)'
)
parser.add_argument('-A', '--everything',
    action = 'store_true',
    help = 'dump all unique values for the current wildcard expression (recurses)'
)
parser.add_argument('-t', '--tee',
    action = 'store_true',
    help = 'tee the output to STDERR, so you can see it and pipe it'
)
parser.add_argument('-j', '--json',
    action = 'store_true',
    help = 'convert output from a.b=foo to JSON valid for Flux2'
)
parser.add_argument('prompts',
    nargs = '*',
    help = 'Prompts to process'
)
args=parser.parse_args()

wm = WildcardManager(Path(args.directory))
generator = RandomPromptGenerator(wildcard_manager=wm)

regexp = re.compile(r'__.+__')
if args.wildcards:
    for name in sorted(wm.get_collection_names()):
        if args.verbose:
            print(name)
            continue
        add_name=True
        for val in sorted(wm.get_all_values(name)):
            if regexp.search(val):
                if add_name:
                    print(name)
                    add_name=False
                print("    " + val)
    sys.exit()
elif args.all:
    # all values for specific wildcard, no recursion
    for prompt in args.prompts:
        for val in wm.get_all_values(prompt):
            print(val)
    sys.exit()
elif args.everything:
    # all unique values for a wildcard expression, recursive
    generator = CombinatorialPromptGenerator(wildcard_manager=wm)
    for prompt in args.prompts:
        for result in set(generator.generate(wm.to_wildcard(prompt))):
            print(result)
    sys.exit()
for prompt in args.prompts:
    # transform JSON to pass through intact
    if args.json:
        prompt = yaml.safe_load(prompt)
    for result in generator.generate(prompt, args.count):
        # normalize the punctuation and spacing
        if args.json:
            cleaned = json.dumps(yaml.safe_load(result.lstrip()))
        else:
            cleaned = multi_replace(result, [
                ( r' ,',         ','  ),
                ( r',(?=[^ ])',  ', ' ),
                ( r' +',         ' '  ),
                ( r'\.(?=[^ ])', '. ' ),
                ( r'\. *\. *',   '. ' ),
                ( r' *\n',       ' '  ),
                ( r'(?<=\. )([a-z])', lambda m: m.group(1).upper())
            ])
        print(cleaned)
        if args.tee:
            print(cleaned, file=sys.stderr)
