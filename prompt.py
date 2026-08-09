#!/usr/bin/env python3
"""
enhance a prompt using custom system prompts and models,
with the default being Hidream's suggested system prompt,
using gpt-oss-20b as the model.
"""

import os
import sys
import importlib
importlib.reload(sys)
import argparse
import re
import configparser

import lmstudio as lms
import secrets

# if '@<' and '>@' are found in the string, pass only the string
# between them to the LLM. If '@<' is followed by a string terminating
# in a ':', use that LLM sysprompt instead of the global one.
# Multiple '@<foo: ...>@' expressions can appear in a prompt, but cannot
# overlap.
#
partial_enhancement_regexp = r'( *)@<(?:([_A-Za-z0-9]+):)? *([^>]+) *>@( *)'

default_vision_model='qwen/qwen3-vl-4b'
# qwen can go into a tight spin and never return without this
vision_config={
    "maxTokens": 1500,
    "repeatPenalty": 1.1
}
default_vision_prompt="""
Analyze this image and provide a detailed image-generation prompt for
advanced models, as a single flowing paragraph. Focus on the subject,
lighting (type, source, intensity), color palette, composition, camera
angle, and artistic style. Do not make up stories about the image,
keep it factual. Do not include any formatting. Put the most important
subject and overall intent at the start, then unfold composition,
action, location, style, technical parameters, and text rendering. Use
complete sentences, rich but precise adjectives, and photography /
painting / design vocabulary. Do not include any expression that
requires the image model to do further reasoning to understand. The
prompt must be self-contained — the prompt alone must suffice to
generate the image accurately.
"""

default_system_prompt="""
[DEFAULT]
prompt =
    You are a Prompt Engineering Engine — an AI image-generation Prompt
    Engineer who is also a creative director with encyclopedic knowledge
    and visual-direction skill. Your task is to analyze the user's raw
    image request, infer implicit knowledge and the best visual approach,
    and rewrite it into a clear, detailed English prompt that is directly
    usable for image generation.
    
    ## Core Goal
    
    Image generation models can only execute direct visual descriptions;
    they cannot fill in background knowledge, logical relations, or text
    content on their own. Therefore you must complete knowledge
    resolution, spatial planning, and visual direction in advance, and
    write the results explicitly into the prompt.
    
    Use the SCALIST framework to expand every scene:
    
    - **Subject**: identity, appearance, color, material, texture, action, expression, clothing.
    - **Composition**: shot type, viewpoint, subject placement, foreground/midground/background layering, negative space, focal point.
    - **Action**: what the subject is doing, direction of motion, posture, interactions.
    - **Location**: scene, indoor/outdoor, period, weather, time of day, environmental detail.
    - **Image style**: photorealistic, cinematic, oil painting, watercolor, anime, 3D render, etc., paired with matching lighting and color mood.
    - **Specs**: photographic/render parameters, e.g. 85mm lens, low-angle shot, shallow depth of field, soft diffused light, dramatic backlighting, matte texture, sharp focus.
    - **Text rendering**: if the user requests text, the exact text must be placed inside English double quotes, with explicit font style, color, size, material, and precise position.
    
    **Knowledge resolution and explicitization.** Anything involving
    poetry, lyrics, famous quotes, formulas, historical figures,
    scientific concepts, landmarks, famous paintings, cultural symbols,
    historical events, UI layouts, or real-world objects must first be
    resolved into concrete answers and visible features, then written into
    the prompt.
    
    **Spatial and logical anchoring.** Rewrite vague relationships into
    explicit layout, e.g. "top left corner", "centered in the foreground",
    "slightly behind the main subject", "background out of focus", "text
    aligned along the bottom edge". Avoid vague phrases like "next to",
    "some", "nice-looking".
    
    **Text-typography precision.** Chinese, English, formulas,
    multilingual text — every character must be preserved verbatim inside
    quotation marks; also specify font (calligraphy, serif, sans-serif,
    handwritten), color, material, and position.
    
    **Real-world grounding.** If the user requests factually accurate
    content — historical artifacts, weather phenomena, portraits,
    architecture, dashboards, app interfaces — use your internal knowledge
    to fill in accurate visual detail.
    
    **Concretizing abstract concepts.** Turn abstract words into visible scenes, symbols, and
    atmospheres.
    
    ## Output prompt requirements
    
    - The prompt must be a single coherent, natural English paragraph — like a Creative Director's Brief, not a keyword pile or tag soup.
    - Length is typically 80–220 words; simple requests can be shorter, complex scenes longer.
    - Put the most important subject and overall intent at the start, then unfold composition, action, location, style, technical parameters, and text rendering.
    - Use complete sentences, rich but precise adjectives, and photography / painting / design vocabulary.
    - Do not include any expression that requires the image model to do further reasoning to understand.
    - The prompt must be self-contained — the prompt alone must suffice to generate the image accurately.
    
    ## Execution steps
    
    **Analyze**: identify core subject, user intent, text requirements, reference constraints, and any implicit knowledge that needs resolving.
    **Reason**: choose the most suitable lighting, lens, angle, texture, style, spatial layout, and factual details for the scene.
    **Rewrite**: output the final, enhanced English single-paragraph prompt.
    
    Output prompt result only, with no other text.
    Do not include any explanation.
    Do not include any text formatting.
"""

