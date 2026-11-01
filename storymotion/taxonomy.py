"""Account-scoped editorial planning; never a renderer or factual acceptance."""
import copy
import json
import re
import unicodedata

from . import template_discovery
from .security import WorkflowError, canonical, digest

MAX_CUSTOM_ITEMS = 1000
IDENT = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
REVISION = re.compile(r'[a-f0-9]{64}\Z')


def fail(code):
    raise WorkflowError('TAXONOMY_' + code)


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        fail('FIELDS: use only the documented fields')


def label(value, maximum):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        fail('LABEL: enter a bounded plain-text name')
    if any(unicodedata.category(c).startswith('C') or c in '<>' for c in value):
        fail('LABEL: control characters and markup are not names')
    result = ' '.join(unicodedata.normalize('NFKC', value).split())
    if not result or len(result) > maximum:
        fail('LABEL: enter a bounded plain-text name')
    return result


def name_key(value):
    return unicodedata.normalize('NFKC', value).casefold()


def item_id(kind, account, name, niche=None):
    return 'local-' + kind + '-' + digest({'account': account, 'name': name_key(name), 'niche': niche})[:24]


def editorial_items():
    niches = {}; topics = {}
    for family, row in template_discovery.catalog().items():
        for name in row['niches']:
            name = label(name, 100); key = 'niche-' + digest(name_key(name))[:24]
            niche = niches.setdefault(key, {'id': key, 'name': name, 'origin': 'bundled_editorial', 'family_ids': []})
            niche['family_ids'].append(family)
            for topic_name in row['sample_topics']:
                topic_name = label(topic_name, 160)
                ident = 'topic-' + digest({'niche': key, 'name': name_key(topic_name)})[:24]
                topic = topics.setdefault(ident, {'id': ident, 'name': topic_name, 'niche': key,
                                                   'origin': 'bundled_editorial', 'family_ids': []})
                topic['family_ids'].append(family)
    for row in [*niches.values(), *topics.values()]:
        row['family_ids'] = sorted(set(row['family_ids']))
    return niches, topics


