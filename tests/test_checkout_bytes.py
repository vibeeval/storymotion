"""Pinned source bytes survive a checkout with Windows-style Git line endings."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('git'), 'Git is required for the local checkout contract')
class CheckoutBytesTests(unittest.TestCase):
    def test_autocrlf_checkout_preserves_text_and_binary_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();source=base/'source';source.mkdir();target=base/'clone'
            config=base/'empty-config';config.write_text('')
            env={k:v for k,v in os.environ.items() if k in {'PATH','SystemRoot','WINDIR','TMP','TEMP','TMPDIR','HOME','USERPROFILE'}}
            env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=str(config))
            def git(*args,cwd=source):
                return subprocess.run(['git',*args],cwd=cwd,env=env,check=True,
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            payload={'pinned.mjs':b'// synthetic pinned source\nexport const value=1;\n',
                     'fixture.bin':b'\0\r\n\xff\n\r\0'}
            (source/'.gitattributes').write_bytes((ROOT/'.gitattributes').read_bytes())
            for name,raw in payload.items():(source/name).write_bytes(raw)
            git('init','--quiet');git('add','--','.')
            git('-c','user.name=Synthetic fixture','-c','user.email=fixture@example.invalid',
                '-c','commit.gpgsign=false','commit','--quiet','-m','Synthetic local checkout fixture')
            git('-c','core.autocrlf=true','clone','--local','--no-hardlinks','--quiet',str(source),str(target),cwd=base)
            for name,raw in payload.items():self.assertEqual((target/name).read_bytes(),raw)
