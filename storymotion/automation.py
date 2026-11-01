from .account_packs import capability, render_profile
"""Compile a fresh structured brief or provider JSON draft into a pinned local job.

No model call occurs here. Provider output is untrusted data; only declared scene
primitives pass validation. Generated drafts remain provisional and require review.
"""
import argparse
import json
from pathlib import Path
from .engine import Engine,ROOT,apply_appearance,validate
from .security import WorkflowError,scan_bytes,write_json


def compile_generated_story(raw,brand):
    if not capability(brand, 'legacy_fixture'):raise WorkflowError('No implemented video renderer profile for this brand')
    if not isinstance(raw,str) or len(raw.encode())>100000 or scan_bytes(raw.encode()):raise WorkflowError('Generated draft invalid or contains a possible secret')
    try:brief=json.loads(raw)
    except ValueError:raise WorkflowError('Expected one JSON story object; markdown/code is not executable input')
    if not isinstance(brief,dict) or brief.get('brand')!=brand:raise WorkflowError('Generated brand binding mismatch')
    if brief.get('audio') is not None or brief.get('alignment')!='provisional_silent':raise WorkflowError('Generated draft cannot read local audio or claim measured alignment')
    allowed={'schema_version','brand','language','title','brief','demo','script','caption','duration','alignment','audio','claims','scenes','cues','continuity','appearance'}
    if set(brief)-allowed:raise WorkflowError('Unsupported generated story fields')
    profile=render_profile(brand);validate(brief,apply_appearance(profile,brief.get('appearance')))
    return brief


def provider_result_to_job(runtime,request_ref,brand,until='prepare'):
    row=runtime.row(request_ref)
    if row['status']!='complete':raise WorkflowError('Provider result is not complete; no automatic replay or regeneration')
    receipt=json.loads(row['receipt'])
    from .security import file_hash,within
    path=within(runtime.store.root,receipt['file'])
    if receipt['media_type']!='text/plain' or not path.is_file() or file_hash(path)!=receipt['sha256']:raise WorkflowError('Provider draft artifact changed or has wrong media type')
    brief=compile_generated_story(path.read_text(),brand)
    source=path.parent/'compiled-story.json';write_json(source,brief)
    with Engine(runtime.store.root) as engine:job=engine.create(source)['job'];engine.run(job,until)
    return {'job':job,'source_provider_request':request_ref,'synthetic_provider_result':receipt['synthetic'],'content_mode':'new_structured_brief_not_fixture_replay','paid_calls':0 if receipt['synthetic'] else 'see_provider_receipt'}


def main():
    p=argparse.ArgumentParser();p.add_argument('brief');p.add_argument('--workspace',default='work');p.add_argument('--hf');p.add_argument('--until',choices=['prepare','check','delivery'],default='prepare');a=p.parse_args()
    with Engine(a.workspace,a.hf) as engine:job=engine.create(a.brief)['job'];engine.run(job,a.until)
    print(json.dumps({'job':job,'content_mode':'input_driven','provider_calls':0,'stage':a.until},indent=2))


if __name__=='__main__':main()
