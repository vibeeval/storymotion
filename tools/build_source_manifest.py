"""Record a clean, locally committed source payload. No downloads or release approval."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from storymotion import __version__
from storymotion.install_policy import source_distribution, verify_source_files
from storymotion.security import WorkflowError

MANIFEST = 'SOURCE-MANIFEST.json'
EXCLUDED = {'.git', '.runtime', 'node_modules', 'work', 'internal', 'private',
            'deliverables', 'evidence', 'reports', 'backups', '__pycache__'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')


def build():
    if ROOT != ROOT.resolve() or not (ROOT / '.git').is_dir() or (ROOT / '.git').is_symlink():
        raise WorkflowError('SOURCE_REPOSITORY_REQUIRED')
    commit = git('rev-parse', 'HEAD').strip()
    names = [n for n in git('ls-files', '-z').split('\0') if n and n != MANIFEST]
    # The payload commit is the last commit before this manifest-only change.
    dirty = [n for n in git('status', '--porcelain', '--untracked-files=normal').splitlines()
             if n[3:] != MANIFEST]
    if dirty:
        raise WorkflowError('SOURCE_PAYLOAD_MUST_BE_COMMITTED: commit reviewed payload changes first')
    files = {}
    for name in sorted(names):
        rel = Path(name)
        if (rel.is_absolute() or '..' in rel.parts or any(p in EXCLUDED for p in rel.parts)
                or (rel.name.startswith('.env') and name != '.env.example')
                or rel.suffix.lower() in {'.zip', '.mp4', '.mov', '.sqlite3', '.db', '.pem', '.key'}):
            raise WorkflowError('SOURCE_PRIVATE_OR_GENERATED_PATH_REFUSED')
        path = ROOT / rel
        if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents if p != ROOT.parent):
            raise WorkflowError('SOURCE_LINK_OR_NONFILE_REFUSED')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    value = {'source_distribution_schema': 1, 'status': 'installable_source_distribution',
             'version': __version__, 'source_commit': commit,
             'source_commit_scope': 'Exact committed payload; this manifest is recorded in a subsequent commit.',
             'original_code_license': 'MIT', 'customer_release_ready': False,
             'rights_pending': True, 'publication_ready': False,
             'native_acceptance': 'unverified', 'browser_acceptance': 'unverified',
             'independent_review': 'pending', 'files': files}
    if not source_distribution(value):
        raise WorkflowError('SOURCE_DISTRIBUTION_CONTRACT_INVALID')
    verify_source_files(ROOT, files)
    (ROOT / MANIFEST).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'manifest': MANIFEST, 'payload_commit': commit, 'files': len(files),
            'publication_ready': False, 'provider_calls': 0, 'downloads': 0}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(build(), indent=2))
    except (WorkflowError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
