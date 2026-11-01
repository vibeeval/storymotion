"""Capability metadata and host-code-only endpoint registrations.

This module performs no I/O except reading the descriptive catalog. It holds no
credential, transport or dispatcher, and cannot authorize a paid call. Existing
secret leases, exact connection approvals and durable claims remain mandatory.
"""
import copy
import dataclasses
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit
from .security import WorkflowError

ROOT=Path(__file__).resolve().parents[1]
REMOTE_PROOF='implemented_contract_tested_live_unverified'
LOCAL_PROOF='implemented_local_runtime_unverified'
STATUSES=(REMOTE_PROOF,LOCAL_PROOF,'planned','no_verified_public_api','unknown_not_verified')


def _id(value):return isinstance(value,str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,79}',value) is not None
def _scope(provider,capability):return provider+':'+capability


@dataclasses.dataclass(frozen=True)
class QueryParameter:
    name:str
    kind:str='literal'
    values:tuple=()
    required:bool=True
    max_length:int=2048
    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}',self.name) or self.name.lower() in {'key','apikey','api_key','token','access_token','secret','authorization'}:raise WorkflowError('Credential query parameters are not allowed')
        if self.kind not in {'literal','identifier','cursor'} or type(self.required) is not bool or type(self.values) is not tuple or type(self.max_length) is not int or not 1<=self.max_length<=2048:raise WorkflowError('Invalid host query registration')
        if self.kind=='literal' and (not self.values or any(not isinstance(v,str) or len(v)>self.max_length for v in self.values)):raise WorkflowError('Literal query registration needs fixed values')
        if self.kind!='literal' and self.values:raise WorkflowError('Dynamic query registration cannot supply aliases')
    def accepts(self,value):
        if not isinstance(value,str) or not 1<=len(value)<=self.max_length:return False
        if self.kind=='literal':return value in self.values
        if self.kind=='identifier':return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',value)) and '..' not in value
        return all(32<=ord(c)<=126 for c in value) # opaque, query-only pagination data


@dataclasses.dataclass(frozen=True)
class Endpoint:
    method:str
    origin:str
    path_template:str
    query:tuple=()
    parameter_limits:tuple=()
    def __post_init__(self):
        try:origin=urlsplit(self.origin);port=origin.port
        except ValueError:raise WorkflowError('Invalid fixed endpoint origin') from None
        if self.method not in {'GET','POST','DELETE','PATCH'} or origin.scheme!='https' or origin.path or origin.query or origin.fragment or origin.username or origin.password or port is not None or '?' in self.origin or '#' in self.origin:
            raise WorkflowError('Endpoint origin must be one fixed HTTPS host without credentials, port or path')
        if not origin.hostname or origin.netloc!=origin.hostname or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',origin.hostname):raise WorkflowError('Endpoint registration needs a fixed public hostname')
        path=self.path_template
        if not isinstance(path,str) or not path.startswith('/') or len(path)>300 or any(c in path for c in ['?','#','%','\\','*']) or any(ord(c)<33 or ord(c)>126 for c in path) or '//' in path or '..' in path:
            raise WorkflowError('Endpoint path must be a bounded fixed path template')
        parameters=re.findall(r'\{([^{}]+)\}',path)
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',p) for p in parameters) or '{' in re.sub(r'\{[^{}]+\}','',path) or '}' in re.sub(r'\{[^{}]+\}','',path):raise WorkflowError('Invalid endpoint path parameter')
        if type(self.parameter_limits) is not tuple or any(type(p) is not tuple or len(p)!=2 or p[0] not in parameters or type(p[1]) is not int or not 1<=p[1]<=160 for p in self.parameter_limits) or len(dict(self.parameter_limits))!=len(self.parameter_limits):raise WorkflowError('Invalid host path parameter limit')
        if type(self.query) is not tuple or any(type(q) is not QueryParameter for q in self.query) or len({q.name for q in self.query})!=len(self.query):raise WorkflowError('Endpoint query parameters must be unique host registrations')
    def accepts(self,method,url):
        if method!=self.method or not isinstance(url,str) or len(url)>4096 or '\\' in url or '#' in url or any(ord(c)<33 or ord(c)>126 for c in url) or re.search(r'%(?![0-9a-fA-F]{2})',url):return False
        try:parsed=urlsplit(url)
        except ValueError:return False
        if parsed.scheme+'://'+parsed.netloc!=self.origin or parsed.fragment or parsed.username or parsed.password:return False
        if '%' in parsed.path or '..' in parsed.path:return False
        pieces=re.split(r'(\{[a-z][a-z0-9_]*\})',self.path_template)
        limits=dict(self.parameter_limits)
        pattern=''.join(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,'+str(limits.get(part[1:-1],160)-1)+'}' if part.startswith('{') else re.escape(part) for part in pieces)
        if not re.fullmatch(pattern,parsed.path):return False
        try:pairs=parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True,max_num_fields=20) if parsed.query else []
        except ValueError:return False
        values=dict(pairs);rules={q.name:q for q in self.query}
        if len(values)!=len(pairs) or set(values)-set(rules) or any(q.required and q.name not in values for q in self.query):return False
        return all(rules[k].accepts(v) for k,v in values.items())


