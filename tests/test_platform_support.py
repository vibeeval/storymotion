"""Compatibility matrix, independent of native/browser acceptance."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from storymotion import platform_support as support, runtime
from tools import first_run

ROOT=Path(__file__).resolve().parents[1]
CASES=[('Darwin','arm64',('', ''),True),('Darwin','x86_64',('', ''),True),
       ('Linux','aarch64',('glibc','2.35'),True),('Linux','x86_64',('glibc','2.31'),True),
       ('Windows','AMD64',('', ''),True),('Linux','x86_64',('musl','1.2.5'),False),
       ('Linux','arm64',('', ''),False),('Linux','x86_64',('glibc','unknown'),False),
       ('Darwin','ppc64',('', ''),False)]


class PlatformSupportTests(unittest.TestCase):
    def test_first_run_and_runtime_share_platform_gate_without_native_acceptance(self):
        for system,machine,libc,expected in CASES:
            with self.subTest(system=system,machine=machine,libc=libc),patch.multiple(support.platform,system=lambda:system,machine=lambda:machine,libc_ver=lambda:libc),patch.object(first_run.shutil,'which',return_value=None),patch.object(sys,'platform','win32' if system=='Windows' else sys.platform),patch.object(sys,'getwindowsversion',return_value=SimpleNamespace(major=10),create=True):
                state=support.platform_status();prereq=first_run.prerequisites()
                self.assertEqual(state['supported'],expected)
                self.assertEqual(prereq['compatibility'],state)
                self.assertEqual(state['native_acceptance'],'unverified')
                self.assertEqual(state['locking'],'Windows LockFileEx' if system=='Windows' else 'POSIX fcntl')
                if not expected:
                    with tempfile.TemporaryDirectory() as temp,patch.object(runtime,'ROOT',Path(temp)),patch.object(runtime.subprocess,'run',side_effect=AssertionError('No native tool')):
                        self.assertFalse(runtime.doctor('hyperframes')['ok'])
                        with self.assertRaisesRegex(Exception,'PLATFORM_UNSUPPORTED'):runtime.setup()
                        self.assertEqual(list(Path(temp).iterdir()),[])

    @unittest.skipUnless(shutil.which('node'),'Node required for the offline JS platform matrix')
    def test_javascript_agrees_with_python_matrix(self):
        values=[]
        for system,machine,libc,expected in CASES:
            values.append([{'Darwin':'darwin','Linux':'linux','Windows':'win32'}.get(system,system),{'aarch64':'arm64','x86_64':'x64','AMD64':'x64'}.get(machine,machine),libc[1] if libc[0]=='glibc' else None,expected])
        script='import {platformSupported} from '+json.dumps((ROOT/'tools/runtime.mjs').as_uri())+';import assert from "node:assert/strict";for(const [system,arch,glibc,expected] of '+json.dumps(values)+')assert.equal(platformSupported(system,arch,glibc),expected);'
        result=subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_windows_cli_routes_platform_locking_without_unconditional_posix_import(self):
        source=(ROOT/'storymotion/__main__.py').read_text()
        self.assertNotIn('native Windows is unsupported',source)
        for name in ('store.py','qa_review.py','family_jobs.py','instance_guard.py'):
            self.assertIn('file_lock as fcntl',(ROOT/'storymotion'/name).read_text())
