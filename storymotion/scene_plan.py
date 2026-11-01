"""Host-validated, manual account scenes; owned SVG only, no model code or IO.

Source/claim and accepted-reference hashes provide traceability. They do not
establish factual truth, license transfer or approval of a new serial episode.
"""
import copy
import html
import re
import textwrap
import unicodedata

from .security import WorkflowError, finite
from .writing_context import audit_bound_claims, validate_binding, validate_canon_proposal


from .account_packs import KINDS, is_serial
ACCOUNTS = KINDS
FIELDS = {'schema_version', 'recipe', 'account', 'canon_revision', 'scenes'}
ITEM_FIELDS = {'scene_id', 'kind', 'content', 'claim_indexes', 'cue_indexes', 'object_id', 'camera'}
_ID = re.compile(r'[a-z][a-z0-9-]{0,59}')
_HEX = re.compile(r'[0-9a-f]{64}')
_URL = re.compile(r'(?i)(?:[a-z][a-z0-9+.-]*://|\bwww\.|\b(?:javascript|data|file|vbscript):|\b[a-z0-9][a-z0-9.-]*\.[a-z]{2,}\b)')
_CODE = re.compile(r'(?i)(?:[<>`{}\[\]\\]|=>|\b(?:eval|alert|fetch|function)\s*\(|\b(?:document|window)\s*\.)')


def _exact(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        raise WorkflowError('Manual scene fields missing or unsupported')


def _plain(value, maximum):
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip()
            or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in value)
            or _URL.search(value) or _CODE.search(value)):
        raise WorkflowError('Scene copy must be bounded plain text without markup, URLs or controls')
    return value


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise WorkflowError('Manual scene IDs must be simple stable IDs')


def _indexes(value, maximum, required=False):
    if (not isinstance(value, list) or len(value) > maximum or required and not value
            or any(type(n) is not int or not 0 <= n < maximum for n in value)
            or len(set(value)) != len(value)):
        raise WorkflowError('Scene indexes must uniquely reference the bound brief')


def _context(brief):
    if (not isinstance(brief, dict) or not isinstance(brief.get('brand'), str) or brief.get('brand') not in ACCOUNTS
            or not isinstance(brief.get('creative'), dict) or not brief['creative']
            or brief.get('raster') is not None):
        raise WorkflowError('Manual account scenes require one supported creative profile without raster')
    scenes, cues, claims = (brief.get(k) for k in ('scenes', 'cues', 'claims'))
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 12 or not all(isinstance(s, dict) for s in scenes):
        raise WorkflowError('Manual scenes require bounded source scenes')
    if not isinstance(cues, list) or not 1 <= len(cues) <= 100 or not all(isinstance(c, dict) for c in cues):
        raise WorkflowError('Manual scenes require bounded subtitle cues')
    if not isinstance(claims, list) or len(claims) > 30:
        raise WorkflowError('Manual scenes require bounded claims')
    seen = set()
    for scene in scenes:
        _id(scene.get('id')); _id(scene.get('object_id'))
        if scene['id'] in seen or not isinstance(scene.get('camera'), str) or scene['camera'] not in {'locked', 'push-in', 'follow-object'}:
            raise WorkflowError('Source scenes require unique IDs and supported cameras')
        seen.add(scene['id'])
        start = finite(scene.get('start'), 'source scene start', 0, 90)
        end = finite(scene.get('end'), 'source scene end', 0, 90)
        if end - start < 1.6:
            raise WorkflowError('Manual scenes require at least1.6seconds')
    for cue in cues:
        start = finite(cue.get('start'), 'source cue start', 0, 90)
        end = finite(cue.get('end'), 'source cue end', 0, 90)
        if end <= start:
            raise WorkflowError('Invalid source cue range')
    binding = validate_binding(brief.get('production_context'), brief['brand'])
    audit_bound_claims(brief)
    if is_serial(brief['brand']):
        if not binding or not binding['canon']:
            raise WorkflowError('Serial manual scenes require an explicit accepted-reference snapshot')
        if brief['creative'].get('canon_status') != 'noncanonical_fixture':
            raise WorkflowError('Manual scenes cannot promote a new draft to accepted canon')
        try:
            validate_canon_proposal(brief, binding)
        except (KeyError, TypeError):
            raise WorkflowError('Serial source does not match the accepted reference') from None
        data = binding['canon']['data']
        objects = {r['id'] for r in data['objects']}
        cast = {r['id'] for r in data['cast']}
        if any(s['object_id'] not in objects or s.get('character_id') not in cast for s in scenes):
            raise WorkflowError('Serial scene object/cast must belong to the accepted reference')
    return binding


