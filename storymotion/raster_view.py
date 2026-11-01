from .account_packs import capability
"""Pure host-owned raster annotation contract and deterministic scene compiler.

This module never opens an asset or executes customer markup. The IO boundary
normalizes the source into a pinned local PNG; this contract describes only its
crop, annotation and bounded camera treatment.
"""
import copy
import html
import re
import unicodedata

from .security import WorkflowError, finite


_RECIPE = 'customer-raster-annotation-1'
_ASSET_FIELDS = {'file', 'sha256', 'source_sha256', 'width', 'height',
                 'container', 'approved_by', 'rights_note', 'rights_confirmed'}
_VIEW_FIELDS = {'scene_id', 'crop', 'highlight', 'label', 'camera'}
_RECT_FIELDS = {'x', 'y', 'width', 'height'}
_CAMERAS = {'locked', 'push-in', 'follow-object'}
_HASH = re.compile(r'[0-9a-f]{64}')
_ID = re.compile(r'[a-z][a-z0-9-]{0,63}')
_IDENT = re.compile(r'[a-z][a-z0-9-]{0,39}')
_COLOR = re.compile(r'#[0-9a-fA-F]{6}')
_URL = re.compile(r'(?i)(?:[a-z][a-z0-9+.-]*://|\bwww\.|\b(?:javascript|data|file|vbscript):|\b[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:\b|/))')
_CODE = re.compile(r'(?i)(?:[<>`{}\[\];\\]|=>|\b(?:eval|alert|function|fetch|document|window|onload|onclick)\s*[=(.])')


def _exact(value, fields, message):
    if not isinstance(value, dict) or set(value) != fields:
        raise WorkflowError(message)


def _text(value, minimum, maximum, message):
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum
            or (minimum and not value.strip())):
        raise WorkflowError(message)
    return value


def _asset(asset):
    _exact(asset, _ASSET_FIELDS, 'Invalid raster asset fields')
    if asset['file'] != 'raster/image.png' or asset['container'] != 'png':
        raise WorkflowError('Raster asset must be the normalized local PNG')
    for name in ('sha256', 'source_sha256'):
        if not isinstance(asset[name], str) or not _HASH.fullmatch(asset[name]):
            raise WorkflowError('Invalid raster asset hash')
    for name in ('width', 'height'):
        if type(asset[name]) is not int or not 64 <= asset[name] <= 4096:
            raise WorkflowError('Invalid raster image dimensions')
    if asset['width'] * asset['height'] > 12_000_000:
        raise WorkflowError('Raster image exceeds pixel limit')
    _text(asset['approved_by'], 1, 200, 'Raster approval identity is required')
    _text(asset['rights_note'], 1, 1000, 'Raster rights note is required')
    if asset['rights_confirmed'] is not True:
        raise WorkflowError('Raster rights confirmation is required')


def _rect(value, minimum, name):
    _exact(value, _RECT_FIELDS, 'Invalid raster ' + name + ' fields')
    for key in ('x', 'y'):
        finite(value[key], 'raster ' + name + ' ' + key, 0, 1)
    for key in ('width', 'height'):
        finite(value[key], 'raster ' + name + ' ' + key, minimum, 1)
    if value['x'] + value['width'] > 1 or value['y'] + value['height'] > 1:
        raise WorkflowError('Raster rectangle exceeds normalized image')


def _view(view, scene):
    _exact(view, _VIEW_FIELDS, 'Invalid raster view fields')
    scene_id = scene.get('id')
    if not isinstance(scene_id, str) or not _ID.fullmatch(scene_id) or view['scene_id'] != scene_id:
        raise WorkflowError('Raster view does not match its source scene')
    _rect(view['crop'], .05, 'crop')
    if view['highlight'] is not None:
        _rect(view['highlight'], .01, 'highlight')
        c, h = view['crop'], view['highlight']
        if (h['x'] < c['x'] or h['y'] < c['y']
                or h['x'] + h['width'] > c['x'] + c['width']
                or h['y'] + h['height'] > c['y'] + c['height']):
            raise WorkflowError('Raster highlight must be inside the crop')
    label = _text(view['label'], 0, 50, 'Invalid raster label length')
    if (any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in label)
            or _URL.search(label) or _CODE.search(label)):
        raise WorkflowError('Raster label must be plain text without code or URLs')
    if (not isinstance(view['camera'], str) or view['camera'] not in _CAMERAS
            or view['camera'] != scene.get('camera')):
        raise WorkflowError('Raster camera does not match its source scene')
    start = finite(scene.get('start'), 'raster scene start', 0, 86_400)
    end = finite(scene.get('end'), 'raster scene end', 0, 86_400)
    if end - start < 1.6:
        raise WorkflowError('Raster scene must be at least 1.6 seconds')


def validate_raster(value, brief):
    """Validate an exact raster recipe against source scenes, without IO.

    The result is an independent copy. Approval/rights statements are explicit
    operator declarations, not an automated license or human QA acceptance.
    """
    if (not isinstance(brief, dict) or not capability(brief.get('brand'), 'raster')
            or not isinstance(brief.get('creative'), dict) or not brief['creative']):
        raise WorkflowError('Raster annotation requires the raster-capable creative brief')
    _exact(value, {'schema_version', 'recipe', 'asset', 'views'}, 'Invalid raster recipe fields')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['recipe'] != _RECIPE:
        raise WorkflowError('Unsupported raster recipe version')
    _asset(value['asset'])
    scenes = brief.get('scenes')
    if not isinstance(scenes, list) or not scenes or not all(isinstance(s, dict) for s in scenes):
        raise WorkflowError('Raster annotation requires source scenes')
    if not isinstance(value['views'], list) or len(value['views']) != len(scenes):
        raise WorkflowError('Raster views must cover every source scene once')
    ids = [s.get('id') for s in scenes]
    if any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise WorkflowError('Raster source scene IDs must be unique')
    for view, scene in zip(value['views'], scenes):
        _view(view, scene)
    return copy.deepcopy(value)


