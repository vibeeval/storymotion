"""Closed, bounded data contracts for local packs and render interpolation."""
import math
import re
import unicodedata

from .security import WorkflowError

IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,59}')
FAMILY_ACTIONS = {
    'approval-conveyor': {'request-route', 'approval-gate', 'receipt-reuse'},
    'hinged-box': {'latch-release', 'lid-rise', 'mechanism-return'},
    'possibility-branches': {'familiar-moment', 'inner-sentence', 'two-explanations', 'distinguish-question', 'observe-cue'},
    'envelope-clue': {'envelope-place', 'envelope-inspect', 'envelope-match'},
}
FAMILY_KINDS = {
    'approval-conveyor': {'process-route', 'object-transform'},
    'hinged-box': set(),
    'possibility-branches': {'possibility-branches', 'observation'},
    'envelope-clue': {'clue-inspect', 'canon-board'},
}
PROFILE_NUMBERS = {
    'title_size': (48, 100), 'subtitle_size': (36, 60),
    'subtitle_top': (0, 1792), 'subtitle_width': (1, 994),
    'handle_left': (0, 1080), 'handle_bottom': (0, 1920), 'handle_size': (8, 72),
}
PROFILE_REQUIRED = {'id', 'name', 'format', 'palette', 'font', 'handle', 'top_brand',
                    'avatar', 'sentence_case', 'assets', 'visual_family'} | set(PROFILE_NUMBERS)
PACK_FIELDS = {'schema_version', 'version', 'scene_actions', 'visual_family', 'duration_range_seconds',
               'wardrobe', 'scene_contract', 'initial_state', 'final_state', 'id', 'display_name', 'niche',
               'procedures', 'visual_families', 'scene_vocab', 'series_rules', 'voice_defaults', 'profile',
               'formats', 'language', 'category', 'capabilities', 'rule_ids', 'rules', 'source_revision',
               'asset_policy', 'acceptance', 'workflow', 'production_workflow', 'revision_policy',
               'repeat_policy', 'brand', 'fixture'}


def _fail():
    raise WorkflowError('CUSTOMER_PROFILE_MALFORMED')


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - (set(required) | set(optional)) or set(required) - set(value):
        _fail()


def _text(value, maximum, minimum=1):
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum
            or minimum and not value.strip()
            or any(unicodedata.category(c).startswith('C') for c in value)
            or '<' in value or '>' in value):
        _fail()


