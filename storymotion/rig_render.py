from .account_packs import capability
"""Original neutral full-body rig shared by local frame-based render engines.

Manual mouth labels are visual poses, not a universal phoneme map. This module
never reads audio, infers articulation, or grants phonetic/human acceptance.
"""
import html
import hashlib
import os
import stat
import json
import math
import re
from pathlib import Path

from .security import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
MOUTHS = tuple('ABCDEFGHX')
PAINTS = ('background', 'ink', 'accent', 'muted')
MODES = {'inset': {'x': 850, 'y': 960, 'scale': .55}, 'serial-courier': {'x': 245, 'y': 785, 'scale': 1}}
NUMERIC = {'path': (), 'circle': ('cx', 'cy', 'r'), 'ellipse': ('cx', 'cy', 'rx', 'ry'),
           'rect': ('x', 'y', 'width', 'height', 'rx'), 'line': ('x1', 'y1', 'x2', 'y2')}


def _exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WorkflowError('Invalid neutral rig fields')


def _number(value, low, high):
    if type(value) not in (int, float):
        raise WorkflowError('Invalid neutral rig number')
    try:
        if not math.isfinite(value) or not low <= value <= high:
            raise WorkflowError('Invalid neutral rig number')
    except OverflowError:
        raise WorkflowError('Invalid neutral rig number') from None
    return value


def _n(value):
    result = format(value, '.10f').rstrip('0').rstrip('.')
    return '0' if result in ('', '-0') else result


def _spec(spec):
    if (not isinstance(spec, dict) or spec.get('rig_id') != 'neutral-presenter-1'
            or not capability(spec.get('account'), 'rig_mode')
            or type(spec.get('fps')) is not int or spec['fps'] != 30):
        raise WorkflowError('Unsupported neutral rig spec')
    duration = _number(spec.get('audio_duration_seconds'), 1, 90)
    timeline = _number(spec.get('timeline_duration_seconds'), duration, 90)
    cues = spec.get('mouthCues')
    if not isinstance(cues, list) or not 1 <= len(cues) <= 2000:
        raise WorkflowError('Invalid rig mouth cues')
    end = 0
    for cue in cues:
        _exact(cue, ('start', 'end', 'value'))
        start, stop = _number(cue['start'], 0, duration), _number(cue['end'], 0, duration)
        if start >= stop or start != end or cue['value'] not in MOUTHS:
            raise WorkflowError('Invalid rig mouth range')
        end = stop
    if end != duration:
        raise WorkflowError('Rig mouth cues must cover actual audio')
    tracks = spec.get('visual_tracks')
    _exact(tracks, ('blinks', 'head'))
    if not isinstance(tracks['blinks'], list) or len(tracks['blinks']) > 80 or not isinstance(tracks['head'], list) or not 2 <= len(tracks['head']) <= 1000:
        raise WorkflowError('Invalid rig tracks')
    end = 0
    for blink in tracks['blinks']:
        _exact(blink, ('start', 'end'))
        start, stop = _number(blink['start'], end, timeline), _number(blink['end'], 0, timeline)
        if start >= stop:
            raise WorkflowError('Invalid blink interval')
        end = stop
    end = -1
    for head in tracks['head']:
        _exact(head, ('time', 'rotate', 'x', 'y'))
        time = _number(head['time'], 0, timeline)
        if time <= end:
            raise WorkflowError('Head keys must increase')
        _number(head['rotate'], -8, 8); _number(head['x'], -12, 12); _number(head['y'], -12, 12)
        end = time
    if tracks['head'][0]['time'] != 0 or end != timeline:
        raise WorkflowError('Head keys must cover the timeline')
    return spec


def sample_rig(spec, seconds):
    """Pure Python oracle matching sampleRig, including half-open frame cues."""
    _spec(spec)
    _number(seconds, -1e12, 1e12)
    frame = max(0, math.floor(seconds * 30 + 1e-7))
    time = frame / 30
    value = 'X'
    if time < spec['audio_duration_seconds']:
        value = next((c['value'] for c in spec['mouthCues'] if c['start'] <= time < c['end']), 'X')
    blink = any(b['start'] <= time < b['end'] for b in spec['visual_tracks']['blinks'])
    time = min(time, spec['timeline_duration_seconds'])
    keys = spec['visual_tracks']['head']; before, after = keys[0], keys[-1]
    for i in range(1, len(keys)):
        if time <= keys[i]['time']:
            before, after = keys[i-1], keys[i]
            break
        before = keys[i]
    p = 0 if after['time'] == before['time'] else min(1, max(0, (time-before['time'])/(after['time']-before['time'])))
    head = {k: before[k] + (after[k]-before[k])*p for k in ('rotate', 'x', 'y')}
    return {'frame': frame, 'value': value, 'blink': blink, 'head': head}


def _palette(palette):
    if not isinstance(palette, dict) or any(not isinstance(palette.get(k), str) or not re.fullmatch('#[a-fA-F0-9]{6}', palette[k]) for k in PAINTS):
        raise WorkflowError('Invalid neutral rig palette')


