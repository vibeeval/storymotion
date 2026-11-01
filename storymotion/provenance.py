from pathlib import Path
from .security import digest,file_hash


def execution_provenance():
    root=Path(__file__).resolve().parents[1]
    paths=[]
    for folder in ['storymotion','vendor','catalog','renderers','knowledge','accountpacks']:
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths += [root/'tools'/name for name in ['cover.mjs','remotion.mjs','runtime.mjs','raster.mjs']]
    paths += [root/'package.json',root/'package-lock.json']
    paths += [root/'optional/remotion/package.json',root/'optional/remotion/package-lock.json']
    hashes={p.relative_to(root).as_posix():file_hash(p) for p in sorted(paths)}
    from .account_packs import catalog
    packs, _ = catalog()
    hashes.update({'accountpacks/active/' + key: digest(value) for key, value in packs.items()})
    return {'fingerprint':digest(hashes),'files':hashes,'mode':'pinned_local_code_registry_vendor_renderer'}
