"""Explicit offline source staging/verification; no install or process launch."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from storymotion.source_update import stage_update,verify_update
from storymotion.security import WorkflowError


def main(argv=None):
    parser=argparse.ArgumentParser(description='Stage a verified release in a new directory, preserving the old installation and work.')
    parser.add_argument('command',choices=('stage','verify'));parser.add_argument('--archive',required=True)
    parser.add_argument('--destination',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--preserve-workspace',action='append',default=[],help='Explicit existing workspace outside the source tree; never used as an update destination')
    args=parser.parse_args(argv)
    try:
        action=stage_update if args.command=='stage' else verify_update
        value=action(args.archive,args.destination,args.sha256,active_root=ROOT,protected_workspaces=args.preserve_workspace)
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except (WorkflowError,OSError,ValueError) as error:
        message=str(error) if isinstance(error,WorkflowError) else 'UPDATE_LOCAL_OPERATION_FAILED: inspect the existing outcome before retry; no cleanup or overwrite was attempted'
        print(json.dumps({'ok':False,'error':message}));return 2


if __name__=='__main__':sys.exit(main())
