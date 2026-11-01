"""Versioned, inert editor hints. Existing template validators remain authoritative.

No renderer introspection or caller-selected imports. Unknown declaration dialects
and absent fields remain JSON fallbacks, including undeclared common metadata.
"""
import copy
import hashlib
import json
import math
import sqlite3

from . import development_templates, template_families
from .account_packs import load_pack
from .local_state import guard_control
from .security import WorkflowError, canonical, digest, file_hash

CONTRACT_SHA256 = 'e7a6dc385d63325d145bd3b6d91d87ffe50f36cb6937d5bd72afda1add586d11'
BASE_EXAMPLES_SHA256 = 'd572948af9ce89c07a6e405e9b7043213d8fabaed83e4c49e0c8114a848ff74d'
UNSAFE_KEYS = {'__proto__', 'prototype', 'constructor'}
MAX_SAFE_INTEGER = 9007199254740991


def fail(message='invalid bounded data'):
    raise WorkflowError('TEMPLATE_FIELDS: ' + message)


def bounded(value):
    count = 0

    def walk(v, depth):
        nonlocal count
        count += 1
        if depth > 24 or count > 20000:
            fail('data too deep or large')
        if isinstance(v, dict):
            for key, item in v.items():
                if not isinstance(key, str) or key in UNSAFE_KEYS:
                    fail('unsafe object key')
                walk(item, depth + 1)
        elif isinstance(v, list):
            for item in v:
                walk(item, depth + 1)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if not math.isfinite(v) or abs(v) > MAX_SAFE_INTEGER:
                fail('number must be finite and within the safe Number range')
        elif v is not None and not isinstance(v, (str, bool)):
            fail()
    walk(value, 0)
    return value


def parse_raw(raw):
    if not isinstance(raw, str) or not 0 < len(raw.encode()) <= 100000:
        fail('bounded raw JSON required')

    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value or key in UNSAFE_KEYS:
                fail('duplicate or unsafe object key')
            value[key] = item
        return value

    def floating(token):
        value = float(token)
        if not math.isfinite(value):
            fail('number is not representable as a finite Number')
        if value == 0 and any(c in '123456789' for c in token.split('e')[0].split('E')[0]):
            fail('number underflows Number; use a representable value')
        # Match JSON.parse -> JSON.stringify on the existing browser prepare
        # route: 1.0 and 1e0 are Number(1), including integer-only controls.
        return int(value) if value.is_integer() and abs(value) <= MAX_SAFE_INTEGER else value

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=floating,
                           parse_constant=lambda token: fail('non-JSON number'))
        return bounded(value)
    except (ValueError, TypeError, RecursionError, OverflowError):
        fail('invalid JSON; draft retained')


def declarations():
    value = development_templates.pinned_json('catalog/template-field-contracts.json', CONTRACT_SHA256)
    bounded(value)
    if (set(value) != {'schema_version', 'input_version', 'development_manifest_sha256', 'baseline_sources', 'declarations'}
            or value['schema_version'] != 1 or value['input_version'] != template_families.VERSION
            or value['development_manifest_sha256'] != development_templates.SOURCE_MANIFEST_SHA256
            or set(value['declarations']) != set(template_families.FAMILIES)
            or set(value['baseline_sources']) != {'storymotion/template_families.py', 'storymotion/style_templates.py'}):
        fail('contract provenance mismatch')
    development_templates.manifest()
    for name, expected in value['baseline_sources'].items():
        if file_hash(guard_control(development_templates.ROOT, name)) != expected:
            fail('baseline declaration source changed')
    return value