def _n(number):
    # Rounded fixed decimal output is reproducible and contains no exponent or
    # negative zero. Source geometry remains in the real image coordinate space.
    return format(float(number), '.8f').rstrip('0').rstrip('.') or '0'


def _pixels(rect, asset):
    return {key: rect[key] * asset['width' if key in {'x', 'width'} else 'height'] for key in _RECT_FIELDS}


def compile_view(scene, view, asset, profile, ident):
    """Compile trusted raster-only SVG and host set/tween motion operations.

    The fixed outer clip survives camera transforms. Crop and highlight use
    source-pixel coordinates inside the nested SVG; the image itself is never
    moved or deformed. Only the camera wrapper and annotation can animate.
    """
    if not isinstance(scene, dict):
        raise WorkflowError('Invalid raster source scene')
    _asset(asset)
    _view(view, scene)
    if (not isinstance(profile, dict) or not capability(profile.get('id'), 'raster')
            or not isinstance(ident, str) or not _IDENT.fullmatch(ident)):
        raise WorkflowError('Invalid raster compiler profile or identifier')
    palette = profile.get('palette')
    if not isinstance(palette, dict) or any(not isinstance(palette.get(k), str) or not _COLOR.fullmatch(palette[k]) for k in ('background', 'ink', 'accent')):
        raise WorkflowError('Invalid raster compiler palette')
    crop = _pixels(view['crop'], asset)
    box = ' '.join(_n(crop[k]) for k in ('x', 'y', 'width', 'height'))
    annotation = ''
    if view['highlight'] is not None:
        h = _pixels(view['highlight'], asset)
        # Stroke scales with source pixels to remain legible in the display.
        stroke = max(crop['width'] / 900, crop['height'] / 720) * 6
        annotation = ('<rect x="' + _n(h['x']) + '" y="' + _n(h['y'])
                      + '" width="' + _n(h['width']) + '" height="' + _n(h['height'])
                      + '" fill="none" stroke="' + palette['accent']
                      + '" stroke-width="' + _n(stroke) + '"/>')
    label = html.escape(view['label'], quote=True)
    # Constrain the actual glyph run to the 900px label area, including long
    # Turkish uppercase labels, rather than assuming a font's average width.
    label_width = min(900, len(view['label']) * 20)
    vector = ('<svg class="objects" viewBox="0 0 1080 900" xmlns="http://www.w3.org/2000/svg" aria-label="Müşteri görseli açıklaması">'
              '<defs><clipPath id="' + ident + '-viewport"><rect x="90" y="70" width="900" height="720"/></clipPath></defs>'
              '<rect x="90" y="70" width="900" height="720" fill="' + palette['background'] + '"/>'
              '<g clip-path="url(#' + ident + '-viewport)"><g id="' + ident + '-camera">'
              '<svg x="90" y="70" width="900" height="720" viewBox="' + box + '" preserveAspectRatio="xMidYMid meet" overflow="hidden">'
              '<image href="assets/customer-image.png" x="0" y="0" width="' + str(asset['width']) + '" height="' + str(asset['height']) + '"/>'
              '<g id="' + ident + '-highlight">' + annotation + '</g></svg></g></g>'
              '<text x="540" y="850" text-anchor="middle" font-family="Schibsted" font-size="30" textLength="' + str(label_width) + '" lengthAdjust="spacingAndGlyphs" fill="' + palette['ink'] + '">' + label + '</text></svg>')
    length = scene['end'] - scene['start']
    initial = {'x': 0, 'y': 0, 'scale': 1, 'svgOrigin': '540 430'}
    ops = [{'target': 'camera', 'op': 'set', 'values': initial},
           {'target': 'highlight', 'op': 'set', 'values': {'opacity': 0}}]
    if view['highlight'] is not None:
        ops.append({'target': 'highlight', 'op': 'tween', 'offset': .15,
                    'duration': min(.4, length - .3), 'before': {'opacity': 0},
                    'after': {'opacity': 1}, 'ease': 'cubic-in-out'})
    if view['camera'] != 'locked':
        final = {**initial, 'scale': 1.08}
        if view['camera'] == 'follow-object' and view['highlight'] is not None:
            h, c = view['highlight'], view['crop']
            # Source aspect ratio may letterbox the crop. Project its center
            # through the same meet transform before deriving a bounded pan.
            fit = min(900 / crop['width'], 720 / crop['height'])
            x = 540 + ((h['x'] + h['width'] / 2) - (c['x'] + c['width'] / 2)) * asset['width'] * fit
            y = 430 + ((h['y'] + h['height'] / 2) - (c['y'] + c['height'] / 2)) * asset['height'] * fit
            final['x'] = round(max(-36, min(36, (540 - x) * .08)), 8)
            final['y'] = round(max(-28.8, min(28.8, (430 - y) * .08)), 8)
        ops.append({'target': 'camera', 'op': 'tween', 'offset': .1,
                    'duration': length - .2, 'before': dict(initial),
                    'after': final, 'ease': 'cubic-in-out'})
    return vector, ops
