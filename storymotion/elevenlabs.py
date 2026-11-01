"""Session BYOK + one-attempt ElevenLabs jobs. Live mode requires an explicit host flag.

No keys in env/vault/files/URLs, no SDK retries, no invoice hard-cap claim.
Demo transport is synthetic tone audio, never real TTS. Timestamps are fresh per audio.
"""
from .local_state import private_directory, private_database, write_private
from .local_state import guard_workspace
import base64
import contextlib
import hashlib
import http.client
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from .providers import SecretBroker,ProviderError,bounded_text,identifier,AUTH_HEADERS,validate_credential_provider,credential_echo,safe_public_json
from .security import canonical,digest,file_hash,within,write_json

MAX_BODY=20*1024*1024
def text_sha(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


def current_execution():
    from .provenance import execution_provenance
    return execution_provenance()['fingerprint']


class VoiceGateInvalidated(ProviderError):
    """Unspent consent no longer authorizes this exact wire request."""


def approval_budget(value,synthetic):
    if value is None and synthetic:
        return {'maximum_microusd':0,'estimate_microusd':0,'quote_source':'Synthetic transport; no charge','api_verified_usd_rate':False}
    if not isinstance(value,dict) or set(value)!={'max_usd','estimate_usd','quote_source','verified_by_user'} or value['verified_by_user'] is not True:
        raise ProviderError('CURRENT_USER_QUOTE_AND_FINITE_BUDGET_REQUIRED')
    from .engine import microusd
    try:maximum=microusd(value['max_usd']);estimate=microusd(value['estimate_usd'])
    except Exception:raise ProviderError('INVALID_VOICE_BUDGET') from None
    if maximum<estimate or (not synthetic and (maximum<=0 or estimate<=0)):raise ProviderError('VOICE_BUDGET_TOO_SMALL_OR_PRICE_UNKNOWN')
    source=bounded_text(value['quote_source'],1000)
    return {'maximum_microusd':maximum,'estimate_microusd':estimate,'quote_source':source,
            'api_verified_usd_rate':False,'price_provenance':'user supplied current quote; not independently API verified'}


class ElevenHTTP:
    synthetic=False
    def __init__(self,enabled=False,timeout=20):
        self.enabled=enabled;self.timeout=timeout;self.pending={};self.lock=threading.Lock()
    def cancel(self,operation):
        with self.lock:connection=self.pending.get(operation)
        if connection:connection.close()
    def request(self,method,path,key,body=None,operation=None,send_gate=None):
        if not self.enabled:raise ProviderError('ELEVENLABS_NETWORK_DISABLED')
        key=validate_credential_provider('elevenlabs',key)
        if key.startswith((b'FAKE_',b'TEST_ONLY_')):raise ProviderError('SYNTHETIC_KEY_CANNOT_GO_LIVE')
        if not ((method=='GET' and (path in {'/v1/models','/v1/user/subscription'} or path.startswith('/v2/voices?')))
                or (method=='POST' and re.fullmatch(r'/v1/text-to-speech/[A-Za-z0-9_-]{1,80}/with-timestamps\?output_format=mp3_44100_128',path))):
            raise ProviderError('ENDPOINT_NOT_ALLOWED')
        connection=http.client.HTTPSConnection('api.elevenlabs.io',timeout=self.timeout)
        operation=operation or uuid.uuid4().hex
        with self.lock:self.pending[operation]=connection
        try:
            deadline=time.monotonic()+self.timeout
            encoded=None if body is None else canonical(body).encode()
            headers={AUTH_HEADERS['elevenlabs']:key.decode('ascii'),'Content-Type':'application/json','Accept':'application/json'}
            if method=='POST' and not callable(send_gate):raise VoiceGateInvalidated('VOICE_WIRE_GATE_REQUIRED')
            with send_gate(method,path,encoded) if method=='POST' else contextlib.nullcontext():
                connection.request(method,path,body=encoded,headers=headers)
            response=connection.getresponse()
            if response.status!=200:raise ProviderError('HTTP_'+str(response.status))
            if response.getheader('Content-Type','').split(';')[0]!='application/json':raise ProviderError('INVALID_CONTENT_TYPE')
            chunks=[];total=0
            while True:
                if time.monotonic()>deadline:raise ProviderError('OUTCOME_UNCERTAIN')
                chunk=response.read1(min(65536,MAX_BODY+1-total))
                if not chunk:break
                chunks.append(chunk);total+=len(chunk)
                if total>MAX_BODY:raise ProviderError('RESPONSE_TOO_LARGE')
            raw=b''.join(chunks)
            if key in raw:raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
            try:return json.loads(raw),response.getheader('request-id') or response.getheader('x-request-id')
            except (ValueError,UnicodeError):raise ProviderError('INVALID_JSON') from None
        except ProviderError:raise
        except (OSError,TimeoutError,http.client.HTTPException):raise ProviderError('OUTCOME_UNCERTAIN') from None
        finally:
            connection.close()
            with self.lock:self.pending.pop(operation,None)


class ElevenDemo:
    synthetic=True
    def __init__(self):self.calls=[]
    def cancel(self,operation):pass
    def request(self,method,path,key,body=None,operation=None,send_gate=None):
        if not key.startswith((b'FAKE_',b'TEST_ONLY_')):raise ProviderError('SYNTHETIC_KEY_REQUIRED')
        if method=='POST' and not callable(send_gate):raise VoiceGateInvalidated('VOICE_WIRE_GATE_REQUIRED')
        with send_gate(method,path,canonical(body).encode()) if method=='POST' else contextlib.nullcontext():
            self.calls.append({'method':method,'path':path,'body_hash':digest(body) if body else None})
        if path.startswith('/v2/voices?'):return {'voices':[{'voice_id':'demo-voice','name':'Sentetik demo · insan sesi değil'}],'has_more':False},None
        if path=='/v1/models':return [{'model_id':'demo-model','name':'Yerel contract fixture','can_do_text_to_speech':True,
            'maximum_text_length_per_request':10000,'token_cost_factor':1,'model_rates':{'character_cost_multiplier':1,'cost_discount_multiplier':1}}],None
        if path=='/v1/user/subscription':return {'tier':'synthetic','character_count':0,'character_limit':100000,'max_credit_limit_extension':0},None
        if method!='POST':raise ProviderError('DEMO_ENDPOINT_UNKNOWN')
        text=body['text'];n=len(text)
        data=(Path(__file__).resolve().parents[1]/'fixtures/synthetic-voice-contract.mp3').read_bytes()
        alignment={'characters':list(text),'character_start_times_seconds':[i*4/n for i in range(n)],
                   'character_end_times_seconds':[(i+1)*4/n for i in range(n)]}
        return {'audio_base64':base64.b64encode(data).decode(),'alignment':alignment,'normalized_alignment':alignment},'synthetic-request'


def positive_int(value):return type(value) is int and 0<value<=1000000000


def validate_alignment(value,duration):
    if type(duration) not in {int,float} or not math.isfinite(duration) or duration<=0:raise ProviderError('INVALID_ALIGNMENT_DURATION')
    if value is None:return None
    if not isinstance(value,dict):raise ProviderError('INVALID_ALIGNMENT')
    chars=value.get('characters');starts=value.get('character_start_times_seconds');ends=value.get('character_end_times_seconds')
    if not all(isinstance(x,list) for x in [chars,starts,ends]) or not 1<=len(chars)<=60000 or len(chars)!=len(starts) or len(chars)!=len(ends):raise ProviderError('INVALID_ALIGNMENT')
    last_start=last_end=0
    for char,a,b in zip(chars,starts,ends):
        # Character spans may share/overlap a phonetic interval. Do not pretend
        # they are disjoint phonemes or clamp/reorder a provider response. Both
        # edges must be ordered and every interval must fit the measured audio.
        if not isinstance(char,str) or not 1<=len(char)<=8 or type(a) not in {int,float} or type(b) not in {int,float} or not math.isfinite(a) or not math.isfinite(b) or not 0<=a<=b<=duration or a<last_start or b<last_end:raise ProviderError('INVALID_ALIGNMENT')
        last_start=a;last_end=b
    return {'characters':chars,'character_start_times_seconds':starts,'character_end_times_seconds':ends}


def fresh_cues(script,tts,alignment):
    # Phonetic TTS substitutions never silently become on-screen spelling.
    if not alignment or script!=tts or ''.join(alignment['characters'])!=script:return None
    spans=list(re.finditer(r'\S+',script));groups=[];current=[]
    for span in spans:
        if current and span.end()-current[0].start()>42:groups.append(current);current=[]
        current.append(span)
        if span.group()[-1:] in '.!?':groups.append(current);current=[]
    if current:groups.append(current)
    cues=[]
    for group in groups:
        a=group[0].start();b=group[-1].end();start=alignment['character_start_times_seconds'][a];end=alignment['character_end_times_seconds'][b-1]
        if end<=start:return None
        cues.append({'start':start,'end':end,'text':script[a:b]})
    return cues


class ElevenService:
    def __init__(self,workspace,mode='off',client=None,ttl=900,approval_ttl=120,source_guard=None):
        if mode not in {'off','demo','live'}:raise ProviderError('INVALID_ELEVENLABS_MODE')
        self.root=guard_workspace(workspace,database='voice-jobs.sqlite3');private_directory(self.root)
        self.mode=mode;self.ttl=ttl;self.approval_ttl=approval_ttl
        self.runtime_execution=current_execution();self.source_guard=source_guard
        self.client=client or (ElevenDemo() if mode=='demo' else ElevenHTTP(enabled=mode=='live'))
        if bool(self.client.synthetic)!=(mode=='demo'):raise ProviderError('TRANSPORT_MODE_MISMATCH')
        self.broker=SecretBroker(real_intake_enabled=mode=='live',ttl_seconds=ttl)
        self.connections={};self.bindings={};self.timers={};self.lock=threading.RLock();self.threads={};self.owner=uuid.uuid4().hex
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS voice_requests(
              id TEXT PRIMARY KEY,job TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,
              approved_until REAL,deadline REAL,owner TEXT,dispatch_count INTEGER NOT NULL DEFAULT 0,
              artifact TEXT,error_code TEXT,approval TEXT,updated REAL NOT NULL,binding_scope TEXT);
              CREATE TABLE IF NOT EXISTS voice_events(seq INTEGER PRIMARY KEY,request TEXT,event TEXT,
                actual_cost_usd TEXT,created REAL NOT NULL);''')
            if 'approval' not in {r[1] for r in db.execute('PRAGMA table_info(voice_requests)')}:
                db.execute('ALTER TABLE voice_requests ADD COLUMN approval TEXT')
            if 'binding_scope' not in {r[1] for r in db.execute('PRAGMA table_info(voice_requests)')}:
                db.execute('ALTER TABLE voice_requests ADD COLUMN binding_scope TEXT')
            if 'claim_sha256' not in {r[1] for r in db.execute('PRAGMA table_info(voice_requests)')}:
                db.execute('ALTER TABLE voice_requests ADD COLUMN claim_sha256 TEXT')
            # Old unspent approvals have no credential-session scope and cannot
            # authorize any newly connected key after this security migration.
            db.execute("UPDATE voice_requests SET status='preview',approved_until=NULL,approval=NULL WHERE status='approved' AND binding_scope IS NULL")
            db.execute("UPDATE voice_requests SET status=CASE WHEN dispatch_count=0 THEN 'invalidated' ELSE 'uncertain' END,approval=CASE WHEN dispatch_count=0 THEN NULL ELSE approval END,approved_until=CASE WHEN dispatch_count=0 THEN NULL ELSE approved_until END,error_code='EXPIRED_DISPATCH_LEASE' WHERE status='dispatching' AND deadline<?",(time.time(),))
    @contextlib.contextmanager
    def db(self):
        guard_workspace(self.root,database='voice-jobs.sqlite3',canonical_alias=False)
        db=private_database(self.root,'voice-jobs.sqlite3',timeout=10);db.row_factory=sqlite3.Row
        try:yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    def event(self,request,event):
        with self.db() as db:db.execute('INSERT INTO voice_events(request,event,actual_cost_usd,created) VALUES(?,?,?,?)',
            (request,event,'0' if self.client.synthetic else None,time.time()))
    def config(self):return {'mode':self.mode,'network_enabled':self.mode=='live','synthetic':self.client.synthetic,
        'key_storage':'session RAM only; active expiry; no env/vault/file','ttl_seconds':self.ttl,
        'live_validation_performed':False,'usd_price':'unknown; no fixed price or invoice cap'}
    def _connection(self,ref):
        with self.lock:
            c=self.connections.get(ref)
            if not c or c['expires']<=time.monotonic():self.disconnect(ref);raise ProviderError('CONNECTION_EXPIRED')
            return dict(c)
    def _scope(self,ref):
        self._connection(ref)
        # Non-credential identifier. No key, key hash or provider account claim
        # is persisted; a new connection always needs its own spending consent.
        return digest({'service_session':self.owner,'connection':ref})
    def connect(self,value):
        if self.mode=='off':raise ProviderError('ELEVENLABS_DISABLED_START_DEMO_OR_EXPLICIT_LIVE_MODE')
        ref=uuid.uuid4().hex
        slot=self.broker.put('elevenlabs',ref,ref,value,synthetic=self.client.synthetic)
        with self.lock:
            self.connections[ref]={'slot':slot,'expires':time.monotonic()+self.ttl,'metadata':None,'metadata_until':0}
            timer=threading.Timer(self.ttl,self.disconnect,args=(ref,));timer.daemon=True;self.timers[ref]=timer;timer.start()
        try:metadata=self.metadata(ref)
        except Exception:self.disconnect(ref);raise
        return {'connection':ref,'expires_in_seconds':self.ttl,'metadata':metadata,**self.config()}
    def disconnect(self,ref=None):
        requests=[]
        with self.lock:
            refs=list(self.connections) if ref is None else [ref]
            for key in refs:
                c=self.connections.pop(key,None);timer=self.timers.pop(key,None)
                if timer:timer.cancel()
                if c:self.broker.clear(c['slot'])
                for request,binding in list(self.bindings.items()):
                    if binding==key:
                        self.bindings.pop(request,None)
                        requests.append((request,digest({'service_session':self.owner,'connection':key})))
        for request,scope in requests:
            try:
                row=self.row(request)
                if row['binding_scope']==scope and row['status'] in {'preview','approved','dispatching'}:self.cancel(request)
            except ProviderError:pass
        return {'disconnected':True}
    def metadata(self,ref):
        c=self._connection(ref)
        with self.lock:self.connections[ref]['metadata_until']=0
        deadline=time.monotonic()+40
        def fetch(path,key):
            if time.monotonic()>deadline:raise ProviderError('METADATA_TIMEOUT')
            try:return self.client.request('GET',path,key)
            except ProviderError as ex:
                if ex.code in {'HTTP_401','HTTP_403'}:self.disconnect(ref)
                raise
        with self.broker.lease(c['slot'],'elevenlabs',ref,ref,self.client.synthetic) as key:
            voices=[];token=None;tokens=set();has_more=False
            for _ in range(5):
                query={'page_size':100,'include_total_count':'false'}
                if token:query['next_page_token']=token
                data,_=fetch('/v2/voices?'+urlencode(query),key)
                if credential_echo(data,key) or not isinstance(data,dict) or not isinstance(data.get('voices'),list):raise ProviderError('INVALID_VOICE_LIST')
                for v in data['voices']:
                    if not isinstance(v,dict) or len(voices)>=1000:raise ProviderError('INVALID_OR_OVERSIZED_VOICE_LIST')
                    voices.append({'voice_id':identifier(v.get('voice_id',''),80),'name':bounded_text(v.get('name','Unnamed voice'),160)})
                has_more=data.get('has_more') is True
                if not has_more:break
                token=data.get('next_page_token')
                if not isinstance(token,str) or not 1<=len(token)<=2000 or token in tokens:raise ProviderError('INVALID_VOICE_PAGINATION')
                tokens.add(token)
            models,_=fetch('/v1/models',key)
            if not isinstance(models,list) or credential_echo(models,key):raise ProviderError('INVALID_MODEL_LIST')
            selected=[]
            for m in models:
                if not isinstance(m,dict):raise ProviderError('INVALID_MODEL_LIST')
                if m.get('can_do_text_to_speech') is not True:continue
                maximum=m.get('maximum_text_length_per_request')
                rate_data=m.get('model_rates') if isinstance(m.get('model_rates'),dict) else {}
                rate_data={k:(rate_data.get(k) if type(rate_data.get(k)) in {int,float} and math.isfinite(rate_data[k]) and 0<=rate_data[k]<=100 else None)
                           for k in ['character_cost_multiplier','cost_discount_multiplier']}
                selected.append({'model_id':identifier(m.get('model_id','')),'name':bounded_text(m.get('name') or m.get('model_id'),160),
                    'maximum_text_length_per_request':maximum if positive_int(maximum) else None,
                    'token_cost_factor':m.get('token_cost_factor') if type(m.get('token_cost_factor')) in {int,float} and math.isfinite(m['token_cost_factor']) and 0<m['token_cost_factor']<=100 else None,
                    'provider_rate_multipliers':rate_data,'verified_usd_rate':False,
                    'requires_alpha_access':m.get('requires_alpha_access') is True})
            subscription,_=fetch('/v1/user/subscription',key)
            if credential_echo(subscription,key) or not isinstance(subscription,dict):raise ProviderError('INVALID_SUBSCRIPTION')
            used=subscription.get('character_count');limit=subscription.get('character_limit')
            if type(used) is not int or used<0 or not positive_int(limit):raise ProviderError('QUOTA_UNVERIFIED')
            metadata={'voices':voices,'voices_truncated':has_more,'models':selected,'subscription':{'used':used,'limit':limit,'remaining':max(0,limit-used)},
                      'observed_at':time.time(),'usd_estimate':None,'price_source':'API model/count metadata; no verified USD rate',
                      'access_scope':'Listed TTS capability is not a guarantee that every voice/model combination is allowed'}
        with self.lock:
            if ref not in self.connections:raise ProviderError('CONNECTION_EXPIRED')
            self.connections[ref].update(metadata=metadata,metadata_until=time.monotonic()+120)
        return metadata
    def _ready_metadata(self,ref):
        c=self._connection(ref)
        if not c['metadata'] or c['metadata_until']<=time.monotonic():raise ProviderError('REFRESH_METADATA_BEFORE_APPROVAL')
        return c['metadata']
    def _verify_source(self,p):
        if p.get('execution_fingerprint')!=self.runtime_execution or current_execution()!=self.runtime_execution:
            raise VoiceGateInvalidated('VOICE_SOURCE_INVALIDATED')
        if self.source_guard:
            try:self.source_guard(p)
            except Exception:raise VoiceGateInvalidated('VOICE_SOURCE_INVALIDATED') from None
    def _verify_payload(self,request,p):
        fields={'job','source_script','source_script_sha256','tts_text','text_sha256','voice_id','model_id','characters','output_format','execution_fingerprint'}
        if not isinstance(p,dict) or set(p)!=fields or digest(p)[:32]!=request:
            raise VoiceGateInvalidated('VOICE_PAYLOAD_INVALIDATED')
        if (any(not isinstance(p[k],str) for k in fields-{'characters'}) or
            text_sha(p['source_script'])!=p['source_script_sha256'] or text_sha(p['tts_text'])!=p['text_sha256'] or
            type(p['characters']) is not int or p['characters']!=len(p['tts_text']) or p['output_format']!='mp3_44100_128'):
            raise VoiceGateInvalidated('VOICE_PAYLOAD_INVALIDATED')
        self._verify_source(p)
    def _verify_approval(self,request,p,approval,scope):
        expected={'request':request,'job':p['job'],'source_script_sha256':p['source_script_sha256'],
            'text_sha256':p['text_sha256'],'voice_id':p['voice_id'],'model_id':p['model_id'],'output_format':p['output_format'],
            'payload_sha256':digest(p),'execution_fingerprint':p['execution_fingerprint'],'connection_scope':scope}
        if (not isinstance(approval,dict) or any(approval.get(k)!=v for k,v in expected.items()) or approval.get('ack_unknown_cost') is not True or approval.get('rights_confirmed') is not True or
            type(approval.get('maximum_characters')) is not int or not p['characters']<=approval['maximum_characters']<=10000):
            raise VoiceGateInvalidated('VOICE_APPROVAL_SCOPE_MISMATCH')
    def _wire_connection(self,ref):
        # No disconnect/cancel side effects while a DB transaction is held.
        # The enclosing service lock serializes expiry, rebind and metadata edits.
        c=self.connections.get(ref)
        if not c or c['expires']<=time.monotonic():raise VoiceGateInvalidated('VOICE_CONNECTION_INVALIDATED')
        if not c['metadata'] or c['metadata_until']<=time.monotonic():raise VoiceGateInvalidated('VOICE_METADATA_INVALIDATED')
        return c
    def _verify_selection(self,ref,p,metadata=None):
        m=metadata if metadata is not None else self._ready_metadata(ref)
        selected=next((v for v in m['models'] if v['model_id']==p['model_id']),None)
        if (p['voice_id'] not in {v['voice_id'] for v in m['voices']} or not selected or selected['requires_alpha_access'] or
            not positive_int(selected['maximum_text_length_per_request']) or p['characters']>min(selected['maximum_text_length_per_request'],10000,m['subscription']['remaining'])):
            raise VoiceGateInvalidated('VOICE_MODEL_OR_QUOTA_INVALIDATED')
    def _claim_hash(self,row):
        return digest({k:row[k] for k in ['id','job','payload','approval','approved_until','binding_scope','owner','deadline']})
    def row(self,request):
        if not isinstance(request,str) or not re.fullmatch('[a-f0-9]{32}',request):raise ProviderError('INVALID_VOICE_REQUEST')
        with self.db() as db:
            db.execute("UPDATE voice_requests SET status=CASE WHEN dispatch_count=0 THEN 'invalidated' ELSE 'uncertain' END,approval=CASE WHEN dispatch_count=0 THEN NULL ELSE approval END,approved_until=CASE WHEN dispatch_count=0 THEN NULL ELSE approved_until END,error_code='EXPIRED_DISPATCH_LEASE',updated=? WHERE id=? AND status='dispatching' AND deadline<?",(time.time(),request,time.time()))
            r=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
        if not r:raise ProviderError('VOICE_REQUEST_NOT_FOUND')
        return dict(r)
    def preview(self,ref,job,script,text,voice,model):
        identifier(job);bounded_text(script,10000);bounded_text(text,10000);identifier(voice,80);identifier(model)
        metadata=self._ready_metadata(ref)
        if voice not in {v['voice_id'] for v in metadata['voices']}:raise ProviderError('VOICE_NOT_IN_CURRENT_LIST')
        selected=next((m for m in metadata['models'] if m['model_id']==model),None)
        if not selected or selected['requires_alpha_access']:raise ProviderError('MODEL_ACCESS_NOT_VERIFIED')
        maximum=selected['maximum_text_length_per_request']
        if not maximum:raise ProviderError('MODEL_LIMIT_UNVERIFIED')
        if len(text)>min(maximum,10000) or len(text)>metadata['subscription']['remaining']:raise ProviderError('CHARACTER_LIMIT_EXCEEDED')
        payload={'job':job,'source_script':script,'source_script_sha256':text_sha(script),'tts_text':text,'text_sha256':text_sha(text),
                 'voice_id':voice,'model_id':model,'characters':len(text),'output_format':'mp3_44100_128','execution_fingerprint':self.runtime_execution}
        self._verify_source(payload)
        safe_public_json(payload,self.broker)
        request=digest(payload)[:32]
        with self.lock,self.db() as db:
            scope=self._scope(ref)
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO voice_requests(id,job,payload,status,updated) VALUES(?,?,?,?,?)',
                       (request,job,canonical(payload),'preview',time.time()))
            old=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
            if old['dispatch_count'] or old['status'] in {'dispatching','uncertain','received_after_cancel_review','completed','failed_known_no_retry'}:
                if old['binding_scope']!=scope and old['status']!='completed':
                    raise ProviderError('VOICE_REQUEST_SCOPE_LOCKED_AFTER_DISPATCH')
                # Completed artifacts can be reused without sending any key;
                # preview must not transfer an in-flight dispatch binding.
            else:
                if old['binding_scope']!=scope or old['status'] in {'cancelled','blocked_before_dispatch','invalidated'}:
                    db.execute("UPDATE voice_requests SET status='preview',approved_until=NULL,approval=NULL,claim_sha256=NULL,binding_scope=?,error_code=NULL,updated=? WHERE id=?",(scope,time.time(),request))
                self.bindings[request]=ref
        self.event(request,'previewed_no_generation')
        return {**self.get(request),'characters':len(text),'model':selected,'quota_snapshot':metadata['subscription'],
                'usd_estimate':None,'billing_cap_guaranteed':False,'maximum_dispatches':1,
                'metadata_observed_at':metadata['observed_at'],'price_source':metadata['price_source'],
                'approval_required':'Exact text/voice/model + finite character cap + acknowledgement of unknown USD/voice rights',
                'text_sha256':payload['text_sha256'],'synthetic':self.client.synthetic}
    def approve(self,ref,request,source_script,maximum_characters,ack_unknown_cost,rights_confirmed,budget=None):
        self._ready_metadata(ref);r=self.row(request);p=json.loads(r['payload'])
        if self.bindings.get(request)!=ref or text_sha(source_script)!=p['source_script_sha256']:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
        if ack_unknown_cost is not True or rights_confirmed is not True or type(maximum_characters) is not int or not p['characters']<=maximum_characters<=10000:raise ProviderError('EXPLICIT_VOICE_APPROVAL_REQUIRED')
        budget=approval_budget(budget,self.client.synthetic)
        safe_public_json(budget,self.broker)
        with self.lock,self.db() as db:
            scope=self._scope(ref)
            metadata=self._wire_connection(ref)['metadata']
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
            p=json.loads(r['payload']);self._verify_payload(request,p);self._verify_selection(ref,p,metadata)
            if self.bindings.get(request)!=ref or r['binding_scope']!=scope:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
            if text_sha(source_script)!=p['source_script_sha256']:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
            if not p['characters']<=maximum_characters<=10000:raise ProviderError('EXPLICIT_VOICE_APPROVAL_REQUIRED')
            if r['dispatch_count'] or r['status'] not in {'preview','approved'}:raise ProviderError('VOICE_REQUEST_CANNOT_BE_REAPPROVED')
            approval={'maximum_characters':maximum_characters,'ack_unknown_cost':True,'rights_confirmed':True,
                'text_sha256':p['text_sha256'],'voice_id':p['voice_id'],'model_id':p['model_id'],'approved_at':time.time(),'budget':budget,
                'connection_scope':scope,'request':request,'job':p['job'],'source_script_sha256':p['source_script_sha256'],
                'output_format':p['output_format'],'payload_sha256':digest(p),'execution_fingerprint':p['execution_fingerprint']}
            db.execute("UPDATE voice_requests SET status='approved',approved_until=?,approval=?,updated=? WHERE id=?",(time.time()+self.approval_ttl,canonical(approval),time.time(),request))
        self.event(request,'approved_one_attempt_unknown_usd_acknowledged');return self.get(request)
    def _claim(self,ref,request,source_script):
        previous=self.row(request)
        if text_sha(source_script)!=json.loads(previous['payload'])['source_script_sha256']:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
        if previous['status']=='completed':return False
        self._ready_metadata(ref);self._connection(ref)
        with self.lock,self.db() as db:
            scope=self._scope(ref)
            metadata=self._wire_connection(ref)['metadata']
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
            if not r:raise ProviderError('VOICE_REQUEST_NOT_FOUND')
            p=json.loads(r['payload'])
            self._verify_payload(request,p);self._verify_selection(ref,p,metadata)
            if self.bindings.get(request)!=ref or text_sha(source_script)!=p['source_script_sha256']:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
            if r['status']=='completed':return False
            if r['status']!='approved' or not r['approved_until'] or r['approved_until']<=time.time() or r['dispatch_count']:raise ProviderError('FRESH_APPROVAL_REQUIRED_OR_NO_RETRY')
            approval=json.loads(r['approval']) if r['approval'] else {}
            if r['binding_scope']!=scope or approval.get('connection_scope')!=scope:raise ProviderError('VOICE_APPROVAL_SCOPE_MISMATCH')
            self._verify_approval(request,p,approval,scope)
            hold=db.execute("SELECT count(*) FROM voice_requests WHERE status IN ('dispatching','uncertain','received_after_cancel_review')").fetchone()[0]
            if hold:raise ProviderError('ANOTHER_VOICE_REQUEST_OR_UNCERTAIN_HOLD')
            db.execute("UPDATE voice_requests SET status='dispatching',owner=?,deadline=?,updated=? WHERE id=?",(self.owner,time.time()+90,time.time(),request))
            claimed=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
            db.execute('UPDATE voice_requests SET claim_sha256=? WHERE id=?',(self._claim_hash(claimed),request))
        return True
    def execute(self,ref,request,source_script,asynchronous=True):
        if not self._claim(ref,request,source_script):return self.get(request)
        if asynchronous:
            thread=threading.Thread(target=self._work,args=(ref,request),daemon=True)
            with self.lock:self.threads[request]=thread
            thread.start();return self.get(request)
        self._work(ref,request);return self.get(request)
    def _work(self,ref,request):
        attempt={'sent':False};key=b''
        try:
            c=self._connection(ref);r=self.row(request);p=json.loads(r['payload'])
            with self.broker.lease(c['slot'],'elevenlabs',ref,ref,self.client.synthetic) as key:
                if r['status']!='dispatching' or r['owner']!=self.owner:return
                response,provider_id=self.client.request('POST','/v1/text-to-speech/'+p['voice_id']+'/with-timestamps?output_format=mp3_44100_128',
                    key,{'text':p['tts_text'],'model_id':p['model_id']},operation=request,
                    send_gate=lambda method,path,encoded:self._wire_gate(ref,request,r,p,method,path,encoded,attempt))
                if not attempt['sent']:raise VoiceGateInvalidated('VOICE_WIRE_GATE_NOT_CONSUMED')
                if credential_echo([response,provider_id],key):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
                if not isinstance(response,dict):raise ProviderError('INVALID_TTS_RESPONSE')
                try:audio=base64.b64decode(response['audio_base64'],validate=True)
                except (ValueError,KeyError,TypeError):raise ProviderError('INVALID_AUDIO_BASE64') from None
                if not 100<=len(audio)<=12*1024*1024 or key in audio or not (audio.startswith(b'ID3') or audio[0]==255 and audio[1]&224==224):raise ProviderError('INVALID_AUDIO_OR_SECRET_ECHO')
                out=within(self.root,request);private_directory(out)
                temp=out/'narration.tmp.mp3';write_private(temp,audio)
                from .engine import probe,checked_process
                from .audio_input import approved_audio_options
                input_options=approved_audio_options(temp)
                media=probe(temp,restricted_audio=True)
                if not 0<media['duration']<=1800 or not any(s['codec_type']=='audio' for s in media['streams']):raise ProviderError('INVALID_AUDIO_DECODE')
                checked_process(['ffmpeg','-v','error','-xerror',*input_options,'-i',temp,'-map','0:a:0','-c:a','pcm_s16le','-f','null','-'],timeout=60)
                alignment=validate_alignment(response.get('alignment'),media['duration'])
                validate_alignment(response.get('normalized_alignment'),media['duration'])
                cues=fresh_cues(p['source_script'],p['tts_text'],alignment)
                sha=hashlib.sha256(audio).hexdigest();temp.replace(out/'narration.mp3')
                timing={'source_audio_sha256':sha,'audio_duration_seconds':media['duration'],'tts_text_sha256':p['text_sha256'],
                    'alignment':alignment,'cues':cues,'old_subtitles_invalid':True,'old_visemes_invalid':True,
                    'visemes':'not_generated; fresh phonetic/visual review required if avatar is used',
                    'scene_timing':'must be re-anchored to this audio; old scene timing cannot be reused','human_listening':'pending',
                    'subtitle_status':'fresh_provider_timing_needs_review' if cues else 'manual_screen_text_mapping_required',
                    'synthetic':self.client.synthetic}
                write_json(out/'timestamps.json',timing)
                if cues:
                    def stamp(t):
                        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
                    write_private(out/'fresh-subtitles.srt','\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
                files={n:file_hash(out/n) for n in ['narration.mp3','timestamps.json']+(['fresh-subtitles.srt'] if cues else [])}
                receipt={'files':files,'source_audio_sha256':sha,'duration':media['duration'],'technical_decode':'pass',
                    'provider_id':identifier(provider_id,160) if provider_id else None,'actual_cost_usd':0 if self.client.synthetic else None,
                    'cost_status':'synthetic_no_charge' if self.client.synthetic else 'unknown_until_provider_billing_receipt',
                    'fresh_timing_required':True,'publication_ready':False,'synthetic':self.client.synthetic}
                if credential_echo(receipt,key):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
                with self.db() as db:
                    db.execute('BEGIN IMMEDIATE');current=db.execute('SELECT status FROM voice_requests WHERE id=?',(request,)).fetchone()[0]
                    status='completed' if current=='dispatching' else 'received_after_cancel_review'
                    db.execute('UPDATE voice_requests SET status=?,artifact=?,updated=? WHERE id=?',(status,canonical(receipt),time.time(),request))
                with self.lock:
                    if ref in self.connections:self.connections[ref]['metadata_until']=0
                self.event(request,'audio_received_fresh_timing_pending')
        except Exception as ex:
            code=ex.code if isinstance(ex,ProviderError) else 'LOCAL_AUDIO_OR_PROVIDER_VALIDATION_FAILED'
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}',str(code)) or credential_echo(code,key) or self.broker.contains_secret(str(code).encode()):code='VOICE_OPERATION_FAILED'
            # A 5xx may arrive after the vendor accepted work. It cannot release
            # the uncertainty hold or imply that the request was not charged.
            known_rejection=code.startswith('HTTP_4')
            status=('invalidated' if isinstance(ex,VoiceGateInvalidated) else 'blocked_before_dispatch') if not attempt['sent'] else 'failed_known_no_retry' if known_rejection else 'uncertain'
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE');now=db.execute('SELECT status,dispatch_count FROM voice_requests WHERE id=?',(request,)).fetchone()
                # A duplicate worker must not overwrite the actual sender's state.
                if attempt['sent'] or now['dispatch_count']==0 and now['status'] not in {'cancelled','completed'}:
                    db.execute('UPDATE voice_requests SET status=?,error_code=?,approved_until=CASE WHEN ? THEN approved_until ELSE NULL END,approval=CASE WHEN ? THEN approval ELSE NULL END,updated=? WHERE id=?',
                        (status,code,attempt['sent'],attempt['sent'],time.time(),request))
            self.event(request,code)
            if code in {'HTTP_401','HTTP_403'}:self.disconnect(ref)
        finally:
            key=b''
            with self.lock:self.threads.pop(request,None)
    @contextlib.contextmanager
    def _wire_gate(self,ref,request,claimed,p,method,path,encoded,attempt):
        # The transport calls this after preparation, immediately around its
        # connection.request write. DB claim and connection mutation serialize.
        with self.lock:
            metadata=self._wire_connection(ref)['metadata']
            scope=digest({'service_session':self.owner,'connection':ref})
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
                if not r or r['status']!='dispatching' or r['owner']!=self.owner or r['dispatch_count']!=0:
                    raise VoiceGateInvalidated('VOICE_WIRE_CLAIM_INVALIDATED')
                if not r['approved_until'] or r['approved_until']<=time.time() or not r['deadline'] or r['deadline']<=time.time():
                    raise VoiceGateInvalidated('VOICE_APPROVAL_EXPIRED_BEFORE_WIRE')
                if self.bindings.get(request)!=ref or r['binding_scope']!=scope:raise VoiceGateInvalidated('VOICE_CONNECTION_INVALIDATED')
                current=json.loads(r['payload']);approval=json.loads(r['approval']) if r['approval'] else {}
                self._verify_payload(request,current);self._verify_approval(request,current,approval,scope);self._verify_selection(ref,current,metadata)
                if r['job']!=current['job'] or canonical(current)!=canonical(p) or not r['claim_sha256'] or r['claim_sha256']!=claimed['claim_sha256'] or r['claim_sha256']!=self._claim_hash(r):
                    raise VoiceGateInvalidated('VOICE_CLAIM_BINDING_INVALIDATED')
                expected_path='/v1/text-to-speech/'+current['voice_id']+'/with-timestamps?output_format=mp3_44100_128'
                expected_body=canonical({'text':current['tts_text'],'model_id':current['model_id']}).encode()
                if method!='POST' or path!=expected_path or encoded!=expected_body:raise VoiceGateInvalidated('VOICE_WIRE_BODY_INVALIDATED')
                if r['approved_until']<=time.time() or r['deadline']<=time.time():raise VoiceGateInvalidated('VOICE_APPROVAL_EXPIRED_BEFORE_WIRE')
                db.execute('UPDATE voice_requests SET dispatch_count=1,updated=? WHERE id=?',(time.time(),request))
                db.execute('INSERT INTO voice_events(request,event,actual_cost_usd,created) VALUES(?,?,?,?)',
                    (request,'dispatch_intent_committed','0' if self.client.synthetic else None,time.time()))
            attempt['sent']=True
            yield
    def cancel(self,request):
        r=self.row(request)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM voice_requests WHERE id=?',(request,)).fetchone()
            if r['status'] in {'preview','approved'} or r['status']=='dispatching' and r['dispatch_count']==0:
                db.execute("UPDATE voice_requests SET status='cancelled',updated=? WHERE id=?",(time.time(),request))
            elif r['status']=='dispatching':
                db.execute("UPDATE voice_requests SET status='uncertain',error_code='CANCEL_AFTER_DISPATCH',updated=? WHERE id=?",(time.time(),request))
        if r['dispatch_count']:self.client.cancel(request)
        self.event(request,'cancel_requested_no_automatic_retry');return self.get(request)
    def get(self,request):
        r=self.row(request);p=json.loads(r['payload']);artifact=json.loads(r['artifact']) if r['artifact'] else None
        if artifact:
            for n,h in artifact['files'].items():
                path=within(self.root,request+'/'+n)
                if not path.is_file() or file_hash(path)!=h:raise ProviderError('VOICE_ARTIFACT_HASH_MISMATCH')
        return {'request':request,'job':r['job'],'status':r['status'],'voice_id':p['voice_id'],'model_id':p['model_id'],
            'characters':p['characters'],'text_sha256':p['text_sha256'],'approved_until':r['approved_until'],
            'dispatch_count':r['dispatch_count'],'error_code':r['error_code'],'artifact':artifact,
            'approval':json.loads(r['approval']) if r['approval'] else None,
            'automatic_retry':False,'actual_cost_usd':0 if self.client.synthetic else None}
    def job_state(self,job):
        with self.db() as db:rows=db.execute('SELECT id FROM voice_requests WHERE job=? ORDER BY updated DESC',(job,)).fetchall()
        return [self.get(r['id']) for r in rows]
    def guard_old_timing(self,job):
        states=self.job_state(job)
        if any(x['artifact'] or x['status'] in {'dispatching','uncertain','received_after_cancel_review'} for x in states):
            raise ProviderError('NEW_AUDIO_REQUIRES_FRESH_TIMING_REVIEW_BEFORE_OLD_PREPARE_CHECK_EXPORT')
    def download(self,request,name):
        r=self.get(request)
        if not r['artifact'] or name not in r['artifact']['files']:raise ProviderError('VOICE_FILE_NOT_AVAILABLE')
        data=within(self.root,request+'/'+name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=r['artifact']['files'][name]:raise ProviderError('VOICE_ARTIFACT_HASH_MISMATCH')
        return data