def descriptor(raw, depth=0):
    """Map only explicit dialects. Never infer item shapes/limits from examples."""
    if depth > 20:
        fail('schema too deep')
    unknown = {'type': 'unknown', 'notes': ['unsupported declaration; edit JSON']}
    number = lambda v: type(v) in (int, float) and math.isfinite(v)
    if isinstance(raw, list):
        if len(raw) == 2 and all(number(v) for v in raw) and raw[0] <= raw[1]:
            return {'type': 'number', 'minimum': raw[0], 'maximum': raw[1],
                    'notes': ['numeric tuple declaration; scalar control only']}
        return unknown
    if not isinstance(raw, dict) or not raw:
        return unknown
    result = {}
    kind = raw.get('type')
    low = raw.get('minItems', raw.get('minimumItems', raw.get('exactItems', raw.get('length'))))
    high = raw.get('maxItems', raw.get('maximumItems', raw.get('exactItems', raw.get('length'))))
    permutation = raw.get('permutation')
    if isinstance(permutation, list) and permutation and all(isinstance(v, str) for v in permutation):
        return {'type': 'array', 'minItems': len(permutation), 'maxItems': len(permutation),
                'items': {'type': 'string', 'enum': permutation}, 'permutation': permutation,
                'notes': ['permutation validated by the template validator']}
    if kind == 'array' or low is not None or high is not None:
        result['type'] = 'array'
        if type(low) is int and type(high) is int and 0 <= low <= high <= 1000:
            result.update(minItems=low, maxItems=high)
        item = raw.get('items', raw.get('item'))
        if item is None:
            if 'range' in raw:
                item = raw['range']
            elif 'enum' in raw:
                item = {'enum': raw['enum']}
            elif 'maxLength' in raw:
                item = {'type': 'string', 'maxLength': raw['maxLength']}
        result['items'] = descriptor(item, depth + 1)
    elif kind == 'object' or 'properties' in raw:
        props = raw.get('properties')
        if not isinstance(props, dict) or not isinstance(raw.get('required', []), list):
            fail('malformed object schema')
        if any(k in UNSAFE_KEYS for k in props) or not set(raw.get('required', [])) <= set(props):
            fail('unsafe or missing schema property')
        result = {'type': 'object', 'properties': {k: descriptor(v, depth + 1) for k, v in props.items()},
                  'required': raw.get('required', []),
                  'required_status': 'declared' if 'required' in raw else 'undeclared'}
    elif 'enum' in raw:
        values = raw['enum']
        if not isinstance(values, list) or not 1 <= len(values) <= 128:
            fail('invalid enum')
        kinds = {type(v) for v in values}
        if len(kinds) != 1 or next(iter(kinds)) not in (str, int, float, bool):
            return unknown
        result = {'type': 'string' if str in kinds else 'boolean' if bool in kinds else 'number', 'enum': values}
    elif kind in ('number', 'integer', 'string', 'boolean'):
        result['type'] = kind
    elif 'minimum' in raw or 'maximum' in raw:
        result['type'] = 'integer' if raw.get('integer') is True else 'number'
    elif 'maxLength' in raw or 'pattern' in raw:
        result['type'] = 'string'
    elif all(isinstance(v, (dict, list)) for v in raw.values()):
        result = {'type': 'object', 'properties': {k: descriptor(v, depth + 1) for k, v in raw.items()},
                  'required': [], 'required_status': 'undeclared', 'notes': ['required/optional status undeclared']}
    else:
        return unknown
    for name in ('minimum', 'maximum', 'minLength', 'maxLength', 'multipleOf'):
        if name in raw and number(raw[name]):
            result[name] = raw[name]
    for name in ('first', 'unique', 'pattern', 'default'):
        if name in raw:
            result[name] = copy.deepcopy(raw[name])
    known = {'type', 'properties', 'required', 'additionalProperties', 'items', 'item', 'minItems', 'maxItems',
             'minimumItems', 'maximumItems', 'exactItems', 'length', 'minimum', 'maximum', 'minLength',
             'maxLength', 'multipleOf', 'range', 'enum', 'integer', 'first', 'unique', 'pattern', 'default'}
    unsupported = sorted(set(raw) - known)
    if unsupported:
        result.setdefault('notes', []).append('validator-only declaration keys: ' + ', '.join(unsupported))
    if any(name in raw and not number(raw[name]) for name in ('minimum', 'maximum')):
        result.setdefault('notes', []).append('dynamic bounds are validator-only')
    return result


def examples(family):
    if family in development_templates.FAMILIES:
        return development_templates.examples(family)
    return development_templates.pinned_json('fixtures/template-families.json', BASE_EXAMPLES_SHA256)['families'][family]


def observed_paths(value, path=()):
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from observed_paths(item, path + (key,))
    elif isinstance(value, list) and value:
        for item in value:
            yield from observed_paths(item, path + ('*',))
    else:
        yield path, value


