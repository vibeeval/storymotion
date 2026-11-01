"""Unsafe ZIPs fail before a destination is created; no network/install calls."""
import io
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from storymotion.archive_safety import safe_extract_zip
from storymotion.security import WorkflowError


class ArchiveSafetyTests(unittest.TestCase):
    def archive(self,root,rows):
        path=root/'source.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(path,'w') as archive:
                for name,data in rows:archive.writestr(name,data)
        return path

    def test_all_members_checked_before_any_write_for_traversal_links_collisions_and_limits(self):
        link=zipfile.ZipInfo('project/link');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
        cases=[ [('safe.txt',b'valid'),('../escape.txt',b'bad')], [('/absolute',b'bad')],
                [('C:/escape',b'bad')], [('project\\escape',b'bad')], [('project//file',b'bad')],
                [('project/./file',b'bad')], [('same.txt',b'a'),('same.txt',b'b')],
                [('Project/a',b'a'),('project/b',b'b')], [('project/node',b'a'),('project/node/child',b'b')],
                [('project/FILE',b'a'),('project/file',b'b')], [(link,b'../../outside')]]
        for rows in cases:
            with self.subTest(rows=str(rows)[:60]),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();archive=self.archive(root,rows);destination=root/'nested/new'
                with self.assertRaises(WorkflowError):safe_extract_zip(archive,destination,scope=root)
                self.assertFalse(destination.parent.exists())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();archive=self.archive(root,[('large',b'12345')]);destination=root/'new'
            with patch('storymotion.archive_safety.MAX_TOTAL_BYTES',4),self.assertRaises(WorkflowError):safe_extract_zip(archive,destination,scope=root)
            self.assertFalse(destination.exists())

    def test_existing_work_and_linked_target_ancestors_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp,tempfile.TemporaryDirectory() as outside:
            root=Path(temp).resolve();archive=self.archive(root,[('project/LICENSE',b'license')])
            target=root/'existing';target.mkdir();(target/'customer.txt').write_text('keep')
            with self.assertRaisesRegex(WorkflowError,'TARGET_EXISTS'):safe_extract_zip(archive,target,scope=root)
            self.assertEqual((target/'customer.txt').read_text(),'keep')
            (root/'linked').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(WorkflowError):safe_extract_zip(archive,root/'linked/new',scope=root)
            self.assertFalse((Path(outside)/'new').exists())
            with self.assertRaises(WorkflowError):safe_extract_zip(archive,Path(outside)/'new',scope=root)

    def test_license_and_binary_bytes_survive_without_extractall(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();rows=[('project/LICENSE',b'Owner terms\n'),('project/vendor/LICENSE.txt',b'Third-party terms\n'),('project/font.woff2',b'\0\1binary\xff')]
            archive=self.archive(root,rows);target=root/'clean'
            with patch.object(zipfile.ZipFile,'extractall',side_effect=AssertionError('Unsafe bulk extraction forbidden')):
                self.assertEqual(safe_extract_zip(archive,target,scope=root),target)
            for name,data in rows:self.assertEqual((target/name).read_bytes(),data)
