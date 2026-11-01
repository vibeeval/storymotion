"""Synthetic ZIP integrity checks. No native executable, download or renderer runs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from storymotion import windows_media as media

ROOT=Path(__file__).resolve().parents[1]

class WindowsMediaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/media.BASE;self.folder.mkdir(parents=True)
        def pe(label):
            raw=bytearray(80);raw[:2]=b'MZ';raw[60:64]=(64).to_bytes(4,'little');raw[64:70]=b'PE\0\0d\x86'
            return bytes(raw)+label
        self.data={'ffmpeg':pe(b'synthetic ffmpeg'),'ffprobe':pe(b'synthetic ffprobe'),'license':b'Synthetic license fixture'}
        self.archive=self.folder/'source.zip'
        with zipfile.ZipFile(self.archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in self.data.items():z.writestr('fixture/'+('LICENSE' if name=='license' else 'bin/'+name+'.exe'),raw)
        self.sha=hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.addCleanup(patch.stopall)
        patch.object(media,'SHA',self.sha).start()
        patch.object(media,'inspect',return_value=None).start() # NTFS/ACL has separate contracts
        (self.root/'renderers').mkdir()
        recipe=json.loads((ROOT/'renderers/windows-media.json').read_text());recipe['archive_sha256']=self.sha
        (self.root/'renderers/windows-media.json').write_text(json.dumps(recipe))
        self.expected=media.archive_hashes(self.archive)
        for name,raw in self.data.items():(self.folder/('LICENSE.txt' if name=='license' else name+'.exe')).write_bytes(raw)
        self.receipt={'schema_version':1,'platform':'win32','architecture':'x64','version':media.VERSION,
            'archive_sha256':self.sha,'recipe_sha256':media.file_hash(self.root/'renderers/windows-media.json'),
            'binaries':{name:self.expected[name] for name in ('ffmpeg','ffprobe')},'license_sha256':self.expected['license']}
        self.save_receipt()

    def save_receipt(self):
        (self.folder/'receipt.json').write_text(json.dumps(self.receipt))

    def node_matches(self):
        script='import {windowsMediaFilesMatch} from '+json.dumps((ROOT/'tools/runtime.mjs').as_uri())+';console.log(JSON.stringify(windowsMediaFilesMatch('+','.join(map(json.dumps,[str(self.folder),self.receipt,self.expected]))+')));'
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_python_positive_uses_selected_archive_members(self):
        self.assertEqual(self.expected,{name:hashlib.sha256(raw).hexdigest() for name,raw in self.data.items()})
        self.assertTrue(media.status(self.root)['ready'])

    def test_python_rejects_binary_and_receipt_tampered_together(self):
        for name in ('ffmpeg','ffprobe'):
            with self.subTest(name=name):
                path=self.folder/(name+'.exe');original=path.read_bytes();changed=original+b'modified'
                path.write_bytes(changed);self.receipt['binaries'][name]=hashlib.sha256(changed).hexdigest();self.save_receipt()
                self.assertFalse(media.status(self.root)['ready'])
                self.assertEqual(media.file_hash(self.archive),self.sha)
                path.write_bytes(original);self.receipt['binaries'][name]=self.expected[name];self.save_receipt()

    def test_python_rejects_license_and_receipt_tampered_together(self):
        (self.folder/'LICENSE.txt').write_bytes(b'changed')
        self.receipt['license_sha256']=hashlib.sha256(b'changed').hexdigest();self.save_receipt()
        self.assertFalse(media.status(self.root)['ready'])

    def test_changed_archive_is_not_an_alternate_trust_root(self):
        with self.archive.open('ab') as stream:stream.write(b'changed')
        self.assertFalse(media.status(self.root)['ready'])

    @unittest.skipUnless(shutil.which('node'),'Node required for offline consumer checks')
    def test_node_positive_and_joint_binary_receipt_tampering(self):
        self.assertTrue(self.node_matches())
        for name in ('ffmpeg','ffprobe'):
            with self.subTest(name=name):
                path=self.folder/(name+'.exe');original=path.read_bytes();changed=original+b'modified'
                path.write_bytes(changed);self.receipt['binaries'][name]=hashlib.sha256(changed).hexdigest()
                self.assertFalse(self.node_matches())
                path.write_bytes(original);self.receipt['binaries'][name]=self.expected[name]
        (self.folder/'LICENSE.txt').write_bytes(b'changed');self.receipt['license_sha256']=hashlib.sha256(b'changed').hexdigest()
        self.assertFalse(self.node_matches())
