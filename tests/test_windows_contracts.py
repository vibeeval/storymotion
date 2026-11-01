"""Offline contracts only: no Windows host, downloads, browser or renderer."""
import contextlib
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from storymotion import windows_native as win
from storymotion.security import WorkflowError
from storymotion import platform_support

ROOT=Path(__file__).resolve().parents[1]

class WindowsContracts(unittest.TestCase):
    def test_dos_names_streams_and_ambiguous_paths_refused(self):
        for value in ('CON','nul.txt','COM1.log','LPT²','a:b','a.','a ','..','x/y','x\\y','x\0y'):
            with self.subTest(value=value),self.assertRaises(WorkflowError):win.component(value)
        self.assertEqual(win.component('Türkçe test.json'),'Türkçe test.json')
        for value in ('\\\\server\\share\\x','C:relative','\\\\?\\C:\\x','C:\\a\\..\\b'):
            with self.subTest(value=value),self.assertRaises(WorkflowError):win.local_path(value)
        self.assertEqual(win.local_path('C:\\Users\\Örnek Kullanıcı\\x'),'C:\\Users\\Örnek Kullanıcı\\x')

    def test_only_windows_x64_ten_or_later(self):
        with patch.object(platform_support.platform,'system',return_value='Windows'),patch.object(sys,'platform','win32'),patch.object(sys,'getwindowsversion',return_value=types.SimpleNamespace(major=10),create=True):
            with patch.object(platform_support.platform,'machine',return_value='AMD64'):self.assertTrue(platform_support.platform_status()['supported'])
            with patch.object(platform_support.platform,'machine',return_value='ARM64'):self.assertFalse(platform_support.platform_status()['supported'])
            with patch.object(platform_support.platform,'machine',return_value='AMD64'),patch.object(sys,'getwindowsversion',return_value=types.SimpleNamespace(major=6)):self.assertFalse(platform_support.platform_status()['supported'])

    def test_lock_flags_shared_exclusive_unlock_and_contention(self):
        kernel=Mock();kernel.LockFileEx.return_value=1;kernel.UnlockFileEx.return_value=1
        with patch.object(win,'api',return_value=(kernel,None)),patch.dict(sys.modules,{'msvcrt':types.SimpleNamespace(get_osfhandle=lambda fd:99)}):
            win.flock(3,win.LOCK_EX|win.LOCK_NB);self.assertEqual(kernel.LockFileEx.call_args.args[1],3)
            win.flock(3,win.LOCK_SH|win.LOCK_NB);self.assertEqual(kernel.LockFileEx.call_args.args[1],1)
            win.flock(3,win.LOCK_UN);kernel.UnlockFileEx.assert_called_once()
            kernel.LockFileEx.return_value=0
            with patch.object(win.C,'get_last_error',return_value=33,create=True),self.assertRaises(BlockingIOError):win.flock(3,win.LOCK_EX|win.LOCK_NB)

    def test_reparse_wrong_type_and_multiple_links_fail_before_acl(self):
        kernel=Mock()
        for attributes,links,directory in ((0x400,1,False),(0x10,1,False),(0,2,False),(0,1,True)):
            def fill(handle,pointer):
                pointer._obj.attributes=attributes;pointer._obj.links=links;return 1
            kernel.GetFileInformationByHandle.side_effect=fill
            with patch.object(win,'api',return_value=(kernel,None)),patch.object(win,'acl') as acl,self.assertRaises(WorkflowError):
                win.handle_info(1,directory=directory)
            acl.assert_not_called()

    def test_ntfs_and_fixed_local_drive_required(self):
        kernel=Mock();kernel.GetDriveTypeW.return_value=4
        with patch.object(win,'api',return_value=(kernel,None)),self.assertRaises(WorkflowError):win.ntfs('C:\\x')
        kernel.GetDriveTypeW.return_value=3
        def volume(*args):args[6].value='FAT32';return 1
        kernel.GetVolumeInformationW.side_effect=volume
        with patch.object(win,'api',return_value=(kernel,None)),self.assertRaises(WorkflowError):win.ntfs('C:\\x')

    def test_no_shell_npm_dispatch_preserves_spaces_and_arguments(self):
        with tempfile.TemporaryDirectory(prefix='windows command ü ') as temp:
            base=Path(temp);(base/'node_modules/npm/bin').mkdir(parents=True);(base/'node_modules/npm/bin/npm-cli.js').write_text('')
            node=base/'node.exe'
            with patch('shutil.which',return_value=str(node)):
                result=win.npm_command(['npm','ci','--cache=C:\\two words\\ö'])
            self.assertEqual(result,[str(node),str(base/'node_modules/npm/bin/npm-cli.js'),'ci','--cache=C:\\two words\\ö'])

    def test_job_assignment_failure_never_releases_payload_and_cleans_owned_child(self):
        kernel=Mock();kernel.CreateJobObjectW.return_value=22;kernel.SetInformationJobObject.return_value=1
        kernel.AssignProcessToJobObject.return_value=0
        child=Mock();child._handle=33
        with patch.object(win,'api',return_value=(kernel,None)),patch.object(win.subprocess,'Popen',return_value=child),patch.object(win.subprocess,'CREATE_NO_WINDOW',0,create=True),patch.object(win.C,'get_last_error',return_value=5,create=True),patch.object(win.C,'WinError',side_effect=lambda value:OSError(value,'mock'),create=True):
            with self.assertRaises(OSError):win.launch(['node','fixture.js'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        child.stdin.write.assert_not_called();child.kill.assert_called_once();kernel.CloseHandle.assert_called_with(22)

    def test_job_assignment_precedes_gate_and_close_is_idempotent(self):
        events=[];kernel=Mock();kernel.CreateJobObjectW.return_value=22;kernel.SetInformationJobObject.return_value=1
        kernel.AssignProcessToJobObject.side_effect=lambda *args:events.append('assigned') or 1
        child=Mock();child._handle=33;stream=child.stdin;stream.write.side_effect=lambda value:events.append(value)
        with patch.object(win,'api',return_value=(kernel,None)),patch.object(win.subprocess,'Popen',return_value=child),patch.object(win.subprocess,'CREATE_NO_WINDOW',0,create=True):
            result=win.launch(['node','a b.js'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            win.close_job(result,terminate=True);win.close_job(result,terminate=True)
        self.assertEqual(events,['assigned',b'G']);kernel.TerminateJobObject.assert_called_once_with(22,1);kernel.CloseHandle.assert_called_once_with(22)

    def test_windows_recipe_has_separate_pinned_provenance(self):
        value=json.loads((ROOT/'renderers/windows-media.json').read_text())
        self.assertEqual(value['archive_sha256'],'60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba')
        self.assertEqual(value['platform'],'win32');self.assertFalse(value['binary_redistributed'])
        self.assertEqual(value['native_acceptance'],'unverified')
        self.assertEqual(json.loads((ROOT/'renderers/ffprobe-source.json').read_text())['version'],'8.1.3')
