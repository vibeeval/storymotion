"""Small pinned reference/palette metadata. No imports, remote fetch or execution."""
import copy
import hashlib
import json
import re

from . import development_templates, template_families
from .local_state import guard_control
from .security import WorkflowError, digest, file_hash, scan_bytes

PINS = {
    'catalog/source-catalog.json': '1edb8c3ff19bf8bf490729303bcca13e1328b426fe9db912d60134a53d82aac9',
    'catalog/style-gallery.json': 'e8db3cfcdb1eb6cee77a5f969b502d2bbd371d04c257c2a2917bc3f381d56bb4',
    'catalog/style-adapters.json': '9e6e53341c54c52d4d3f4449747336c2a403c6c4eda2c729c1ff9e0c377e3958',
}
COLORS = {'background', 'ink', 'muted', 'accent'}


def fail():
    raise WorkflowError('REFERENCE_CATALOG_INVALID_OR_UNAVAILABLE')


def pairs(rows):
    value = {}
    for key, item in rows:
        if key in value or key in {'__proto__', 'constructor', 'prototype'}:
            fail()
        value[key] = item
    return value


def pinned(name):
    raw = guard_control(development_templates.ROOT, name).read_bytes()
    if len(raw) > 100000 or hashlib.sha256(raw).hexdigest() != PINS[name] or scan_bytes(raw):
        fail()
    return json.loads(raw, object_pairs_hook=pairs)


def rows(value, key):
    if (type(value) is not dict or set(value) != {'schema_version', key}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value[key]) is not list or not 1 <= len(value[key]) <= 100):
        fail()
    seen = set()
    for row in value[key]:
        if type(row) is not dict or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}', row.get('id', '')):
            fail()
        if row['id'] in seen or not isinstance(row.get('name'), str) or not 1 <= len(row['name']) <= 120:
            fail()
        seen.add(row['id'])
    return value[key]


def metadata(kind):
    """Validate exact local evidence, including notices and the real palette scope."""
    if kind == 'references':
        result = rows(pinned('catalog/source-catalog.json'), kind)
        adapters = pinned('catalog/style-adapters.json')['adapters']
        expected = {row['source_style_id']: row for row in adapters}
        if set(expected) != {r['id'] for r in result}:
            fail()
        for row in result:
            adapter = expected[row['id']]; provenance = adapter['provenance']
            target = {
                'id': adapter['source_style_id'], 'name': provenance['source_name'], 'kind': 'technique_reference',
                'repository_url': provenance['repository'], 'reference_urls': [p['url'] for p in provenance['paths']],
                'commit': provenance['commit'], 'license': 'MIT', 'attribution': provenance['copyright'],
                'notice_path': provenance['notice_path'], 'notice_sha256': provenance['notice_sha256'],
                'license_scope': 'bounded_code_only', 'asset_rights': 'not_assessed', 'reference_only': True,
                'preview_url': None, 'preview_state': 'missing_preview', 'family_ids': [adapter['family_id']],
                'planning_mapping': None,
            }
            if digest(row) != digest(target) or adapter['family_id'] not in template_families.FAMILIES:
                fail()
            if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', row['repository_url']):
                fail()
            if not re.fullmatch(r'[a-f0-9]{40}', row['commit']) or any(
                    not url.startswith(row['repository_url'] + '/blob/' + row['commit'] + '/')
                    or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_./-]+', url) for url in row['reference_urls']):
                fail()
            if (row['notice_path'] != 'vendor/notices/mg-styles-15-MIT.txt'
                    or file_hash(guard_control(development_templates.ROOT, row['notice_path'])) != row['notice_sha256']):
                fail()
    elif kind == 'styles':
        result = rows(pinned('catalog/style-gallery.json'), kind)
        for row in result:
            if (set(row) != {'id', 'name', 'kind', 'palette', 'origin_family', 'license_scope', 'preview_url',
                            'preview_state', 'compatibility', 'planning_mapping', 'excluded_family_ids'}
                    or row['kind'] != 'palette' or row['origin_family'] not in
                    {'kinetic-grid', 'causal-path', 'exploded-blueprint', 'isometric-process'}
                    or row['license_scope'] != 'MIT_original_StoryMotion_palette_only' or row['preview_url'] is not None
                    or row['preview_state'] != 'palette_values_only' or row['planning_mapping'] is not None
                    or row['compatibility'] != 'development_common_palette'
                    or type(row['excluded_family_ids']) is not list
                    or any(type(n) is not str or n not in development_templates.FAMILIES for n in row['excluded_family_ids'])
                    or len(set(row['excluded_family_ids'])) != len(row['excluded_family_ids'])
                    or type(row['palette']) is not dict
                    or set(row['palette']) != COLORS or any(not isinstance(c, str) or not re.fullmatch(r'#[0-9A-F]{6}', c)
                                                           for c in row['palette'].values())
                    or row['palette'] != template_families.FAMILIES[row['origin_family']]['palette']):
                fail()
        # This is the existing public development-validator common palette input,
        # not an inferred module-specific field or a new editor declaration.
        development_templates.manifest()
        result = [dict(row, family_ids=sorted(set(development_templates.FAMILIES) - set(row['excluded_family_ids']))) for row in result]
    else:
        fail()
    return copy.deepcopy(result)


def catalog(dashboard, kind, account):
    try:
        dashboard.taxonomy.account(account)  # registered account + current-source gate
        result = metadata(kind)
        value = {'schema_version': 1, 'account': account, 'kind': kind, 'items': result,
                 'count': len(result), 'provider_calls': 0, 'actual_render': False,
                 'planning_supported': False}
        return dict(value, revision=digest(value))
    except (OSError, ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        fail()