@dataclasses.dataclass(frozen=True)
class AdapterRegistration:
    provider:str
    capability:str
    credential_scope:str=None
    endpoints:tuple=()
    proof_status:str=REMOTE_PROOF
    execution:str='remote'
    category:str='text'
    name:str=''
    def __post_init__(self):
        if not _id(self.provider) or not _id(self.capability) or self.category not in {'text','image','video','audio'}:raise WorkflowError('Invalid provider/capability registration')
        if type(self.endpoints) is not tuple or any(type(e) is not Endpoint for e in self.endpoints):raise WorkflowError('Endpoints require explicit host Endpoint objects')
        if self.execution=='remote':
            if self.credential_scope!=_scope(self.provider,self.capability) or not self.endpoints or self.proof_status!=REMOTE_PROOF:raise WorkflowError('Remote registration needs exact provider/capability credential scope and contract proof')
        elif self.execution=='local':
            if self.credential_scope is not None or self.endpoints or self.proof_status!=LOCAL_PROOF:raise WorkflowError('Local render registration has no credential or remote endpoint')
        else:raise WorkflowError('Unknown execution kind')
        if not isinstance(self.name,str) or len(self.name)>120 or any(ord(c)<32 for c in self.name):raise WorkflowError('Invalid provider label')


@dataclasses.dataclass(frozen=True)
class ConnectionBinding:
    provider:str
    capability:str
    credential_scope:str
    connection_id:str


