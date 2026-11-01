"""Local host-authored source snapshots and attested serial references.

Metadata only: no URL fetch, PDF/media import, provider transport or automatic
canon promotion. Hashes prove binding, not source truth or human acceptance.
"""
import copy
import json
import re
import unicodedata
from urllib.parse import urlsplit
from .security import WorkflowError,canonical,digest

from .account_packs import ACCOUNTS, is_serial


def text(value,maximum):
    if not isinstance(value,str) or not 1<=len(value.strip())<=maximum or any(ord(c)<32 and c not in '\n\t' for c in value):raise WorkflowError('Bounded context text required')
    return unicodedata.normalize('NFC',value.strip())


def ident(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z][a-z0-9-]{0,59}',value):raise WorkflowError('Context IDs must be simple stable IDs')
    return value


def revision(value):
    if value is not None and (not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value)):raise WorkflowError('Invalid context revision')
    return value


def account_id(account):
    if not isinstance(account,str) or account not in ACCOUNTS:raise WorkflowError('Unknown writing context account')
    return account


def sources(value):
    if not isinstance(value,dict) or len(value)>8:raise WorkflowError('At most eight host source references per revision')
    result={}
    for key,row in value.items():
        ident(key)
        if not isinstance(row,dict) or set(row)!={'url','title','locator','excerpt','rights_note'}:raise WorkflowError('Source fields must be URL/title/locator/short excerpt/rights note')
        data={k:text(row[k],2000 if k=='url' else 300 if k=='excerpt' else 240 if k=='rights_note' else 160) for k in row}
        if len(data['excerpt'].split())>25:raise WorkflowError('Source excerpt is limited to25words; raw references are not imported')
        try:p=urlsplit(data['url']);port=p.port
        except ValueError:raise WorkflowError('Invalid reference URL') from None
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or port not in (None,443) or any(c.isspace() for c in data['url']) or '\\' in data['url']:
            raise WorkflowError('Reference URL must be HTTPS without credentials, query or fragment; URLs are never fetched')
        result[key]=data
    return result


def canon(value):
    fields={'series_id','episode_id','bible_version','origin','final_sha256','accepted_by','narrator','cast','objects','open_clues','source_revision'}
    if not isinstance(value,dict) or set(value)!=fields:raise WorkflowError('Accepted final reference fields missing or unsupported; drafts are not canon')
    result={k:ident(value[k]) for k in ('series_id','episode_id')}
    result.update(bible_version=text(value['bible_version'],120),origin=value['origin'],final_sha256=revision(value['final_sha256']),accepted_by=text(value['accepted_by'],120),narrator=value['narrator'],source_revision=revision(value['source_revision']))
    if not result['final_sha256'] or not isinstance(result['origin'],str) or result['origin'] not in {'customer_attested_final','synthetic_reference_test'} or result['narrator']!='first_person':raise WorkflowError('Only explicitly attested final reference or labeled synthetic reference, first person, is allowed')
    for key,fields,maximum in [('cast',{'id','wardrobe'},8),('objects',{'id','state','identity_note'},16),('open_clues',{'id','object_id','description'},32)]:
        rows=value[key]
        if not isinstance(rows,list) or not (0 if key=='open_clues' else 1)<=len(rows)<=maximum:raise WorkflowError('Bounded canon cast/object/clue records required')
        normalized=[];ids=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!=fields:raise WorkflowError('Canon record fields missing or unsupported')
            rid=ident(row['id'])
            if rid in ids:raise WorkflowError('Canon record ID repeated')
            ids.add(rid);normalized.append({k:ident(v) if k in {'id','object_id'} else text(v,500) for k,v in row.items()})
        result[key]=normalized
    objects={r['id'] for r in result['objects']}
    if any(c['object_id'] not in objects for c in result['open_clues']):raise WorkflowError('Clue must reference a pinned object')
    return result


def snapshot(kind,account,data,parent):
    value={'kind':kind,'account':account,'parent':parent,'data':data};return {**value,'revision':digest(value)}


def validate_snapshot(value,kind,account):
    if not isinstance(value,dict) or set(value)!={'kind','account','parent','data','revision'} or value['kind']!=kind or value['account']!=account:raise WorkflowError('Context snapshot/account mismatch')
    revision(value['parent']);revision(value['revision']);normalized=sources(value['data']) if kind=='sources' else canon(value['data'])
    if normalized!=value['data'] or snapshot(kind,account,normalized,value['parent'])!=value:raise WorkflowError('Context snapshot hash/content changed')
    return value


def validate_binding(value,account):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'schema_version','account','sources','canon','binding_sha256'} or type(value['schema_version']) is not int or value['schema_version']!=1 or value['account']!=account:raise WorkflowError('Invalid host production context binding')
    for kind in ('sources','canon'):
        if value[kind] is not None:validate_snapshot(value[kind],kind,account)
    if value['canon'] is not None and not is_serial(account):raise WorkflowError('Serial canon belongs only to the serial profile')
    if digest({k:v for k,v in value.items() if k!='binding_sha256'})!=value['binding_sha256']:raise WorkflowError('Host context binding hash changed')
    if value['canon'] and value['canon']['data']['source_revision']!=(value['sources']['revision'] if value['sources'] else None):raise WorkflowError('Canon reference belongs to another source revision; explicit updated reference required')
    return value


def registry(binding):return binding['sources']['data'] if binding and binding['sources'] else None


