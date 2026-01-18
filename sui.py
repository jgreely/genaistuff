#!/usr/bin/env python
"""
A script that uses the SwarmUI API to generate images based on
parameters taken from a mix of command-line options, canned
modifications, JSON files, and metadata from previous
SwarmUI-generated images.
"""

import io
import os
import sys
import base64
import configparser
import json
import exiftool
import click
import requests
from requests.exceptions import HTTPError
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from PIL import ImageFilter
import math
import re
import importlib.resources
from string import Template
from datetime import datetime

invalid_params = [
    'swarm_version',
    'rounding',
    'fix_resolution',
    'host',
    'port'
]

# canned sets of parameters; override by creating ~/.sui
# 
default_rules = """
# 'rounding' field is used internally to calculate the resolutions
# for aspect ratios (most models prefer resolutions where X and Y
# are divisible by 64), and is not passed to SwarmUI.
# 'fix_resolution' field is used internally to round up the requested
# resolution to /64 and then crop it after image generation.
#
#[DEFAULT]
#host = remoteswarm.example.com
#port = 9999
#
[sdxl]
model=sd_xl_base_1.0
cfgscale=6.5
steps=36
sidelength=1024
rounding=64
sampler=dpmpp_2m_sde_gpu
scheduler=beta

[zit]
model = z_image_turbo_bf16
steps= 9
cfgscale = 1.0
sidelength=1024
rounding=64
sampler = euler_ancestral
scheduler = simple
sigmashift = 3.0
fix_resolution = true

[512]
sidelength=512
rounding=16

[768]
sidelength=768
rounding=16

[2k]
sidelength=1472
rounding=64

[2x]
refinercontrolpercentage = 0.4
refinermethod = PostApply
refinerupscale = 2.0
# recommended: model-4xNomosUniDAT_bokeh_jpg_-_v2-0
refinerupscalemethod = pixel-lanczos
refinersampler = seeds_2
refinerscheduler = kl_optimal
refinerdotiling = true

[vary15]
variationseed = -1
variationseedstrength = 0.15
"""

