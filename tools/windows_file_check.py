"""Bounded local inspection and pinned archive hashes for Node; no mutation."""
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    if sys.platform!='win32' or len(sys.argv)!=2:sys.exit(2)
    try:
        from storymotion.windows_native import inspect
        if sys.argv[1]=='--media-hashes':
            from storymotion.windows_media import archive_hashes, BASE
            print(json.dumps(archive_hashes(ROOT/BASE/'source.zip')))
        else:
            path=Path(sys.argv[1]);path.relative_to(ROOT)
            inspect(path,missing=False)
    except Exception:sys.exit(2)