def _primitives(rows, palette):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise WorkflowError('Invalid rig geometry list')
    parts = []
    for shape in rows:
        _exact(shape, ('tag', 'attrs'))
        tag, attrs = shape['tag'], shape['attrs']
        if not isinstance(tag, str) or tag not in NUMERIC or not isinstance(attrs, dict) or len(attrs) > 16:
            raise WorkflowError('Unsupported rig primitive')
        for key, value in attrs.items():
            if key == 'd' and tag == 'path':
                if not isinstance(value, str) or not 1 <= len(value) <= 1000 or not re.fullmatch('[MmLlHhVvCcSsQqTtAaZz0-9eE+., \\-]+', value):
                    raise WorkflowError('Invalid rig path')
            elif key in ('fill', 'stroke'):
                if value not in (*PAINTS, 'none'):
                    raise WorkflowError('Invalid rig paint')
            elif key == 'stroke-linecap':
                if value not in ('butt', 'round', 'square'):
                    raise WorkflowError('Invalid rig cap')
            elif key == 'stroke-linejoin':
                if value not in ('round', 'miter', 'bevel'):
                    raise WorkflowError('Invalid rig join')
            elif key in (*NUMERIC[tag], 'stroke-width'):
                _number(value, -1000, 1000)
                if key in ('r', 'rx', 'ry', 'width', 'height', 'stroke-width') and value < 0:
                    raise WorkflowError('Invalid rig dimension')
            else:
                raise WorkflowError('Unsupported rig attribute')
        if tag == 'path' and 'd' not in attrs:
            raise WorkflowError('Rig path missing')
        rendered = []
        for key, value in attrs.items():
            if key in ('fill', 'stroke') and value != 'none':
                value = palette[value]
            elif type(value) in (int, float):
                value = _n(value)
            rendered.append(key + '="' + html.escape(str(value), quote=True) + '"')
        parts.append('<' + tag + ' ' + ' '.join(rendered) + '/>')
    return ''.join(parts)


def rig_svg(definition, palette, state, mode='inset'):
    """Shared descriptor -> full1920px SVG. No customer SVG/URL/script inputs."""
    _exact(definition, ('schema_version', 'rig_id', 'license', 'coordinate_system', 'modes', 'body', 'head', 'eyes', 'mouths'))
    if definition['schema_version'] != 1 or type(definition['schema_version']) is not int or definition['rig_id'] != 'neutral-presenter-1' or definition['license'] != 'original_project_vectors':
        raise WorkflowError('Unsupported rig definition')
    _exact(definition['coordinate_system'], ('width', 'height', 'neck'))
    _exact(definition['modes'], MODES)
    for placement in definition['modes'].values():
        _exact(placement, ('x', 'y', 'scale'))
        for number in placement.values():
            _number(number, -1000, 1000)
    coords = definition['coordinate_system']
    if type(coords['width']) is not int or type(coords['height']) is not int or not isinstance(coords['neck'], list) or len(coords['neck']) != 2 or any(type(v) is not int for v in coords['neck']):
        raise WorkflowError('Unsupported rig coordinate types')
    if coords != {'width': 1080, 'height': 1920, 'neck': [0, 80]} or definition['modes'] != MODES or not isinstance(mode, str) or mode not in MODES:
        raise WorkflowError('Unsupported rig coordinate system or placement')
    _palette(palette)
    if not isinstance(state, dict) or state.get('value') not in MOUTHS or type(state.get('blink')) is not bool or not isinstance(state.get('head'), dict):
        raise WorkflowError('Invalid rig state')
    head = state['head']
    _exact(head, ('rotate', 'x', 'y'))
    _number(head['rotate'], -8, 8); _number(head['x'], -12, 12); _number(head['y'], -12, 12)
    _exact(definition['eyes'], ('open', 'closed')); _exact(definition['mouths'], MOUTHS)
    body, face = _primitives(definition['body'], palette), _primitives(definition['head'], palette)
    mouth_markup = ''
    for value in MOUTHS:
        mouth = definition['mouths'][value]
        _exact(mouth, ('label', 'shapes'))
        if not isinstance(mouth['label'], str) or len(mouth['label']) > 200:
            raise WorkflowError('Invalid rig mouth description')
        mouth_markup += '<g id="neutral-rig-mouth-' + value + '" opacity="' + ('1' if value == state['value'] else '0') + '">' + _primitives(mouth['shapes'], palette) + '</g>'
    pos = definition['modes'][mode]
    transform = f'translate({_n(head["x"])} {_n(head["y"])}) translate(0 80) rotate({_n(head["rotate"])}) translate(0 -80)'
    return ('<svg id="neutral-rig-layer" class="neutral-rig" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" style="position:absolute;inset:0;width:1080px;height:1920px;pointer-events:none" aria-label="Özgün nötr karakter; elle hizalanmış görsel prova">'
            f'<g id="neutral-rig-placement" transform="translate({_n(pos["x"])} {_n(pos["y"])}) scale({_n(pos["scale"])})"><g id="neutral-rig-body">' + body + '</g>'
            f'<g id="neutral-rig-head" transform="{transform}">' + face + '<g id="neutral-rig-eyes-open" opacity="' + ('0' if state['blink'] else '1') + '">' + _primitives(definition['eyes']['open'], palette) + '</g>'
            '<g id="neutral-rig-eyes-closed" opacity="' + ('1' if state['blink'] else '0') + '">' + _primitives(definition['eyes']['closed'], palette) + '</g>' + mouth_markup + '</g></g></svg>')


