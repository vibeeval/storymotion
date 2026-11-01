"""Bounded, read-only episode/draft history; never an acceptance receipt."""
import base64
import binascii
import json
import re
import sqlite3

from .account_packs import is_serial
from .security import WorkflowError, canonical
from .writing_context import ident, revision

DEFAULT_LIMIT = 100
MAX_LIMIT = 200
FIELDS = {'account', 'series', 'limit', 'episode_cursor', 'draft_cursor', 'selected_revision'}


def _invalid():
    raise WorkflowError('SERIES_HISTORY_QUERY_INVALID: limit must be 1–200; use the returned cursor with its original account/series scope')


def _encode(value):
    return base64.urlsafe_b64encode(canonical(value).encode()).decode().rstrip('=')


def _decode(value, kind, scope):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9_-]{1,1024}', value):
        _invalid()
    try:
        data = json.loads(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True))
        if (not isinstance(data, dict) or set(data) != {'v', 'kind', 'scope', 'watermark', 'last'}
                or type(data['v']) is not int or data['v'] != 1 or data['kind'] != kind
                or data['scope'] != scope or type(data['watermark']) is not int
                or not 0 <= data['watermark'] <= 2**63 - 1 or _encode(data) != value):
            _invalid()
        if kind == 'episodes':
            if data['last'] is None: _invalid()
            revision(data['last'])
        elif type(data['last']) is not int or not 1 <= data['last'] <= data['watermark']:
            _invalid()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, binascii.Error):
        _invalid()


def _where(scope):
    clauses = []; args = []
    if scope['account'] is not None:
        clauses.append("json_extract(e.record,'$.canon.account')=?"); args.append(scope['account'])
    if scope['series'] is not None:
        clauses.append('e.series=?'); args.append(scope['series'])
    return ' AND '.join(clauses) or '1', args


def _summary(service, db, key):
    record = service._episode(db, key); value = record['canon']['data']
    ident(record['canon']['account']); ident(value['series_id']); ident(value['episode_id'])
    if (type(record['ordinal']) is not int or not 1 <= record['ordinal'] <= 10000
            or not isinstance(record['job'], str) or not re.fullmatch('[a-f0-9]{24}', record['job'])
            or value['final_sha256'] is None): _invalid()
    revision(value['final_sha256']); draft = service._draft_head(db,key); revision(draft)
    return {'revision':key, 'account':record['canon']['account'], 'series_id':value['series_id'],
            'episode_id':value['episode_id'], 'ordinal':record['ordinal'],
            'final_sha256':value['final_sha256'], 'current':service._head(db,value['series_id']) == key,
            'job':record['job'], 'draft_revision':draft,
            'next_ordinal':record['ordinal'] + 1}


