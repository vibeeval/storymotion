from .local_state import open_control
"""Read-only, account-scoped access to template preparation records.

This adapter never instantiates a Store (which would create state). Normal
dashboard job IDs and roots are deliberately not part of this namespace.
Historical reads do not authorize execution/resume under a changed runtime.
"""
import contextlib
import datetime
from . import file_lock as fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .account_packs import load_pack
from .family_receipts import check_receipt
from .local_state import guard_control, guard_private, guard_workspace, validate_open_control
from .providers import safe_public_json
from .security import WorkflowError, canonical, digest, scan_bytes

JOB = re.compile(r'[a-f0-9]{24}')
SHA = re.compile(r'[a-f0-9]{64}')
PUBLIC = frozenset(('index.html', 'hyperframes.json', 'index.motion.json', 'timeline.json',
    'profile.json', 'cover.svg', 'cover.html', 'caption.txt', 'subtitles.srt', 'BRIEF.md',
    'template-motion.mjs', 'template-scene.json', 'template-selection.json', 'WORKFLOW.md',
    'source-brief.json', 'writing-context.json', 'remotion-props.json', 'remotion-entry.jsx', 'edit-motion.mjs'))
BASE = PUBLIC - {'source-brief.json', 'writing-context.json', 'remotion-props.json', 'remotion-entry.jsx', 'edit-motion.mjs'}
PRIVATE_PATH = re.compile(r'(?i)/[u]sers/|/home/|[a-z]:\\')


def refused():
    raise WorkflowError('FAMILY_RECORD_UNAVAILABLE: record, paths or manifest could not be verified')


def decode(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:refused()
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: refused())
    except (ValueError, RecursionError, UnicodeError, TypeError):
        refused()