def _copy_audit(item, brief):
    strings = []
    for value in item['content'].values():
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, list):
            strings.extend(value)
    copy_brief = {'brand': brief['brand'], 'creative': brief['creative'],
                  'production_context': brief.get('production_context'),
                  'title': '', 'script': ' '.join(strings), 'caption': '', 'scenes': [],
                  'claims': [brief['claims'][i] for i in item['claim_indexes']]}
    from .creative import audit_audience_copy
    audit_audience_copy(brief['brand'], copy_brief)
    audit_bound_claims(copy_brief)


def _item(item, scene, brief, binding):
    _exact(item, ITEM_FIELDS)
    if item['scene_id'] != scene['id'] or item['object_id'] != scene['object_id'] or item['camera'] != scene['camera']:
        raise WorkflowError('Manual scene ID, object or camera differs from its source')
    if not isinstance(item['kind'], str) or item['kind'] not in KINDS[brief['brand']]:
        raise WorkflowError('Manual scene kind belongs to another account profile')
    _indexes(item['claim_indexes'], len(brief['claims']), not is_serial(brief['brand']))
    _indexes(item['cue_indexes'], len(brief['cues']))
    expected = [i for i, c in enumerate(brief['cues']) if c['start'] < scene['end'] and c['end'] > scene['start']]
    if item['cue_indexes'] != expected:
        raise WorkflowError('Scene subtitle references must exactly cover overlapping source cues')
    content, kind = item['content'], item['kind']
    if kind == 'possibility-branches':
        _exact(content, {'left', 'right', 'question'})
        _plain(content['left'], 38); _plain(content['right'], 38); _plain(content['question'], 55)
    elif kind == 'observation':
        _exact(content, {'object', 'prompt', 'observation'})
        if not isinstance(content['object'], str) or content['object'] not in {'phone', 'clock', 'chair'}:
            raise WorkflowError('Unsupported neutral observation object')
        _plain(content['prompt'], 55); _plain(content['observation'], 55)
    elif kind == 'process-route':
        _exact(content, {'nodes', 'from_node', 'to_node'})
        nodes = content['nodes']
        if not isinstance(nodes, list) or not 2 <= len(nodes) <= 4:
            raise WorkflowError('A schematic process requires2to4nodes')
        for node in nodes:
            _plain(node, 20)
        if any(type(content[k]) is not int or not 0 <= content[k] < len(nodes) for k in ('from_node', 'to_node')) or content['from_node'] == content['to_node']:
            raise WorkflowError('Process route must change between existing nodes')
    elif kind == 'object-transform':
        _exact(content, {'object', 'before', 'after'})
        if not isinstance(content['object'], str) or content['object'] not in {'document', 'device', 'container'}:
            raise WorkflowError('Unsupported neutral transformation object')
        _plain(content['before'], 28); _plain(content['after'], 28)
    else:
        _exact(content, {'clue_id', 'note'} if kind == 'clue-inspect' else {'clue_ids', 'note'})
        _plain(content['note'], 55)
        ids = [content['clue_id']] if kind == 'clue-inspect' else content['clue_ids']
        if not isinstance(ids, list) or not 1 <= len(ids) <= 3:
            raise WorkflowError('Serial scene requires1to3existing clues')
        for clue_id in ids:
            _id(clue_id)
        if len(set(ids)) != len(ids):
            raise WorkflowError('Serial clue IDs cannot repeat')
        clues = {r['id']: r for r in binding['canon']['data']['open_clues']}
        for clue_id in ids:
            if clue_id not in clues or clues[clue_id]['object_id'] != scene['object_id']:
                raise WorkflowError('Clue must refer to this exact accepted object')
            _plain(clues[clue_id]['description'], 500)
    _copy_audit(item, brief)


