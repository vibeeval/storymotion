"""Four original families and three explicit, bounded MIT source adaptations.

The scene graph is data, shared by the explicit HF and Remotion adapters. Each
family has its own layout and choreography; no source HTML, prompt or media is
executed or copied. Captions use caller-supplied timing, not inferred speech.
"""
from .local_state import private_directory, write_private
import copy
import hashlib
import html
import json
import math
import re
import shutil
import unicodedata
from pathlib import Path

from . import __version__
from .security import WorkflowError, canonical, digest, file_hash, finite, scan_bytes, write_json
from . import style_templates, development_templates, template_discovery

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
FAMILIES = {
    'kinetic-grid': {'name': 'Kinetik tipografi / grid', 'kind': 'phrases',
                     'description': 'Satır blokları, karşı yönlü girişler ve ritmik grid vurguları.',
                     'palette': {'background': '#F5F1E8', 'ink': '#17202D', 'muted': '#4B5968', 'accent': '#B63B22'}},
    'causal-path': {'name': 'Nedensel SVG çizimi', 'kind': 'nodes',
                    'description': 'Düğümler arasındaki yönlü yollar çizilir; işaret adım adım ilerler.',
                    'palette': {'background': '#FBFCFA', 'ink': '#17332E', 'muted': '#48665F', 'accent': '#087F65'}},
    'exploded-blueprint': {'name': 'Patlatılmış mekanizma', 'kind': 'parts',
                          'description': 'İzinli parametrik parçalar ayrılır, ölçülür ve tekrar birleşir.',
                          'palette': {'background': '#0C2438', 'ink': '#ECF3F8', 'muted': '#9DB8CA', 'accent': '#FFCC64'}},
    'isometric-process': {'name': 'İzometrik veri / süreç', 'kind': 'series',
                         'description': 'Değerler izometrik hacimlere dönüşür; süreç yolu aşamalar arasında ilerler.',
                         'palette': {'background': '#F2F5F7', 'ink': '#1E2E48', 'muted': '#4F617A', 'accent': '#5843AF'}},
}
FAMILIES.update(style_templates.FAMILIES)
FAMILIES.update(development_templates.FAMILIES)
ADAPTER_FILES = ('storymotion/template_families.py','storymotion/style_templates.py',
                 'storymotion/template_studio.py','storymotion/engine.py','storymotion/compose.py',
                 'renderers/template-motion.mjs','renderers/remotion/entry.jsx',
                 'catalog/style-adapters.json','fixtures/template-families.json',
                 'vendor/notices/mg-styles-15-MIT.txt')


def invalid(message):
    raise WorkflowError('TEMPLATE_INPUT: ' + message)