def multi_replace(text, replacements):
    """
    Perform multiple regex search-and-replace actions in sequence on the given text.

    :param text: The input string to modify.
    :param replacements: A list of tuples (pattern, replacement) where:
                         - pattern: regex pattern to search for
                         - replacement: string to replace the matched pattern
    :return: The modified string after all replacements.
    """
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags = re.DOTALL)
    return text

# expects a match to the regexp r'( *)@<(?:([_A-Za-z0-9]+):)? *([^>]+) *>@( *)'
#   @< prompt >@
#   @<label: prompt >@
#   1 - prefix whitespace
#   2 - optional sysprompt label followed by ':'
#   3 - prompt
#   4 - suffix whitespace
def partial_enhance(m):
    chat = lms.Chat()
    prefix = m.group(1)
    sysprompt = m.group(2) if m.group(2) else ''
    prompt = m.group(3)
    suffix = m.group(4)
    if sysprompt and config.has_option('DEFAULT', sysprompt):
        chat.add_system_prompt(config.get('DEFAULT', sysprompt))
    elif sysprompt:
        print(f"system prompt '{sysprompt}' not found in ~/.pyprompt")
        sys.exit()
    else:
        chat.add_system_prompt(system_prompt)
    chat.add_user_message(prompt)
    # DEBUG:
    # explicit random seed for debugging an llmster issue
    # prediction = model.respond(chat, config={"seed": secrets.randbits(64)})
    prediction = model.respond(chat)
    response = prediction.content
    if args.debug:
        print(f'DEBUG-partial: |{sysprompt}|{prefix}|{response}|{suffix}|',
            file=sys.stderr)
    else:
        response = multi_replace(response, [
            ( r'^.*</seed:think>', '' ), # seed-oss-style
            ( r'^.*</think>', '' ),
            ( r'^.*<.message.>', '' )
        ])
    return f'{prefix}{response}{suffix}'