def _page(db, kind, scope, limit, cursor):
    condition, args = _where(scope)
    table = 'series_episodes e' if kind == 'episodes' else 'series_drafts d JOIN series_episodes e ON e.revision=d.previous'
    alias = 'e' if kind == 'episodes' else 'd'
    maximum = db.execute('SELECT COALESCE(MAX(rowid),0) FROM '+('series_episodes' if kind == 'episodes' else 'series_drafts')).fetchone()[0]
    decoded = _decode(cursor,kind,scope) if cursor is not None else None
    watermark = decoded['watermark'] if decoded else maximum
    if watermark > maximum: _invalid()
    bounded = condition+' AND '+alias+'.rowid<=?'; bounded_args = [*args,watermark]
    total = db.execute('SELECT COUNT(*) FROM '+table+' WHERE '+bounded,bounded_args).fetchone()[0]
    live_total = db.execute('SELECT COUNT(*) FROM '+table+' WHERE '+condition,args).fetchone()[0]
    after = ''; after_args = []
    if decoded:
        if kind == 'episodes':
            last = db.execute('SELECT e.series,e.ordinal FROM '+table+' WHERE '+bounded+' AND e.revision=?',[*bounded_args,decoded['last']]).fetchone()
            if not last: _invalid()
            after = ' AND (e.series,e.ordinal,e.revision)>(?,?,?)'
            after_args = [last['series'],last['ordinal'],decoded['last']]
        else:
            if not db.execute('SELECT 1 FROM '+table+' WHERE '+bounded+' AND d.rowid=?',[*bounded_args,decoded['last']]).fetchone(): _invalid()
            after = ' AND d.rowid>?'; after_args = [decoded['last']]
    fields = 'e.revision' if kind == 'episodes' else "d.rowid AS position,d.revision,d.previous,d.child,json_extract(e.record,'$.canon.account') AS account,e.series AS series_id,(SELECT h.revision=d.revision FROM series_draft_heads h WHERE h.previous=d.previous) AS current"
    order = 'e.series,e.ordinal,e.revision' if kind == 'episodes' else 'd.rowid'
    rows = db.execute('SELECT '+fields+' FROM '+table+' WHERE '+bounded+after+' ORDER BY '+order+' LIMIT ?',[*bounded_args,*after_args,limit+1]).fetchall()
    more = len(rows) > limit; rows = rows[:limit]
    next_cursor = _encode({'v':1,'kind':kind,'scope':scope,'watermark':watermark,
                          'last':rows[-1]['revision'] if kind == 'episodes' else rows[-1]['position']}) if more else None
    return rows, {'limit':limit,'total':total,'live_total':live_total,'cursor':cursor,
                  'next_cursor':next_cursor,'has_more':more,'watermark':watermark}


def state(service, query):
    if not isinstance(query, dict) or set(query) - FIELDS: _invalid()
    service.d.clean(query)
    scope = {'account':query.get('account'), 'series':query.get('series')}
    if 'account' in query and not is_serial(query['account']): _invalid()
    if 'series' in query: ident(query['series'])
    limit = query.get('limit',DEFAULT_LIMIT)
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT: _invalid()
    selected = query.get('selected_revision'); revision(selected)
    try:
        with service.d.connection() as db:
            db.execute('BEGIN')
            episode_rows, episode_page = _page(db,'episodes',scope,limit,query.get('episode_cursor'))
            draft_rows, draft_page = _page(db,'drafts',scope,limit,query.get('draft_cursor'))
            episodes = [_summary(service,db,r['revision']) for r in episode_rows]
            selected_episode = None
            if selected is not None:
                # Archive filters do not switch the active editor's reference.
                # Pin it independently, still within the requested account.
                condition,args = _where({'account':scope['account'],'series':None})
                if not db.execute('SELECT 1 FROM series_episodes e WHERE '+condition+' AND e.revision=?',[*args,selected]).fetchone(): _invalid()
                selected_episode = _summary(service,db,selected)
            series_ids = {r['series_id'] for r in episodes}
            if scope['series'] is not None: series_ids.add(scope['series'])
            if selected_episode: series_ids.add(selected_episode['series_id'])
            active = []
            for series_id in sorted(series_ids):
                head = service._head(db,series_id)
                if head:
                    summary = _summary(service,db,head)
                    if scope['account'] is None or summary['account'] == scope['account']: active.append(summary)
            drafts = []
            for row in draft_rows:
                revision(row['revision']); revision(row['previous']); ident(row['account']); ident(row['series_id'])
                if not isinstance(row['child'],str) or not re.fullmatch('[a-f0-9]{24}',row['child']): _invalid()
                # Preserve the legacy SQLite 0/1/NULL current field for API clients.
                drafts.append({k:row[k] for k in ('revision','previous','child','account','series_id','current')})
        return {'episodes':episodes,'drafts':drafts,'active_episodes':active,'selected_episode':selected_episode,
                'history':{'schema_version':1,'scope':scope,'episodes':episode_page,'drafts':draft_page},
                'human_acceptance':'incomplete','publication_ready':False}
    except (sqlite3.Error, ValueError, KeyError, TypeError, RecursionError):
        raise WorkflowError('SERIES_HISTORY_UNAVAILABLE: history could not be verified; no records changed') from None