def read_owned(root, relative, maximum=8 * 1024 * 1024):
    """Open each component without following links; return verified inode bytes."""
    path = guard_control(root, relative)
    parts = Path(relative).parts
    if Path(relative).as_posix() != relative or any(p in {'.', '..'} for p in parts):refused()
    if os.name=='nt':
        from .windows_native import read
        return read(root,relative,maximum)
    descriptors = []
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(descriptor)
        before = validate_open_control(descriptor)
        if before.st_size > maximum:refused()
        chunks = [];size = 0
        while True:
            block = os.read(descriptor, min(65536, maximum + 1 - size))
            if not block:break
            chunks.append(block);size += len(block)
            if size > maximum:refused()
        after = os.fstat(descriptor);current = path.lstat()
        signature = lambda s:(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
        if signature(before) != signature(after) or signature(after) != signature(current) or not stat.S_ISREG(current.st_mode):refused()
        return b''.join(chunks)
    finally:
        for descriptor in reversed(descriptors):os.close(descriptor)


class FamilyJobs:
    def __init__(self, studio):
        self.studio = studio
        self.dashboard = studio.dashboard

    def clean(self, value):
        raw = canonical(value).encode()
        if len(raw) > 1024 * 1024 or PRIVATE_PATH.search(raw.decode()):refused()
        for broker in (self.dashboard.llm.broker, self.dashboard.eleven.broker):
            safe_public_json(value, broker)

    @contextlib.contextmanager
    def connection(self):
        """No mkdir, lock creation, SQLite migration, event or write on GET."""
        if not self.studio.lock.acquire(blocking=False):
            raise WorkflowError('FAMILY_HISTORY_BUSY: preparation in progress; retry explicitly')
        fd = None;db = None
        try:
            guard_workspace(self.dashboard.workspace, canonical_alias=False)
            root = guard_control(self.dashboard.workspace, 'family-renders', 'dir')
            if not root.exists():
                yield None, root
                return
            guard_workspace(root, canonical_alias=False)
            path = guard_control(root, 'jobs.sqlite3')
            if not path.exists():
                yield None, root
                return
            fd = open_control(guard_control(root, '.workflow.lock'), os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
            validate_open_control(fd)
            try:fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:raise WorkflowError('FAMILY_HISTORY_BUSY: workflow in progress; retry explicitly') from None
            # Engine uses rollback journals. Reject a hot/WAL store rather than
            # letting a read create SQLite sidecars or silently ignore WAL data.
            with path.open('rb') as stream:header = stream.read(100)
            if len(header)!=100 or header[:16]!=b'SQLite format 3\x00' or header[18:20]!=b'\x01\x01':refused()
            if any(guard_control(root, 'jobs.sqlite3'+suffix).exists() for suffix in ('-journal', '-wal', '-shm')):refused()
            db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=0)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            yield db, root
        except (OSError, sqlite3.Error, ValueError, TypeError, RecursionError):
            refused()
        finally:
            try:
                if db is not None:db.close()
            finally:
                try:
                    if fd is not None:os.close(fd)
                finally:self.studio.lock.release()

    def identity(self, root, row, account, current):
        key = row['id']
        if not isinstance(key, str) or not JOB.fullmatch(key) or len(row['payload']) > 1024 * 1024:refused()
        payload = decode(row['payload'])
        if not isinstance(payload, dict) or set(payload) != {'render_engine', 'engine_version', 'engine_sha256', 'vendor_sha256', 'brief', 'profile', 'execution'}:refused()
        if digest(payload)[:24] != key:refused()
        brief = payload['brief'];profile = payload['profile'];proof = payload['execution']
        if (not isinstance(brief, dict) or not isinstance(profile, dict) or brief.get('brand') != account
                or profile.get('id') != account or payload['render_engine'] not in ('hyperframes', 'remotion')
                or not isinstance(proof, dict) or not isinstance(proof.get('files'), dict)
                or any(not isinstance(n, str) or not isinstance(h, str) or not SHA.fullmatch(h) for n, h in proof['files'].items())
                or digest(proof['files']) != proof.get('fingerprint')):refused()
        spec = brief.get('template_family')
        from .template_families import FAMILIES, VERSION
        from .development_templates import FAMILIES as DEVELOPMENT
        if (not isinstance(spec, dict) or not isinstance(spec.get('id'), str)
                or spec['id'] not in set(FAMILIES) | set(DEVELOPMENT)
                or set(spec)!={'id','version','parameters'} or spec['version'] != VERSION
                or not isinstance(spec['parameters'], dict) or not isinstance(brief.get('caption'), str)):refused()
        self.clean(payload)
        source_name = 'family-inputs/' + digest(brief) + '.json'
        guard_private(self.dashboard.workspace, source_name)
        source = read_owned(self.dashboard.workspace, source_name, 1024 * 1024)
        if decode(source) != brief:refused()
        check_receipt(self.dashboard.workspace, key, payload, source=source)
        try:created = datetime.datetime.fromisoformat(row['created']).isoformat()
        except (TypeError, ValueError):refused()
        return payload, {'ref': {'kind': 'family', 'account': account, 'id': key}, 'job': key,
            'account': account, 'family': spec['id'], 'engine': payload['render_engine'], 'created': created,
            'spec_summary': {'id': spec['id'], 'version': spec.get('version'), 'duration': spec.get('parameters', {}).get('duration')},
            'source_current': proof['fingerprint'] == current == self.dashboard.runtime_execution,
            'actual_render': False, 'publication_acceptance': 'pending',
            'detail_url': '/api/family-jobs/' + account + '/' + key}

    def verified(self, root, key, payload, stage):
        if not stage or stage['status'] != 'complete':refused()
        guard_private(root, key, 'dir')
        if not isinstance(stage['manifest'], str) or len(stage['manifest']) > 128 * 1024:refused()
        manifest = decode(stage['manifest'])
        if not isinstance(manifest, dict) or not 1 <= len(manifest) <= 256:refused()
        if any(not isinstance(n, str) or not isinstance(h, str) or not SHA.fullmatch(h) for n, h in manifest.items()):refused()
        expected = set(BASE);anchored = {}
        proof = payload['execution']['files']
        for name, sha in proof.items():
            if name.startswith('vendor/'):
                anchored['assets/' + name[len('vendor/'):]] = sha
        anchored['template-motion.mjs'] = proof.get('renderers/template-motion.mjs')
        anchored['WORKFLOW.md'] = proof.get('knowledge/production-playbook.md')
        if payload['brief'].get('production_context'):
            expected.update(('source-brief.json', 'writing-context.json'))
        if payload['render_engine'] == 'remotion':expected.update(('remotion-props.json', 'remotion-entry.jsx', 'edit-motion.mjs'))
        from .development_templates import FAMILIES as DEVELOPMENT
        if payload['brief']['template_family']['id'] in DEVELOPMENT:
            name = 'template-registry/source-manifest.json'
            raw = read_owned(root, key + '/' + name)
            if hashlib.sha256(raw).hexdigest() != proof.get('renderers/' + name):refused()
            source = decode(raw)
            for name, sha in source['files'].items():
                if name.startswith('renderers/'):
                    if proof.get(name) != sha:refused()
                    anchored[name[len('renderers/'):]] = sha
            anchored['template-registry/source-manifest.json'] = proof['renderers/template-registry/source-manifest.json']
        if set(manifest) != expected | set(anchored):refused()
        if any(manifest.get(name) != sha for name, sha in anchored.items()):refused()
        values = {};total = 0
        for name, sha in manifest.items():
            if name in PUBLIC - {'template-motion.mjs', 'WORKFLOW.md', 'edit-motion.mjs'}:
                guard_private(root, key + '/' + name)
            raw = read_owned(root, key + '/' + name);total += len(raw)
            if total > 32 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sha:refused()
            if name in PUBLIC:
                text = raw.decode('utf-8')
                if scan_bytes(raw):refused()
                self.clean(html.unescape(text))
                if name.endswith('.json'):self.clean(decode(raw))
                values[name] = raw
        if decode(values['profile.json']) != payload['profile']:refused()
        if values['caption.txt'] != (payload['brief']['caption']+'\n').encode():refused()
        selection = decode(values['template-selection.json'])
        if not isinstance(selection, dict) or selection.get('template_family') != payload['brief']['template_family']:refused()
        if 'source-brief.json' in values and decode(values['source-brief.json']) != payload['brief']:refused()
        return manifest, values

    def listing(self, account):
        load_pack(account)
        from .provenance import execution_provenance
        current = execution_provenance()['fingerprint']
        jobs = [];unavailable = 0
        with self.connection() as (db, root):
            if db is not None:
                # Engine payloads use canonical JSON. SQL narrows bounded reads;
                # identity() still validates the parsed account, type and digest.
                marker = canonical({'brand': account})[1:-1]
                rows = db.execute('SELECT * FROM jobs WHERE length(payload)<=1048576 AND instr(payload,?)>0 ORDER BY created DESC,id DESC LIMIT 100', (marker,)).fetchall()
                for row in rows:
                    try:
                        payload, item = self.identity(root, row, account, current)
                        stage = db.execute("SELECT * FROM stages WHERE job=? AND name='prepare'", (row['id'],)).fetchone()
                        item['prepare_status'] = stage['status'] if stage and stage['status'] in {'complete', 'running', 'failed', 'pending'} else 'unavailable'
                        # List is a recorded-stage summary, not a file verification
                        # receipt. Detail/download always revalidate all bytes.
                        item['artifacts_status'] = 'not_checked'
                        jobs.append(item)
                    except (WorkflowError, OSError, KeyError, TypeError, ValueError, RecursionError):unavailable += 1
        return {'kind': 'family', 'account': account, 'jobs': jobs, 'unavailable_records': unavailable,
                'limit': 100, 'scope': 'prepare_only', 'artifacts_verified_on': 'detail_and_download'}

    def execution_snapshot(self, account, key, *, require_current=True):
        """Private server interface over the existing verified history boundary.

        Never returned over HTTP. No receipt minting, migration or Store creation.
        The original input and complete prepare manifest are checked while the
        existing read-only connection holds its source workflow lock.
        """
        load_pack(account)
        from .provenance import execution_provenance
        current = execution_provenance()['fingerprint']
        if not isinstance(key, str) or not JOB.fullmatch(key):refused()
        # Existing public history reads use a nonblocking lock. Dispatch waits
        # for those bounded reads rather than failing a newly approved attempt.
        with self.studio.lock, self.connection() as (db, root):
            row = db.execute('SELECT * FROM jobs WHERE id=? AND length(payload)<=1048576', (key,)).fetchone() if db is not None else None
            if row is None:refused()
            payload, item = self.identity(root, row, account, current)
            stage = db.execute("SELECT * FROM stages WHERE job=? AND name='prepare'", (key,)).fetchone()
            if not stage or stage['status'] != 'complete':refused()
            check_receipt(self.dashboard.workspace, key, payload, manifest=decode(stage['manifest']))
            manifest, _ = self.verified(root, key, payload, stage)
            raw = read_owned(self.dashboard.workspace, 'family-inputs/' + digest(payload['brief']) + '.json', 1024 * 1024)
            if decode(raw) != payload['brief']:refused()
            if require_current and not item['source_current']:
                raise WorkflowError('FAMILY_RENDER_SOURCE_CHANGED: prepare again under the current runtime')
            proof = {'account': account, 'prepare_job': key, 'engine': payload['render_engine'],
                     'payload_sha256': digest(payload), 'source_sha256': hashlib.sha256(raw).hexdigest(),
                     'manifest_sha256': digest(manifest), 'execution_fingerprint': payload['execution']['fingerprint']}
            return {'proof': proof, 'preparation_revision': digest(proof), 'source_current': item['source_current'],
                    'payload': payload, 'raw': raw}

    def detail(self, account, key, token=None, view=False):
        load_pack(account)
        from .provenance import execution_provenance
        current = execution_provenance()['fingerprint']
        if not isinstance(key, str) or not JOB.fullmatch(key):refused()
        with self.connection() as (db, root):
            row = db.execute('SELECT * FROM jobs WHERE id=? AND length(payload)<=1048576', (key,)).fetchone() if db is not None else None
            if row is None:refused()
            payload, item = self.identity(root, row, account, current)
            stage = db.execute("SELECT * FROM stages WHERE job=? AND name='prepare'", (key,)).fetchone()
            item.update(spec=payload['brief']['template_family'], prepare_status=stage['status'] if stage and stage['status'] in {'complete', 'running', 'failed', 'pending'} else 'unavailable', files=[], artifacts_status='unavailable')
            try:
                if not stage or stage['status']!='complete':refused()
                check_receipt(self.dashboard.workspace, key, payload, manifest=decode(stage['manifest']))
                manifest, values = self.verified(root, key, payload, stage)
            except (WorkflowError, OSError, ValueError, TypeError, KeyError, RecursionError, UnicodeError):
                if token is not None:refused()
                return item
            item.update(artifacts_status='verified', manifest_sha256=digest(manifest), manifest_file_count=len(manifest))
            for name, raw in sorted(values.items()):
                artifact = digest({'kind': 'family_artifact', 'account': account, 'job': key, 'manifest': digest(manifest), 'name': name})
                url = '/family-files/' + account + '/' + key + '/' + artifact
                item['files'].append({'name': name, 'bytes': len(raw), 'sha256': manifest[name], 'download_url': url,
                                      'view_url': url + '/view' if name == 'cover.svg' else None})
                if token is not None and artifact == token:
                    if view and name != 'cover.svg':refused()
                    return name, raw
            if token is not None:refused()
            return item