parser = argparse.ArgumentParser(
    prog='prompt',
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        Small app that calls lmstudio to optimize prompts.
        The following keys in the "[DEFAULT]" section of ~/.pyprompt
        will be used as default values for the LM Studio server url,
        model, and system prompt: url, model, prompt. All other keys
        will be interpreted as names for alternative system prompts.
    """
)
parser.add_argument('-i', '--images',
    action='append', default=[],
    help='ask a vision-capable model to describe the contents of the files passed as arguments')
parser.add_argument('-r', '--raw',
    action='store_true',
    help='do not strip newlines from output')
parser.add_argument('-s', '--show-prompts',
    action='store_true',
    help='list system prompts available in ~/.pyprompt'
)
parser.add_argument('-S', '--sysprompt-dump',
    action='store_true',
    help='dump the contents of the named/default system prompt')
parser.add_argument('-l', '--list',
    action='store_true',
    help = 'list available models on the server.'
)
parser.add_argument('-m', '--model',
    type=str,
    help = 'installed model to use for prompt optimization.'
)
parser.add_argument('-t', '--temperature',
    type = float,
    default = 0.75,
    help = 'randomness of output (higher = more; default=0.75).'
)
parser.add_argument('-C', '--context',
    type = int,
    default = 4096,
    help = 'context length limit (default=4096).'
)
parser.add_argument('-p', '--penalty',
    type = float,
    default = 1.1, # some models can spin endlessly at 1.0 w/LM Studio
    help = 'repetition penalty, >1.0 reduces repetitive crap (adjust gently).'
)
parser.add_argument('-T', '--tokens',
    type = int,
    default = 1500,
    help = 'maximum number of tokens to return from one request (default=1500).'
)
parser.add_argument('-n', '--no-think',
    action='store_true',
    help='send custom config to disable thinking mode')
parser.add_argument('-u', '--url',
    type= str,
    help='URL of LM Studio server')
parser.add_argument('-e', '--escape',
    action='store_true',
    help='''
        escape character sequences that trigger errors with CLIP parsers,
        specifically a colon inside of parentheses or brackets.
    ''')
parser.add_argument('-c', '--clipstrip',
    action='store_true',
    help='remove CLIP emphasis "(...:1.1)", "[...:0.5]"'
)
parser.add_argument('-d', '--debug',
    action='store_true',
    help='print raw response from LLM, to catch formatting errors and refusals'
)
parser.add_argument('sysprompt',
    nargs = '*',
    help='''
        optional system-prompt keys in ~/.pyprompt, to be applied
        globally in order; the first argument, if present, will be
        applied to any sub-expressions that do not specify their
        own sysprompt. To use the built-in default sysprompt when
        additional arguments are present, use 'default' as the
        argument
    '''
)
args=parser.parse_args()

config = configparser.RawConfigParser(default_section=None)
config.read_string(default_system_prompt)
config_file = os.path.join(os.path.expanduser("~"), ".pyprompt")
if os.path.isfile(config_file):
    config.read(config_file)
system_prompts = list()
if args.images:
    system_prompts.append(default_vision_prompt)
else:
    system_prompts.append(config.get('DEFAULT', 'prompt'))

SERVER_API_HOST = config.get('DEFAULT', 'url', fallback='localhost:1234')
if args.url:
    SERVER_API_HOST = args.url
lms.configure_default_client(SERVER_API_HOST)
lms.set_sync_api_timeout(120)

if args.model:
    model_id = args.model
elif args.images:
    model_id = default_vision_model
else:
    model_id = config.get('DEFAULT', 'model', fallback='openai/gpt-oss-20b')

if args.show_prompts:
    for sysprompt in config.options('DEFAULT'):
        if sysprompt not in ['prompt', 'url', 'model']:
            print(sysprompt)
    sys.exit()

if args.list:
    llm_only = lms.list_downloaded_models("llm")
    for model in llm_only:
        print(model.model_key)
    sys.exit()

if args.sysprompt and len(args.sysprompt) > 0:
    system_prompts = list() # override default
    for prompt_key in args.sysprompt:
        if prompt_key in ['default', '-', '.']:
            if args.images:
                system_prompts.append(default_vision_prompt)
            else:
                system_prompts.append(config.get('DEFAULT', 'prompt'))
        elif config.has_option('DEFAULT', prompt_key):
            system_prompts.append(config.get('DEFAULT', prompt_key))
        else:
            print(f"system prompt '{prompt_key}' not found in ~/.pyprompt")
            sys.exit()

if args.sysprompt_dump:
    for prompt in system_prompts:
        print(prompt)
    sys.exit()

if args.no_think:
    custom_fields = { "enableThinking": False }
else:
    custom_fields = { }
model = lms.llm(model_id, config = {
    "temperature" : args.temperature,
    "contextLength" : args.context,
    "repeatPenalty" : args.penalty,
    "maxTokens" : args.tokens,
    "customFields": custom_fields
})
if args.debug:
    print('Model config:', model.get_load_config())
    print('Model info:', model.get_info())

if args.images:
    # TODO: all sysprompts after the first should fall through to
    # standard prompt-enhancing code
    system_prompt = system_prompts[0]
    for image_file in args.images:
        try:
            image_handle = lms.prepare_image(image_file)
        except Exception as e:
            print(e)
            sys.exit()
        chat = lms.Chat()
        chat.add_system_prompt(system_prompt)
        chat.add_user_message("Describe the attached image",
            images=[image_handle])
        prediction = model.respond(chat, config=vision_config)
        response = prediction.content
        if args.debug:
            print(f'DEBUG: |{system_prompt}|{response}|',
                file=sys.stderr)
        else:
            response = multi_replace(response, [
                ( r'^.*</seed:think>', '' ), # seed-oss-style
                ( r'^.*</think>', '' ),
                ( r'^.*<.message.>', '' )
            ])
            if not args.raw:
                response = multi_replace(response, [
                    ( r'\n', ' ' ),
                    # gemma-4, need to make it one-line first
                    ( r'^.*<channel.>', '')
                ])
            response = multi_replace(response, [
                ( r'^ +', '' ),
                ( r' +$', '' ),
                ( r'’+', '’' ),
                ( r'\.+', '.'),
                ( r' +', ' ' )
            ])
            print(response, flush=True)
    sys.exit()

for prompt in sys.stdin:
    if args.clipstrip:
        prompt = multi_replace(prompt, [
            ( r'\(([^)]+):[^)]+\)', r'\1' ),
            ( r'\[([^]]+):[^]]+\]', r'\1' )
        ])
    for system_prompt in system_prompts:
        if '@<' in prompt and '>@' in prompt:
            response = re.sub(partial_enhancement_regexp,
                partial_enhance,
                prompt)
        else:
            # fresh chat each time, to prevent context cruft
            chat = lms.Chat()
            chat.add_system_prompt(system_prompt)
            chat.add_user_message(prompt)
            prediction = model.respond(chat)
            response = prediction.content
            if args.debug:
                print(f'DEBUG: |{system_prompt}|{response}|',
                    file=sys.stderr)
            else:
                response = multi_replace(response, [
                    ( r'^.*</seed:think>', '' ), # seed-oss-style
                    ( r'^.*</think>', '' ),
                    ( r'^.*<.message.>', '' )
                ])
        prompt = response
    if not args.debug:
        if not args.raw:
            response = multi_replace(response, [
                ( r'\n', ' ' ),
                # gemma-4, need to make it one-line first
                ( r'^.*<channel.>', '') 
            ])
        response = multi_replace(response, [
            ( r'^ +', '' ),
            ( r' +$', '' ),
            ( r'’+', '’' ),
            ( r'\.+', '.'),
            ( r' +', ' ' )
        ])
        if args.escape:
            response = multi_replace(response, [
                ( r'\[([^]]*):([^]]*)\]', r'\[\1:\2]' ),
                ( r'\(([^)]*):([^)]*)\)', r'\(\1:\2)' )
            ])
    try:
        print(response, flush=True)
    except:
        sys.exit()
