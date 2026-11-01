"""Provider-specific request/response code and fail-closed HTTPS transport.

No environment discovery, credential persistence, SDK retries or automatic live enable.
UI/session approval and live enablement belong to the caller, never this module.
"""
import contextlib
import dataclasses
import hashlib
import http.client
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import quote
from typing import Callable,Optional
from .security import WorkflowError,canonical,digest,scan_bytes


class ProviderError(WorkflowError):
    def __init__(self,code):
        # Never concatenate a provider body, URL, key or exception into an error.
        self.code=code
        super().__init__('Provider operation: '+code)


PROVIDERS={'openai','anthropic','gemini','openrouter','elevenlabs'}
AUTH_HEADERS={'openai':'Authorization','anthropic':'x-api-key','gemini':'x-goog-api-key','openrouter':'Authorization','elevenlabs':'xi-api-key'}
ANTHROPIC_VERSION='2023-06-01'


def opaque_key(value):
    if not isinstance(value,str) or not 1<=len(value)<=512 or any(not 33<=ord(char)<=126 for char in value):
        raise ProviderError('MALFORMED_CREDENTIAL')
    # Preserve opaque bytes exactly: no stripping, prefix inference or URL routing.
    # Printable non-whitespace ASCII is safe for the fixed authentication header.
    return value.encode('ascii')


def validate_credential_provider(provider,key):
    """Validate selected provider and opaque header syntax, never infer ownership."""
    if provider not in PROVIDERS:raise ProviderError('UNSUPPORTED_PROVIDER')
    if not isinstance(key,bytes):raise ProviderError('MALFORMED_CREDENTIAL')
    try:value=opaque_key(key.decode('ascii'))
    except (ValueError,UnicodeError):raise ProviderError('MALFORMED_CREDENTIAL') from None
    return value


def request_headers(provider,key):
    raw=validate_credential_provider(provider,key)
    auth=raw.decode() if provider in {'elevenlabs','anthropic','gemini'} else 'Bearer '+raw.decode()
    headers={'Content-Type':'application/json','Accept':'application/json',AUTH_HEADERS[provider]:auth}
    if provider=='anthropic':headers['anthropic-version']=ANTHROPIC_VERSION
    return headers


def credential_echo(value,key):
    """Find a leased opaque credential in decoded values, without JSON escaping."""
    if not isinstance(key,bytes) or not key:raise ProviderError('MALFORMED_CREDENTIAL')
    try:needle=key.decode('ascii')
    except UnicodeError:raise ProviderError('MALFORMED_CREDENTIAL') from None
    pending=[value];seen=set()
    while pending:
        item=pending.pop()
        if isinstance(item,str):
            if needle in item:return True
        elif isinstance(item,(bytes,bytearray,memoryview)):
            if key in bytes(item):return True
        elif isinstance(item,(dict,list,tuple)):
            if id(item) in seen:continue
            seen.add(id(item))
            if isinstance(item,dict):pending.extend(item.keys());pending.extend(item.values())
            else:pending.extend(item)
    return False


