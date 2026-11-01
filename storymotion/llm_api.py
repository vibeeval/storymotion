"""Bounded read-only discovery for four fixed LLM providers.

No env/key discovery, redirects, proxies or retries. Catalog metadata cannot
prove adapter success, account billing access, a USD tariff or free production.
"""
import http.client
import json
import time
from urllib.parse import urlencode,urlsplit,parse_qs
from .providers import (ProviderError,identifier,model_identifier,bounded_text,
    request_headers,validate_credential_provider,credential_echo)

HOSTS={'openai':'api.openai.com','anthropic':'api.anthropic.com',
       'gemini':'generativelanguage.googleapis.com','openrouter':'openrouter.ai'}
SYNTHETIC_MODEL_IDS={'openai':'synthetic-openai-text','anthropic':'synthetic-anthropic-text',
                     'gemini':'synthetic-gemini-text','openrouter':'synthetic/openrouter-text'}
MAX_BODY=4*1024*1024


def _provider(provider):
    if provider not in HOSTS:raise ProviderError('UNSUPPORTED_LLM_PROVIDER')


def _result(provider,models,truncated,filtered,synthetic):
    return {'provider':provider,'models':models,'truncated':truncated,'filtered_models':filtered,
        'observed_at':time.time(),'usd_estimate':None,'verified_usd_rate':False,
        'price_source':'No independently verified current USD tariff or complete invoice estimate',
        'compatibility':'Conditional metadata filtering is not successful generation or universal model support',
        'credential_scope':('Public catalogue metadata does not verify this account generation/billing access' if provider=='openrouter'
                            else 'Exact supplied connection key; no provider account identity inferred'),
        'synthetic':synthetic}


def _positive(value):return value if type(value) is int and 0<value<=1000000000 else None


def _cursor(value):
    if not isinstance(value,str) or not 1<=len(value)<=2048 or any(not 33<=ord(c)<=126 for c in value):
        raise ProviderError('INVALID_MODEL_PAGINATION')
    return value


def _model(provider,value):
    if not isinstance(value,dict):raise ProviderError('INVALID_MODEL_LIST')
    raw=value.get('name') if provider=='gemini' else value.get('id')
    if not isinstance(raw,str):raise ProviderError('INVALID_MODEL_LIST')
    try:model=model_identifier(provider,raw)
    except ProviderError:return None
    if value.get('lifecycle')=='retired':return None
    output=input_limit=context=None
    compatibility='not_verified_for_this_adapter'
    if provider=='gemini':
        methods=value.get('supportedGenerationMethods')
        if not raw.startswith('models/') or not isinstance(methods,list) or 'generateContent' not in methods:return None
        name=value.get('displayName',model);output=_positive(value.get('outputTokenLimit'));input_limit=_positive(value.get('inputTokenLimit'))
        compatibility='metadata_generateContent_only; text output and account access unverified'
    elif provider=='openrouter':
        architecture=value.get('architecture');parameters=value.get('supported_parameters')
        if not isinstance(architecture,dict) or not isinstance(parameters,list) or 'max_tokens' not in parameters:return None
        if not all(isinstance(architecture.get(k),list) and 'text' in architecture[k] for k in ('input_modalities','output_modalities')):return None
        top=value.get('top_provider');top=top if isinstance(top,dict) else {}
        output=_positive(top.get('max_completion_tokens'));context=_positive(value.get('context_length'))
        name=value.get('name',model);compatibility='metadata_text_and_max_tokens_only; upstream access unverified'
    else:
        name=value.get('display_name',model) if provider=='anthropic' else model
        if provider=='anthropic':output=_positive(value.get('max_tokens'));input_limit=_positive(value.get('max_input_tokens'))
    if name is None:name=model
    result={'id':model,'name':bounded_text(name,160),'max_output_tokens':output,'max_input_tokens':input_limit,'compatibility':compatibility}
    if provider=='openrouter':result['context_window_tokens']=context  # includes output; not an invented input-only limit
    return result


def _path(provider,after):
    if provider=='openai':return '/v1/models'
    if provider=='anthropic':return '/v1/models?'+urlencode({'limit':100,**({'after_id':after} if after else {})})
    if provider=='gemini':return '/v1beta/models?'+urlencode({'pageSize':100,**({'pageToken':after} if after else {})})
    return '/api/v1/models?'+urlencode({'offset':after or 0,'limit':100})


def _validate_path(provider,path):
    u=urlsplit(path);query=parse_qs(u.query,keep_blank_values=True)
    if u.scheme or u.netloc or u.fragment or any(len(v)!=1 for v in query.values()):raise ProviderError('ENDPOINT_NOT_ALLOWED')
    if provider=='openai':
        if path!='/v1/models':raise ProviderError('ENDPOINT_NOT_ALLOWED')
    elif provider=='anthropic':
        if u.path!='/v1/models' or set(query)-{'limit','after_id'} or query.get('limit')!=['100']:raise ProviderError('ENDPOINT_NOT_ALLOWED')
        if 'after_id' in query:identifier(query['after_id'][0])
    elif provider=='gemini':
        if u.path!='/v1beta/models' or set(query)-{'pageSize','pageToken'} or query.get('pageSize')!=['100']:raise ProviderError('ENDPOINT_NOT_ALLOWED')
        if 'pageToken' in query:_cursor(query['pageToken'][0])
    elif provider=='openrouter':
        if u.path!='/api/v1/models' or set(query)!={'offset','limit'} or query['limit']!=['100'] or not query['offset'][0].isdigit():raise ProviderError('ENDPOINT_NOT_ALLOWED')
        if int(query['offset'][0])>500 or int(query['offset'][0])%100:raise ProviderError('ENDPOINT_NOT_ALLOWED')


