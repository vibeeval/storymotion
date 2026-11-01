"""Exact fixed development registry. Data-only caller input, bounded local SVG."""
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from .local_state import guard_control
from .security import WorkflowError,canonical,file_hash

ROOT=Path(__file__).resolve().parents[1]
SOURCE_MANIFEST_SHA256='5becc0ef36ca0e8fab176e8b43e0adeb164072b6147288cb67a60f4349c910d1'
CATALOG_SHA256='85487a6dc1ec98ab2decb968e4615030fffdcbaac365a167c4b753f11350c7cd'

UNRENDERABLE=re.compile(r'[<>]|(?:javascript|https?|data):|expression\s*\(|@import',re.I)

def fail():raise WorkflowError('TEMPLATE_REGISTRY_INPUT_INVALID')

def pinned_json(relative,expected):
    path=guard_control(ROOT,relative)
    raw=path.read_bytes() if path.is_file() else b''
    if hashlib.sha256(raw).hexdigest()!=expected:fail()
    return json.loads(raw)

def manifest():
    value=pinned_json('renderers/template-registry/source-manifest.json',SOURCE_MANIFEST_SHA256)
    for name,expected in value['files'].items():
        if not re.fullmatch(r'(?:renderers/template-registry/(?:modules/)?[A-Za-z0-9_.-]+|renderers/svg-tree\.mjs|tools/template_registry\.mjs)',name):fail()
        path=guard_control(ROOT,name)
        if not path.is_file() or file_hash(path)!=expected:fail()
    return value

def catalog():
    value=pinned_json('catalog/development-templates.json',CATALOG_SHA256)
    if len(value['families'])!=84 or len({r['id'] for r in value['families']})!=84:fail()
    return value['families']

FAMILIES={r['id']:{k:r[k] for k in ('name','kind','description','palette')} for r in catalog()}

def bridge(data):
    manifest()
    try:
        raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw.encode())>262144:fail()
        env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1','HYPERFRAMES_TELEMETRY_DISABLED':'1'}
        result=subprocess.run(['node',str(ROOT/'tools/template_registry.mjs')],cwd=ROOT,input=raw,env=env,text=True,capture_output=True,timeout=20)
        if result.returncode:
            if result.stderr=='TEMPLATE_NUMERIC_DOMAIN_LABELS_INVALID\n':
                raise WorkflowError('TEMPLATE_INPUT: domain_bounds: exact quarter-tick labels must fit the 155px axis slot at 28px; choose bounds with a shorter exact decimal representation')
            fail()
        if len(result.stdout.encode())>8000000:fail()
        value=json.loads(result.stdout)
        if value.get('ok') is not True:fail()
        return value['result']
    except (OSError,ValueError,TypeError,KeyError,RecursionError,OverflowError,subprocess.TimeoutExpired):
        fail()

@functools.lru_cache(maxsize=512)
def _validated(raw,identity):
    return canonical(bridge({'op':'validate','spec':json.loads(raw)}))

def validate_spec(spec):
    try:
        manifest()
        raw=json.dumps(spec,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw.encode())>120000:fail()
        # Mirrors the bounded SVG parser's rule for text echoed into aria/data attributes.
        if UNRENDERABLE.search(raw):raise WorkflowError('TEMPLATE_INPUT: development template text cannot contain < or >, URL schemes or CSS directives')
        return json.loads(_validated(raw,SOURCE_MANIFEST_SHA256))
    except (ValueError,TypeError,KeyError,RecursionError,OverflowError):fail()

@functools.lru_cache(maxsize=64)
def _frame(raw,seconds,identity):
    result=bridge({'op':'frames','spec':json.loads(raw),'times':[seconds]})
    return canonical(result['frames'][0]['tree'])

def frame_tree(spec,seconds):
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not 0<=seconds<=45:fail()
    manifest()
    return json.loads(_frame(canonical(validate_spec(spec)),seconds,SOURCE_MANIFEST_SHA256))

def examples(key):
    row=next((v for v in catalog() if v['id']==key),None)
    if row is None:fail()
    return pinned_json('fixtures/development-templates/'+key+'.json',row['fixture_sha256'])['cases']

def _adaptation(row):
    return {'source_item_id':row['source_id'],'source_name':row['name'],'license':'MIT',
            'strategy':'original_implementation_not_source_code_port','original_implementation':True,
            'source_license':'metadata_reference_not_a_code_grant','implementation_license':'MIT',
            'scope':'MIT covers original StoryMotion code and documentation only; external source films, prompts and assets are not included.',
            'commercial_acceptance':'pending','requires_caller_media':row['requires_caller_media']}

def stage(package_root,out):
    if Path(package_root).resolve()!=ROOT:fail()
    proof=manifest();files=[];out=Path(out)
    for source in sorted(proof['files']):
        if source.startswith('tools/'):continue
        relative=source[len('renderers/'):]
        parent=Path(relative).parent
        current=Path()
        for part in parent.parts:
            current=current/part
            folder=guard_control(out,current,'dir');folder.mkdir(mode=0o700,exist_ok=True)
        target=guard_control(out,relative)
        shutil.copyfile(guard_control(ROOT,source),target)
        if file_hash(target)!=proof['files'][source]:fail()
        files.append(relative)
    receipt=guard_control(out,'template-registry/source-manifest.json')
    shutil.copyfile(ROOT/'renderers/template-registry/source-manifest.json',receipt)
    files.append('template-registry/source-manifest.json')
    return files

def adaptation(key):
    row=next((v for v in catalog() if v['id']==key),None)
    return _adaptation(row) if row else None

def source_records():
    return {row['source_id']:_adaptation(row) for row in catalog()}

def requires_media(key):
    return next((row['requires_caller_media'] for row in catalog() if row['id']==key),False)

def staged_files():
    return sorted([name[len('renderers/'):] for name in manifest()['files'] if name.startswith('renderers/')]+['template-registry/source-manifest.json'])

def verify_staged(out):
    out=Path(out)
    for source,expected in manifest()['files'].items():
        if source.startswith('renderers/'):
            path=guard_control(out,source[len('renderers/'):])
            if not path.is_file() or file_hash(path)!=expected:fail()
    path=guard_control(out,'template-registry/source-manifest.json')
    if not path.is_file() or file_hash(path)!=SOURCE_MANIFEST_SHA256:fail()
