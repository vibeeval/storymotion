"""Pinned editorial discovery metadata for 91 templates. Not visual acceptance."""
import hashlib
import json
from pathlib import Path
from .local_state import guard_control
from .security import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_SHA256 = 'd8038dab5481591ce4728d138ac66f7e8e74b5690ce7b2b123f209e185ebc68c'
SOURCE_SHA256 = '2c4fe5e1e4903a1bb6ffd3443d5d8978d7a862eba3c66933218d35abe68290d8'


def _invalid():
    raise WorkflowError('TEMPLATE_DISCOVERY_INVALID')


def catalog():
    """Hash-pinned per-family editorial fields; scores remain null."""
    path = guard_control(ROOT, 'catalog/template-discovery-91.json')
    raw = path.read_bytes() if path.is_file() else b''
    if hashlib.sha256(raw).hexdigest() != DISCOVERY_SHA256:
        _invalid()
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        _invalid()
    if value.get('source_sha256') != SOURCE_SHA256:
        _invalid()
    rows = value.get('families')
    if not isinstance(rows, list) or len(rows) != 91:
        _invalid()
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in result:
            _invalid()
        if row.get('visual_score') is not None:
            _invalid()
        assess = row.get('instagram_assessment')
        if not isinstance(assess, dict) or assess.get('score_100') is not None or assess.get('status') != 'not_assessed':
            _invalid()
        age = row.get('age_hypothesis')
        if not isinstance(age, dict) or age.get('status') != 'hypothesis_not_measured':
            _invalid()
        if type(row.get('requires_caller_media')) is not bool:
            _invalid()
        result[row['id']] = row
    if len(result) != 91:
        _invalid()
    return result
