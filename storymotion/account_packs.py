"""Bounded local AccountPack data; no imports or executable customer plugins."""
import copy
import json
import os
import stat
import re
from collections.abc import Mapping, Set
from pathlib import Path

from .security import WorkflowError, canonical, scan_bytes

ROOT = Path(__file__).resolve().parents[1]
from .account_pack_schema import IDENTIFIER, validate_pack, validate_render_profile
MAX_BYTES = 65536


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON field')
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError('Non-finite JSON constant')


def _read_pack(path):
    # Open each project-relative component through directory descriptors. A
    # linked work/ ancestor cannot redirect reads into another directory.
    if os.name=='nt':
        from .windows_native import read
        return read(ROOT,path.relative_to(ROOT),MAX_BYTES)
    parts = path.relative_to(ROOT).parts
    directory = os.open(Path(ROOT).resolve(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
                raise ValueError('Not a bounded regular file')
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
        current = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        key = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns)
        if len(raw) > MAX_BYTES or key(before) != key(after) or key(after) != key(current) or not stat.S_ISREG(current.st_mode):
            raise ValueError('Pack changed while reading')
        return raw
    finally:
        os.close(directory)


def _validate(path):
    try:
        raw = _read_pack(path)
        if scan_bytes(raw):
            raise ValueError()
        pack = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        validate_pack(pack, path.stem)
        canonical(pack)
        return pack
    except (OSError, UnicodeError, ValueError, RecursionError, TypeError, KeyError, AttributeError, OverflowError, WorkflowError):
        raise WorkflowError('CUSTOMER_PROFILE_MALFORMED') from None


def _linked_folder(folder):
    current = ROOT
    for part in folder.relative_to(ROOT).parts:
        current = current / part
        if current.is_symlink():
            return True
    return not folder.resolve().is_relative_to(Path(ROOT).resolve())


def catalog():
    packs, errors = {}, []
    for folder in (ROOT / 'accountpacks/neutral', ROOT / 'work/accountpacks'):
        if _linked_folder(folder) or folder.exists() and not folder.is_dir():
            errors.append({'file': folder.name, 'code': 'CUSTOMER_PROFILE_MALFORMED'})
            continue
        if not folder.exists():
            continue
        for path in sorted(folder.glob('*.json')):
            try:
                pack = _validate(path)
                if pack['id'] in packs:
                    raise WorkflowError('CUSTOMER_PROFILE_DUPLICATE')
                packs[pack['id']] = pack
            except WorkflowError as error:
                errors.append({'file': path.name, 'code': str(error)})
    return packs, errors


def load_pack(account):
    if not isinstance(account, str) or not IDENTIFIER.fullmatch(account):
        raise WorkflowError('Unknown AccountPack identifier')
    packs, _ = catalog()
    if account not in packs:
        raise WorkflowError('Unknown or malformed AccountPack')
    return copy.deepcopy(packs[account])


def capability(account, name):
    if not isinstance(account, str) or account not in ACCOUNTS:
        return None
    return load_pack(account)['capabilities'].get(name)


def is_serial(account):
    return isinstance(account, str) and account in ACCOUNTS and load_pack(account)['series_rules']['enabled']


def render_profile(account):
    return load_pack(account)['profile']


def sample_brief(account):
    return load_pack(account)['fixture']


def template_brief(account, adapter):
    pack = load_pack(account)
    return pack.get('legacy_fixture', pack['fixture']) if adapter == 'hyperframes-fixture' else pack['fixture']


def account_catalog(base):
    result = copy.deepcopy(base)
    packs, errors = catalog()
    result['accounts'] = [{'id': p['id'], 'name': p['display_name'], 'display_name': p['display_name'],
                           'niche': p['niche'], 'handle': '', 'language': p.get('language', 'tr'),
                           'category': p.get('category', 'explainer'), 'formats': p['formats'],
                           'tone': 'Customer-authored method pending.', 'style': p['visual_family'],
                           'capabilities': p['capabilities'], 'series_rules': p['series_rules'],
                           'status': 'technical_fixture_human_acceptance_pending'} for p in packs.values()]
    result['account_pack_errors'] = errors
    return result


class AccountIDs(Set):
    def __contains__(self, value):
        return isinstance(value, str) and value in catalog()[0]

    def __iter__(self):
        return iter(catalog()[0])

    def __len__(self):
        return len(catalog()[0])


class SceneKinds(Mapping):
    def __contains__(self, key):
        return bool(capability(key, 'manual_scene_kinds'))

    def __getitem__(self, key):
        return set(load_pack(key)['capabilities']['manual_scene_kinds'])

    def __iter__(self):
        return (key for key in ACCOUNTS if self[key])

    def __len__(self):
        return sum(1 for _ in self)


ACCOUNTS = AccountIDs()
KINDS = SceneKinds()