def audit_bound_claims(brief):
    from .claims import audit_claims
    binding=validate_binding(brief.get('production_context'),brief.get('brand'))
    fiction=is_serial(brief.get('brand')) and brief.get('creative',{}).get('canon_status')=='noncanonical_fixture'
    return audit_claims(brief,registry(binding),fictional=fiction)


def validate_canon_proposal(value,binding):
    if not binding or not binding['canon']:return
    data=binding['canon']['data'];continuity=value['continuity'];objects={r['id']:r for r in data['objects']};cast={r['id']:r for r in data['cast']}
    if not continuity or continuity['object_id'] not in objects or continuity['previous']!=objects[continuity['object_id']]['state']:raise WorkflowError('Proposal must start at the same accepted reference object/state')
    if any(c['id'] not in cast or c['wardrobe']!=cast[c['id']]['wardrobe'] for c in value['creative']['characters']):raise WorkflowError('Proposal cast/wardrobe contradicts the selected accepted reference')
    # The current renderer vocabulary remains a noncanonical rehearsal. A
    # reference binding cannot silently upgrade it into an accepted new episode.
    if value['creative']['canon_status']!='noncanonical_fixture':raise WorkflowError('New proposal cannot promote itself to accepted canon')


def bound_brief(account,value,binding=None,history=()):
    from .creative import validate_proposal
    raw=copy.deepcopy(value);embedded=raw.pop('production_context',None)
    if binding is not None and embedded is not None and binding!=embedded:raise WorkflowError('Proposal host context binding changed')
    binding=validate_binding(binding if binding is not None else embedded,account)
    normalized=validate_proposal(account,raw,history=history,source_registry=registry(binding));validate_canon_proposal(normalized,binding)
    if binding is not None:normalized['production_context']=copy.deepcopy(binding)
    return normalized


class WritingContexts:
    def __init__(self,db,lock,safe):
        self.db=db;self.lock=lock;self.safe=safe
        with db() as conn:conn.executescript('''CREATE TABLE IF NOT EXISTS writing_context_revisions(revision TEXT PRIMARY KEY,kind TEXT,account TEXT,payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS writing_context_heads(kind TEXT,account TEXT,revision TEXT,PRIMARY KEY(kind,account));''')
    def _head(self,db,kind,account):
        row=db.execute('SELECT revision FROM writing_context_heads WHERE kind=? AND account=?',(kind,account)).fetchone();return row[0] if row else None
    def _snapshot(self,db,kind,account,head):
        if head is None:return None
        row=db.execute('SELECT payload FROM writing_context_revisions WHERE revision=? AND kind=? AND account=?',(head,kind,account)).fetchone()
        if not row:raise WorkflowError('Context revision missing')
        return validate_snapshot(json.loads(row[0]),kind,account)
    def state(self,account):
        account_id(account)
        with self.lock,self.db() as db:
            result={kind:self._snapshot(db,kind,account,self._head(db,kind,account)) for kind in ('sources','canon')}
        self.safe(result);return {'account':account,**result,'source_truth':'pending_human_review','canon_authority':'host_attested_reference_not_independent_final_QA'}
    def save(self,kind,account,data,expected,confirmed):
        account_id(account);revision(expected)
        if kind not in ('sources','canon') or kind=='canon' and not is_serial(account):raise WorkflowError('Unsupported context kind/profile')
        if confirmed is not True:raise WorkflowError('Explicit rights/accepted-final confirmation required')
        data=sources(data) if kind=='sources' else canon(data);self.safe(data)
        with self.lock,self.db() as db:
            db.execute('BEGIN IMMEDIATE');head=self._head(db,kind,account)
            if head!=expected:raise WorkflowError('Context revision changed; reload before saving')
            for r in db.execute("SELECT payload FROM llm_requests WHERE status IN ('dispatching','uncertain','received_after_cancel_review')"):
                if json.loads(r[0])['context']['account']==account:raise WorkflowError('Writing context locked by in-flight/uncertain account request; no silent rebind')
            source_head=self._head(db,'sources',account)
            if kind=='canon' and data['source_revision']!=source_head:raise WorkflowError('Accepted reference must pin the current source revision')
            prior=self._snapshot(db,kind,account,head)
            if prior and prior['data']==data:return self.state(account)
            value=snapshot(kind,account,data,head);self.safe(value)
            db.execute('INSERT INTO writing_context_revisions VALUES(?,?,?,?)',(value['revision'],kind,account,canonical(value)))
            db.execute('INSERT INTO writing_context_heads VALUES(?,?,?) ON CONFLICT(kind,account) DO UPDATE SET revision=excluded.revision',(kind,account,value['revision']))
        return self.state(account)
    def bind(self,account,source_revision=None,canon_revision=None):
        account_id(account);revision(source_revision);revision(canon_revision)
        with self.lock,self.db() as db:
            heads={k:self._head(db,k,account) for k in ('sources','canon')}
            if heads!={'sources':source_revision,'canon':canon_revision}:raise WorkflowError('Pin current source/canon revision; new preview/approval required')
            result={'schema_version':1,'account':account,**{k:self._snapshot(db,k,account,h) for k,h in heads.items()}}
        if not any(heads.values()):return None
        result['binding_sha256']=digest(result);return validate_binding(result,account)
    def assert_current(self,account,binding):
        validate_binding(binding,account)
        current=self.bind(account,binding['sources']['revision'] if binding and binding['sources'] else None,binding['canon']['revision'] if binding and binding['canon'] else None)
        if current!=binding:raise WorkflowError('Writing context changed; new preview required')