def _definition(spec):
    from .viseme import rig_descriptor
    descriptor = rig_descriptor(ROOT)
    if spec.get('rig_sha256') != descriptor['sha256']:
        raise WorkflowError('Pinned neutral rig definition changed')
    path = ROOT / descriptor['file']
    try:
        for part in (path, *path.parents):
            if part.is_symlink():
                raise WorkflowError('Pinned neutral rig definition path changed')
        if os.name=='nt':
            from .windows_native import read
            raw=read(ROOT,descriptor['file'],65_536)
            if hashlib.sha256(raw).hexdigest()!=descriptor['sha256']:raise WorkflowError('Pinned neutral rig definition changed')
        else:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise WorkflowError('Pinned neutral rig definition must be a regular file')
                raw = stream.read(65_537)
                after = os.fstat(stream.fileno())
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise WorkflowError('Pinned neutral rig definition path changed')
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or len(raw) > 65_536 or hashlib.sha256(raw).hexdigest() != descriptor['sha256']):
                raise WorkflowError('Pinned neutral rig definition changed during read')
        return json.loads(raw)
    except (OSError, ValueError):
        raise WorkflowError('Pinned neutral rig definition unavailable') from None


def hf_markup(spec, palette):
    """Stable fullSVG with all9mouth/2eye groups; timeline controls visibility."""
    _spec(spec)
    return rig_svg(_definition(spec), palette, {'value': 'X', 'blink': False, 'head': {'rotate': 0, 'x': 0, 'y': 0}},
                   capability(spec['account'], 'rig_mode'))


def hf_program(spec):
    """Append explicit discrete frame-state sets and linear head tweens to tl.

    Native frames use times f/30. No callback/onUpdate is needed on suppressed
    seeks. Continuous head tween interpolation agrees at those native frames;
    mouth/eye transitions are quantized to the same frame timestamp convention.
    """
    _spec(spec)
    _definition(spec)
    initial = sample_rig(spec, 0)
    # GSAP may skip rendering an unchanged totalTime(0) on the first seek.
    # Establish the same frame-zero state immediately and also keep timeline
    # sets at zero so reverse/suppressed seeks restore it deterministically.
    all_mouths = ','.join('#neutral-rig-mouth-' + m for m in MOUTHS)
    first_head = spec['visual_tracks']['head'][0]
    setup = [(all_mouths, {'opacity': 0}), ('#neutral-rig-mouth-' + initial['value'], {'opacity': 1}),
             ('#neutral-rig-eyes-open', {'opacity': 0 if initial['blink'] else 1}),
             ('#neutral-rig-eyes-closed', {'opacity': 1 if initial['blink'] else 0}),
             ('#neutral-rig-head', {'x': first_head['x'], 'y': first_head['y'], 'rotation': first_head['rotate'], 'svgOrigin': '0 80'})]
    commands = ['gsap.set(' + json.dumps(selector) + ',' + json.dumps(values, separators=(',', ':')) + ');' for selector, values in setup]
    def set_at(selector, values, time):
        commands.append('tl.set(' + json.dumps(selector) + ',' + json.dumps(values, separators=(',', ':')) + ',' + _n(time) + ');')
    previous = None
    count = math.ceil(spec['timeline_duration_seconds'] * 30 - 1e-8)
    for frame in range(count + 1):
        state = sample_rig(spec, frame / 30)
        discrete = (state['value'], state['blink'])
        if discrete != previous:
            time = frame / 30
            # One write per target per boundary: overlapping hide-all/show-one
            # zero-duration tweens can revert each other on a reverse seek.
            for mouth in MOUTHS:
                set_at('#neutral-rig-mouth-' + mouth, {'opacity': 1 if mouth == state['value'] else 0}, time)
            set_at('#neutral-rig-eyes-open', {'opacity': 0 if state['blink'] else 1}, time)
            set_at('#neutral-rig-eyes-closed', {'opacity': 1 if state['blink'] else 0}, time)
            previous = discrete
    keys = spec['visual_tracks']['head']
    first = keys[0]
    set_at('#neutral-rig-head', {'x': first['x'], 'y': first['y'], 'rotation': first['rotate'], 'svgOrigin': '0 80'}, 0)
    for before, after in zip(keys, keys[1:]):
        a = {'x': before['x'], 'y': before['y'], 'rotation': before['rotate'], 'svgOrigin': '0 80'}
        b = {'x': after['x'], 'y': after['y'], 'rotation': after['rotate'], 'svgOrigin': '0 80', 'duration': after['time'] - before['time'], 'ease': 'none', 'immediateRender': False}
        commands.append('tl.fromTo("#neutral-rig-head",' + json.dumps(a, separators=(',', ':')) + ',' + json.dumps(b, separators=(',', ':')) + ',' + _n(before['time']) + ');')
    return ''.join(commands)