def validate_scene_plan(value, brief):
    """Return an independent strict plan; source truth and new canon stay pending."""
    binding = _context(brief)
    _exact(value, FIELDS)
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['recipe'] != 'manual-account-scenes-1' or value['account'] != brief['brand']):
        raise WorkflowError('Manual scene recipe/profile mismatch')
    expected = binding['canon']['revision'] if binding and binding['canon'] else None
    if value['canon_revision'] != expected or (expected is not None and not _HEX.fullmatch(expected)):
        raise WorkflowError('Manual scene plan must pin the exact accepted-reference revision')
    if not isinstance(value['scenes'], list) or len(value['scenes']) != len(brief['scenes']):
        raise WorkflowError('One ordered manual item per source scene is required')
    for item, scene in zip(value['scenes'], brief['scenes']):
        _item(item, scene, brief, binding)
    return copy.deepcopy(value)


def _text(value, x, y, size, color, width=880):
    # Glyph run has a fixed maximum width independent of the selected font.
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Schibsted" font-size="{size}" '
            f'fill="{color}" textLength="{min(width, max(1, len(value) * size * .53))}" lengthAdjust="spacingAndGlyphs">'
            + html.escape(value, quote=True) + '</text>')


def _paragraph(value, x, y, size, color, columns=45, max_lines=8, width=830):
    lines = textwrap.wrap(value, width=columns, break_long_words=True, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(' .') + '…'
    return ''.join(_text(line, x, y + i * (size + 7), size, color, width) for i, line in enumerate(lines))


def _object(kind, x, y, ink, bg, accent):
    if kind in {'phone', 'device'}:
        return f'<rect x="{x-75}" y="{y-130}" width="150" height="260" rx="22" fill="{bg}" stroke="{ink}" stroke-width="7"/><path d="M{x-40} {y-85}H{x+40}M{x-40} {y-40}H{x+15}M{x-40} {y+5}H{x+30}" fill="none" stroke="{accent}" stroke-width="6"/>'
    if kind == 'clock':
        return f'<circle cx="{x}" cy="{y}" r="125" fill="{bg}" stroke="{ink}" stroke-width="8"/><path d="M{x} {y-78}V{y}L{x+62} {y+40}" fill="none" stroke="{accent}" stroke-width="8"/>'
    if kind == 'chair':
        return f'<path d="M{x-85} {y+15}V{y-110}H{x+85}V{y+15}M{x-100} {y+15}H{x+100}M{x-75} {y+15}V{y+130}M{x+75} {y+15}V{y+130}" fill="none" stroke="{ink}" stroke-width="10"/>'
    if kind == 'document':
        return f'<path d="M{x-90} {y-120}H{x+55}L{x+90} {y-85}V{y+120}H{x-90}ZM{x+55} {y-120}V{y-85}H{x+90}" fill="{bg}" stroke="{ink}" stroke-width="7"/><path d="M{x-55} {y-50}H{x+55}M{x-55} {y}H{x+55}M{x-55} {y+50}H{x+25}" fill="none" stroke="{accent}" stroke-width="7"/>'
    return f'<rect x="{x-100}" y="{y-85}" width="200" height="170" rx="8" fill="{bg}" stroke="{ink}" stroke-width="7"/><path d="M{x-100} {y-40}H{x+100}M{x} {y-85}V{y-40}" fill="none" stroke="{accent}" stroke-width="7"/>'


def _tween(target, before, after, length, offset=.15):
    return {'target': target, 'op': 'tween', 'offset': offset, 'duration': length - offset - .15,
            'before': before, 'after': after, 'ease': 'cubic-in-out'}


def compile_scene(scene, item, profile, ident, brief):
    """Compile one validated scene to own neutral SVG + canonical host motion."""
    binding = _context(brief)
    if not isinstance(scene, dict) or scene not in brief['scenes']:
        raise WorkflowError('Manual compiler scene is not in its source brief')
    _item(item, scene, brief, binding)
    if (not isinstance(profile, dict) or profile.get('id') != brief['brand']
            or not isinstance(ident, str) or not re.fullmatch('[a-z][a-z0-9-]{0,39}', ident)):
        raise WorkflowError('Invalid manual compiler profile or identifier')
    palette = profile.get('palette')
    if not isinstance(palette, dict) or any(not isinstance(palette.get(k), str) or not re.fullmatch('#[0-9a-fA-F]{6}', palette[k]) for k in ('background', 'ink', 'accent', 'muted')):
        raise WorkflowError('Manual compiler requires fixed hex palette colors')
    bg, ink, accent, muted = (palette[k] for k in ('background', 'ink', 'accent', 'muted'))
    length, c, kind = scene['end'] - scene['start'], item['content'], item['kind']
    initial = {'x': 0, 'y': 0, 'scale': 1, 'svgOrigin': '540 450'}
    ops = [{'target': 'camera', 'op': 'set', 'values': initial}]
    if item['camera'] != 'locked':
        ops.append(_tween('camera', dict(initial), {**initial, 'scale': 1.06,
                           'x': -12 if item['camera'] == 'follow-object' else 0}, length))
    body = ''
    if kind == 'possibility-branches':
        body = f'<path d="M540 620V530L265 350M540 530L815 350" fill="none" stroke="{muted}" stroke-width="5"/>'
        body += '<g id="' + ident + '-object">' + _object('phone', 540, 650, ink, bg, accent) + '</g>'
        for target, x, label in [('left', 265, c['left']), ('right', 815, c['right'])]:
            body += f'<g id="{ident}-{target}"><circle cx="{x}" cy="300" r="165" fill="{bg}" stroke="{accent}" stroke-width="6"/>' + _paragraph(label, x, 288, 28, ink, columns=20, max_lines=2, width=290) + '</g>'
            ops += [{'target': target, 'op': 'set', 'values': {'opacity': 0}}, _tween(target, {'opacity': 0}, {'opacity': 1}, length)]
        body += _text(c['question'], 540, 855, 31, ink)
    elif kind == 'observation':
        body = _text(c['prompt'], 540, 145, 32, ink)
        body += f'<g id="{ident}-object">' + _object(c['object'], 540, 445, ink, bg, accent) + '</g>'
        body += f'<g id="{ident}-observation"><path d="M300 660H780" stroke="{accent}" stroke-width="6"/>' + _text(c['observation'], 540, 760, 31, ink) + '</g>'
        ops += [{'target': 'object', 'op': 'set', 'values': {'y': 18}}, _tween('object', {'y': 18}, {'y': 0}, length),
                {'target': 'observation', 'op': 'set', 'values': {'opacity': 0}}, _tween('observation', {'opacity': 0}, {'opacity': 1}, length, .3)]
    elif kind == 'process-route':
        body = _text('Şematik süreç · gerçek ürün arayüzü değil', 540, 140, 27, muted)
        xs = [170 + i * 740 / (len(c['nodes']) - 1) for i in range(len(c['nodes']))]
        body += f'<path d="M170 430H910" stroke="{muted}" stroke-width="6"/>'
        for x, label in zip(xs, c['nodes']):
            body += f'<rect x="{x-90}" y="330" width="180" height="200" rx="16" fill="{bg}" stroke="{ink}" stroke-width="6"/>' + _paragraph(label, x, 410, 26, ink, columns=12, max_lines=2, width=155)
        body += f'<circle id="{ident}-token" cx="0" cy="590" r="25" fill="{accent}"/>'
        ops += [{'target': 'token', 'op': 'set', 'values': {'x': xs[c['from_node']]}},
                _tween('token', {'x': xs[c['from_node']]}, {'x': xs[c['to_node']]}, length)]
        body += _text('Kaynakla bağlı açıklama · doğruluk incelemesi açık', 540, 780, 26, muted)
    elif kind == 'object-transform':
        body = _text('Şematik dönüşüm · gerçek ürün ekranı değil', 540, 140, 27, muted)
        for target, x, label in [('before', 285, c['before']), ('after', 795, c['after'])]:
            body += f'<g id="{ident}-{target}">' + _object(c['object'], x, 430, ink, bg, accent) + _text(label, x, 680, 29, ink, 390) + '</g>'
        body += f'<path d="M440 430H635L605 400M635 430L605 460" stroke="{accent}" stroke-width="8" fill="none"/>'
        ops += [{'target': 'before', 'op': 'set', 'values': {'opacity': 1}}, _tween('before', {'opacity': 1}, {'opacity': .4}, length),
                {'target': 'after', 'op': 'set', 'values': {'opacity': .2}}, _tween('after', {'opacity': .2}, {'opacity': 1}, length)]
    else:
        canon = binding['canon']['data']
        label = 'Sentetik referans provası · yeni kanon değil' if canon['origin'] == 'synthetic_reference_test' else 'Kabul referansına bağlı taslak · yeni kanon değil'
        body = _text(label, 540, 110, 26, muted)
        clues = {r['id']: r for r in canon['open_clues']}
        ids = [c['clue_id']] if kind == 'clue-inspect' else c['clue_ids']
        if kind == 'clue-inspect':
            clue = clues[ids[0]]
            body += f'<g id="{ident}-clue"><rect x="170" y="190" width="740" height="500" rx="18" fill="{bg}" stroke="{ink}" stroke-width="6"/>'
            body += _text(clue['id'], 540, 260, 29, accent) + _paragraph(clue['description'], 540, 325, 28, ink, columns=45, max_lines=8, width=670) + '</g>'
            body += f'<g id="{ident}-inspect"><circle cx="775" cy="650" r="85" fill="none" stroke="{accent}" stroke-width="10"/><path d="M835 710L895 770" stroke="{accent}" stroke-width="15"/></g>'
            ops += [{'target': 'inspect', 'op': 'set', 'values': {'x': 35, 'opacity': 0}}, _tween('inspect', {'x': 35, 'opacity': 0}, {'x': 0, 'opacity': 1}, length)]
        else:
            body += f'<path d="M140 215V735" stroke="{accent}" stroke-width="5"/>'
            for i, clue_id in enumerate(ids):
                y = 210 + i * 190
                clue = clues[clue_id]
                body += f'<g id="{ident}-clue-{["a", "b", "c"][i]}"><circle cx="140" cy="{y+70}" r="12" fill="{accent}"/><path d="M140 {y+70}H220" stroke="{accent}" stroke-width="5"/><rect x="220" y="{y}" width="700" height="160" rx="12" stroke="{ink}" stroke-width="5" fill="{bg}"/>'
                body += _text(clue_id, 570, y + 40, 26, accent, 640) + _paragraph(clue['description'], 570, y + 82, 25, ink, columns=48, max_lines=2, width=630) + '</g>'
                target = 'clue-' + ['a', 'b', 'c'][i]
                ops += [{'target': target, 'op': 'set', 'values': {'opacity': 0}}, _tween(target, {'opacity': 0}, {'opacity': 1}, length, .15 + i * .12)]
        body += _text(c['note'], 540, 840, 30, ink)
        body += _text('Nesne: ' + scene['object_id'], 540, 795 if kind == 'clue-inspect' else 790, 23, muted)
    vector = ('<svg class="objects" viewBox="0 0 1080 900" xmlns="http://www.w3.org/2000/svg" aria-label="Elle seçilmiş kaynaklı sahne">'
              f'<defs><clipPath id="{ident}-frame"><rect x="50" y="50" width="980" height="840"/></clipPath></defs>'
              f'<g clip-path="url(#{ident}-frame)"><g id="{ident}-camera">' + body + '</g></g></svg>')
    from .edit_plan import validate_operations
    validate_operations(ops, length)
    return vector, ops