class swarmui:
    """simple API wrapper for SwarmUI"""
    def __init__(self, *, host:str, port:str):
        self._headers = {
            'user-agent': 'sui/1.0.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self._config = configparser.RawConfigParser()
        config_file = os.path.join(os.path.expanduser("~"), ".sui")
        if os.path.isfile(config_file):
            self._config.read(config_file)
        else:
            self._config.read_string(default_rules)
        if host:
            self._host = host
        elif self._config.has_option('DEFAULT', 'host'):
            self._host = self._config.get('DEFAULT', 'host')
        else:
            self._host = 'localhost'
        if port:
            self._port = port
        elif self._config.has_option('DEFAULT', 'port'):
            self._port = self._config.get('DEFAULT', 'port')
        else:
            self._port = '7801'

    @property
    def baseurl(self):
        return f"http://{self.host}:{self.port}"
    @property
    def host(self):
        return self._host
    @host.setter
    def host(self, value):
        self._host = value
    @property
    def port(self):
        return self._port
    @port.setter
    def port(self, value):
        self._port = value

    def create_session(self):
        response = self._post("/API/GetNewSession", params={})
        self._change_usersettings(session=response['session_id'])
        return response['session_id']

    def generate_image(self, params:dict, *, outfile="sui-output.png",
        session:str):
        params['session_id'] = session
        params['images'] = 1
        if 'imageformat' not in params:
            params['imageformat'] = 'PNG'
        if 'save_on_server' not in self.params:
            params['donotsave'] = True
        # strip invalid params that generate warnings in logfiles
        for noise in invalid_params:
            if noise in params:
                del params[noise]
        for fixup in ['loras', 'loraweights', 'loratencweights', 'lorasectionconfinement']:
            if fixup in params:
                _array2str(params, fixup)
        response = self._post("/API/GenerateText2Image", params=params,
            timeout=3600)
        imagefile = response['images'][0]
        if 'personalnote' in params:
            source = params['personalnote']
        else:
            source = ""
        self._download_image(imagefile, outfile, source)
        return(outfile)

    def list_rules(self):
        return self._config.sections()

    def get_rule_params(self, rule:str):
        if self._config.has_section(rule):
            items = dict(self._config.items(section=rule))
            return items
        print(f"Warning: config file has no rule '{rule}'")
        return dict()

    def merge_params(self, sets:list):
        """merge multiple sets of parameters into one, keeping the last version of each key"""
        params = dict()
        for s in sets:
            for item in s:
                if s[item] == 'unset' and item in params:
                    del params[item]
                else:
                    params[item] = s[item]
        return params

    def get_models(self, *, type='Stable-Diffusion'):
        """retrieve the names of available models (base, lora, vae)"""
        params = {
            "session_id": self.session_id,
            "path": "",
            "depth": 4,
            "subtype": type # Stable-Diffusion, LoRA, VAE
        }
        response = self._post("/API/ListModels", params=params)
        return response['files']

    def get_luts(self):
        """retrieve the names of PostRender extension LUTS"""
        luts = dict()
        response = self._post("/API/ListT2IParams",
            params={'session_id': self.session_id})
        for param in response['list']:
            if param['id'] == 'lutname':
                luts = param['values']
        return luts


    def _get(self, call:str, *, timeout=30):
        """Send GET request to a SwarmUI endpoint"""
        url = f"{self.baseurl}{call}"
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            raise SystemExit(err)
        return response

    def _post(self, call:str, *, params:dict, timeout=5):
        """Send POST request with JSON parameters to a SwarmUI endpoint"""
        url = f"{self.baseurl}{call}"
        try:
            response = requests.post(url, json=params, headers=self._headers,
                timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            raise SystemExit(err)
        if 'error' in response.json():
            print(f"{call} failed: {response.json()['error']}")
        return response.json()

    # Warning: this API call always returns success; you *must* check
    # the server logs for failures.
    def _change_usersettings(self, *, session:str):
        """force specific filename format, as PNG, with metadata"""
        params = {
            'session_id': session,
            'settings': {
                'fileformat.reformattransientimages': True,
                'fileformat.savemetadata': True
            }
        }
        response = self._post("/API/ChangeUserSettings", params=params)

    def _download_image(self, imagefile:str, outputfile:str, source:str):
        """download generated image from SwarmUI server"""
        if 'base64' in imagefile:
            b64 = imagefile.split(',')[1]
            img = base64.b64decode(b64)
            img_stream = io.BytesIO(img)
        else:
            img_stream = io.BytesIO()
            response = self._get(f"/{imagefile}")
            for chunk in response.iter_content(chunk_size=16*1024):
                img_stream.write(chunk)
        output = Image.open(img_stream)

        ops = dict()
        meta = output.info
        if 'parameters' in meta:
            ops['meta'] = meta['parameters']
        if 'jpeg_output' in self.params and self.params['jpeg_output']:
            if 'jpeg_quality' in self.params:
                ops['jpg'] = self.params['jpeg_output']
            else:
                ops['jpg'] = True
        if self.crop:
            ops['crop'] = self.crop
        if self.unsharp_mask:
            ops['unsharp'] = {'r': self.um_r, 'p': self.um_p, 't': self.um_t}
        ops['save'] = outputfile
        if source:
            ops['source'] = source # DocumentName
        process(ops).apply(output)

# TODO: store key ops in 'personalnotes', so they can be used
# in a re-gen.
class process:
    """
    collect all client-side post-processing operations: crop,
    unsharp-mask, resize, jpeg-conversion.
    """
    def __init__(self, ops:dict):
        self._op = dict()
        if ops:
            for k in ops:
                self._op[k] = ops[k]
        # each op is a dict
        # order of operations:
        #   op=meta (val=metadata_dict; used by save op)
        #   op=crop (val=bbox; used by fix_resolution, can be different
        #           for each image)
        #   op=size (val=percentage (<100))
        #   op=sharp (val={'r': radius, 'p': percent, 't': threshold})
        #   op=jpg (val=quality (<100))
        #   op=source (val=original image being re-genned)
        #   op=save (val=filename)
    @property
    def op(self):
        """list of operations to process for an image"""
        return self._op
    @op.setter
    def op(self, value):
        for k,v in value:
            self._op[k] = v
        return self._op

    def delete(self, op):
        if op in self._op:
            del self._op[op]

    def apply(self, image:Image):
        """return an Image object with all operations applied in sequence"""
        op = self.op
        if 'meta' in op:
            image_meta = op['meta']
        else:
            image_meta = None
        if 'crop' in op:
            image = image.crop(op['crop'])
        if 'size' in op:
            size = op['size']
            if size < 100:
                image = image.resize((int(image.width * size/100),
                    int(image.height * size/100)))
        if 'sharp' in op:
            image = image.filter(ImageFilter.UnsharpMask(
                radius=float(op['sharp']['r']), percent=int(op['sharp']['p']),
                threshold=int(op['sharp']['t'])))
        if 'jpg' in op:
            jpg_quality = 85
            if type(op['jpg']) is int and op['jpg'] < 100 and op['jpg'] > 0:
                jpg_quality = op['jpg']
            # in-memory conversion
            f = io.BytesIO()
            image.save(f, 'JPEG', optimize=True, quality=jpg_quality,
                progressive=True)
            f.seek(0)
            image = Image.open(f)
        if 'save' in op:
            exif = image.getexif()
            if 'source' in op:
                exif[269] = op['source']
            if image.format == 'JPEG':
                try:
                    image.save(op['save'], exif=exif)
                except Exception as e:
                    click.FileError(f"{op['save']}: {e}")
                exiftool.ExifToolHelper().set_tags(op['save'],
                    {'EXIF:UserComment': json.dumps(json.loads(image_meta))},
                    params=['-overwrite_original', '-preserve'])
            else:
                png_meta = PngInfo()
                png_meta.add_text('parameters', image_meta)
                try:
                    image.save(op['save'], exif=exif, pnginfo=png_meta)
                except Exception as e:
                    click.FileError(f"{op['save']}: {e}")
        return image

    def as_json(self):
        return json.dumps(self.op)


def get_file_params(file:str, verbose=False):
    """load image params from either a JSON file or image metadata"""
    base, ext = os.path.splitext(file)
    if ext.lower() == '.json':
        with open(file, "r") as jfile:
            return json.load(jfile)
    elif ext.lower() in ['.png', '.jpg', '.jpeg']:
        with Image.open(file) as image:
            metadata = image.info
            params = dict()
            if image.format == 'PNG':
                if 'parameters' in metadata:
                    p = metadata["parameters"]
                    if j := json.loads(p):
                        if sui := j["sui_image_params"]:
                            params = sui
                        if verbose:
                            params = j
            elif image.format == 'JPEG':
                metadata = exiftool.ExifToolHelper().get_metadata(file)[0]
                if 'EXIF:UserComment' in metadata:
                    if j := json.loads(metadata['EXIF:UserComment']):
                        if sui := j["sui_image_params"]:
                            params = sui
                        if verbose:
                            params = j
            else:
                print(f"{file}: no SwarmUI metadata found")
        return params
    else:
        print(f"{file}: unknown file type")

# swarmui request format is slightly different from returned metadata
# (array fields: loras, loraweights, lorasectionconfinement)
# 
def _array2str(d:dict, k:str):
    """convert d[k] from list to comma-separated string"""
    if type(d[k]) is list:
        d[k] = ','.join(d[k])
def _str2array(d:dict, k:str):
    """convert d[k] from comma-separated string to list"""
    if type(d[k]) is str:
        d[k] = d[k].split(',')


@click.group()
@click.option('-h', '--host', default='',
    help='server name or IP address')
@click.option('-p', '--port', default='',
    help='port server is listening on')
@click.option('-a', '--aspect', type=str,
    help='aspect ratio as X:Y or as specific XxY pixel resolution')
@click.option('-s', '--sidelength', default='1024/64',
    help='model sidelength as pixels/divisor (default 1024/64)')
@click.option('-f', '--fix-resolution', is_flag=True,
    help='''
        round XxY resolution up to nearest /64, then crop after generating;
        this avoids visual artifacts at image edges for certain models
    ''')
@click.option('-j', '--jpeg-output', is_flag=True,
    help='''
        tell SwarmUI to generate JPG output instead of PNG. This is
        done after any other client-side modifications such as
        --fix-resolution and --unsharp.
    ''')
@click.option('-J', '--jpeg-quality', type=int,
    help='JPEG conversion quality (default 85)')
@click.option('-t', '--template', default='$pre-$set-$seq.$ext',
    help="""
        filename template for generated images (default "$pre-$set-$seq.$ext").
        The following variables are available: pre, set, seq, ext, ymd, hms.
        A template without a $seq variable will generate a fixed filename,
        overwriting it if it already exists.
    """)
@click.option('--pre', default='genai',
    help='template variable "pre"')
@click.option('--set', default='img',
    help='template variable "set"')
@click.option('--seq', default=1,
    help='template variable "seq" initial value (auto-increments)')
@click.option('--pad', default=4,
    help='zero-padding length for "seq" (default 4)')
def cli(host, port, aspect, sidelength, pre, set, seq, pad, template,
    fix_resolution, jpeg_output, jpeg_quality):
    # TODO: process global options here to simplify subcommands;
    # just put them in a convenient global dict
    pass


@cli.command()
@click.option('-m', '--model', type=str,
    help='''
        Case-insensitive unique substring of base model name to render
        images with (use list-models to see what's available on the
        server).
    ''')
@click.option('-l', '--loras', type=str, multiple=True,
    help='''
        Case-insensitive unique substring of LoRA model name to enable
        for rendering. Append ":0.x" to set strength < 1; you can also
        add a second option ":base" or ":refine" to restrict the LoRA
        to that part of the render (e.g. "zelda:0.8:base").
    ''')
@click.option('-r', '--rules', multiple=True,
    help='config-file parameter set (overrides file params)')
@click.option('-p', '--params', multiple=True,
    help='''
        comma-separated list of SwarmUI parameters and values as p=v
        (overrides file params and rules)
    ''')
@click.option('-s', '--save-on-server', is_flag=True,
    help='''
        tell SwarmUI to save the generated images; by default,
        only the downloaded copy will exist.
    ''')
@click.option('-n', '--dry-run', is_flag=True,
    help='just print the arguments that would be used to generate images')
@click.option('-L', '--lut-name', type=str,
    help='''
        Case-insensitive unique substring identifying a LUT to apply
        after rendering; this requires the SwarmUI PostRender
        extension and some .cube files in Models/lut. It can be
        applied at reduced strength by adding ":0.x", as with LoRAs.
        Use list-luts to see what's available.
    ''')
@click.option('-u', '--unsharp-mask', is_flag=True,
    help='apply unsharp mask to images before saving')
@click.option('-U', '--unsharp-params', default='0.65/65/5',
    help='''
        unsharp mask parameters as radius/percentage/threshold
        (default "0.65/65/5").
    ''')
@click.option('-c', '--count-stdin', default=1,
    help='number of incoming lines on STDIN; used only by the progress bar.')
@click.argument('sources', nargs=-1)
@click.pass_context
def gen(ctx, model, loras, params, rules, sources, dry_run, save_on_server, lut_name, unsharp_mask, unsharp_params, count_stdin):
    """
    Generate images with common parameters and different prompts.

    If an argument is a filename, read all metadata from it (accepts PNG,
    JPG, and JSON files) and use as params for generating an image. Note
    that SwarmUI stores metadata in the PNG-specific 'parameters' field,
    and for JPG in the EXIF 'UserComment' field. The JSON format is
    a single dict containing key/value pairs (the same format generated
    by "sui params -j").

    If one or more non-file arguments are passed, use them as separate
    prompts, generatimg one image for each.

    If no arguments are passed, read one-line prompts from STDIN and
    generate one image for each.
    """        

    s = swarmui(
        host=ctx.parent.params['host'],
        port=ctx.parent.params['port']
    )
    s.params = ctx.parent.params
    session_id = s.create_session()
    s.session_id = session_id
    if sources:
        images = list(sources)
    else:
        images = sys.stdin
    seq = s.params['seq']
    outname=None
    with click.progressbar(images, length=count_stdin, item_show_func=lambda a: outname) as bar:
        for image in bar:
            if os.path.isfile(image):
                image_params = get_file_params(image)
                # strip previous-gen's requests, to avoid surprises
                for noise in ['imageformat', 'donotsave']:
                    if noise in image_params:
                        del image_params[noise]
                # store original filename in metadata (transferred to EXIF)
                image_params['personalnote'] = os.path.basename(image)
            else:
                image_params = { "prompt": image.rstrip() }
            if rules:
                for rule_arg in rules:
                    for rule in rule_arg.split(','):
                        image_params = s.merge_params([image_params,
                            s.get_rule_params(rule)])
            if params:
                for param_arg in params:
                    for param in param_arg.split(','):
                        k, v = param.split('=')
                        image_params[k] = v
            if model:
                model_fullname = substring_match(model,
                        [x['name'] for x in s.get_models()],
                        match_type='model')
                image_params['model'] = model_fullname
            if loras:
                if 'loras' not in image_params:
                    image_params['loras'] = list()
                new_loras = list(loras)
                # don't add the same lora twice in re-gens!
                for lora in loras:
                    if ':' in lora:
                        loraname, rest = lora.split(':', 1)
                        if loraname in image_params['loras']:
                            new_loras.remove(lora)
                loras = new_loras
                if 'loraweights' not in image_params:
                    image_params['loraweights'] = list()
                for lora in loras:
                    loraweight = "1"
                    if ':' in lora:
                        lora, loraweight = lora.split(':', 1)
                    lora_fullname = substring_match(lora,
                        [x['name'] for x in s.get_models(type='LoRA')],
                        match_type='LoRA')
                    image_params['loras'].append(lora_fullname)
                    image_params['loraweights'].append(loraweight)
                # lorasectionconfinement is only present if any lora uses it
                # global=0, base=5, refiner=1
                use_confine = False
                if 'lorasectionconfinement' in image_params:
                    ls_confine = list(image_params['lorasectionconfinement'])
                else:
                    ls_confine = list()
                for i,loraweight in enumerate(image_params['loraweights']):
                    if i < len(ls_confine):
                        continue
                    if ':' in loraweight:
                        l_weight, l_section = loraweight.split(':')
                        image_params['loraweights'][i] = l_weight
                        ls_confine.append('5' if l_section == 'base' else '1')
                        use_confine = True
                    else:
                        ls_confine.append('0')
                if use_confine:
                    image_params['lorasectionconfinement'] = ls_confine
            s.unsharp_mask = unsharp_mask
            if '/' in unsharp_params:
                s.um_r, s.um_p, s.um_t = unsharp_params.split('/')
            if lut_name:
                lut_strength = 1.0
                if ':' in lut_name:
                    lut_name, lut_strength = lut_name.split(':')
                match = substring_match(lut_name, s.get_luts(), match_type='LUT')
                image_params['lutname'] = match
                image_params['lutlutstrength'] = lut_strength
                image_params['lutlogspace'] = False
            if s.params['aspect']:
                if s.params['sidelength']:
                    if '/' in s.params['sidelength']:
                        sidelength, rounding = s.params['sidelength'].split('/')
                    else:
                        sidelength = s.params['sidelength']
                        rounding = 64
                    sidelength = int(sidelength)
                elif image_params['sidelength']:
                    sidelength = int(image_params['sidelength'])
                    if image_params['rounding']:
                        rounding = image_params['rounding']
                    else:
                        rounding = 64
                width, height = get_aspect_pixels(s.params['aspect'],
                    side=sidelength, rounding=int(rounding))
                image_params['width'] = width
                image_params['height'] = height
            s.crop = ()
            if 'fix_resolution' in image_params:
                old_w = int(image_params['width'])
                old_h = int(image_params['height'])
                if old_w % 64 > 0:
                    new_w = (old_w // 64 + 1) * 64
                else:
                    new_w = old_w
                if old_h % 64 > 0:
                    new_h = (old_h // 64 + 1) * 64
                else:
                    new_h = old_h
                if new_w > old_w or new_h > old_h:
                    delta_w = (new_w - old_w) // 2;
                    delta_h = (new_h - old_h) // 2;
                    s.crop = (delta_w, delta_h, old_w + delta_w, old_h + delta_h)
                    if 'refinerupscale' in image_params:
                        mul = float(image_params['refinerupscale'])
                        s.crop = tuple([int(mul * i) for i in s.crop])
                    image_params['width'] = new_w
                    image_params['height'] = new_h
            if 'jpeg_output' in s.params and s.params['jpeg_output']:
                ext = 'jpg'
            else:
                ext = 'png'
            outname = format_filename(pre=s.params['pre'],
                set=s.params['set'], pad=s.params['pad'], seq=seq,
                template=ctx.parent.params['template'], ext=ext)
            while os.path.isfile(outname):
                if not re.search(r'\$seq', ctx.parent.params['template']):
                    # prevent infinite loop if no $seq in template
                    break
                seq += 1
                outname = format_filename(pre=s.params['pre'],
                    set=s.params['set'], pad=s.params['pad'], seq=seq,
                    template=ctx.parent.params['template'], ext=ext)
            if dry_run:
                print(f"output file: {outname}")
                print(f"session_id: {session_id}")
                print(json.dumps(image_params, indent=4))
            else:
                image = s.generate_image(image_params, session=session_id,
                    outfile=outname)
            seq += 1

@cli.command()
@click.option('-j', '--json', 'json_output', is_flag=True,
    help='generate JSON output instead of default K=V')
@click.option('-v', '--verbose', is_flag=True,
    help='includes all metadata; implies --json')
@click.option('-p', '--prompt', is_flag=True,
    help='print just the prompt(s), one per line')
@click.argument('files', nargs=-1)
@click.pass_context
def params(ctx, json_output, verbose, prompt, files):
    """dump parameters from JSON, PNG, and JPG files"""
    if verbose:
        json_output = True
    output = list()
    for file in files:
        params = get_file_params(file, verbose)
        if params:
            if prompt:
                print(params['prompt'])
            elif json_output:
                params['_filename'] = file
                output.append(params)
            else:
                print(f'filename={file}')
                for k in params:
                    print(f'{k}={params[k]}')
                if len(files) > 1:
                    print()
    if output:
        if len(output) > 1:
            print(json.dumps(output, sort_keys=True, indent=4))
        else:
            print(json.dumps(output[0], sort_keys=True, indent=4))

@cli.command()
@click.argument('files', nargs=-1)
@click.pass_context
def prompt(ctx, files):
    """shortcut for 'params -p'"""
    for file in files:
        params = get_file_params(file)
        if params:
            print(params['prompt'])

@cli.command()
@click.option('-v', '--verbose', is_flag=True,
    help='print contents of all rules for ~/.sui')
@click.pass_context
def list_rules(ctx, verbose):
    """list all rules defined in ~/.sui or default config"""
    s = swarmui()
    for rule in s.list_rules():
        if verbose:
            print(f"[{rule}]")
            keys = s.get_rule_params(rule)
            for k in keys:
                print(f"{k}={keys[k]}")
            print()
        else:
            print(rule)

@cli.command()
@click.option('-t', '--type', default='base', 
    help='model type (default "base")',
    type=click.Choice(['base', 'lora', 'vae']))
@click.option('-v', '--verbose', is_flag=True,
    help='print more detail about each model')
@click.argument('search', nargs=-1)
@click.pass_context
def list_models(ctx, type, verbose, search):
    """print list of available models"""
    subtype = 'Stable-Diffusion'
    match type:
        case 'lora':
            subtype = 'LoRA'
        case 'vae':
            subtype = 'VAE'
    s = swarmui(
        host=ctx.parent.params['host'],
        port=ctx.parent.params['port']
    )
    s.params = ctx.parent.params
    s.session_id = s.create_session()
    for model in s.get_models(type=subtype):
        found = True
        if search:
            found = False
            for key in ['name', 'architecture', 'compat_class']:
                if key in model and model[key] and search[0].casefold() in model[key].casefold():
                    found = True
        if found:
            if verbose:
                print(model['title'])
                for key in ['name', 'architecture', 'compat_class', 'resolution', 'trigger_phrase']:
                    if key in model and model[key]:
                        print(f'    {key}={model[key]}')
                if 'description' in model and model['description']:
                    url = re.search('(https://civitai.com/[^"]+)(?:")',
                        model['description'])
                    if url:
                        print(f'    url={url.group(1)}')
                    
            else:
                print(os.path.splitext(model['name'])[0])

@cli.command()
@click.argument('search', nargs=-1)
@click.pass_context
def list_luts(ctx, search):
    """print list of available LUTs"""
    s = swarmui(
        host=ctx.parent.params['host'],
        port=ctx.parent.params['port']
    )
    s.params = ctx.parent.params
    s.session_id = s.create_session()
    if search:
        for lut in s.get_luts():
            if search[0].casefold() in lut.casefold():
                print(lut)
    else:
        for lut in s.get_luts():
            print(lut)

@cli.command()
@click.option('-n', '--dry-run', is_flag=True,
    help='just print the before/after filenames')
@click.argument('files', nargs=-1)
@click.pass_context
# TODO: add -j support to convert all to JPEG
def rename(ctx, dry_run, files):
    """
    rename files to use a consistent format based on --pre|set|seq;
    preserves existing file extension.
    """
    params = ctx.parent.params
    seq = params['seq']
    for file in files:
        base, ext = os.path.splitext(file)
        ext = ext.removeprefix('.')
        outname = format_filename(pre=params['pre'],
            set=params['set'], pad=params['pad'], seq=seq, ext=ext,
            template=ctx.parent.params['template'])
        if dry_run:
            print(file, outname)
        else:
            try:
                os.rename(file, outname)
            except Exception as e:
                click.FileError(f"rename '{file}' to '{outname}': {e}")
        seq += 1


@cli.command()
@click.option('-n', '--dry-run', is_flag=True,
    help='just print the before/after filenames')
@click.option('-r', '--resize', default=100,
    help='percentage to resize image to (default: no change)')
@click.argument('files', nargs=-1)
@click.pass_context
def jpg(ctx, dry_run, resize, files):
    """convert PNG files to JPG, preserving metadata and optionally resizing"""
    for file in files:
        if os.path.isfile(file):
            params = json.dumps(get_file_params(file, True))
            with Image.open(file) as image:
                base, ext = os.path.splitext(file)
                outname = f"{base}.jpg"
                ops = dict()
                if resize < 100:
                    ops['size'] = resize
                if dry_run:
                    print(file, outname)
                else:
                    ops['meta'] = params
                    ops['jpg'] = True
                    ops['save'] = outname
                    process(ops).apply(image)


@cli.command()
@click.pass_context
def status(ctx):
    "return server/backend status"
    s = swarmui(
        host=ctx.parent.params['host'],
        port=ctx.parent.params['port']
    )
    session_id = s.create_session()
    response = s._post("/API/GetCurrentStatus",
        params={'session_id': session_id})
    print(json.dumps(response['status'], indent=4))
    print(json.dumps(response['backend_status'], indent=4))

def substring_match(item:str, match_list:list, /, match_type='match'):
    """
    do a case-sensitive substring match of a list, returning a single
    match, and exiting with an error for multiple or zero matches
    """
    matches = [x for x in match_list if item.casefold() in x.casefold()]
    if len(matches) > 1:
        raise click.UsageError(f"Error: ambiguous {match_type} '{item}', matches:\n  {'\n  '.join(matches)}")
    elif len(matches) == 0:
        raise click.UsageError(f"Error: {match_type} '{item}' not found on server")
    return matches[0]


def format_filename(*, pre="swarmui", set="img", seq=1,
    pad=4, ext="png", template:str):
    """return a consistently-formatted filename for a sequenced image"""
    if template:
        if not re.search(r'\..+$', template):
            template += '.$ext'
        now = datetime.now()
        # TODO: add more filename-formatting variables
        return Template(template).safe_substitute({
            'pre': pre,
            'set': set,
            'seq': str(seq).zfill(pad),
            'ext': ext,
            'ymd': now.strftime('%Y%m%d'),
            'hms': now.strftime('%H%M%S')
        })
    else:
        return f"{pre}-{set}-{seq}.{ext}"


def get_aspect_pixels(ratio:str, *, side=1024, rounding=64):
    """calculate best XxY-pixel approximation for aspect ratio"""
    if 'x' in ratio:
        # user requested specific width x height
        width, height = [int(x) for x in ratio.split('x')]
        return width, height
    elif ':' not in ratio:
        a_w = 1.0
        a_h = 1.0
    else:
        a_w, a_h = [float(x) for x in ratio.split(':')]
    scale = math.sqrt(side * side / (a_w * a_h))
    ideal_w = a_w * scale
    ideal_h = a_h * scale
    width = int(ideal_w) - (int(ideal_w) % rounding)
    height = int(ideal_h) - (int(ideal_h) % rounding)
    while width * height > side * side and width > 0 and height > 0:
        if width >= height:
            width -= rounding
        else:
            height -= rounding
    return width, height


if __name__ == '__main__':
    cli()
