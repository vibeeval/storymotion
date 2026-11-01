"""Shared AccountPack audience and numeric/price intake guards for templates."""
import copy
import hashlib
import json
import re
from pathlib import Path
from .claims import audit_claims,numeric_tokens
from .creative import audit_audience_copy
from .local_state import guard_control
from .security import WorkflowError,canonical
from .writing_context import validate_binding,registry

ROOT=Path(__file__).resolve().parents[1]
SURFACE_SHA256='d0e06f90a0387d29e5a506bd635ebcb79a9f904d4c4057d31f52071ef8152566'
PATTERN=re.compile(r'[a-z][a-z0-9_]*(?:\[\])*(?:\.[a-z][a-z0-9_]*(?:\[\])*)*')
REASONS=('timing','index','simulation_state')

def _invalid():raise WorkflowError('TEMPLATE_CLAIM_SURFACE_INVALID')

def _patterns(value):
    if not isinstance(value,list) or value!=sorted(set(value)) or any(not isinstance(v,str) or not PATTERN.fullmatch(v) for v in value):_invalid()
    return set(value)

def _row(value,keys):
    if not isinstance(value,dict) or set(value)!=keys or not isinstance(value['exempt_numbers'],dict) or set(value['exempt_numbers'])!=set(REASONS):_invalid()
    groups=[_patterns(value.get('guarded_numbers',[]))]+[_patterns(value['exempt_numbers'][k]) for k in REASONS]
    if sum(len(v) for v in groups)!=len(set().union(*groups)):_invalid()
    return {'hidden':_patterns(value['hidden_strings']),'guarded':groups[0],'exempt':set().union(*groups[1:])}

def surface():
    """Pinned per-family declaration of caller fields that reach rendered text."""
    from .template_families import FAMILIES
    path=guard_control(ROOT,'catalog/template-claim-surface.json')
    raw=path.read_bytes() if path.is_file() else b''
    if hashlib.sha256(raw).hexdigest()!=SURFACE_SHA256:_invalid()
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)!={'schema_version','policy','common','families'} or type(value['schema_version']) is not int or value['schema_version']!=1:_invalid()
    common=_row(value['common'],{'hidden_strings','exempt_numbers'})
    if not isinstance(value['families'],dict) or set(value['families'])!=set(FAMILIES):_invalid()
    result={}
    for key,row in value['families'].items():
        row=_row(row,{'hidden_strings','guarded_numbers','exempt_numbers'})
        if row['guarded']&common['exempt']:_invalid()
        result[key]={'hidden':row['hidden']|common['hidden'],'guarded':row['guarded']}
    return result

def _number(value):
    return str(int(value)) if isinstance(value,float) and value.is_integer() else repr(value) if isinstance(value,float) else str(value)

def audience_fields(spec):
    """(field path, text) for every caller string and guarded number that reaches rendered text."""
    row=surface().get(spec['id'])
    if row is None:_invalid()
    fields=[]
    def visit(value,path):
        if isinstance(value,dict):
            for name,child in value.items():visit(child,(path+'.' if path else '')+name)
        elif isinstance(value,list):
            for child in value:visit(child,path+'[]')
        elif isinstance(value,str):
            if path not in row['hidden']:fields.append((path,value))
        elif type(value) in (int,float) and path in row['guarded']:fields.append((path,_number(value)))
    visit(spec['parameters'],'')
    return fields

def audience_values(spec):
    return [text for _,text in audience_fields(spec)]

def audit_template(brief):
    if len(canonical(brief).encode())>120000:raise WorkflowError('TEMPLATE_INPUT: bounded template brief required')
    claims=brief.get('claims')
    if not isinstance(claims,list) or len(claims)>30:raise WorkflowError('TEMPLATE_INPUT: bounded scoped claims required')
    for row in claims:
        if not isinstance(row,dict) or set(row)!={'text','source','scope'}:raise WorkflowError('TEMPLATE_INPUT: exact scoped claim fields required')
        if any(not isinstance(row[name],str) or not row[name].strip() or len(row[name])>limit for name,limit in (('text',2000),('source',100),('scope',1000))):raise WorkflowError('TEMPLATE_INPUT: bounded scoped claim text required')
    binding=validate_binding(brief.get('production_context'),brief['brand'])
    from .template_families import validate_spec
    fields=audience_fields(validate_spec(brief['template_family']))
    covered=numeric_tokens(' '.join(row['text'] for row in claims))
    uncovered=sorted({path for path,text in fields if numeric_tokens(text)-covered})
    if uncovered:
        raise WorkflowError('TEMPLATE_INPUT: unsourced displayed number in parameters '+', '.join(uncovered[:8])+(' …' if len(uncovered)>8 else '')
                            +'; add a caller-registered scoped claim whose text contains those exact values')
    value=copy.deepcopy(brief)
    value['scenes']=value['scenes']+[{'heading':'','information':' '.join(text for _,text in fields)}]
    audit_audience_copy(brief['brand'],value)
    # A silent/demo template is not a fictional-account exemption. Source
    # traceability never claims independent truth or publication acceptance.
    return audit_claims(value,registry(binding),fictional=False)
