from .account_packs import capability
"""Fresh, explicitly supplied mouth/visual annotations for an owned neutral rig.

No media is read, no phoneme extractor runs, and amplitude is never interpreted
as a phoneme. Annotation provenance is an operator attestation, not acoustic or
perceptual truth. Human phonetic and visual acceptance always remain pending.
"""
import copy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import unicodedata

from .audio_retime import script_sha
from .security import WorkflowError, canonical, digest, scan_bytes

ROOT = Path(__file__).resolve().parents[1]
RIG_ID = 'neutral-presenter-1'
RIG_FILE = 'renderers/neutral-rig.json'
MOUTH_VALUES = frozenset('ABCDEFGHX')
MAX_SPEC_BYTES = 110_000
MAX_DESCRIPTOR_BYTES = 65_536
FIELDS = {'schema_version', 'account', 'rig_id', 'rig_sha256', 'source_audio_sha256',
          'source_script_sha256', 'source_timing_sha256', 'audio_duration_seconds',
          'timeline_duration_seconds', 'fps', 'provenance', 'mouthCues', 'visual_tracks'}
PROVENANCE_FIELDS = {'method', 'tool', 'note', 'approved_by', 'rights_confirmed', 'human_phonetic', 'human_visual'}


def _fail(message='Invalid manual rig/viseme contract'):
    raise WorkflowError(message)


def _exact(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        _fail('Manual rig fields are missing or unsupported')


def _number(value, minimum, maximum):
    if type(value) not in (int, float):
        _fail('Rig timing and motion values must be finite numbers')
    try:
        number = float(value)
    except (OverflowError, ValueError):
        _fail('Rig timing and motion values must be finite numbers')
    if not math.isfinite(number) or not minimum <= number <= maximum:
        _fail('Rig timing or motion escapes its bounded range')
    return number


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        _fail('Exact lowercase SHA256 rig/source bindings are required')
    return value


def _text(value, maximum):
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum
            or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in value)):
        _fail('Bounded plain annotation provenance text is required')
    return unicodedata.normalize('NFC', value.strip())


def _json_bytes(value, limit):
    try:
        raw = canonical(value).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        _fail('Rig annotations must be bounded finite JSON')
    if len(raw) > limit or scan_bytes(raw):
        _fail('Rig annotations exceed their JSON boundary or contain a possible credential')
    return raw


