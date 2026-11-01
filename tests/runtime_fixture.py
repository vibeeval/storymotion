"""Owned offline setup fixtures; never an installation or rights acceptance."""
import json
import shutil
from pathlib import Path
from storymotion.install_policy import graph_plan,graph_receipt,selected_graphs
ROOT=Path(__file__).resolve().parents[1]
METADATA=('package.json','package-lock.json','optional/remotion/package.json','optional/remotion/package-lock.json','renderers/ffprobe-source.json','vendor/licenses/ffmpeg-8.1.3-COPYING.LGPLv2.1','vendor/licenses/ffmpeg-8.1.3-LICENSE.md')
def copy_metadata(root):
    for name in METADATA:
        target=Path(root)/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
def packages(root,engine='all'):
    for graph in selected_graphs(engine):
        g=graph_plan(graph,root=root);folder=Path(root)/g['directory'];manifest=json.loads((folder/'package.json').read_text())
        for name,version in manifest['dependencies'].items():
            p=folder/'node_modules'/name/'package.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'version':version}))
def receipts(root,engine='all'):
    (Path(root)/'.runtime').mkdir(exist_ok=True)
    for graph in selected_graphs(engine):
        g=graph_plan(graph,root=root);p=Path(root)/('.runtime/npm-'+graph+'.json');p.write_text(json.dumps(graph_receipt(graph,g['package_lock_sha256'],g['package_json_sha256'])))
    return Path(root)/'.runtime/npm-core.json'