def text(value, name, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        invalid(name + ': boş veya fazla uzun metin')
    if any(unicodedata.category(c).startswith('C') and c not in '\n\t' for c in value):
        invalid(name + ': denetim karakteri')
    return ' '.join(value.split())


def fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(optional) != set(required):
        invalid('beklenen alanlar: ' + ', '.join(sorted(required)))


def fit_lines(value, width, maximum=56, minimum=30, max_lines=3):
    """Conservative, deterministic fit; actual font bboxes are audited in Chrome.

    No ellipsis, clipping or silent word loss. Unbreakable oversized tokens are
    refused, allowing the caller to edit instead of exporting cropped text.
    """
    def units(word):
        return sum(1.0 if c in 'MW@%ĞÖÜŞÇ' or ord(c) > 0x2FFF else .72 if c.isupper() else .62
                   for c in word)
    for size in range(maximum, minimum - 1, -1):
        lines = []; current = ''
        for word in value.split():
            if units(word) * size > width:
                lines = None; break
            candidate = (current + ' ' + word).strip()
            if current and units(candidate) * size > width:
                lines.append(current); current = word
            else:
                current = candidate
        if lines is not None:
            if current: lines.append(current)
            if len(lines) <= max_lines:
                return {'lines': lines, 'font_size': size, 'line_height': round(size * 1.22, 3),
                        'width': width, 'height': round(size * 1.22 * len(lines), 3)}
    invalid('Metin bu alana sığmıyor; kısaltın veya daha kısa sözcükler kullanın')


def validate_spec(spec):
    try:
        return _validate_spec(spec)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        invalid('geçersiz sınırlı şablon girdisi')


def _validate_spec(spec):
    fields(spec, {'id', 'version', 'parameters'})
    if not isinstance(spec['id'],str) or spec['id'] not in FAMILIES or type(spec['version']) is not str or spec['version'] != VERSION:
        invalid('bilinmeyen aile veya sürüm; otomatik başka şablon yok')
    if spec['id'] in development_templates.FAMILIES:return development_templates.validate_spec(spec)
    p = copy.deepcopy(spec['parameters']); family = spec['id']; kind = FAMILIES[family]['kind']
    required = {'title', 'duration', 'narration', 'cues', kind}
    if family == 'causal-path': required.add('edges')
    optional = style_templates.OPTIONAL.get(family, {'unit'} if family == 'isometric-process' else {'separation'} if family == 'exploded-blueprint' else set())
    fields(p, required, optional)
    p['title'] = text(p['title'], 'başlık', 160)
    fit_lines(p['title'], 900, 64, 40, 4)
    p['duration'] = finite(p['duration'], 'template duration', 3, 45)
    if abs(p['duration'] * 30 - round(p['duration'] * 30)) > 1e-6:
        invalid('süre 30 fps kare sınırında olmalı')
    p['narration'] = text(p['narration'], 'anlatım', 1500)
    if not isinstance(p['cues'], list) or not 1 <= len(p['cues']) <= 24:
        invalid('1–24 zamanlanmış altyazı gerekli')
    previous = 0
    for cue in p['cues']:
        fields(cue, {'start', 'end', 'text'})
        cue['start'] = finite(cue['start'], 'cue start', 0, p['duration'])
        cue['end'] = finite(cue['end'], 'cue end', 0, p['duration'])
        cue['text'] = text(cue['text'], 'altyazı', 95)
        if cue['start'] < previous or cue['end'] - cue['start'] < .2:
            invalid('altyazı sıralı, çakışmasız ve en az 0,2 saniye olmalı')
        fit_lines(cue['text'], 890, 43, 32, 3); previous = cue['end']
    if ' '.join(c['text'] for c in p['cues']) != p['narration']:
        invalid('altyazılar anlatım metnini eksiksiz ve aynı sırayla içermeli')
    if family in style_templates.FAMILIES:
        style_templates.validate_parameters(family,p,fields,text,fit_lines,finite,invalid)
        if scan_bytes(canonical(p).encode()): invalid('olası gizli değer; girdi kaydedilmedi')
        return {'id': family, 'version': VERSION, 'parameters': p}
    items = p[kind]
    low, high = (2, 4) if family == 'kinetic-grid' else (2, 5) if family in {'causal-path', 'isometric-process'} else (2, 4)
    if not isinstance(items, list) or not low <= len(items) <= high:
        invalid(f'{kind}: {low}–{high} öğe gerekli')
    for item in items:
        expected = {'text'} if family == 'kinetic-grid' else {'id', 'label'} if family == 'causal-path' else {'shape', 'label'} if family == 'exploded-blueprint' else {'label', 'value'}
        fields(item, expected)
        label_key = 'text' if family == 'kinetic-grid' else 'label'
        item[label_key] = text(item[label_key], label_key, 110 if family == 'kinetic-grid' else 60)
        fit_lines(item[label_key], 750 if family == 'kinetic-grid' else 570 if family == 'causal-path' else 240 if family == 'exploded-blueprint' else 150,
                  62 if family == 'kinetic-grid' else 37, 32 if family != 'isometric-process' else 25, 3)
        if family == 'causal-path' and (not isinstance(item['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,23}', item['id'])):
            invalid('düğüm kimliği kısa ve sade olmalı')
        if family == 'exploded-blueprint' and item['shape'] not in {'plate', 'cylinder', 'coil', 'filter'}:
            invalid('parça geometrisi plate/cylinder/coil/filter olmalı')
        if family == 'isometric-process': item['value'] = finite(item['value'], 'data value', 0, 1000000)
    if family == 'causal-path':
        ids = [n['id'] for n in items]
        if len(set(ids)) != len(ids): invalid('tekrarlanan düğüm kimliği')
        if not isinstance(p['edges'], list) or not 1 <= len(p['edges']) <= 7: invalid('1–7 yönlü bağlantı gerekli')
        seen = set()
        for edge in p['edges']:
            fields(edge, {'from', 'to'})
            if edge['from'] not in ids or edge['to'] not in ids or ids.index(edge['from']) >= ids.index(edge['to']):
                invalid('bağlantılar var olan düğümleri ileri sırada bağlamalı; döngü yok')
            pair = (edge['from'], edge['to'])
            if pair in seen: invalid('tekrarlanan bağlantı')
            seen.add(pair)
        if {v for pair in seen for v in pair}!=set(ids):invalid('her düğüm en az bir açık bağlantıya katılmalı')
    if family == 'exploded-blueprint': p['separation'] = finite(p.get('separation', 160), 'part separation', 110, 180)
    if family == 'isometric-process':
        p['unit'] = text(p.get('unit', 'birim'), 'birim', 16)
        if not any(n['value'] > 0 for n in items): invalid('en az bir veri değeri sıfırdan büyük olmalı')
    if scan_bytes(canonical(p).encode()): invalid('olası gizli değer; girdi kaydedilmedi')
    return {'id': family, 'version': VERSION, 'parameters': p}


def source_context(ids):
    if not isinstance(ids, list) or len(ids) > 32 or not all(isinstance(v, str) for v in ids) or len(set(ids)) != len(ids):
        invalid('en fazla32benzersiz kaynak kimliği')
    records = {v['provenance']['source_item_id']:v['provenance'] for v in json.loads((ROOT/'catalog/style-adapters.json').read_text())['adapters']}
    records.update(development_templates.source_records())
    if any(key not in records for key in ids):invalid('bilinmeyen kaynak kimliği')
    value = {'source_item_ids': ids, 'source_items': [copy.deepcopy(records[key]) for key in ids], 'tags': [],
             'relationship': 'planning_reference_not_implemented_style'}
    return {**value, 'binding_sha256': digest(value)}


def planning_subject(value,account):
    if value is None:return None
    if not isinstance(value,dict) or len(canonical(value))>100000:invalid('konu seçimi geçersiz')
    check={k:v for k,v in value.items() if k!='binding_sha256'}
    if value.get('binding_sha256')!=digest(check) or value.get('production_profile')!=account or value.get('style_applied_by_taxonomy') is not False or value.get('sources_verified') is not False or value.get('human_review')!='pending':
        invalid('konu seçimi plan bağı değişti')
    if value.get('capability',{}).get('render_verified',False):invalid('kaynak konu/stil render kabulü olamaz')
    ids=value.get('catalog_selection',{}).get('source_item_ids',[])
    if value.get('source_items',[])!=source_context(ids)['source_items']:invalid('konu kaynak kimlikleri değişti')
    return copy.deepcopy(value)


def make_brief(account, spec, source_item_ids=None,subject=None,*,claims=None,production_context=None):
    from .account_packs import load_pack
    load_pack(account)
    spec = validate_spec(spec); p = spec['parameters']; duration = p['duration']
    brief = {'schema_version': 1, 'brand': account, 'title': p['title'],
            'brief': FAMILIES[spec['id']]['description'], 'script': p['narration'], 'caption': p['title'],
            'duration': duration, 'demo': True, 'alignment': 'provisional_silent', 'audio': None,
            'claims': copy.deepcopy([] if claims is None else claims), 'production_context':copy.deepcopy(production_context),
            'brand_identity': {'name': '', 'handle': ''},
            'scenes': [{'id': 'family-scene', 'start': 0, 'end': duration, 'action': spec['id'],
                        'heading': p['title'], 'information': 'Kullanıcı parametreli özgün şablon.',
                        'object_before': 'Parametreli başlangıç.', 'object_after': 'Parametreli sonuç.'}],
            'cues': p['cues'], 'template_family': spec, 'template_context': source_context(source_item_ids or []),
            'template_subject':planning_subject(subject,account)}
    # Circular: template_intake.surface() imports FAMILIES from this module.
    from .template_intake import audit_template
    brief['template_audit']=audit_template(brief)
    return brief


def validate_brief(brief, profile):
    try:
        return _validate_brief(brief,profile)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError):
        invalid('geçersiz şablon brief bağı')


def _validate_brief(brief, profile):
    spec = validate_spec(brief.get('template_family'))
    if brief.get('brand') != profile['id']: invalid('profil bağı uyuşmuyor')
    allowed = {'schema_version', 'brand', 'title', 'brief', 'script', 'caption', 'duration', 'demo', 'alignment', 'audio',
               'claims', 'brand_identity', 'scenes', 'cues', 'template_family', 'template_context','template_subject','production_context','template_audit'}
    if set(brief) - allowed: invalid('bu aileyle desteklenmeyen ek üretim alanı')
    generated = make_brief(brief['brand'], spec, brief.get('template_context', {}).get('source_item_ids', []),brief.get('template_subject'),claims=brief.get('claims'),production_context=brief.get('production_context'))
    for name in ['schema_version', 'title', 'script', 'duration', 'cues', 'scenes', 'template_context','template_subject','claims','production_context','template_audit']:
        if brief.get(name) != generated[name]: invalid(name + ': sürümlü parametre bağı değişti')
    if type(brief.get('demo')) is not bool or brief.get('alignment') not in {'provisional_silent', 'imported_timing'}:
        invalid('demo/zamanlama durumu gerekli')
    text(brief.get('brief'),'brief',1500);text(brief.get('caption'),'caption',2000)
    if scan_bytes(canonical(brief).encode()): invalid('olası gizli değer')
    # Circular: template_intake.surface() imports FAMILIES from this module.
    from .template_intake import audit_template
    if brief.get('template_audit')!=audit_template(brief):invalid('template claim audit changed')
    profile['palette'] = copy.deepcopy(spec['parameters'].get('palette', FAMILIES[spec['id']]['palette']))
    return spec


def adapter_fingerprint():
    return digest({n: file_hash(ROOT / n) for n in ADAPTER_FILES})


def capabilities():
    from .account_packs import catalog
    from .template_intake import surface
    packs, errors = catalog()
    examples=json.loads((ROOT/'fixtures/template-families.json').read_text())['families']
    claim_surface=surface()
    discovery=template_discovery.catalog()
    if set(discovery)!=set(FAMILIES):
        invalid('discovery catalog must cover the exact 91 family IDs')
    result=[]
    for key,family in FAMILIES.items():
        cases=development_templates.examples(key) if key in development_templates.FAMILIES else examples[key]
        media=next((r['requires_caller_media'] for r in development_templates.catalog() if r['id']==key),False)
        editorial=discovery[key]
        if editorial['requires_caller_media']!=media:
            invalid('discovery media flag must match the registry')
        result.append({'id':key,'version':VERSION,'name':family['name'],'description':family['description'],
          'kind':family['kind'],'profile_ids':sorted(packs),'aspect_ratio':'9:16',
          'engines':{engine:{'implemented':True,'render_verified':False,'state':'implemented_pending_native_acceptance'}
                     for engine in ('hyperframes','remotion')},
          'source_styles_implemented':style_templates.implemented_sources(key),'adaptation':style_templates.adaptation(key),
          'rights':'MIT_bounded_code_adaptation_with_notice' if key in style_templates.FAMILIES else 'original_code_and_vectors',
          'human_publication_acceptance':'pending','preview_url':None,'preview_state':'missing_preview',
          'requires_caller_media':media,
          'niches':list(editorial['niches']),'content_types':list(editorial['content_types']),
          'sample_topics':list(editorial['sample_topics']),'audience_hypothesis':editorial['audience_hypothesis'],
          'age_hypothesis':copy.deepcopy(editorial['age_hypothesis']),'visual_score':None,
          'instagram_assessment':copy.deepcopy(editorial['instagram_assessment']),
          'editorial_description':editorial['editorial_description'],
          'readiness':'caller_media_proxy_only' if media else 'prepare_only_native_pending',
          'claim_guarded_numbers':sorted(claim_surface[key]['guarded']),
          'examples':[{'name':c['name'],'spec':copy.deepcopy(c['spec']) if key in development_templates.FAMILIES else validate_spec(c['spec'])} for c in cases]})
    return {'families':result,'account_pack_errors':errors,'provider_calls':0,'source_reference_styles_render_verified':False,
            'restoration_scope':'91 exact templates: 7 baseline plus84 fixed registry; render/visual acceptance pending',
            'discovery_source_sha256':template_discovery.SOURCE_SHA256}


def adapter_catalog():
    """Explicit renderer overlay; imported records and taxonomy plans stay references."""
    return [{'family_id':f['id'],'source_style_id':f['adaptation']['source_item_id'],
             'source_name':f['adaptation']['source_name'],'license':f['adaptation']['license'],
             'strategy':f['adaptation'].get('strategy','bounded_source_code_adaptation'),
             'original_implementation':f['adaptation'].get('original_implementation',False),
             'source_license':f['adaptation'].get('source_license',f['adaptation']['license']),
             'implementation_license':f['adaptation'].get('implementation_license','MIT'),
             'scope':f['adaptation']['scope'],'engines':f['engines'],
             'preview_url':f['preview_url']}
            for f in capabilities()['families'] if f['adaptation']]


def node(tag, attrs=None, children=None, content=None, ident=None, motion=None):
    return {'tag': tag, 'attrs': attrs or {}, 'children': children or [], 'text': content,
            'id': ident, 'motion': motion or []}


def group(children, x=0, y=0, ident=None, motion=None):
    return node('g', {'transform': f'translate({x} {y})'}, [node('g', {}, children, ident=ident, motion=motion)])


def tween(start, duration, before, after, ease='power2.out'):
    # JSON round-trips an IEEE-754 time without loss. Decimal rounding can move
    # an instantaneous tick past an exact video frame (e.g. 2/3 -> .666667),
    # making both renderers hold the previous position for one extra frame.
    return {'start': start, 'duration': duration, 'from': before, 'to': after, 'ease': ease}


def label(value, x, y, width, ink, size=56, minimum=30, lines=3, weight=600, anchor='start', ident=None, motion=None):
    fit = fit_lines(value, width, size, minimum, lines)
    attrs = {'x': x, 'y': y, 'fill': ink, 'font-size': fit['font_size'], 'font-weight': weight,
             'text-anchor': anchor, 'data-template-text': 'true', 'data-slot-width': width,
             'data-full-text': value}
    children = [node('tspan', {'x': x, 'dy': 0 if i == 0 else fit['line_height']}, content=line) for i, line in enumerate(fit['lines'])]
    return node('text', attrs, children, ident=ident, motion=motion)


def kinetic(p, palette):
    d = p['duration']; ink = palette['ink']; accent = palette['accent']; muted = palette['muted']; out = []
    out += [node('line', {'x1': 90, 'y1': y, 'x2': 990, 'y2': y, 'stroke': muted, 'stroke-width': 2}) for y in [540, 1420]]
    for i, phrase in enumerate(p['phrases']):
        y = 640 + i * (720 / len(p['phrases'])); start = d * (.08 + i * .13)
        size=min(62,int((720/len(p['phrases'])-35)/3/1.22))
        fitted=fit_lines(phrase['text'],750,size,32,3)
        underline=5+(len(fitted['lines'])-1)*fitted['line_height']+fitted['font_size']*.28+12
        content = [label(f'{i+1:02}', 0, 0, 80, muted, 28, 28, 1),
                   label(phrase['text'], 105, 5, 750, ink, size, 32, 3),
                   group([node('rect', {'x': 0, 'y': 0, 'width': 650, 'height': 8, 'fill': accent,'data-template-decoration':'underline'})],
                         x=105, y=underline, ident=f'kg-rule-{i}', motion=[tween(start + .08, d * .15, {'scaleX': 0}, {'scaleX': 1})])]
        out.append(group(content, x=90, y=y, ident=f'kg-phrase-{i}', motion=[tween(start, d * .16, {'x': -85 if i % 2 == 0 else 85, 'opacity': 0}, {'x': 0, 'opacity': 1})]))
    out.append(group([node('rect', {'x': -28, 'y': -28, 'width': 56, 'height': 56, 'fill': accent})],
                     x=940, y=520, ident='kg-turn', motion=[tween(0, d * .85, {'rotation': -30, 'scaleX': .5, 'scaleY': .5}, {'rotation': 90, 'scaleX': 1, 'scaleY': 1}, 'power2.inOut')]))
    return out


def causal(p, palette):
    d = p['duration']; out = []; ink = palette['ink']; accent = palette['accent']; bg = palette['background']
    positions = {n['id']: (190 if i % 2 == 0 else 860, 630 + i * 170) for i, n in enumerate(p['nodes'])}
    for i, edge in enumerate(p['edges']):
        x1, y1 = positions[edge['from']]; x2, y2 = positions[edge['to']]
        rail=95 if i%2==0 else 985
        points=[(x1,y1+42),(x1,y1+72),(rail,y1+72),(rail,y2-72),(x2,y2-72),(x2,y2-42)]
        path='M'+'L'.join(f'{x} {y}' for x,y in points)
        start=d*(.12+i*.09);length=d*.23
        out.append(node('path', {'d': path, 'fill': 'none', 'stroke': accent, 'stroke-width': 6, 'pathLength': 1000,
                                'stroke-dasharray': 1000}, ident=f'cp-edge-{i}', motion=[tween(start,length, {'strokeDashoffset': 1000}, {'strokeDashoffset': 0}, 'none')]))
        distances=[abs(b[0]-a[0])+abs(b[1]-a[1]) for a,b in zip(points,points[1:])];total=sum(distances);offset=0
        moves=[tween(start,0,{'opacity':0},{'opacity':1},'none')]
        for a,b,distance in zip(points,points[1:],distances):
            segment=length*distance/total
            moves.append(tween(start+offset,segment,{'x':a[0]-x1,'y':a[1]-(y1+42)},{'x':b[0]-x1,'y':b[1]-(y1+42)},'none'));offset+=segment
        moves.append(tween(start+length,0,{'opacity':1},{'opacity':0},'none'))
        out.append(group([node('circle',{'cx':0,'cy':0,'r':10,'fill':ink})],x=x1,y=y1+42,ident=f'cp-pulse-{i}',motion=moves))
        out.append(node('polygon',{'points':f'{x2},{y2-42} {x2-10},{y2-60} {x2+10},{y2-60}','fill':accent},ident=f'cp-arrow-{i}',motion=[tween(start+length*.9,0,{'opacity':0},{'opacity':1},'none')]))
    for i, item in enumerate(p['nodes']):
        x, y = positions[item['id']]; right = x < 500
        content = [node('circle', {'cx': 0, 'cy': 0, 'r': 42, 'fill': bg, 'stroke': ink, 'stroke-width': 5}),
                   label(str(i + 1), 0, 12, 60, accent, 34, 34, 1, anchor='middle'),
                   label(item['label'], 86 if right else -680, -35, 570, ink, 37, 32, 3)]
        out.append(group(content, x=x, y=y, ident=f'cp-node-{i}', motion=[tween(d * (.03 + i * .12), d * .13, {'y': 24, 'opacity': 0}, {'y': 0, 'opacity': 1})]))
    return out


def exploded(p, palette):
    d = p['duration']; out = []; ink = palette['ink']; accent = palette['accent']; muted = palette['muted']; n = len(p['parts']); gap = p['separation']
    for x in range(90, 1000, 90): out.append(node('line', {'x1': x, 'y1': 560, 'x2': x, 'y2': 1450, 'stroke': muted, 'stroke-width': .7, 'opacity': .22}))
    for y in range(560, 1451, 90): out.append(node('line', {'x1': 90, 'y1': y, 'x2': 990, 'y2': y, 'stroke': muted, 'stroke-width': .7, 'opacity': .22}))
    top = 1000 - (n - 1) * gap / 2; bottom = 1000 + (n - 1) * gap / 2
    out.append(node('path', {'d': f'M150 {top}H120V{bottom}H150M108 {top}H132M108 {bottom}H132', 'fill': 'none', 'stroke': accent, 'stroke-width': 3}))
    for i, part in enumerate(p['parts']):
        assembled = 1000 + (i - (n - 1) / 2) * 52; target = 1000 + (i - (n - 1) / 2) * gap; delta = target - assembled
        shape = part['shape']; pieces = []
        style = {'fill': palette['background'], 'stroke': ink, 'stroke-width': 4}
        if shape == 'plate':
            pieces = [node('path', {**style, 'd': 'M-170 0L-110 -35H170L110 0Z M-170 0V22H110L170 -13V-35 M110 0V22'})]
        elif shape == 'cylinder':
            pieces = [node('path', {**style, 'd': 'M-128 -22V40C-128 80 128 80 128 40V-22'}), node('ellipse', {**style, 'cx': 0, 'cy': -22, 'rx': 128, 'ry': 35})]
        elif shape == 'coil':
            points = ' '.join(f'{-140 + j * 20},{-26 if j % 2 == 0 else 26}' for j in range(15))
            pieces = [node('polyline', {'points': points, 'fill': 'none', 'stroke': accent, 'stroke-width': 7, 'stroke-linejoin': 'round'})]
        else:
            pieces = [node('path', {**style, 'd': 'M-145 -35H145V35H-145Z'})]
            pieces += [node('line', {'x1': x, 'y1': -32, 'x2': x + 35, 'y2': 32, 'stroke': muted, 'stroke-width': 3}) for x in range(-130, 111, 30)]
        pieces.append(node('line', {'x1': -185, 'y1': 0, 'x2': 185, 'y2': 0, 'stroke': muted, 'stroke-width': 1, 'stroke-dasharray': '6 8'}))
        out.append(group(pieces, x=500, y=assembled, ident=f'eb-part-{i}', motion=[
            tween(d * .12, d * .30, {'y': 0}, {'y': delta}, 'power2.inOut'),
            tween(d * .75, d * .20, {'y': delta}, {'y': 0}, 'power2.inOut')]))
        callout = [node('path', {'d': f'M690 {target}H735', 'stroke': accent, 'stroke-width': 3}),
                   label(part['label'], 750, target - 8, 240, ink, 37, 32, 3)]
        out.append(node('g', {}, callout, ident=f'eb-callout-{i}', motion=[
            tween(d * .37, d * .08, {'opacity': 0}, {'opacity': 1}),
            tween(d * .69, d * .06, {'opacity': 1}, {'opacity': 0})]))
    out.append(label('Ayrılma → açıklama → birleşme', 90, 1480, 900, muted, 32, 32, 1))
    return out


def isometric(p, palette):
    d = p['duration']; out = []; ink = palette['ink']; accent = palette['accent']; muted = palette['muted']; bg = palette['background']
    series = p['series']; maximum = max(n['value'] for n in series); count = len(series)
    spacing = min(175, 760 / count); bases = [(160 + i * spacing, 1240 - i * 55) for i in range(count)]
    for row in range(5):
        out.append(node('path', {'d': f'M95 {1100+row*70}L850 {860+row*70}L990 {940+row*70}', 'fill': 'none', 'stroke': muted, 'stroke-width': 1, 'opacity': .35}))
    for i, item in enumerate(series):
        x, y = bases[i]; h = 390 * item['value'] / maximum
        # A zero value has no vertical volume. The visible top plane is the
        # common isometric footprint, not a fictitious positive baseline.
        shapes = [node('path', {'d': f'M0 0V{-h}L95 {-h+34}V34Z', 'fill': accent, 'stroke': ink, 'stroke-width': 2,
                                'data-metric-value':item['value'],'data-metric-height':h}),
                  node('path', {'d': f'M95 34V{-h+34}L145 {-h+9}V9Z', 'fill': muted, 'stroke': ink, 'stroke-width': 2}),
                  node('path', {'d': f'M0 {-h}L50 {-h-25}L145 {-h+9}L95 {-h+34}Z', 'fill': bg, 'stroke': ink, 'stroke-width': 3})]
        out.append(group(shapes, x=x, y=y, ident=f'ip-volume-{i}', motion=[tween(d * (.10 + i * .07), d * .32, {'scaleY': .02}, {'scaleY': 1}, 'power2.inOut')]))
        out.append(label(f"{item['value']:g}", x + 20, y - h - 45, 160, ink, 40, 28, 1, ident=f'ip-value-{i}', motion=[tween(d * (.30+i*.07), d*.1, {'opacity':0,'y':20}, {'opacity':1,'y':0})]))
        out.append(label(item['label'], x - 10, y + 95, 150, ink, 35, 25, 3))
    route = 'M' + 'L'.join(f'{x+70} {y+35}' for x, y in bases)
    out.append(node('path', {'d': route, 'fill': 'none', 'stroke': accent, 'stroke-width': 5, 'stroke-dasharray': '10 8'}))
    x0,y0=bases[0]; moves=[]
    for i in range(count-1):
        a=bases[i]; b=bases[i+1]
        moves.append(tween(d*(.45+i*.10),d*.10,{'x':a[0]-x0,'y':a[1]-y0},{'x':b[0]-x0,'y':b[1]-y0},'none'))
    out.append(group([node('circle',{'cx':0,'cy':0,'r':14,'fill':ink,'stroke':bg,'stroke-width':4})],x=x0+70,y=y0+35,ident='ip-process-marker',motion=moves))
    out.append(label('Ölçek: ' + p['unit'], 90, 1490, 900, muted, 32, 32, 1))
    return out


def compile_scene(brief):
    spec = validate_spec(brief['template_family']); family = spec['id']; p = spec['parameters']; palette = FAMILIES[family]['palette']; d = p['duration']
    if family in development_templates.FAMILIES:
        tree=development_templates.frame_tree(spec,0)
        return {'schema_version':1,'family':family,'version':VERSION,'width':1080,'height':1920,'duration':d,
                'palette':p['palette'],'nodes':tree['children'],'module':'development84','spec':spec,
                'parameters_sha256':digest(p),'audio_timing':'caller_supplied_cues_not_inferred_speech',
                'real_caller_media_verified':False}
    nodes = [node('rect', {'x':0,'y':0,'width':1080,'height':1920,'fill':palette['background']}),
             label(FAMILIES[family]['name'],90,115,900,palette['muted'],28,28,1),
             label(p['title'],90,220,900,palette['ink'],64,40,4)]
    if family in style_templates.FAMILIES:
        nodes += style_templates.compile_nodes(family,p,palette,node,group,label,tween)
    else:
        nodes += {'kinetic-grid':kinetic,'causal-path':causal,'exploded-blueprint':exploded,'isometric-process':isometric}[family](p,palette)
    for i, cue in enumerate(p['cues']):
        # The first cue must exist at frame zero, before the paused timeline
        # advances. Later cues enter at their explicit start boundary.
        motion=[] if cue['start']==0 else [tween(cue['start'],0,{'opacity':0},{'opacity':1},'none')]
        motion.append(tween(cue['end'],0,{'opacity':1},{'opacity':0},'none'))
        nodes.append(label(cue['text'],540,1660,890,palette['ink'],43,32,3,anchor='middle',ident=f'family-cue-{i}',motion=motion))
    nodes.append(label('Yerel şablon · İnsan incelemesi bekliyor',90,1850,900,palette['muted'],25,25,1))
    return {'schema_version':1,'family':family,'version':VERSION,'width':1080,'height':1920,'duration':d,
            'palette':palette,'nodes':nodes,'parameters_sha256':digest(p),'audio_timing':'caller_supplied_cues_not_inferred_speech'}


def initial_motion(motion):
    value={'x':0,'y':0,'scaleX':1,'scaleY':1,'rotation':0,'opacity':1};seen=set()
    for m in sorted(motion,key=lambda m:m['start']):
        for k,v in m['from'].items():
            if k not in seen:value[k]=v;seen.add(k)
    return value


def _terminal_cover(tree,parameters):
    # Static cover typography is separate from the seek-safe cell animation.
    # Retain every input character; prefer whitespace boundaries for short words.
    def wrap(value,columns):
        rows=[]
        while len(value)>columns:
            spaces=[i+1 for i,c in enumerate(value[:columns]) if c.isspace()]
            end=spaces[-1] if spaces else columns
            rows.append(value[:end]);value=value[end:]
        if value:rows.append(value)
        return rows
    for size in (42,40,38,36,34,32):
        rows=[row for value in parameters['lines'] for row in wrap(value,800//size)]
        leading=math.ceil(size*1.2)
        if len(rows)*leading<=500:break
    else:invalid('terminal kapak metni güvenli alana sığmıyor')
    replaced=0
    def visit(node):
        nonlocal replaced
        children=node.get('children',[])
        glyphs=[child for child in children if child.get('tag')=='text'
                and child.get('attrs',{}).get('xml:space')=='preserve'
                and child['attrs'].get('font-size')=='28']
        if glyphs:
            if replaced:invalid('terminal kapak metin yapısı belirsiz')
            ink=glyphs[0]['attrs']['fill'];first=children.index(glyphs[0]);identities={id(n) for n in glyphs}
            text=[{'tag':'text','attrs':{'x':'130','y':str(740+i*leading),'fill':ink,
                   'font-size':str(size),'xml:space':'preserve'},'children':[{'tag':'#text','text':value}]}
                  for i,value in enumerate(rows)]
            node['children']=[n for n in children[:first] if id(n) not in identities]+text+[n for n in children[first:] if id(n) not in identities]
            replaced+=1
        attrs=node.get('attrs',{})
        if node.get('tag')=='path' and attrs.get('opacity')=='0.6' and re.fullmatch(r'M130 [0-9.]+H950',attrs.get('d','')):
            attrs['d']='M130 690H950'
        if node.get('tag')=='text' and attrs.get('x')=='130' and attrs.get('y')=='1380':
            node['children']=[{'tag':'#text','text':str(sum(len(v) for v in parameters['lines']))+' karakter · statik kapak özeti'}]
        for child in node.get('children',[]):visit(child)
    visit(tree)
    if replaced!=1:invalid('terminal kapak hücreleri bulunamadı')
    return tree


def svg_markup(scene,seconds=None,*,cover=False):
    if type(cover) is not bool:invalid('kapak seçimi boolean olmalı')
    if scene.get('module'):
        covered={'constrained-part-section','iris-silhouette-chase','terminal-raster','dimension-construction'}
        parameters=None
        if cover and scene['spec']['id'] in covered:
            parameters=development_templates.validate_spec(scene['spec'])['parameters']
            if scene['spec']['id']=='constrained-part-section':seconds=parameters['duration']
        tree=development_templates.frame_tree(scene['spec'],0 if seconds is None else seconds)
        if cover and scene['spec']['id']=='terminal-raster':tree=_terminal_cover(tree,parameters)
        captions={'iris-silhouette-chase':('38',1430),'dimension-construction':('30',600)}
        if cover and scene['spec']['id'] in captions:
            size,minimum=captions[scene['spec']['id']];found=[]
            def caption(node):
                children=node.get('children',[])
                if (node.get('tag')=='g' and 'opacity' in node.get('attrs',{}) and children
                        and all(n.get('tag')=='text' and n.get('attrs',{}).get('font-size')==size
                                and minimum<=float(n['attrs'].get('y','0'))<=minimum+100 for n in children)):
                    node['attrs']['opacity']='1';found.append(node)
                for child in children:caption(child)
            caption(tree)
            if len(found)!=1:invalid('kapak açıklamasının metin yapısı belirsiz')
        def element(n):
            if n['tag']=='#text':return html.escape(n['text'])
            attrs=' '.join(f'{k}="{html.escape(v,quote=True)}"' for k,v in n['attrs'].items())
            return '<'+n['tag']+' '+attrs+'>'+''.join(element(c) for c in n['children'])+'</'+n['tag']+'>'
        return element(tree)
    if seconds is not None:
        frame=round(seconds*30)/30
        if abs(seconds-frame)<=.0000005:seconds=frame
    def sampled(motion):
        value=initial_motion(motion)
        if seconds is None:return value
        for m in sorted(motion,key=lambda m:m['start']):
            if seconds<m['start']:continue
            t=1 if m['duration']==0 else max(0,min(1,(seconds-m['start'])/m['duration']))
            if m['ease']=='power2.out':t=1-(1-t)**3
            elif m['ease']=='power2.inOut':t=4*t**3 if t<.5 else 1-(-2*t+2)**3/2
            for k,v in m['to'].items():value[k]=m['from'][k]+(v-m['from'][k])*t
        return value
    def element(n):
        attrs=' '.join(f'{k}="{html.escape(str(v),quote=True)}"' for k,v in n['attrs'].items())
        body=html.escape(n['text']) if n['text'] is not None else ''.join(element(c) for c in n['children'])
        raw=f'<{n["tag"]} {attrs}>{body}</{n["tag"]}>'
        if n['id']:
            v=sampled(n['motion']);transform=f'translate({v["x"]} {v["y"]}) rotate({v["rotation"]}) scale({v["scaleX"]} {v["scaleY"]})'
            dash=f' stroke-dashoffset="{v["strokeDashoffset"]}"' if 'strokeDashoffset' in v else ''
            return f'<g id="{n["id"]}" transform="{transform}" opacity="{v["opacity"]}"{dash}>{raw}</g>'
        return raw
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" role="img" aria-label="Parametrik şablon sahnesi">'+''.join(element(n) for n in scene['nodes'])+'</svg>'


def _export_license(package_root):
    """Carry the first-party grant without relabeling bundled third-party work."""
    from .local_state import guard_control
    root=Path(package_root)
    notice='notices/StoryMotion-MIT.txt';scope_notice='notices/StoryMotion-MIT-SCOPE.txt'
    try:
        source=guard_control(root,'LICENSE').read_bytes()
        licensed=guard_control(root,'vendor/'+notice).read_bytes()
        scope=guard_control(root,'vendor/'+scope_notice).read_bytes()
        if source!=licensed or not source.startswith(b'MIT License\n') or not scope:
            invalid('StoryMotion MIT notice missing or different from the current source LICENSE')
        text=licensed.decode('utf-8');scope_text=scope.decode('utf-8')
    except (OSError,UnicodeError):
        invalid('StoryMotion MIT notice missing or different from the current source LICENSE')
    return ({'spdx':'MIT','scope':'StoryMotion_original_code_and_documentation_only',
             'notice_path':'assets/'+notice,'notice_sha256':hashlib.sha256(licensed).hexdigest(),
             'scope_notice_path':'assets/'+scope_notice,'scope_notice_sha256':hashlib.sha256(scope).hexdigest(),
             'third_party_terms':'Separate third-party notices and licenses remain under assets; no grant to third-party code, fonts, runtime components or caller media.'},
            text,scope_text)


def build(payload,out,package_root):
    brief=payload['brief'];scene=compile_scene(brief);out=Path(out);assets=out/'assets'
    controlled=['index.html','cover.html','cover.svg','template-motion.mjs','template-scene.json','template-selection.json',
                'hyperframes.json','index.motion.json','timeline.json','profile.json','caption.txt','subtitles.srt','BRIEF.md']
    from .local_state import guard_control
    for name in controlled:guard_control(out,name)
    guard_control(out,'assets','dir')
    for path in assets.rglob('*'):
        guard_control(out,path.relative_to(out),'dir' if path.is_dir() else 'file')
    if assets.is_symlink() or any(p.is_symlink() for p in assets.rglob('*')) or any((out/n).is_symlink() or (out/(n+'.tmp')).is_symlink() for n in controlled):
        invalid('şablon çıktı yolu bağlantılı; dosya yazılmadı')
    licensing,license_text,license_scope=_export_license(package_root)
    assets.mkdir(parents=True,exist_ok=True)
    shutil.copytree(package_root/'vendor',assets,dirs_exist_ok=True)
    from .edit_plan import verify_staged_assets
    verify_staged_assets(payload,out)
    module_files=development_templates.stage(package_root,out) if scene.get('module') else []
    shutil.copyfile(package_root/'renderers/template-motion.mjs',out/'template-motion.mjs')
    family=brief['template_family']['id'];adaptation=style_templates.adaptation(family)
    write_json(out/'template-scene.json',scene);write_json(out/'template-selection.json',{'template_family':brief['template_family'],'source_context':brief['template_context'],'subject':brief.get('template_subject'),
        'render_adapter':payload.get('render_engine','hyperframes'),'source_styles_implemented':style_templates.implemented_sources(family),
        'style_adaptation':adaptation,'storymotion_license':licensing,'audio_sha256':payload.get('audio_sha256'),'publication_acceptance':'pending','caller_media_status':'proxy_only_not_decoded' if scene.get('module') and development_templates.requires_media(family) else 'not_applicable'})
    bindings=[]
    def visit(n):
        if n.get('id') and n.get('motion'):
            bindings.append({'id':n['id'],'motion':n['motion']})
        for c in n['children']:visit(c)
    for n in scene['nodes']:visit(n)
    # One paused GSAP clock drives the exact shared stateless sampler. A plain
    # object setter runs even when a host suppresses timeline callbacks during
    # seeks. SVG matrices are written directly on non-clip wrappers: GSAP's
    # SVG origin cache must not move a scaled chart's baseline across seeks.
    sampler=(package_root/'renderers/template-motion.mjs').read_text()
    if '</script' in sampler.lower():invalid('yerel sampler script sınırı geçersiz')
    sampler=sampler.replace('export function ','function ')
    program=sampler+'\nconst scene='+canonical(scene).replace('<','\\u003c')+';\nconst bindings='+json.dumps(bindings)+';\n'+"""
    const compiled=scene.module?StoryMotionTemplates.compileStaged(scene.spec):null;
    function paint(seconds){if(compiled){const tree=StoryMotionTemplates.parseSvg(compiled.render(videoFrameTime(seconds)));document.getElementById('family-module').replaceChildren(StoryMotionTemplates.svgDom(tree,document));return;}for(const binding of bindings){const n=document.getElementById(binding.id),v=sampleMotion(binding.motion,seconds);
      n.setAttribute('transform',`translate(${v.x} ${v.y}) rotate(${v.rotation}) scale(${v.scaleX} ${v.scaleY})`);
      n.setAttribute('opacity',v.opacity);if(v.strokeDashoffset!==undefined)n.setAttribute('stroke-dashoffset',v.strokeDashoffset);
    }}
    let current=0;const cursor={get seconds(){return current;},set seconds(value){current=value;paint(value);}};
    const tl=gsap.timeline({paused:true});
    """+f"tl.fromTo(cursor,{{seconds:0}},{{seconds:{brief['duration']},duration:{brief['duration']},ease:'none',immediateRender:false}},0);"+"paint(0);window.__timelines['root']=tl;"
    audio=''
    if brief.get('audio'):
        source=Path(payload['audio_source']);target=assets/('narration'+source.suffix.lower());shutil.copy2(source,target)
        audio=f'<audio id="family-narration" class="clip" src="assets/{target.name}" data-start="0" data-duration="{payload["audio_duration"]}" data-track-index="3" data-volume="1"></audio>'
    styles="""@font-face{font-family:Schibsted;src:url('assets/fonts/schibsted-grotesk-latin-ext-wght-normal.woff2')}@font-face{font-family:Schibsted;src:url('assets/fonts/schibsted-grotesk-latin-wght-normal.woff2');unicode-range:U+000D,U+0020-007E,U+00A0-00AC,U+00AE-00FF,U+0102,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,U+0303-0304,U+0308,U+0323,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+2044,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}html,body{margin:0;width:100%;height:100%;overflow:hidden;font-family:Schibsted,sans-serif}#root{width:100%;height:100%;position:relative;overflow:hidden}svg{display:block;font-family:Schibsted,sans-serif}text{font-family:Schibsted,sans-serif}"""
    head=f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{html.escape(brief["title"])}</title><script src="assets/gsap.min.js"></script><style>{styles}</style></head>'
    if scene.get('module'):head=head.replace('</head>','<script src="template-registry/bundle.js"></script></head>')
    visual=svg_markup(scene)
    if scene.get('module'):visual='<div id="family-module">'+visual+'</div>'
    markup=head+f'<body><div id="root" data-composition-id="root" data-width="1080" data-height="1920" data-duration="{brief["duration"]}" data-fps="30">{visual}{audio}</div><script>(()=>{{'+program+'})();</script></body></html>'
    write_private(out/'index.html',markup)
    cover_svg=svg_markup(scene,brief['duration']*.55,cover=True)
    write_private(out/'cover.svg',cover_svg)
    # Cover uses the same family, held at its constructed static layout, not a generic box.
    write_private(out/'cover.html',head+'<body>'+cover_svg+'</body></html>')
    write_json(out/'hyperframes.json',{'$schema':'https://hyperframes.heygen.com/schema/hyperframes.json','paths':{'assets':'assets','blocks':'compositions'}})
    target='#family-module' if scene.get('module') else {'kinetic-grid':'#kg-phrase-0','causal-path':'#cp-node-0','exploded-blueprint':'#eb-part-0','isometric-process':'#ip-volume-0',
            'liquid-merge':'#lm-drop-0','bauhaus-modules':'#bm-tile-0','pixel-journey':'#pj-motif-0'}[family]
    assertions=[
        {'kind':'appearsBy','selector':target,'bySec':brief['duration']*.6},
        {'kind':'staysInFrame','selector':target}]
    assertions.append({'kind':'keepsMoving','withinSelector':'#root','maxStaticSec':max(2,brief['duration']*.6)})
    write_json(out/'index.motion.json',{'duration':brief['duration'],'assertions':assertions,
                                    'owned_graphic_motion_required':False})
    write_json(out/'timeline.json',{'duration':brief['duration'],'alignment':brief['alignment'],'playback_rate':1,'scenes':brief['scenes'],'cues':brief['cues'],'family':brief['template_family']['id']})
    write_json(out/'profile.json',payload['profile'])
    write_private(out/'caption.txt',brief['caption']+'\n')
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    write_private(out/'subtitles.srt','\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(brief['cues']))+'\n')
    note=''
    if adaptation:
        if adaptation.get('original_implementation'):
            note='\nOriginal archived implementation; source reference ID: '+adaptation['source_item_id']+'\n'+adaptation['scope']+'\nNative, caller-media and commercial acceptance pending.\n'
        else:note='\n\n'+adaptation['repository']+'/tree/'+adaptation['commit']+'\n'+adaptation['scope']+'\n'+adaptation['copyright']+' · MIT\nLicense: assets/notices/mg-styles-15-MIT.txt\n'
    # A space after a line-ending colon preserves the complete notice text
    # without looking like a Windows drive path to the existing privacy gate.
    license_note='\n\n## StoryMotion original-code license\n\n'+license_scope+'\nNotice: '+licensing['notice_path']+'\n\n'+license_text.replace(':\n',': \n')
    write_private(out/'BRIEF.md','# '+brief['title']+'\n\nGenerated by StoryMotion '+__version__+' (local deterministic templates, no model call).\n\n'+brief['brief']+'\n\n'+brief['script']+'\n\nYerel parametrik şablon; sağlayıcı çağrısı yok. İnsan/yayın kabulü bekliyor.\n'+note+license_note)
    return ['index.html','hyperframes.json','index.motion.json','timeline.json','profile.json','cover.svg','cover.html','caption.txt','subtitles.srt','BRIEF.md','template-motion.mjs','template-scene.json','template-selection.json']+module_files+[p.relative_to(out).as_posix() for p in sorted(assets.rglob('*')) if p.is_file()]