class CapabilityRegistry:
    def __init__(self):self._registrations={}
    def register(self,registration):
        if type(registration) is not AdapterRegistration:raise WorkflowError('Only host AdapterRegistration objects can register adapters; catalog JSON is descriptive')
        key=(registration.provider,registration.capability)
        if key in self._registrations:raise WorkflowError('Adapter registration already exists; silent replacement is disabled')
        self._registrations[key]=registration;return registration
    def get(self,provider,capability):
        try:return self._registrations[(provider,capability)]
        except (KeyError,TypeError):raise WorkflowError('No host adapter registered for selected provider/capability') from None
    def supported(self,capability):return tuple(sorted(p for p,c in self._registrations if c==capability))
    def registrations(self):return tuple(self._registrations[k] for k in sorted(self._registrations))
    def validate_endpoint(self,provider,capability,method,url):
        registration=self.get(provider,capability)
        if registration.execution!='remote' or not any(e.accepts(method,url) for e in registration.endpoints):raise WorkflowError('Endpoint outside the exact selected provider/capability registration')
        return registration
    def assert_connection(self,provider,capability,binding):
        registration=self.get(provider,capability)
        if type(binding) is not ConnectionBinding or registration.execution!='remote' or (binding.provider,binding.capability,binding.credential_scope)!=(provider,capability,registration.credential_scope) or not isinstance(binding.connection_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',binding.connection_id):
            raise WorkflowError('Independent exact provider/capability connection required; no credential fallback')
        return registration


def builtin_registry(adapters,*,elevenlabs_available=False,local_renderers=()):
    """Snapshot real adapter objects supplied by host, never catalog declarations.

    This registers known endpoint contracts; it does not enable transport, intake
    a key, discover/install a renderer or validate an account/model live.
    """
    registry=CapabilityRegistry()
    specs={
        'openai':('OpenAI',(Endpoint('POST','https://api.openai.com','/v1/responses'),Endpoint('GET','https://api.openai.com','/v1/models'))),
        'anthropic':('Anthropic',(Endpoint('POST','https://api.anthropic.com','/v1/messages'),Endpoint('GET','https://api.anthropic.com','/v1/models',
            (QueryParameter('limit',values=('100',)),QueryParameter('after_id','identifier',required=False,max_length=160))))),
        'gemini':('Google Gemini',(Endpoint('POST','https://generativelanguage.googleapis.com','/v1beta/models/{model}:generateContent',parameter_limits=(('model',120),)),Endpoint('GET','https://generativelanguage.googleapis.com','/v1beta/models',
            (QueryParameter('pageSize',values=('100',)),QueryParameter('pageToken','cursor',required=False))))),
        'openrouter':('OpenRouter',(Endpoint('POST','https://openrouter.ai','/api/v1/chat/completions'),Endpoint('GET','https://openrouter.ai','/api/v1/models',
            (QueryParameter('offset',values=('0','100','200','300','400')),QueryParameter('limit',values=('100',))))))}
    if not isinstance(adapters,dict):raise WorkflowError('Host must supply actual adapter mapping')
    for provider,(name,endpoints) in specs.items():
        adapter=adapters.get(provider)
        if adapter is not None and getattr(adapter,'provider',None)==provider and getattr(adapter,'capability',None)=='text' and callable(getattr(adapter,'build',None)) and callable(getattr(adapter,'parse',None)):
            registry.register(AdapterRegistration(provider,'text',_scope(provider,'text'),endpoints,name=name))
    voice=adapters.get('elevenlabs')
    if (voice is not None and getattr(voice,'provider',None)=='elevenlabs' and getattr(voice,'capability',None)=='voice' and callable(getattr(voice,'build',None)) and callable(getattr(voice,'parse',None))) or elevenlabs_available is True:
        endpoints=(Endpoint('POST','https://api.elevenlabs.io','/v1/text-to-speech/{voice_id}',(QueryParameter('output_format',values=('mp3_44100_128',)),),parameter_limits=(('voice_id',80),)),
            Endpoint('POST','https://api.elevenlabs.io','/v1/text-to-speech/{voice_id}/with-timestamps',(QueryParameter('output_format',values=('mp3_44100_128',)),),parameter_limits=(('voice_id',80),)),
            Endpoint('GET','https://api.elevenlabs.io','/v1/models'),Endpoint('GET','https://api.elevenlabs.io','/v1/user/subscription'),
            Endpoint('GET','https://api.elevenlabs.io','/v2/voices',(QueryParameter('page_size',values=('100',)),QueryParameter('include_total_count',values=('false',)),QueryParameter('next_page_token','cursor',required=False))))
        registry.register(AdapterRegistration('elevenlabs','voice','elevenlabs:voice',endpoints,category='audio',name='ElevenLabs'))
    for engine in local_renderers:
        if engine not in {'hyperframes','remotion'}:raise WorkflowError('Unknown built-in local renderer; use explicit host registration for a new implementation')
        registry.register(AdapterRegistration(engine,'animation_render',proof_status=LOCAL_PROOF,execution='local',category='video',name='HyperFrames' if engine=='hyperframes' else 'Remotion'))
    return registry


def load_catalog():
    value=json.loads((ROOT/'catalog/capabilities.json').read_text())
    if not isinstance(value,dict) or set(value)!={'schema_version','reviewed_at','scope','providers','local_renderers'} or value['schema_version']!=1:raise WorkflowError('Invalid descriptive capability catalog')
    seen=set()
    for row in value['providers']+value['local_renderers']:
        if not isinstance(row,dict) or set(row)!={'provider','name','capability','category','execution','status','enabled','documentation','limits','retention'} or not _id(row.get('provider')) or not _id(row.get('capability')) or row.get('status') not in STATUSES or row.get('enabled') is not False:raise WorkflowError('Catalog must be descriptive and disabled by default')
        if row['category'] not in {'text','image','video','audio'} or row['execution'] not in {'remote','local'} or not isinstance(row['name'],str) or not 1<=len(row['name'])<=120 or row['limits'] is not None or row['retention']!='unknown_not_verified':raise WorkflowError('Invalid capability metadata or unverified retention/limits')
        if not isinstance(row['documentation'],list) or len(row['documentation'])>5:raise WorkflowError('Invalid official documentation list')
        for source in row['documentation']:
            if not isinstance(source,dict) or set(source)!={'title','url'} or not isinstance(source['title'],str) or not 1<=len(source['title'])<=150:raise WorkflowError('Invalid documentation reference')
            try:url=urlsplit(source['url']);port=url.port
            except (ValueError,TypeError):raise WorkflowError('Invalid documentation URL') from None
            if url.scheme!='https' or not url.hostname or url.username or url.password or port is not None or url.fragment or url.query or '\\' in source['url']:raise WorkflowError('Documentation must use a bounded HTTPS source URL')
        key=(row['provider'],row['capability'])
        if key in seen:raise WorkflowError('Duplicate capability catalog row')
        seen.add(key)
    return value


def build_registry(available_adapters=None,*,local_renderers=None):
    """Lazy host bootstrap; no JSON registration, install or provider request.

    Source presence establishes a local implementation entry, not doctor/render
    readiness on this computer. Callers may pass () to hide local render entries.
    """
    if available_adapters is None:
        from .providers import ADAPTERS
        available_adapters=ADAPTERS
    if local_renderers is None:
        local_renderers=[]
        common=all((ROOT/p).is_file() for p in ['storymotion/engine.py','storymotion/compose.py','renderers/versions.json'])
        if common:
            if (ROOT/'vendor/gsap.min.js').is_file():local_renderers.append('hyperframes')
            if (ROOT/'renderers/remotion/entry.jsx').is_file() and (ROOT/'tools/remotion.mjs').is_file():local_renderers.append('remotion')
    return builtin_registry(available_adapters,local_renderers=local_renderers)


def public_capabilities(registry):
    if type(registry) is not CapabilityRegistry:raise WorkflowError('Public capabilities require the host registry')
    catalog=load_catalog();rows=catalog['providers']+catalog['local_renderers'];known={(r['provider'],r['capability']) for r in rows}
    for registration in registry.registrations():
        if (registration.provider,registration.capability) not in known:
            rows.append({'provider':registration.provider,'name':registration.name or registration.provider,'capability':registration.capability,
                'category':registration.category,'execution':registration.execution,'status':registration.proof_status,'enabled':False,'documentation':[],
                'limits':None,'retention':'unknown_not_verified'})
    result=[]
    for row in rows:
        try:registration=registry.get(row['provider'],row['capability'])
        except WorkflowError:registration=None
        available=registration is not None;capability=row['capability']
        target='writer' if capability=='text' else 'voice' if capability=='voice' else 'render' if capability=='animation_render' else None
        result.append({'provider':row['provider'],'name':row['name'],'capability':capability,'category':row['category'],
            'execution':row['execution'],'status':registration.proof_status if available else row['status'],
            'adapter_registered':available,'selectable':available,'dispatch_enabled':False,'live_verified':False,
            'credential_scope':registration.credential_scope if available else None,'limits':None,'retention':'unknown_not_verified','models':[],
            'documentation':copy.deepcopy(row['documentation']),'disabled_reason':None if available else 'adapter_not_registered',
            'ui_target':target if available else None})
    return sorted(result,key=lambda r:(r['category'],r['provider'],r['capability']))