def _next(provider,value,after):
    if provider=='openai':return None
    if provider=='anthropic':
        if type(value.get('has_more')) is not bool:raise ProviderError('INVALID_MODEL_PAGINATION')
        return identifier(value.get('last_id')) if value['has_more'] else None
    if provider=='gemini':
        token=value.get('nextPageToken')
        return _cursor(token) if token not in (None,'') else None
    links=value.get('links')
    if links is None:return None
    if not isinstance(links,dict):raise ProviderError('INVALID_MODEL_PAGINATION')
    link=links.get('next')
    if link is None:return None
    if not isinstance(link,str):raise ProviderError('INVALID_MODEL_PAGINATION')
    _validate_path(provider,link)
    offset=int(parse_qs(urlsplit(link).query)['offset'][0])
    if offset!=(after or 0)+100:raise ProviderError('INVALID_MODEL_PAGINATION')
    return offset


class LLMMetadataHTTP:
    synthetic=False
    def __init__(self,enabled=False,timeout=20,max_pages=5,max_models=1000):
        if type(enabled) is not bool or type(timeout) not in {int,float} or not 1<=timeout<=60:raise ProviderError('INVALID_METADATA_POLICY')
        if type(max_pages) is not int or not 1<=max_pages<=5 or type(max_models) is not int or not 1<=max_models<=1000:raise ProviderError('INVALID_METADATA_POLICY')
        self.enabled=enabled;self.timeout=timeout;self.max_pages=max_pages;self.max_models=max_models
    def _request(self,provider,path,key,deadline):
        _provider(provider);_validate_path(provider,path)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ProviderError('METADATA_TIMEOUT')
        connection=http.client.HTTPSConnection(HOSTS[provider],timeout=min(self.timeout,remaining))
        try:
            connection.request('GET',path,headers=request_headers(provider,key))
            response=connection.getresponse()
            if response.status!=200:raise ProviderError('HTTP_'+str(response.status))
            if response.getheader('Content-Type','').split(';')[0].strip().lower()!='application/json':raise ProviderError('INVALID_CONTENT_TYPE')
            chunks=[];size=0
            while True:
                if time.monotonic()>=deadline:raise ProviderError('METADATA_TIMEOUT')
                chunk=response.read1(min(65536,MAX_BODY+1-size))
                if time.monotonic()>=deadline:raise ProviderError('METADATA_TIMEOUT')
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>MAX_BODY:raise ProviderError('RESPONSE_TOO_LARGE')
            raw=b''.join(chunks)
            if key in raw:raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
            try:value=json.loads(raw)
            except (ValueError,UnicodeError):raise ProviderError('INVALID_JSON') from None
            if credential_echo(value,key):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
            return value
        except ProviderError:raise
        except (OSError,TimeoutError,http.client.HTTPException):raise ProviderError('METADATA_TIMEOUT_OR_NETWORK_ERROR') from None
        finally:connection.close()
    def list_models(self,provider,key):
        if not self.enabled:raise ProviderError('LLM_METADATA_NETWORK_DISABLED')
        _provider(provider);key=validate_credential_provider(provider,key)
        if key.startswith((b'FAKE_',b'TEST_ONLY_')):raise ProviderError('SYNTHETIC_KEY_CANNOT_GO_LIVE')
        deadline=time.monotonic()+self.timeout;models=[];ids=set();tokens=set();after=None;filtered=0;truncated=False
        pages=1 if provider=='openai' else self.max_pages
        for _ in range(pages):
            value=self._request(provider,_path(provider,after),key,deadline)
            field='models' if provider=='gemini' else 'data'
            if not isinstance(value,dict) or not isinstance(value.get(field),list):raise ProviderError('INVALID_MODEL_LIST')
            for item in value[field]:
                if len(models)>=self.max_models:truncated=True;break
                model=_model(provider,item)
                if model is None:filtered+=1;continue
                if model['id'] in ids:raise ProviderError('DUPLICATE_MODEL_ID')
                ids.add(model['id']);models.append(model)
            next_page=_next(provider,value,after)
            if next_page is None:break
            truncated=True
            if next_page in tokens:raise ProviderError('INVALID_MODEL_PAGINATION')
            tokens.add(next_page);after=next_page
            if len(models)>=self.max_models:break
            truncated=False
        else:truncated=True
        result=_result(provider,models,truncated,filtered,False)
        if credential_echo(result,key):raise ProviderError('CREDENTIAL_ECHO_BLOCKED')
        return result


class LLMMetadataDemo:
    synthetic=True
    def list_models(self,provider,key):
        _provider(provider);key=validate_credential_provider(provider,key)
        if not key.startswith((b'FAKE_',b'TEST_ONLY_')):raise ProviderError('SYNTHETIC_KEY_REQUIRED')
        return _result(provider,[{'id':SYNTHETIC_MODEL_IDS[provider],
            'name':'Sentetik '+provider+' contract modeli · gerçek vendor modeli değil',
            'max_output_tokens':8000,'max_input_tokens':None,'compatibility':'synthetic_contract_only'}],False,0,True)
