"""Fresh project traversal parity/fault tests; isolated owned data, no native."""
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storymotion import local_state as state
from storymotion.security import WorkflowError
from project_scope_reference import old_guard_project_scope


class ProjectScopeWalkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'project';self.root.mkdir()

    def file(self,name,content=b'Original synthetic fixture'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content);return path

    def image(self,root=None):
        root=root or self.root
        return {str(p.relative_to(root)):(p.lstat().st_mode,p.lstat().st_nlink,p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None) for p in root.rglob('*')}

    def same(self,accepted=True):
        before=self.image()
        for function in (old_guard_project_scope,state.guard_project_scope):
            if accepted:self.assertEqual(function(self.root),self.root)
            else:
                with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(self.root)
        self.assertEqual(self.image(),before)

    def test_empty_missing_and_owned_nested_build_and_work_trees_match(self):
        self.same();missing=self.root/'absent'
        self.assertEqual(old_guard_project_scope(missing),missing);self.assertEqual(state.guard_project_scope(missing),missing)
        for name in ('work/jobs/a/input.json','.runtime/ffmpeg/stages/a/source/src/config.h',
                     '.runtime/development/probe/stages/b/source/config.h','.runtime/npm-cache/a/cache'):
            self.file(name)
        self.same()

    def test_static_build_modes_are_not_repaired_or_subject_to_private_state_modes(self):
        a=self.file('.runtime/build/source.c');a.chmod(0o644);a.parent.chmod(0o755)
        b=self.file('work/static.js');b.chmod(0o755)
        self.same();self.assertEqual(stat.S_IMODE(a.stat().st_mode),0o644)

    def test_existing_private_permission_gates_still_reject_shared_mutable_modes(self):
        state.private_directory(self.root/'work/family-inputs')
        path=self.file('work/family-inputs/draft.json');path.chmod(0o644);self.same()
        with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_PERMISSIONS'):state.guard_workspace(self.root/'work')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)

    def test_unreadable_mutable_directory_refused_without_permission_repair(self):
        p=self.file('work/blocked/entry').parent;p.chmod(0o000)
        try:
            for function in (old_guard_project_scope,state.guard_project_scope):
                with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(self.root)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o000)
        finally:p.chmod(0o700)  # Test-fixture cleanup only.

    def test_existing_vendor_exclusions_are_identical_and_roots_are_checked(self):
        target=self.base/'outside';target.mkdir();(target/'keep').write_bytes(b'Keep')
        for parent in ('node_modules/pkg','optional/remotion/node_modules/pkg','.runtime/chrome/browser','.runtime/probe/stages/build'):
            p=self.root/parent;p.mkdir(parents=True);(p/'vendor-link').symlink_to(target,target_is_directory=True)
        self.same();self.assertEqual((target/'keep').read_bytes(),b'Keep')

    def test_nested_internal_external_dangling_and_directory_symlinks_are_refused(self):
        self.file('work/ordinary.txt');outside=self.base/'outside';outside.mkdir();(outside/'keep').write_bytes(b'Keep')
        for target,directory in ((self.root/'work/ordinary.txt',False),(outside/'keep',False),(outside,True),(self.base/'missing',False)):
            p=self.root/'work/link';p.symlink_to(target,target_is_directory=directory)
            self.same(False);p.unlink()
        self.assertEqual((outside/'keep').read_bytes(),b'Keep')

    def test_top_control_vendor_and_optional_roots_cannot_be_links(self):
        outside=self.base/'outside';outside.mkdir()
        for name in ('work','.runtime','node_modules','.runtime/chrome','.runtime/npm-cache','.runtime/setup-state','optional/remotion/node_modules'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.symlink_to(outside,target_is_directory=True)
            self.same(False);p.unlink()

    def test_private_probe_and_ffmpeg_builds_have_no_new_exemption(self):
        target=self.base/'outside';target.write_bytes(b'Keep')
        for name in ('.runtime/ffmpeg/stages/a/source/linked','.runtime/development/probe/stages/b/source/linked'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.symlink_to(target)
            self.same(False);p.unlink()

    def test_exempt_vendor_directory_is_not_opened_or_subject_to_new_read_permission(self):
        p=self.root/'.runtime/chrome';p.mkdir(parents=True);p.chmod(0o000)
        try:
            for function in (old_guard_project_scope,state.guard_project_scope):self.assertEqual(function(self.root),self.root)
        finally:p.chmod(0o700)

    def test_hardlinks_are_refused_without_changing_target(self):
        source=self.base/'outside';source.write_bytes(b'Keep');p=self.root/'work/hard';p.parent.mkdir();os.link(source,p)
        before=(source.read_bytes(),source.stat().st_mtime_ns,source.stat().st_nlink)
        self.same(False);self.assertEqual((source.read_bytes(),source.stat().st_mtime_ns,source.stat().st_nlink),before)

    def test_fifo_and_synthetic_socket_modes_are_refused(self):
        p=self.root/'work/special';p.parent.mkdir();os.mkfifo(p,0o600)
        for function in (old_guard_project_scope,state.guard_project_scope):
            with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(self.root)
        p.unlink()
        # This executor refused AF_UNIX bind (EPERM); do not retry or route
        # around that refusal. Synthetic stat data exercises the same type gate.
        p.write_bytes(b'Synthetic socket-mode fixture');inode=p.stat().st_ino;real_lstat=Path.lstat;real_stat=os.stat
        def changed(info):
            if info.st_ino!=inode:return info
            values={n:getattr(info,n) for n in dir(info) if n.startswith('st_')};values['st_mode']=stat.S_IFSOCK|0o600
            return SimpleNamespace(**values)
        with patch.object(Path,'lstat',lambda path:changed(real_lstat(path))),patch.object(os,'stat',lambda *a,**kw:changed(real_stat(*a,**kw))):
            for function in (old_guard_project_scope,state.guard_project_scope):
                with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(self.root)

    def test_foreign_root_and_nested_ownership_are_refused(self):
        target=self.file('work/nested/entry');real_lstat=Path.lstat;real_stat=os.stat;inode=target.stat().st_ino
        def changed(info):
            if info.st_ino!=inode:return info
            values={n:getattr(info,n) for n in dir(info) if n.startswith('st_')};values['st_uid']=os.getuid()+1
            return SimpleNamespace(**values)
        with patch.object(Path,'lstat',lambda p:changed(real_lstat(p))),patch.object(os,'stat',lambda *a,**kw:changed(real_stat(*a,**kw))):
            for function in (old_guard_project_scope,state.guard_project_scope):
                with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(self.root)
        with patch.object(os,'getuid',return_value=os.getuid()+1):self.same(False)

    def test_direct_root_alias_refused_and_initial_ancestor_alias_canonicalizes_as_before(self):
        alias=self.base/'alias';alias.symlink_to(self.root,target_is_directory=True)
        for function in (old_guard_project_scope,state.guard_project_scope):
            with self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):function(alias)
        outer=self.base/'outer';outer.symlink_to(self.base,target_is_directory=True)
        self.assertEqual(old_guard_project_scope(outer/'project'),self.root);self.assertEqual(state.guard_project_scope(outer/'project'),self.root)

    def test_wrong_top_root_kind_is_refused(self):
        for name in ('work','.runtime','node_modules'):
            p=self.file(name)
            self.same(False);p.unlink()

    def test_entry_and_depth_limits_are_explicit_and_never_silently_truncate(self):
        self.file('work/a/b/leaf');self.file('work/second')
        self.assertEqual(old_guard_project_scope(self.root),self.root)
        with patch.object(state,'PROJECT_SCAN_MAX_ENTRIES',2),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_SCAN_LIMIT'):state.guard_project_scope(self.root)
        with patch.object(state,'PROJECT_SCAN_MAX_DEPTH',2),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_SCAN_LIMIT'):state.guard_project_scope(self.root)
        self.same()

    def test_unavailable_fd_primitives_fail_closed(self):
        with patch.object(state,'_PROJECT_FD_SUPPORTED',False),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(self.root)

    def test_no_directory_is_enumerated_twice_or_revalidated_via_absolute_ancestors(self):
        self.file('work/a/b/leaf');self.file('.runtime/build/a/config.h');seen=[];real_scan=os.scandir
        def scan(fd):
            self.assertIsInstance(fd,int);i=os.fstat(fd);key=(i.st_dev,i.st_ino);self.assertNotIn(key,seen);seen.append(key)
            return real_scan(fd)
        with patch.object(os,'scandir',side_effect=scan),patch.object(state,'guard_control',wraps=state.guard_control) as guard:
            state.guard_project_scope(self.root)
        self.assertEqual(guard.call_count,7);self.assertEqual(len(seen),6)

    def test_directory_swap_to_external_link_before_open_is_refused(self):
        self.file('work/branch/leaf');outside=self.base/'outside';outside.mkdir();(outside/'keep').write_bytes(b'Keep')
        real_open=os.open;swapped=[]
        def opened(name,*a,**kw):
            if name=='branch' and not swapped:
                (self.root/'work/branch').rename(self.base/'moved');(self.root/'work/branch').symlink_to(outside,target_is_directory=True);swapped.append(True)
            return real_open(name,*a,**kw)
        with patch.object(os,'open',side_effect=opened),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(self.root)
        self.assertTrue(swapped);self.assertEqual((outside/'keep').read_bytes(),b'Keep')

    def test_opened_directory_replacement_is_detected_and_descriptors_close(self):
        branch=self.file('work/branch/leaf').parent;inode=branch.stat().st_ino;real_scan=os.scandir;opened=[];closed=[];real_open=os.open;real_close=os.close;swapped=[]
        def opening(*a,**kw):
            fd=real_open(*a,**kw);opened.append(fd);return fd
        def closing(fd):closed.append(fd);return real_close(fd)
        def scan(fd):
            if os.fstat(fd).st_ino==inode and not swapped:
                branch.rename(self.base/'moved');branch.mkdir();swapped.append(True)
            return real_scan(fd)
        with patch.object(os,'open',side_effect=opening),patch.object(os,'close',side_effect=closing),patch.object(os,'scandir',side_effect=scan),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):
            state.guard_project_scope(self.root)
        self.assertTrue(swapped);self.assertCountEqual(opened,closed)

    def test_owned_regular_file_replacement_and_in_place_mutation_are_detected(self):
        target=self.file('work/entry');real_stat=os.stat
        for replace in (False,True):
            changed=[]
            def observed(name,*a,**kw):
                info=real_stat(name,*a,**kw)
                if name=='entry' and not changed:
                    if replace:target.rename(self.base/'old-entry')
                    target.write_bytes(b'Changed fixture');changed.append(True)
                return info
            with patch.object(os,'stat',side_effect=observed),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(self.root)
            self.assertTrue(changed);target.write_bytes(b'Original synthetic fixture')

    def test_directory_entry_addition_after_enumeration_is_detected(self):
        target=self.file('work/first');real_stat=os.stat;changed=[]
        def observed(name,*a,**kw):
            info=real_stat(name,*a,**kw)
            if name=='first' and not changed:self.file('work/late');changed.append(True)
            return info
        with patch.object(os,'stat',side_effect=observed),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(self.root)

    def test_root_replacement_before_open_is_refused(self):
        self.file('work/leaf');real_open=os.open;changed=[]
        def opened(name,*a,**kw):
            if name==self.root and not changed:self.root.rename(self.base/'old-project');self.root.mkdir();changed.append(True)
            return real_open(name,*a,**kw)
        with patch.object(os,'open',side_effect=opened),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(self.root)

    def test_ancestor_link_replacement_after_root_open_is_detected(self):
        holder=self.root/'holder';project=holder/'selected';(project/'work').mkdir(parents=True)
        outside=self.base/'outside';(outside/'selected/work').mkdir(parents=True);(outside/'selected/work/keep').write_bytes(b'Keep')
        real_open=os.open;changed=[]
        def opened(name,*a,**kw):
            if name=='work' and not changed:
                holder.rename(self.root/'moved-holder');holder.symlink_to(outside,target_is_directory=True);changed.append(True)
            return real_open(name,*a,**kw)
        with patch.object(os,'open',side_effect=opened),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):state.guard_project_scope(project)
        self.assertTrue(changed);self.assertEqual((outside/'selected/work/keep').read_bytes(),b'Keep')

    def test_scandir_failure_closes_all_owned_descriptors(self):
        self.file('work/a/leaf');real_open=os.open;real_close=os.close;opened=[];closed=[]
        def opening(*a,**kw):fd=real_open(*a,**kw);opened.append(fd);return fd
        def closing(fd):closed.append(fd);return real_close(fd)
        with patch.object(os,'open',side_effect=opening),patch.object(os,'close',side_effect=closing),patch.object(os,'scandir',side_effect=PermissionError('Synthetic scan failure')),self.assertRaisesRegex(WorkflowError,'LOCAL_STATE_UNSAFE'):
            state.guard_project_scope(self.root)
        self.assertCountEqual(opened,closed)


if __name__=='__main__':unittest.main()