def _id(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        _fail()


def _boolean(value):
    if type(value) is not bool:
        _fail()


def _number(value, minimum, maximum):
    if type(value) not in (int, float):
        _fail()
    try:
        if not math.isfinite(value) or not minimum <= value <= maximum:
            _fail()
    except OverflowError:
        _fail()


def _list(value, minimum=0, maximum=20):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail()


def _ids(value, minimum=1, maximum=20):
    _list(value, minimum, maximum)
    for item in value:
        _id(item)
    if len(set(value)) != len(value):
        _fail()


def _texts(value, minimum=0, maximum=20, text_maximum=500):
    _list(value, minimum, maximum)
    for item in value:
        _text(item, text_maximum)


def _palette(value):
    _object(value, {'background', 'ink', 'muted', 'accent'})
    if any(not isinstance(c, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in value.values()):
        _fail()


def validate_render_profile(profile):
    """Validate every value interpolated into HTML, SVG, CSS or renderer props."""
    _object(profile, PROFILE_REQUIRED, {'continuity_required', 'voice_policy'})
    _id(profile['id']); _id(profile['format'])
    _text(profile['name'], 200); _text(profile['assets'], 500)
    if profile['font'] != 'Schibsted' or not isinstance(profile['visual_family'], str) or profile['visual_family'] not in FAMILY_ACTIONS:
        _fail()
    _palette(profile['palette'])
    _text(profile['handle'], 32, 0)
    if profile['handle'] and not re.fullmatch(r'@?[A-Za-z0-9_][A-Za-z0-9_.]{0,29}', profile['handle']):
        _fail()
    for field, bounds in PROFILE_NUMBERS.items():
        _number(profile[field], *bounds)
    for field in ('top_brand', 'avatar', 'sentence_case'):
        _boolean(profile[field])
    if 'continuity_required' in profile:
        _boolean(profile['continuity_required'])
    if 'voice_policy' in profile:
        _text(profile['voice_policy'], 500)
    return profile


def validate_pack(pack, expected_id):
    _object(pack, PACK_FIELDS, {'legacy_fixture'})
    _id(pack['id'])
    if pack['id'] != expected_id or type(pack['schema_version']) is not int or pack['schema_version'] != 1:
        _fail()
    for field in ('display_name', 'niche', 'version', 'source_revision'):
        _text(pack[field], 200)
    if not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}(?:-[A-Za-z0-9.-]{1,40})?', pack['version']):
        _fail()
    _ids(pack['visual_families'], 1, 4)
    family = pack['visual_family']
    if not isinstance(family, str) or family not in FAMILY_ACTIONS or family not in pack['visual_families'] or set(pack['visual_families']) - FAMILY_ACTIONS.keys():
        _fail()
    _ids(pack['scene_actions'], 1, 12); _ids(pack['scene_vocab'], 1, 12)
    if pack['scene_vocab'] != pack['scene_actions'] or set(pack['scene_actions']) != FAMILY_ACTIONS[family]:
        _fail()
    _object(pack['scene_contract'], set(pack['scene_actions']))
    for action in pack['scene_actions']:
        row = pack['scene_contract'][action]
        _object(row, {'state_before', 'state_after'})
        _id(row['state_before']); _id(row['state_after'])
    _id(pack['initial_state']); _id(pack['final_state'])
    if pack['wardrobe'] is not None:
        _text(pack['wardrobe'], 100)
    _list(pack['duration_range_seconds'], 2, 2)
    low, high = pack['duration_range_seconds']
    _number(low, 1, 90); _number(high, low, 90)
    _object(pack['series_rules'], {'enabled', 'fictional'})
    for value in pack['series_rules'].values():
        _boolean(value)
    if pack['series_rules']['enabled'] and family != 'envelope-clue' or pack['series_rules']['fictional'] and not pack['series_rules']['enabled']:
        _fail()
    _object(pack['voice_defaults'], {'provider', 'voice_id'})
    if pack['voice_defaults'] != {'provider': 'off', 'voice_id': None}:
        _fail()
    caps = pack['capabilities']
    _object(caps, {'legacy_fixture', 'raster', 'manual_scene_kinds', 'rig_mode', 'certainty_guard'})
    for field in ('legacy_fixture', 'raster', 'certainty_guard'):
        _boolean(caps[field])
    _ids(caps['manual_scene_kinds'], 0, 6)
    if set(caps['manual_scene_kinds']) - FAMILY_KINDS[family]:
        _fail()
    if set(caps['manual_scene_kinds']) & {'clue-inspect', 'canon-board'} and not pack['series_rules']['enabled']:
        raise WorkflowError('CUSTOMER_PROFILE_MALFORMED: clue-inspect/canon-board require series_rules.enabled=true; their accepted-reference canon must be supplied before planning scenes')
    allowed_rig = {'approval-conveyor': 'inset', 'envelope-clue': 'serial-courier'}.get(family)
    if caps['rig_mode'] is not None and caps['rig_mode'] != allowed_rig:
        _fail()
    if caps['raster'] and family != 'hinged-box' or caps['rig_mode'] == 'serial-courier' and not pack['series_rules']['enabled']:
        _fail()
    profile = validate_render_profile(pack['profile'])
    if (profile['id'] != pack['id'] or profile['visual_family'] != family
            or profile.get('continuity_required', False) != pack['series_rules']['enabled']):
        _fail()
    _ids(pack['formats'], 1, 12)
    if pack['language'] != 'tr' or pack['category'] not in ('story', 'explainer'):
        _fail()
    _list(pack['rule_ids'], 1, 32)
    if any(not isinstance(r, str) or not re.fullmatch(r'[A-Z][A-Z0-9-]{0,39}', r) for r in pack['rule_ids']):
        _fail()
    if len(set(pack['rule_ids'])) != len(pack['rule_ids']) or 'CORE-01' not in pack['rule_ids']:
        _fail()
    _list(pack['rules'], 1, 32)
    for rule in pack['rules']:
        _object(rule, {'id', 'text'}); _text(rule['text'], 1000)
        if rule['id'] not in pack['rule_ids']:
            _fail()
    if len(pack['rules']) != len(pack['rule_ids']) or {r['id'] for r in pack['rules']} != set(pack['rule_ids']):
        _fail()
    _list(pack['procedures'], 1, 20)
    for procedure in pack['procedures']:
        _object(procedure, {'id', 'status', 'instruction'})
        _id(procedure['id']); _text(procedure['instruction'], 2000)
        if procedure['status'] not in ('TODO', 'authored'):
            _fail()
    _object(pack['asset_policy'], {'allowed', 'commercial_transfer'})
    if pack['asset_policy']['allowed'] != 'original_project_vectors':
        _fail()
    _text(pack['asset_policy']['commercial_transfer'], 500)
    _object(pack['acceptance'], {'publication_ready', 'source_truth', 'creative'})
    if pack['acceptance'] != {'publication_ready': False, 'source_truth': 'pending_human_review', 'creative': 'pending_human_review'} or type(pack['acceptance']['publication_ready']) is not bool:
        _fail()
    _texts(pack['workflow'], 1)
    _list(pack['production_workflow'], 0, 20)
    for stage in pack['production_workflow']:
        _object(stage, {'stage', 'requires', 'gate'})
        _id(stage['stage']); _texts(stage['requires'], 1); _text(stage['gate'], 500)
    _object(pack['revision_policy'], (), {'method', 'script_change', 'audio_change', 'geometry_change', 'limit'})
    for key, value in pack['revision_policy'].items():
        _texts(value) if key.endswith('_change') else _text(value, 1000)
    _object(pack['repeat_policy'], (), {'executable', 'scope', 'same_family_limit'})
    for key, value in pack['repeat_policy'].items():
        _texts(value) if key == 'executable' else _text(value, 1000)
    _object(pack['brand'], {'palette'}); _palette(pack['brand']['palette'])
    if pack['brand']['palette'] != profile['palette']:
        _fail()
    # Reuse the closed host output schema without calling the pack registry.
    from .creative import _schema_for_pack, _check
    _check(pack['fixture'], _schema_for_pack(pack))
    if not low <= pack['fixture']['duration'] <= high:
        _fail()
    if 'legacy_fixture' in pack:
        _validate_legacy_fixture(pack['legacy_fixture'], pack)
    return pack


def _validate_legacy_fixture(value, pack):
    fields = {'schema_version', 'brand', 'title', 'brief', 'demo', 'script', 'caption',
              'duration', 'alignment', 'audio', 'claims', 'scenes', 'cues'}
    _object(value, fields, {'language', 'continuity'})
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['brand'] != pack['id'] or not pack['capabilities']['legacy_fixture']
            or value['audio'] is not None or value['alignment'] != 'provisional_silent'
            or value['claims'] != []):
        _fail()
    for key in ('title', 'brief', 'script', 'caption'):
        _text(value[key], 65 if key == 'title' else 10000)
    _boolean(value['demo']); _number(value['duration'], 1, 90)
    if value.get('language', 'tr') != pack['language']:
        _fail()
    if 'continuity' in value:
        _object(value['continuity'], {'object_id', 'previous', 'next'})
        _id(value['continuity']['object_id'])
        _text(value['continuity']['previous'], 500); _text(value['continuity']['next'], 500)
    _list(value['scenes'], 1, 12); _list(value['cues'], 1, 100)
    for scene in value['scenes']:
        _object(scene, {'id', 'start', 'end', 'heading', 'action', 'information', 'object_before', 'object_after'},
                {'nodes', 'from_node', 'to_node'})
        _id(scene['id']); _number(scene['start'], 0, 90); _number(scene['end'], 0, 90)
        for field in ('heading', 'information', 'object_before', 'object_after'):
            _text(scene[field], 50 if field == 'heading' else 1200)
        if scene['action'] not in ('unlock', 'open', 'reveal', 'flow'):
            _fail()
        if scene['action'] == 'flow':
            _texts(scene.get('nodes'), 2, 4, 14)
            if any(type(scene.get(k)) is not int for k in ('from_node', 'to_node')):
                _fail()
    for cue in value['cues']:
        _object(cue, {'start', 'end', 'text'})
        _number(cue['start'], 0, 90); _number(cue['end'], 0, 90); _text(cue['text'], 95)
    from .engine import validate
    validate(value, pack['profile'])
