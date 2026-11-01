import sys
from .account_packs import ACCOUNTS
import argparse
import json
import shutil
from pathlib import Path
from .engine import Engine, ROOT, STAGES
from .security import WorkflowError, scan_tree


def parser():
    p=argparse.ArgumentParser(description='Story Motion MVP — local only; no live model or voice calls')
    p.add_argument('--workspace',default='work')
    p.add_argument('--hf',help='Path to installed hyperframes dist/cli.js; no automatic installation')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('templates',help='List 91 fixed bounded templates and input examples; native acceptance is separate')
    a=sub.add_parser('create');a.add_argument('brief');a.add_argument('--dry-run',action='store_true');a.add_argument('--engine',choices=['hyperframes','remotion'],default='hyperframes')
    a=sub.add_parser('run');a.add_argument('job');a.add_argument('--until',choices=STAGES,default='delivery')
    for name in ['status','logs']:
        sub.add_parser(name).add_argument('job')
    a=sub.add_parser('voice-request');a.add_argument('job');a.add_argument('--provider',required=True);a.add_argument('--model',required=True);a.add_argument('--voice',required=True);a.add_argument('--estimate-usd',required=True);a.add_argument('--quote-source',required=True)
    a=sub.add_parser('budget-approve');a.add_argument('request');a.add_argument('--max-usd',required=True);a.add_argument('--approved-by',required=True);a.add_argument('--hours',type=float,default=1)
    a=sub.add_parser('voice-execute');a.add_argument('request');a.add_argument('--simulate-uncertain',action='store_true')
    a=sub.add_parser('reconcile');a.add_argument('request');a.add_argument('receipt')
    a=sub.add_parser('scan');a.add_argument('path',nargs='?',default='.')
    a=sub.add_parser('doctor');a.add_argument('--engine',choices=['hyperframes','remotion','all'],default='hyperframes');a.add_argument('--strict',action='store_true')
    a=sub.add_parser('setup',help='Install through the source/license and explicit download gates')
    a.add_argument('--engine',choices=['hyperframes','remotion','all'],default='hyperframes')
    a.add_argument('--skip-npm',action='store_true',help='Requires a completed matching engine/lock npm receipt and pinned packages')
    a.add_argument('--allow-downloads',action='store_true')
    a.add_argument('--license-sha256','--accept-eula-sha256',dest='license_sha256',metavar='LICENSE_SHA256',help='Exact SHA256 of the reviewed source LICENSE; the older flag is a compatibility alias, not an additional contract')
    a=sub.add_parser('workflow-status',help='Read-only source/code/test scope and open acceptance gates');a.add_argument('--account',choices=list(ACCOUNTS))
    a=sub.add_parser('edit-plan',help='Compile bounded scene/object/camera/assets plan; no DB, network or media render');a.add_argument('brief');a.add_argument('--engine',choices=['hyperframes','remotion'],required=True)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.command=='setup':
        # Keep every public installation command behind the same manifest,
        # source-license, download and dependency checks. Failed setup must not
        # create a job workspace before those checks run.
        from tools.first_run import main as install_main
        install_args=['install','--engine',args.engine]
        if args.skip_npm:install_args.append('--skip-npm')
        if args.allow_downloads:install_args.append('--allow-downloads')
        if args.license_sha256 is not None:
            install_args.extend(['--license-sha256',args.license_sha256])
        return install_main(install_args)
    e=Engine(args.workspace,args.hf)
    try:
        c=args.command
        if c=='templates':
            from .template_families import capabilities
            result=capabilities()
        elif c=='create':result=e.create(args.brief,args.dry_run,args.engine)
        elif c=='run':result=e.run(args.job,args.until)
        elif c=='status':e.payload(args.job);result=e.store.status(args.job)
        elif c=='logs':e.payload(args.job);result=e.logs(args.job)
        elif c=='voice-request':result=e.request(args.job,args.provider,args.model,args.voice,args.estimate_usd,args.quote_source)
        elif c=='budget-approve':result=e.approve(args.request,args.max_usd,args.approved_by,args.hours)
        elif c=='voice-execute':result=e.execute_voice(args.request,args.simulate_uncertain)
        elif c=='reconcile':result=e.reconcile(args.request,json.loads(Path(args.receipt).read_text()))
        elif c=='scan':
            findings=scan_tree(args.path);print(json.dumps({'ok':not findings,'findings':findings},indent=2));return int(bool(findings))
        elif c=='doctor':
            from .runtime import doctor
            result=doctor(args.engine)
        elif c=='workflow-status':
            from .workflow_state import workflow_status
            result=workflow_status(args.account)
        elif c=='edit-plan':
            _,payload=e.plan(args.brief,args.engine)
            if 'edit_plan' not in payload:raise WorkflowError('Edit plan requires the versioned creative scene contract')
            result=payload['edit_plan']
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if c=='doctor' and args.strict and not result['ok'] else 0
    except (WorkflowError,ValueError,KeyError,OSError,TypeError) as ex:
        # Do not include malformed input or raw exception values outside controlled WorkflowError.
        message=str(ex) if isinstance(ex,WorkflowError) else 'Invalid input or local filesystem operation failed'
        print(json.dumps({'ok':False,'error':message},ensure_ascii=False),file=sys.stderr);return 2
    finally:e.close()


if __name__=='__main__':sys.exit(main())
