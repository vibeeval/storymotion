"""Customer display identity, separate from immutable workflow/profile IDs."""
import copy
import re
import unicodedata
from .security import WorkflowError, canonical, scan_bytes


def normalize_identity(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - {'name', 'handle'}:
        raise WorkflowError('Marka alanlarında yalnız ad ve isteğe bağlı handle kullan')
    result = {}
    for field, limit in [('name', 60), ('handle', 32)]:
        text = value.get(field, '')
        if not isinstance(text, str):
            raise WorkflowError('Marka adı ve handle metin olmalı')
        text = unicodedata.normalize('NFKC', text).strip()
        if len(text) > limit or any(unicodedata.category(c).startswith('C') for c in text):
            raise WorkflowError('Marka adı veya handle uzunluğu/karakterleri geçersiz')
        if any(c in text for c in '<>') or re.search(r'(?i)(?:https?://|www\.)', text):
            raise WorkflowError('Marka alanlarına bağlantı veya işaretleme alınmaz')
        result[field] = text
    if result['handle'] and not re.fullmatch(r'@?[A-Za-z0-9_][A-Za-z0-9_.]{0,29}', result['handle']):
        raise WorkflowError('Handle yalnız harf, rakam, nokta ve alt çizgi içerebilir')
    if result['handle'] and not result['handle'].startswith('@'):
        result['handle'] = '@' + result['handle']
    if scan_bytes(canonical(result).encode()):
        raise WorkflowError('Marka alanında olası gizli değer; kaydedilmedi')
    return result


def apply_identity(profile, identity):
    profile = copy.deepcopy(profile)
    identity = normalize_identity(identity)
    profile.update(name=identity['name'] or 'Kendi markanız', handle=identity['handle'])
    return profile