def bounded_text(value,limit=50000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or '\x00' in value:
        raise ProviderError('INVALID_TEXT')
    if scan_bytes(value.encode()):raise ProviderError('POSSIBLE_SECRET_IN_INPUT')
    return value


def identifier(value,limit=120,slash=False):
    pattern=r'[A-Za-z0-9_.:/-]+' if slash else r'[A-Za-z0-9_.-]+'
    if not isinstance(value,str) or not 1<=len(value)<=limit or not re.fullmatch(pattern,value) or value.startswith(('/', '.')) or '..' in value:
        raise ProviderError('INVALID_IDENTIFIER')
    return value


def model_identifier(provider,value):
    """Provider-specific model syntax; a model string can never select a host."""
    if provider=='gemini':
        if isinstance(value,str) and value.startswith('models/'):value=value[len('models/'):]
        return identifier(value)
    if provider=='openrouter':
        identifier(value,slash=True)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*(?::[A-Za-z0-9][A-Za-z0-9_.-]*)?',value):
            raise ProviderError('INVALID_MODEL_IDENTIFIER')
        # Automatic model routers are outside an explicitly selected model job.
        if value in {'openrouter/auto','openrouter/free'}:raise ProviderError('AUTOMATIC_MODEL_ROUTER_UNSUPPORTED')
        return value
    if provider not in {'openai','anthropic'}:raise ProviderError('UNSUPPORTED_LLM_PROVIDER')
    return identifier(value)


def bounded_int(value,minimum=1,maximum=16000):
    if type(value) is not int or not minimum<=value<=maximum:raise ProviderError('INVALID_LIMIT')
    return value


class SecretBroker:
    """Active-expiry RAM broker. Real-key intake is disabled unless a caller opts in.

    Enabling this object is not a UI feature, provider verification or spending grant.
    Tests use explicitly synthetic strings only. Python cannot guarantee OS-level wiping.
    """
    def __init__(self,real_intake_enabled=False,ttl_seconds=900):
        if not isinstance(ttl_seconds,(int,float)) or not 0<ttl_seconds<=900:raise ProviderError('INVALID_TTL')
        self.real_intake_enabled=real_intake_enabled;self.ttl=ttl_seconds
        self._slots={};self._timers={};self._lock=threading.RLock()
    def __repr__(self):return '<SecretBroker: values redacted>'
    def put(self,provider,job,request_hash,value,synthetic=False):
        if provider not in PROVIDERS:raise ProviderError('UNSUPPORTED_PROVIDER')
        identifier(job);identifier(request_hash)
        if not synthetic and not self.real_intake_enabled:raise ProviderError('REAL_KEY_INTAKE_DISABLED')
        if synthetic and (not isinstance(value,str) or not value.startswith(('FAKE_','TEST_ONLY_'))):raise ProviderError('SYNTHETIC_KEY_REQUIRED')
        raw=bytearray(opaque_key(value));ref=uuid.uuid4().hex
        with self._lock:
            self._slots[ref]={'provider':provider,'job':job,'request_hash':request_hash,'raw':raw,'expires':time.monotonic()+self.ttl,'synthetic':synthetic}
            timer=threading.Timer(self.ttl,self.clear,args=(ref,));timer.daemon=True;self._timers[ref]=timer;timer.start()
        return ref
    def clear(self,ref=None):
        with self._lock:
            for key in list(self._slots) if ref is None else [ref]:
                slot=self._slots.pop(key,None);timer=self._timers.pop(key,None)
                if timer:timer.cancel()
                if slot:
                    for i in range(len(slot['raw'])):slot['raw'][i]=0
    def status(self):
        with self._lock:
            return [{'ref':k,'provider':v['provider'],'job':v['job'],'synthetic':v['synthetic']} for k,v in self._slots.items() if v['expires']>time.monotonic()]
    @contextlib.contextmanager
    def lease(self,ref,provider,job,request_hash,allow_synthetic):
        with self._lock:
            slot=self._slots.get(ref)
            if not slot or slot['expires']<=time.monotonic():
                self.clear(ref);raise ProviderError('CREDENTIAL_EXPIRED_OR_MISSING')
            if (slot['provider'],slot['job'],slot['request_hash'])!=(provider,job,request_hash):raise ProviderError('CREDENTIAL_SCOPE_MISMATCH')
            if slot['synthetic'] and not allow_synthetic:raise ProviderError('SYNTHETIC_KEY_CANNOT_GO_LIVE')
            raw=bytes(slot['raw'])
        try:yield raw
        finally:raw=b''
    @contextlib.contextmanager
    def send_lease(self,ref,provider,job,request_hash,allow_synthetic):
        # Serialize explicit clear/expiry against the built-in send boundary.
        # Ordinary response-processing leases remain immutable but unlocked.
        with self._lock:
            with self.lease(ref,provider,job,request_hash,allow_synthetic) as raw:
                yield raw
    def contains_secret(self,raw):
        with self._lock:return any(bytes(s['raw']) in raw for s in self._slots.values() if s['raw'])


@dataclasses.dataclass(frozen=True)
class Plan:
    provider:str
    capability:str
    model:str
    url:str
    body:dict=dataclasses.field(repr=False)
    @property
    def fingerprint(self):return digest({'provider':self.provider,'capability':self.capability,'model':self.model,'url':self.url,'body':self.body})
    def public(self):
        return {'provider':self.provider,'capability':self.capability,'model':self.model,'method':'POST','endpoint':self.url,
                'request_hash':self.fingerprint,'body_sha256':digest(self.body),'auth_header':AUTH_HEADERS[self.provider],
                'credential':'[REDACTED]','live_default':False}


@dataclasses.dataclass(frozen=True)
class Response:
    status:int
    content_type:str
    body:bytes=dataclasses.field(repr=False)


@dataclasses.dataclass(frozen=True)
class Result:
    provider:str
    provider_id:Optional[str]
    media_type:str
    data:bytes=dataclasses.field(repr=False)
    usage:dict
    @property
    def sha256(self):return hashlib.sha256(self.data).hexdigest()
    def public(self):return {'provider':self.provider,'provider_id':self.provider_id,'media_type':self.media_type,'sha256':self.sha256,'bytes':len(self.data),'usage':self.usage,'actual_cost':'unknown_until_provider_receipt'}


def check_response(response,broker=None):
    if type(response.status) is not int or response.status!=200:
        code='RATE_LIMITED' if response.status==429 else 'AUTH_REJECTED' if response.status in {401,403} else 'HTTP_ERROR'
        raise ProviderError(code)
    if broker and broker.contains_secret(response.body):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
    if len(response.body)>16*1024*1024:raise ProviderError('RESPONSE_TOO_LARGE')


def json_response(response,broker=None):
    check_response(response,broker)
    if response.content_type.split(';')[0].strip()!='application/json':raise ProviderError('UNEXPECTED_CONTENT_TYPE')
    try:result=json.loads(response.body)
    except (ValueError,UnicodeError):raise ProviderError('MALFORMED_RESPONSE')
    if not isinstance(result,dict):raise ProviderError('MALFORMED_RESPONSE')
    return result


def usage_counts(value,names):
    if value is None:return {'reported':False}
    if not isinstance(value,dict):raise ProviderError('INVALID_USAGE')
    result={'reported':True}
    for name in names:
        if name in value:result[name]=bounded_int(value[name],0,100000000)
    return result


class OpenAIResponses:
    provider='openai';capability='text'
    def build(self,model,prompt,max_output_tokens=2000):
        identifier(model);bounded_text(prompt);bounded_int(max_output_tokens,16)
        return Plan('openai','text',model,'https://api.openai.com/v1/responses',{'model':model,'input':prompt,'max_output_tokens':max_output_tokens,'store':False})
    def parse(self,response,broker=None):
        value=json_response(response,broker)
        if value.get('status')!='completed':raise ProviderError('INCOMPLETE_RESPONSE')
        try:text=''.join(c['text'] for item in value['output'] if item.get('type')=='message' for c in item['content'] if c.get('type')=='output_text')
        except (KeyError,TypeError,AttributeError):raise ProviderError('MALFORMED_RESPONSE')
        bounded_text(text,200000)
        provider_id=identifier(value.get('id',''),160)
        return Result('openai',provider_id,'text/plain',text.encode(),usage_counts(value.get('usage'),['input_tokens','output_tokens','total_tokens']))


class OpenRouterChat:
    provider='openrouter';capability='text'
    def build(self,model,prompt,max_output_tokens=2000):
        model=model_identifier('openrouter',model);bounded_text(prompt);bounded_int(max_output_tokens,16,8000)
        return Plan('openrouter','text',model,'https://openrouter.ai/api/v1/chat/completions',{'model':model,'messages':[{'role':'user','content':prompt}],
            'max_tokens':max_output_tokens,'stream':False,'provider':{'allow_fallbacks':False,'require_parameters':True}})
    def parse(self,response,broker=None):
        value=json_response(response,broker)
        try:
            if not isinstance(value['choices'],list) or len(value['choices'])!=1:raise ProviderError('MALFORMED_RESPONSE')
            choice=value['choices'][0]
            if choice['finish_reason']!='stop':raise ProviderError('INCOMPLETE_RESPONSE')
            message=choice['message']
            if message.get('role')!='assistant':raise ProviderError('MALFORMED_RESPONSE')
            if message.get('refusal'):raise ProviderError('MODEL_REFUSAL')
            if message.get('tool_calls') or message.get('function_call'):raise ProviderError('UNSUPPORTED_MODEL_OUTPUT')
            text=bounded_text(message['content'],200000)
        except (KeyError,IndexError,TypeError,AttributeError):raise ProviderError('MALFORMED_RESPONSE')
        return Result('openrouter',identifier(value.get('id',''),160),'text/plain',text.encode(),usage_counts(value.get('usage'),['prompt_tokens','completion_tokens','total_tokens']))


class GeminiGenerateContent:
    provider='gemini';capability='text'
    def build(self,model,prompt,max_output_tokens=2000):
        model=model_identifier('gemini',model);bounded_text(prompt);bounded_int(max_output_tokens,16,8000)
        return Plan('gemini','text',model,'https://generativelanguage.googleapis.com/v1beta/models/'+quote(model,safe='')+':generateContent',
            {'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'maxOutputTokens':max_output_tokens}})
    def parse(self,response,broker=None):
        value=json_response(response,broker)
        feedback=value.get('promptFeedback')
        if feedback is not None:
            if not isinstance(feedback,dict):raise ProviderError('MALFORMED_RESPONSE')
            if feedback.get('blockReason') not in (None,'','BLOCK_REASON_UNSPECIFIED'):raise ProviderError('MODEL_REFUSAL')
        candidates=value.get('candidates')
        if not isinstance(candidates,list) or len(candidates)!=1:raise ProviderError('MALFORMED_RESPONSE')
        candidate=candidates[0]
        if not isinstance(candidate,dict):raise ProviderError('MALFORMED_RESPONSE')
        if candidate.get('finishReason')!='STOP':raise ProviderError('INCOMPLETE_RESPONSE')
        for owner in (candidate,feedback or {}):
            ratings=owner.get('safetyRatings',[])
            if not isinstance(ratings,list):raise ProviderError('MALFORMED_RESPONSE')
            for rating in ratings:
                if not isinstance(rating,dict) or ('blocked' in rating and type(rating['blocked']) is not bool):raise ProviderError('MALFORMED_RESPONSE')
                if rating.get('blocked'):raise ProviderError('MODEL_REFUSAL')
        content=candidate.get('content')
        if not isinstance(content,dict) or content.get('role')!='model':raise ProviderError('MALFORMED_RESPONSE')
        parts=content.get('parts')
        if not isinstance(parts,list) or not parts:raise ProviderError('MALFORMED_RESPONSE')
        text=[]
        for part in parts:
            if not isinstance(part,dict) or set(part)-{'text','thought','thoughtSignature'}:raise ProviderError('UNSUPPORTED_MODEL_OUTPUT')
            if 'thought' in part and type(part['thought']) is not bool:raise ProviderError('MALFORMED_RESPONSE')
            if not part.get('thought',False):text.append(bounded_text(part.get('text'),200000))
        output=bounded_text(''.join(text),200000)
        provider_id=identifier(value['responseId'],160) if value.get('responseId') is not None else None
        return Result('gemini',provider_id,'text/plain',output.encode(),usage_counts(value.get('usageMetadata'),
            ['promptTokenCount','candidatesTokenCount','totalTokenCount','cachedContentTokenCount','thoughtsTokenCount','toolUsePromptTokenCount']))


class AnthropicMessages:
    provider='anthropic';capability='text'
    def build(self,model,prompt,max_output_tokens=2000):
        identifier(model);bounded_text(prompt);bounded_int(max_output_tokens,16)
        return Plan('anthropic','text',model,'https://api.anthropic.com/v1/messages',
            {'model':model,'messages':[{'role':'user','content':prompt}],'max_tokens':max_output_tokens,'stream':False})
    def parse(self,response,broker=None):
        value=json_response(response,broker)
        if value.get('type')!='message' or value.get('role')!='assistant':raise ProviderError('MALFORMED_RESPONSE')
        details=value.get('stop_details')
        if isinstance(details,dict) and details.get('type')=='refusal':raise ProviderError('MODEL_REFUSAL')
        if value.get('stop_reason')!='end_turn':raise ProviderError('INCOMPLETE_RESPONSE')
        content=value.get('content')
        if not isinstance(content,list) or not content:raise ProviderError('MALFORMED_RESPONSE')
        text=[]
        for block in content:
            if not isinstance(block,dict):raise ProviderError('MALFORMED_RESPONSE')
            if block.get('type')=='text':text.append(bounded_text(block.get('text'),200000))
            elif block.get('type') not in {'thinking','redacted_thinking'}:raise ProviderError('UNSUPPORTED_MODEL_OUTPUT')
        output=bounded_text(''.join(text),200000)
        return Result('anthropic',identifier(value.get('id',''),160),'text/plain',output.encode(),
            usage_counts(value.get('usage'),['input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens']))


class ElevenLabsSpeech:
    provider='elevenlabs';capability='voice'
    def build(self,model,text,voice_id):
        identifier(model);identifier(voice_id,80);bounded_text(text,10000)
        return Plan('elevenlabs','voice',model,'https://api.elevenlabs.io/v1/text-to-speech/'+voice_id+'?output_format=mp3_44100_128',{'text':text,'model_id':model})
    def parse(self,response,broker=None):
        check_response(response,broker)
        if response.content_type.split(';')[0].strip() not in {'audio/mpeg','audio/mp3'}:raise ProviderError('UNEXPECTED_CONTENT_TYPE')
        if not (response.body.startswith(b'ID3') or (len(response.body)>2 and response.body[0]==255 and response.body[1]&224==224)):raise ProviderError('INVALID_AUDIO_SIGNATURE')
        return Result('elevenlabs',None,'audio/mpeg',response.body,{'reported':False,'technical_decode':'required_before_use','alignment':'not_generated'})


ADAPTERS={'openai':OpenAIResponses(),'anthropic':AnthropicMessages(),'gemini':GeminiGenerateContent(),'openrouter':OpenRouterChat(),'elevenlabs':ElevenLabsSpeech()}


def validate_plan(plan):
    try:return _validate_plan(plan)
    except ProviderError:raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError):raise ProviderError('MALFORMED_PLAN') from None


def _validate_plan(plan):
    if not isinstance(plan,Plan) or plan.provider not in ADAPTERS:raise ProviderError('UNSUPPORTED_PROVIDER')
    b=plan.body
    if plan.provider=='openai':
        if set(b)!={'model','input','max_output_tokens','store'} or b['store'] is not False:raise ProviderError('UNSUPPORTED_REQUEST_OPTIONS')
        expected=ADAPTERS['openai'].build(b['model'],b['input'],b['max_output_tokens'])
    elif plan.provider=='openrouter':
        if set(b)!={'model','messages','max_tokens','stream','provider'} or b['stream'] is not False or len(b['messages'])!=1 or set(b['messages'][0])!={'role','content'} or b['messages'][0]['role']!='user':raise ProviderError('UNSUPPORTED_REQUEST_OPTIONS')
        expected=ADAPTERS['openrouter'].build(b['model'],b['messages'][0]['content'],b['max_tokens'])
    elif plan.provider=='gemini':
        if set(b)!={'contents','generationConfig'} or len(b['contents'])!=1 or set(b['contents'][0])!={'role','parts'} or b['contents'][0]['role']!='user' or len(b['contents'][0]['parts'])!=1 or set(b['contents'][0]['parts'][0])!={'text'} or set(b['generationConfig'])!={'maxOutputTokens'}:
            raise ProviderError('UNSUPPORTED_REQUEST_OPTIONS')
        expected=ADAPTERS['gemini'].build(plan.model,b['contents'][0]['parts'][0]['text'],b['generationConfig']['maxOutputTokens'])
    elif plan.provider=='anthropic':
        if set(b)!={'model','messages','max_tokens','stream'} or b['stream'] is not False or len(b['messages'])!=1 or set(b['messages'][0])!={'role','content'} or b['messages'][0]['role']!='user':raise ProviderError('UNSUPPORTED_REQUEST_OPTIONS')
        expected=ADAPTERS['anthropic'].build(b['model'],b['messages'][0]['content'],b['max_tokens'])
    else:
        if set(b)!={'text','model_id'}:raise ProviderError('UNSUPPORTED_REQUEST_OPTIONS')
        prefix='https://api.elevenlabs.io/v1/text-to-speech/'
        if not plan.url.startswith(prefix):raise ProviderError('ENDPOINT_NOT_ALLOWED')
        voice=plan.url[len(prefix):].split('?')[0];expected=ADAPTERS['elevenlabs'].build(b['model_id'],b['text'],voice)
    if canonical(dataclasses.asdict(expected))!=canonical(dataclasses.asdict(plan)):raise ProviderError('PLAN_MUTATED_OR_ENDPOINT_NOT_ALLOWED')


@dataclasses.dataclass(frozen=True)
class Permit:
    request_hash:str
    job:str
    maximum_microusd:int
    estimate_microusd:int
    expires_at:float
    approved_by:str=dataclasses.field(repr=False)
    # Stateful callers supply a final authorization context. It is RAM-only,
    # excluded from repr/equality, and never part of a request or receipt.
    send_gate:Optional[Callable]=dataclasses.field(default=None,repr=False,compare=False)
    def verify(self,plan,job):
        if self.request_hash!=plan.fingerprint or self.job!=job or self.expires_at<=time.time() or not self.approved_by.strip():raise ProviderError('APPROVAL_SCOPE_OR_EXPIRY')
        bounded_int(self.maximum_microusd,0,10000000000);bounded_int(self.estimate_microusd,0,10000000000)
        if self.maximum_microusd<self.estimate_microusd:raise ProviderError('BUDGET_TOO_SMALL')
    def validate_wire(self,plan,job,method,url,encoded):
        # This is called after transport preparation, at the last built-in send
        # boundary. Recheck the bytes actually about to be submitted.
        validate_plan(plan);self.verify(plan,job)
        if method!='POST' or url!=plan.url or encoded!=canonical(plan.body).encode():
            raise ProviderError('WIRE_REQUEST_CHANGED')
    @contextlib.contextmanager
    def wire(self,plan,job,method,url,encoded,key):
        self.validate_wire(plan,job,method,url,encoded)
        if self.send_gate is not None and not callable(self.send_gate):raise ProviderError('FINAL_SEND_GATE_REQUIRED')
        gate=self.send_gate(plan,method,url,encoded,key) if self.send_gate is not None else contextlib.nullcontext()
        with gate:yield


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ProviderError('REDIRECT_BLOCKED')


class _SendGatedHTTPSHandler(urllib.request.HTTPSHandler):
    """Prepare TLS first; authorize only the connected, non-retrying POST write."""
    def __init__(self,transport,plan,permit,job,key,deadline):
        # Retain HTTPSHandler/HTTPSConnection's default verified SSL context.
        super().__init__()
        self.transport=transport;self.plan=plan;self.permit=permit;self.job=job;self.key=key;self.deadline=deadline
    def https_open(self,request):
        if request._tunnel_host:raise ProviderError('PROXY_TUNNEL_BLOCKED')
        owner=self
        class Connection(http.client.HTTPSConnection):
            _wire_deadline=None
            def request(self,method,url,body=None,headers=None,*,encode_chunked=False):
                headers=headers or {}
                actual={name.lower():value for name,value in headers.items()}
                expected=request_headers(owner.plan.provider,owner.key)
                if encode_chunked or any(actual.get(name.lower())!=value for name,value in expected.items()):
                    raise ProviderError('WIRE_HEADERS_CHANGED')
                # DNS, TCP and verified TLS happen before any credential/header
                # write and outside the service/broker authorization locks.
                self.connect()
                if self.sock is None:raise ProviderError('TRANSPORT_CONNECTION_NOT_READY')
                if time.monotonic()>=owner.deadline:raise ProviderError('TRANSPORT_PREPARATION_EXPIRED')
                if owner.transport.allow_live is not True:raise ProviderError('LIVE_TRANSPORT_DISABLED')
                previous=self.auto_open;self.auto_open=0
                try:
                    with owner.permit.wire(owner.plan,owner.job,method,request.full_url,body,owner.key):
                        self._wire_deadline=owner.deadline
                        super().request(method,url,body,headers,encode_chunked=encode_chunked)
                finally:
                    self._wire_deadline=None;self.auto_open=previous
            def send(self,data):
                if self._wire_deadline is None:raise ProviderError('FINAL_SEND_GATE_REQUIRED')
                remaining=self._wire_deadline-time.monotonic()
                if remaining<=0:raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
                if self.sock is None:raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
                # bytes-only canonical requests make each sendall obey the
                # remaining absolute write budget, with no implicit reconnect.
                self.sock.settimeout(remaining)
                return super().send(data)
        options={'context':self._context}
        # Python 3.12 removed the older check_hostname constructor argument;
        # use the same options as that interpreter's standard HTTPSHandler.
        if hasattr(self,'_check_hostname'):options['check_hostname']=self._check_hostname
        return self.do_open(Connection,request,**options)


class HTTPSTransport:
    """Real HTTPS implementation, OFF by default; one attempt, no redirects/proxies."""
    synthetic=False
    def __init__(self,allow_live=False,timeout=30):
        if type(allow_live) is not bool or not 1<=timeout<=60:raise ProviderError('INVALID_TRANSPORT_POLICY')
        self.allow_live=allow_live;self.timeout=timeout
    def exchange(self,plan,key,permit,job):
        if not self.allow_live:raise ProviderError('LIVE_TRANSPORT_DISABLED')
        validate_plan(plan);permit.verify(plan,job)
        key=validate_credential_provider(plan.provider,key)
        if key.startswith((b'FAKE_',b'TEST_ONLY_')):raise ProviderError('SYNTHETIC_KEY_CANNOT_GO_LIVE')
        request=urllib.request.Request(plan.url,data=canonical(plan.body).encode(),method='POST',headers=request_headers(plan.provider,key))
        deadline=time.monotonic()+self.timeout
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
            _SendGatedHTTPSHandler(self,plan,permit,job,key,deadline))
        try:
            if self.allow_live is not True:raise ProviderError('LIVE_TRANSPORT_DISABLED')
            permit.validate_wire(plan,job,request.get_method(),request.full_url,request.data)
            # The custom HTTPS connection performs the stateful gate after
            # connect, around request writing only. Headers/body are read with
            # no authorization locks held. Socket timeouts are not a claim of a
            # total DNS/slow-response wall-clock bound.
            response=opener.open(request,timeout=self.timeout)
            with response:
                if hasattr(response,'read1'):
                    chunks=[];size=0
                    while True:
                        if time.monotonic()>=deadline:raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
                        chunk=response.read1(min(65536,16*1024*1024+1-size))
                        if time.monotonic()>=deadline:raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
                        if not chunk:break
                        chunks.append(chunk);size+=len(chunk)
                        if size>16*1024*1024:raise ProviderError('RESPONSE_TOO_LARGE')
                    raw=b''.join(chunks)
                else:
                    # Small test response objects may expose only read(). Real
                    # urllib HTTPS responses take the bounded chunk path above.
                    raw=response.read(16*1024*1024+1)
                    if time.monotonic()>=deadline:raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN')
                if len(raw)>16*1024*1024:raise ProviderError('RESPONSE_TOO_LARGE')
                return Response(response.status,response.headers.get('Content-Type',''),raw)
        except urllib.error.HTTPError as error:raise ProviderError('HTTP_'+str(error.code)) from None
        except (urllib.error.URLError,TimeoutError,socket.timeout,OSError):raise ProviderError('TRANSPORT_OUTCOME_UNCERTAIN') from None


class MockTransport:
    synthetic=True
    def __init__(self,response=None,error=None):self.response=response;self.error=error;self.calls=[]
    def exchange(self,plan,key,permit,job):
        validate_plan(plan);permit.verify(plan,job);opaque_key(key.decode())
        with permit.wire(plan,job,'POST',plan.url,canonical(plan.body).encode(),key):
            self.calls.append(plan.public())
        if self.error:raise ProviderError(self.error)
        if not isinstance(self.response,Response):raise ProviderError('MOCK_RESPONSE_REQUIRED')
        return self.response


def execute(plan,broker,slot,permit,transport,job,consume=None):
    validate_plan(plan);permit.verify(plan,job)
    if isinstance(transport,HTTPSTransport) and not transport.allow_live:raise ProviderError('LIVE_TRANSPORT_DISABLED')
    if not isinstance(transport,(HTTPSTransport,MockTransport)):raise ProviderError('UNTRUSTED_TRANSPORT')
    with broker.lease(slot,plan.provider,job,plan.fingerprint,allow_synthetic=transport.synthetic) as raw:
        response=transport.exchange(plan,raw,permit,job)
        if raw in response.body:raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
        result=ADAPTERS[plan.provider].parse(response,broker)
        # Keep this lease's immutable key through parsing. JSON escapes can hide
        # it in metadata on the wire, and disconnect/TTL can empty the broker.
        # Check every returned field before a caller can persist a receipt.
        parsed_metadata=canonical(result.public()).encode()
        if credential_echo(result.data,raw) or credential_echo(result.public(),raw) or broker.contains_secret(result.data) or broker.contains_secret(parsed_metadata):
            raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
        # The persistence callback runs before this request's key lease ends.
        return consume(result,raw) if consume is not None else result


def safe_public_json(value,broker):
    raw=canonical(value).encode()
    if broker.contains_secret(raw) or scan_bytes(raw):raise ProviderError('SECRET_EXPORT_BLOCKED')
    def walk(x):
        if isinstance(x,str) and broker.contains_secret(x.encode()):raise ProviderError('SECRET_EXPORT_BLOCKED')
        if isinstance(x,dict):
            for k,v in x.items():
                if re.search(r'(?i)(api.?key|authorization|xi-api-key|password|access.?token|secret)',k):raise ProviderError('SECRET_FIELD_EXPORT_BLOCKED')
                walk(k);walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(value);return raw