class Taxonomy:
    def __init__(self, dashboard):
        self.d = dashboard
        self.base_niches, self.base_topics = editorial_items()
        with self.d.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS taxonomy_items(account TEXT NOT NULL,id TEXT NOT NULL,'
                       'kind TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(account,id))')
            db.execute('CREATE TABLE IF NOT EXISTS taxonomy_selection(account TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS taxonomy_revision(account TEXT PRIMARY KEY,generation INTEGER NOT NULL)')

    def account(self, account):
        if not isinstance(account, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,59}', account):
            fail('ACCOUNT')
        if account not in {row['id'] for row in self.d.catalog['accounts']}:
            fail('ACCOUNT')
        from .account_packs import load_pack
        load_pack(account)
        self.d.assert_runtime_current()
        return account

    def _stored(self, account, row):
        try:
            if row['kind'] not in ('niche', 'topic') or len(row['payload'].encode()) > 4000:
                fail('STATE_INVALID')
            value = json.loads(row['payload'])
            expected = {'id', 'name', 'account', 'origin'} | ({'niche'} if row['kind'] == 'topic' else set())
            if type(value) is not dict or set(value) != expected:
                fail('STATE_INVALID')
            if value['account'] != account or value['origin'] != 'customer_local':
                fail('STATE_INVALID')
            name = label(value['name'], 100 if row['kind'] == 'niche' else 160)
            niche = value.get('niche')
            if name != value['name'] or (row['kind'] == 'topic' and (not isinstance(niche, str) or not IDENT.fullmatch(niche))):
                fail('STATE_INVALID')
            if row['id'] != value['id'] or value['id'] != item_id(row['kind'], account, name, niche):
                fail('STATE_INVALID')
            self.d.clean(value)
            return {**value, 'family_ids': []}
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError, AttributeError):
            fail('STATE_INVALID')

    def _state(self, db, account):
        niches = copy.deepcopy(self.base_niches); topics = copy.deepcopy(self.base_topics)
        rows = db.execute('SELECT id,kind,payload FROM taxonomy_items WHERE account=? ORDER BY id LIMIT ?',
                          (account, MAX_CUSTOM_ITEMS + 1)).fetchall()
        if len(rows) > MAX_CUSTOM_ITEMS:
            fail('STATE_INVALID: catalog exceeds its documented bound; no records changed')
        for row in rows:
            value = self._stored(account, row)
            target = niches if row['kind'] == 'niche' else topics
            if value['id'] in target:
                fail('STATE_INVALID')
            target[value['id']] = value
        if any(topic['niche'] not in niches for topic in topics.values()):
            fail('STATE_INVALID')
        selected = db.execute('SELECT payload FROM taxonomy_selection WHERE account=?', (account,)).fetchone()
        selection = None
        if selected:
            try:
                if len(selected['payload']) > 500:fail('STATE_INVALID')
                selection = json.loads(selected['payload'])
                fields(selection, {'niche', 'topic'})
                if (not isinstance(selection['niche'], str) or not isinstance(selection['topic'], str) or
                        selection['niche'] not in niches or selection['topic'] not in topics or
                        topics[selection['topic']]['niche'] != selection['niche']):
                    fail('STATE_INVALID')
            except (ValueError, TypeError, KeyError, RecursionError):
                fail('STATE_INVALID')
        ordered = lambda values: sorted(values.values(), key=lambda row: (name_key(row['name']), row['id']))
        row = db.execute('SELECT generation FROM taxonomy_revision WHERE account=?', (account,)).fetchone()
        generation = row['generation'] if row else 0
        if type(generation) is not int or not 0 <= generation < 2**53 - 1:fail('STATE_INVALID')
        value = {'account': account, 'niches': ordered(niches), 'topics': ordered(topics), 'selection': selection, 'generation': generation}
        revision = digest(value)
        return {**value, 'revision': revision, 'planning_context': self._context(value, revision),
                'custom_count': len(rows), 'custom_limit': MAX_CUSTOM_ITEMS, 'provider_calls': 0,
                'classification': 'editorial_planning_not_factual_or_demographic_validation',
                'template_readiness_source': '/api/template-families'}

    def _context(self, value, revision):
        selected = value['selection']
        if selected is None:return None
        context = {'schema_version': 1, 'production_profile': value['account'], 'catalog_revision': revision,
                   'niche': copy.deepcopy(next(row for row in value['niches'] if row['id'] == selected['niche'])),
                   'topic': copy.deepcopy(next(row for row in value['topics'] if row['id'] == selected['topic'])),
                   'style_applied_by_taxonomy': False, 'sources_verified': False, 'human_review': 'pending',
                   'classification': 'editorial_planning_not_factual_or_demographic_validation',
                   'capability': {'state': 'planning_only', 'renderer': None, 'render_verified': False},
                   'catalog_selection': {'source_item_ids': []}, 'source_items': []}
        self.d.clean(context)
        return {**context, 'binding_sha256': digest(context)}

    def _revision(self, expected, state):
        if not isinstance(expected, str) or not REVISION.fullmatch(expected):fail('REVISION')
        if expected != state['revision']:fail('REVISION_CHANGED: refresh the catalog; local edits were not saved')

    def _bump(self, db, account):
        db.execute('INSERT INTO taxonomy_revision(account,generation) VALUES(?,1) ON CONFLICT(account) DO UPDATE SET generation=generation+1', (account,))

    def state(self, account):
        with self.d.revision_lock:
            account = self.account(account)
            with self.d.connection() as db:
                db.execute('BEGIN')
                return self._state(db, account)

    def create(self, data):
        self.d.clean(data)
        if type(data) is not dict:fail('FIELDS')
        expected = {'account', 'kind', 'name', 'expected_revision'} | ({'niche'} if data.get('kind') == 'topic' else set())
        fields(data, expected)
        if data['kind'] not in ('niche', 'topic'):fail('KIND')
        name = label(data['name'], 100 if data['kind'] == 'niche' else 160)
        self.d.clean(name)
        with self.d.revision_lock:
            account = self.account(data['account'])
            with self.d.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                state = self._state(db, account);self._revision(data['expected_revision'], state)
                niche = data.get('niche')
                if data['kind'] == 'topic' and (not isinstance(niche, str) or niche not in {row['id'] for row in state['niches']}):
                    fail('TOPIC_PARENT: choose a niche in this AccountPack catalog')
                values = state['niches'] if data['kind'] == 'niche' else state['topics']
                existing = next((row for row in values if name_key(row['name']) == name_key(name) and row.get('niche') == niche), None)
                if existing:return {'created': False, 'item': existing, 'state': state}
                if state['custom_count'] >= MAX_CUSTOM_ITEMS:
                    fail('CAPACITY: 1000 custom records per account; existing records and selection are retained')
                value = {'id': item_id(data['kind'], account, name, niche), 'name': name,
                         'account': account, 'origin': 'customer_local'}
                if niche is not None:value['niche'] = niche
                self.d.clean(value)
                db.execute('INSERT INTO taxonomy_items(account,id,kind,payload) VALUES(?,?,?,?)',
                           (account, value['id'], data['kind'], canonical(value)))
                self._bump(db, account)
                return {'created': True, 'item': {**value, 'family_ids': []}, 'state': self._state(db, account)}

    def select(self, data):
        self.d.clean(data)
        fields(data, {'account', 'niche', 'topic', 'expected_revision'})
        with self.d.revision_lock:
            account = self.account(data['account'])
            with self.d.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                state = self._state(db, account);self._revision(data['expected_revision'], state)
                niche, topic = data['niche'], data['topic']
                if niche is None and topic is None:
                    if state['selection'] is None:return state
                    db.execute('DELETE FROM taxonomy_selection WHERE account=?', (account,))
                else:
                    if not isinstance(niche, str) or not isinstance(topic, str):fail('SELECTION')
                    if niche not in {row['id'] for row in state['niches']} or topic not in {row['id'] for row in state['topics']}:
                        fail('SELECTION: IDs must belong to this account catalog')
                    if next(row for row in state['topics'] if row['id'] == topic)['niche'] != niche:
                        fail('TOPIC_PARENT: topic does not belong to the chosen niche')
                    if state['selection'] == {'niche': niche, 'topic': topic}:return state
                    db.execute('INSERT INTO taxonomy_selection(account,payload) VALUES(?,?) ON CONFLICT(account) DO UPDATE SET payload=excluded.payload',
                               (account, canonical({'niche': niche, 'topic': topic})))
                self._bump(db, account)
                return self._state(db, account)

    def bind(self, account, token):
        self.d.clean(token)
        fields(token, {'revision', 'niche', 'topic'})
        state = self.state(account)
        self._revision(token['revision'], state)
        if state['selection'] is None or state['selection'] != {'niche': token['niche'], 'topic': token['topic']}:
            fail('SELECTION_CHANGED: apply the current planning selection first')
        return state['planning_context']

    def action(self, action, data):
        try:
            self.d.clean(data)
            if action == 'state':
                fields(data, {'account'})
                return self.state(data['account'])
            if action == 'create':return self.create(data)
            if action == 'select':return self.select(data)
            fail('ACTION')
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            fail('INPUT: malformed planning request; no changes saved')