def rig_descriptor(root=None):
    """Hash only the fixed, local, nonsymlink neutral descriptor; never a URL.

    The renderer owns the full vector-schema validator. This boundary checks its
    fixed identity/license/mouth vocabulary and returns no executable content.
    """
    try:
        selected = Path(ROOT if root is None else root)
        if '..' in selected.parts:
            _fail('Pinned neutral rig descriptor root cannot traverse parents')
        base = Path(os.path.abspath(selected))
        path = base / RIG_FILE
        for component in [*reversed(path.parents), path]:
            if stat.S_ISLNK(component.lstat().st_mode):
                _fail('Neutral rig descriptor paths must not contain symlinks')
        if not stat.S_ISDIR(base.lstat().st_mode):
            _fail('Pinned neutral rig directory is unavailable')
        if os.name=='nt':
            from .windows_native import read
            raw=read(base,RIG_FILE,MAX_DESCRIPTOR_BYTES)
        else:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    _fail('Pinned neutral rig descriptor must be an ordinary file')
                raw = stream.read(MAX_DESCRIPTOR_BYTES + 1)
                after = os.fstat(stream.fileno())
            current = path.lstat()
            if (not raw or len(raw) > MAX_DESCRIPTOR_BYTES or stat.S_ISLNK(current.st_mode) or
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or
                    (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                _fail('Pinned neutral rig descriptor changed during inspection')
            for component in [*reversed(path.parents), path]:
                if stat.S_ISLNK(component.lstat().st_mode):
                    _fail('Neutral rig descriptor paths must not contain symlinks')
        def unique(pairs):
            value = {}
            for name, item in pairs:
                if name in value:
                    _fail('Duplicate neutral rig descriptor property')
                value[name] = item
            return value
        data = json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: _fail('Neutral rig descriptor must be finite JSON'))
        _json_bytes(data, MAX_DESCRIPTOR_BYTES)
        if (not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or
                data.get('rig_id') != RIG_ID or data.get('license') != 'original_project_vectors' or
                not isinstance(data.get('mouths'), dict) or set(data['mouths']) != MOUTH_VALUES):
            _fail('Pinned original neutral rig identity or mouth vocabulary changed')
        return {'schema_version': 1, 'rig_id': RIG_ID, 'sha256': hashlib.sha256(raw).hexdigest(),
                'file': RIG_FILE, 'license': data['license']}
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise WorkflowError('Pinned neutral rig descriptor missing or invalid; inspect the fixed local rig asset') from None


def validate_rig(spec, brief, root=None):
    """Normalize manual/external annotations bound to the exact current audio.

    Callers must separately validate the measured host brief and decode its audio.
    No old timing, amplitude heuristic, self-certified human pass or automatic
    phoneme/viseme inference is accepted here. Mouth timestamps need not land on
    video frames: their exact audio-second boundaries are sampled at fixed30fps.
    """
    _exact(spec, FIELDS)
    _json_bytes(spec, MAX_SPEC_BYTES)
    if (type(spec['schema_version']) is not int or spec['schema_version'] != 1 or
            type(spec['fps']) is not int or spec['fps'] != 30):
        _fail('Manual rig schema1 and exact integer30fps are required')
    if (not isinstance(brief, dict) or not isinstance(brief.get('brand'), str) or not capability(brief['brand'], 'rig_mode') or
            spec['account'] != brief['brand']):
        _fail('Neutral rig is an explicit opt-in for only technology or serial story profiles')
    descriptor = rig_descriptor(root)
    if spec['rig_id'] != RIG_ID or _hash(spec['rig_sha256']) != descriptor['sha256']:
        _fail('Manual rig descriptor binding changed')
    audio, timing, script = brief.get('audio'), brief.get('audio_timing'), brief.get('script')
    if not isinstance(audio, dict) or not isinstance(timing, dict) or not isinstance(script, str) or not script.strip():
        _fail('Current host audio, exact script and measured timing are required')
    audio_hash, script_hash = _hash(audio.get('sha256')), script_sha(script)
    _json_bytes(timing, 2_000_000)
    timing_hash = digest(timing)
    if (timing.get('source_audio_sha256') != audio_hash or timing.get('source_script_sha256') != script_hash or
            _hash(spec['source_audio_sha256']) != audio_hash or _hash(spec['source_script_sha256']) != script_hash or
            _hash(spec['source_timing_sha256']) != timing_hash):
        _fail('Audio, script or timing revision changed; fresh annotations are required')
    audio_duration = _number(timing.get('audio_duration_seconds'), 1, 90)
    timeline_duration = _number(timing.get('timeline_duration_seconds'), 1, 90)
    if (audio_duration > timeline_duration or _number(brief.get('duration'), 1, 90) != timeline_duration or
            _number(spec['audio_duration_seconds'], 1, 90) != audio_duration or
            _number(spec['timeline_duration_seconds'], 1, 90) != timeline_duration):
        _fail('Annotations must bind exact measured audio and timeline durations')
    result = copy.deepcopy(spec)
    result.update(audio_duration_seconds=audio_duration, timeline_duration_seconds=timeline_duration)
    provenance = spec['provenance']
    _exact(provenance, PROVENANCE_FIELDS)
    if (not isinstance(provenance['method'], str) or provenance['method'] not in
            {'manual_annotation', 'external_phoneme_export', 'synthetic_test'} or
            provenance['rights_confirmed'] is not True or provenance['human_phonetic'] != 'pending' or
            provenance['human_visual'] != 'pending'):
        _fail('Explicit annotation rights and pending human phonetic/visual acceptance are required')
    result['provenance'] = {**provenance, 'tool': _text(provenance['tool'], 120),
                            'note': _text(provenance['note'], 1000), 'approved_by': _text(provenance['approved_by'], 200)}
    cues = spec['mouthCues']
    if not isinstance(cues, list) or not 1 <= len(cues) <= 2000:
        _fail('One to2000 explicit mouth intervals must cover the measured audio')
    last = 0.0
    normalized = []
    for cue in cues:
        _exact(cue, {'start', 'end', 'value'})
        start, end = _number(cue['start'], 0, audio_duration), _number(cue['end'], 0, audio_duration)
        if start != last or end <= start or not isinstance(cue['value'], str) or cue['value'] not in MOUTH_VALUES:
            _fail('Mouth intervals must be contiguous, positive and ordered; X explicitly denotes a pause')
        normalized.append({'start': start, 'end': end, 'value': cue['value']})
        last = end
    if last != audio_duration:
        _fail('Mouth intervals must cover0 through the exact measured audio duration')
    result['mouthCues'] = normalized
    tracks = spec['visual_tracks']
    _exact(tracks, {'blinks', 'head'})
    blinks = tracks['blinks']
    if not isinstance(blinks, list) or len(blinks) > 80:
        _fail('At most80 explicit non-overlapping blinks are allowed')
    normalized_blinks, last = [], 0.0
    for blink in blinks:
        _exact(blink, {'start', 'end'})
        start, end = _number(blink['start'], 0, timeline_duration), _number(blink['end'], 0, timeline_duration)
        # Decimal spellings preserve inclusive .04/.4 bounds without a permissive
        # timestamp tolerance or floating subtraction rejecting e.g .24-.2.
        length = Decimal(str(end)) - Decimal(str(start))
        if start < last or not Decimal('.04') <= length <= Decimal('.4'):
            _fail('Blinks must be ordered, non-overlapping and last0.04 through0.4seconds')
        normalized_blinks.append({'start': start, 'end': end})
        last = end
    head = tracks['head']
    if not isinstance(head, list) or not 2 <= len(head) <= 1000:
        _fail('Two to1000 explicit linear head keyframes are required')
    normalized_head, last = [], -1.0
    for point in head:
        _exact(point, {'time', 'rotate', 'x', 'y'})
        time = _number(point['time'], 0, timeline_duration)
        if time <= last:
            _fail('Head keyframe timestamps must strictly increase')
        normalized_head.append({'time': time, 'rotate': _number(point['rotate'], -8, 8),
                                'x': _number(point['x'], -12, 12), 'y': _number(point['y'], -12, 12)})
        last = time
    if normalized_head[0]['time'] != 0 or last != timeline_duration:
        _fail('Head keyframes must cover0 through the exact timeline duration')
    result['visual_tracks'] = {'blinks': normalized_blinks, 'head': normalized_head}
    _json_bytes(result, MAX_SPEC_BYTES)
    return result