def coverage(schema, spec):
    paths = {}
    for path, value in observed_paths(spec['parameters']):
        node = schema
        for part in path:
            node = node.get('items', {}) if part == '*' else node.get('properties', {}).get(part, {})
        kind = node.get('type')
        supported = (kind == 'string' and isinstance(value, str) or kind == 'boolean' and type(value) is bool
                     or kind in ('number', 'integer') and type(value) in (int, float))
        key = '/'.join(path)
        if key not in paths or not supported:
            paths[key] = 'declared_supported' if supported else 'JSON_fallback'
    optional = []
    def declared(node, path=()):
        if node['type'] == 'object':
            for key, child in node['properties'].items():
                if node.get('required_status') == 'declared' and key not in node['required']:
                    optional.append('/'.join(path + (key,)))
                declared(child, path + (key,))
        elif node['type'] == 'array':
            declared(node['items'], path + ('*',))
    declared(schema)
    return {'observed_paths': paths, 'observed_count': len(paths), 'declared_optional_paths': optional,
            'supported_observed_count': sum(v == 'declared_supported' for v in paths.values()),
            'fully_typed': False, 'status': 'partial; coupled rules remain in authoritative validation',
            'exhaustive_contract_coverage': False}


def contract(account, family, version, example):
    load_pack(account)
    if not isinstance(family, str) or family not in template_families.FAMILIES or version != template_families.VERSION:
        fail('unknown family/version')
    snapshot = declarations()
    row = next((v for v in examples(family) if v['name'] == example), None)
    if row is None:
        fail('unknown example')
    raw = snapshot['declarations'][family]
    schema = descriptor(raw if raw.get('type') == 'object' else {'type': 'object', 'properties': raw})
    value = {'schema_version': 1, 'account': account, 'family': family, 'version': version, 'example': example,
             'example_sha256': digest(row['spec']), 'declaration_sha256': digest(raw),
             'contract_source_sha256': CONTRACT_SHA256, 'parameters': schema,
             'provenance': {'kind': 'public_PARAMETER_SCHEMA' if family in development_templates.FAMILIES else 'baseline_validator_declaration',
                            'development_manifest_sha256': snapshot['development_manifest_sha256'],
                            'baseline_sources': snapshot['baseline_sources']},
             'coverage': coverage(schema, row['spec'])}
    return {**value, 'digest': digest(value)}


def action(studio, operation, data):
    try:
        return _action(studio, operation, data)
    except (OSError, sqlite3.Error, UnicodeError):
        # Read-only endpoints must not enter Handler's write-failure logging
        # path when a contract or current state cannot be read.
        fail('local contract/state unavailable; no changes saved')


def _action(studio, operation, data):
    dashboard = studio.dashboard
    dashboard.clean(data)
    bounded(data)
    required = {'account', 'family', 'version', 'example'}
    optional = set()
    if operation == 'validate':
        required |= {'engine', 'raw_spec', 'contract_digest'}
        optional = {'claims', 'source_revision', 'canon_revision', 'planning'}
    elif operation != 'fields':
        fail('unknown action')
    template_families.fields(data, required, optional)
    with dashboard.revision_lock, studio.lock:
        dashboard.assert_runtime_current()
        current = contract(*(data[k] for k in ('account', 'family', 'version', 'example')))
        if operation == 'fields':
            return current
        if data['contract_digest'] != current['digest']:
            fail('stale contract; explicitly reload fields')
        if data['engine'] not in ('hyperframes', 'remotion'):
            fail('engine required')
        spec = parse_raw(data['raw_spec'])
        dashboard.clean(spec)
        if not isinstance(spec, dict) or spec.get('id') != data['family'] or spec.get('version') != data['version']:
            fail('spec identity/version mismatch')
        claims = data.get('claims', [])
        binding = dashboard.llm.contexts.bind(data['account'], data.get('source_revision'), data.get('canon_revision')) if claims or data.get('source_revision') is not None or data.get('canon_revision') is not None else None
        subject = dashboard.taxonomy.bind(data['account'], data['planning']) if 'planning' in data else None
        brief = template_families.make_brief(data['account'], spec, subject=subject, claims=claims, production_context=binding)
        dashboard.clean(brief)
        if binding is not None:
            dashboard.llm.contexts.assert_current(data['account'], binding)
        if 'planning' in data and dashboard.taxonomy.bind(data['account'], data['planning']) != subject:
            fail('planning changed')
        normalized = bounded(brief['template_family'])
        request_digest = digest(data)
        return {'schema_version': 1, 'account': data['account'], 'family': data['family'], 'version': data['version'],
                'example': data['example'], 'engine': data['engine'], 'contract_digest': current['digest'],
                'request_digest': request_digest, 'raw_sha256': hashlib.sha256(data['raw_spec'].encode()).hexdigest(),
                'normalized_spec': normalized, 'normalization_changed': canonical(spec) != canonical(normalized),
                'raw_lexemes_may_normalize': True, 'source_revision': data.get('source_revision'),
                'canon_revision': data.get('canon_revision'), 'planning': data.get('planning'),
                'provider_calls': 0, 'actual_render': False, 'authorization': False}
