from pack_fixture_case import PackFixtureCase
"""Rig byte-integrity tests using original synthetic files, never media/render."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from storymotion import rig_assets
from storymotion.rig_assets import required_rig_assets, stage_rig_assets, verify_rig_assets
from storymotion.security import WorkflowError, canonical, digest


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class RigAssetTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-rig-assets-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'source'
        self.out = self.base / 'prepared'
        (self.root / 'renderers').mkdir(parents=True)
        self.out.mkdir()
        # Minimal original identity fixture, not a renderable/accepted rig.
        definition = {'schema_version': 1, 'rig_id': 'neutral-presenter-1',
                      'license': 'original_project_vectors',
                      'mouths': {key: {'label': 'Synthetic ' + key, 'shapes': []} for key in 'ABCDEFGHX'}}
        (self.root / 'renderers/neutral-rig.json').write_text(canonical(definition))
        (self.root / 'renderers/rig-motion.mjs').write_text('// Original synthetic integrity fixture; not executed.\n')
        self.specs = required_rig_assets(self.root)
        # Intentionally asset-layer metadata: the separate pure viseme suite
        # verifies its full contract. This test does not attest audio/phonetics.
        rig = {'rig_id': 'neutral-presenter-1', 'rig_sha256': self.specs[0]['sha256'],
               'source_audio_sha256': _sha(b'SYNTHETIC_NO_AUDIO'),
               'provenance': {'method': 'synthetic_test', 'human_phonetic': 'pending', 'human_visual': 'pending'}}
        self.payload = {'brief': {'rig': rig}, 'edit_plan': {'rig_assets': copy.deepcopy(self.specs), 'rig_sha256': digest(rig)}}
        self.patch_root = patch.object(rig_assets, 'ROOT', self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)

    def stage(self):
        files = stage_rig_assets(self.specs, self.out, self.root)
        self.write_json('rig.json', self.payload['brief']['rig'])
        return files

    def write_json(self, name, data):
        (self.out / name).write_text(canonical(data))

    def binding(self):
        return {'rig_sha256': digest(self.payload['brief']['rig']), 'rig_definition_sha256': self.specs[0]['sha256']}

    def deliver(self):
        self.stage()
        self.write_json('edit-plan.json', self.payload['edit_plan'])
        self.write_json('render-engine.json', {'engine': 'synthetic_no_render', **self.binding()})
        self.write_json('qa.json', {'technical': 'not_run', 'human_review': 'pending', **self.binding()})
        files = {str(path.relative_to(self.out)): _sha(path.read_bytes())
                 for path in self.out.rglob('*') if path.is_file() and path.name not in {'delivery.json', 'delivery.zip'}}
        self.write_json('delivery.json', {'status': 'synthetic_test_only', **self.binding(), 'files': files})
        self.archive()

    def archive(self, mutate=None):
        raw = {str(path.relative_to(self.out)): path.read_bytes() for path in self.out.rglob('*')
               if path.is_file() and path.name != 'delivery.zip'}
        if mutate:
            mutate(raw)
        with zipfile.ZipFile(self.out / 'delivery.zip', 'w') as archive:
            for name, data in raw.items():
                archive.writestr(name, data)

    def verify(self, delivery=False):
        return verify_rig_assets(self.payload, self.out, delivery=delivery)

    def assert_no_staging(self):
        self.assertEqual(list(self.out.iterdir()), [])

    def test_required_specs_have_fixed_paths_roles_rights_and_raw_source_hashes(self):
        expected = [('renderers/neutral-rig.json', 'assets/rig/definition.json', 'neutral_rig_definition', 'original_project_vectors'),
                    ('renderers/rig-motion.mjs', 'assets/rig/rig-motion.mjs', 'neutral_rig_motion', 'original_project_code')]
        for spec, values in zip(self.specs, expected):
            self.assertEqual(set(spec), {'path', 'staged_file', 'sha256', 'role', 'rights'})
            self.assertEqual(tuple(spec[key] for key in ('path', 'staged_file', 'role', 'rights')), values)
            self.assertEqual(spec['sha256'], _sha((self.root / spec['path']).read_bytes()))
        self.specs[0]['rights'] = 'changed test copy'
        self.assertEqual(required_rig_assets()[0]['rights'], 'original_project_vectors')

    def test_no_rig_and_empty_specs_are_noops_without_io(self):
        with patch.object(rig_assets, 'required_rig_assets', side_effect=AssertionError('No source read allowed')):
            self.assertIsNone(verify_rig_assets({'brief': {}}, self.base / 'absent', delivery=True))
            self.assertIsNone(verify_rig_assets({'brief': {'rig': None}}, self.base / 'absent'))
            self.assertEqual(stage_rig_assets([], self.base / 'absent', self.base / 'absent'), [])
            self.assertEqual(stage_rig_assets(None, self.base / 'absent'), [])

    def test_stage_copies_exact_bytes_and_prepare_repairs_only_safe_regular_files(self):
        self.assertEqual(self.stage(), [spec['staged_file'] for spec in self.specs])
        self.verify()
        for spec in self.specs:
            self.assertEqual((self.out / spec['staged_file']).read_bytes(), (self.root / spec['path']).read_bytes())
        (self.out / self.specs[1]['staged_file']).write_bytes(b'corrupt staging')
        with self.assertRaises(WorkflowError):
            self.verify()
        self.stage()
        self.verify()
        self.assertFalse(any(path.name.endswith('.tmp') for path in self.out.rglob('*')))

    def test_plan_spec_changes_and_duplicates_fail_before_any_staging(self):
        bad = [None, {}, [self.specs[0]], self.specs + [self.specs[1]], [self.specs[0], self.specs[0]], list(reversed(self.specs))]
        # None alone is the documented no-rig no-op.
        bad = bad[1:]
        for field, value in [('path', '../outside'), ('staged_file', '/tmp/elsewhere'),
                             ('staged_file', 'assets/rig/../escape'), ('sha256', 'a' * 64),
                             ('role', 'unverified'), ('rights', 'assumed')]:
            specs = copy.deepcopy(self.specs)
            specs[1][field] = value
            bad.append(specs)
        extra = copy.deepcopy(self.specs)
        extra[0]['url'] = 'not_allowed'
        bad.append(extra)
        for specs in bad:
            with self.subTest(specs=specs), self.assertRaises(WorkflowError):
                stage_rig_assets(specs, self.out, self.root)
            self.assert_no_staging()

    def test_changed_source_never_rebases_existing_plan_or_writes(self):
        for index in (0, 1):
            path = self.root / self.specs[index]['path']
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaises(WorkflowError):
                stage_rig_assets(self.specs, self.out, self.root)
            self.assert_no_staging()
            path.write_bytes(original)

    def test_source_change_between_pinning_and_copy_fails_before_writes(self):
        real_required = required_rig_assets
        path = self.root / self.specs[1]['path']
        def change_after_pinning(root):
            result = real_required(root)
            path.write_bytes(b'changed after pinning')
            return result
        with patch.object(rig_assets, 'required_rig_assets', side_effect=change_after_pinning):
            with self.assertRaises(WorkflowError):
                stage_rig_assets(self.specs, self.out, self.root)
        self.assert_no_staging()

    def test_source_files_must_be_present_regular_bounded_and_unlinked(self):
        for name in ('renderers/neutral-rig.json', 'renderers/rig-motion.mjs'):
            path = self.root / name
            original = path.read_bytes()
            for kind in ('missing', 'directory', 'empty', 'oversize', 'symlink', 'hardlink'):
                with self.subTest(name=name, kind=kind):
                    path.unlink()
                    other = self.base / 'outside-source-fixture'
                    other.write_bytes(original)
                    if kind == 'directory': path.mkdir()
                    elif kind == 'empty': path.write_bytes(b'')
                    elif kind == 'oversize': path.write_bytes(b'x' * (rig_assets.MAX_MOTION + 1))
                    elif kind == 'symlink': path.symlink_to(other)
                    elif kind == 'hardlink': os.link(other, path)
                    with self.assertRaises(WorkflowError): required_rig_assets(self.root)
                    self.assertEqual(other.read_bytes(), original)
                    if path.is_dir() and not path.is_symlink(): path.rmdir()
                    elif path.exists() or path.is_symlink(): path.unlink()
                    other.unlink()
                    path.write_bytes(original)

    def test_source_root_or_ancestor_symlink_is_refused(self):
        alias = self.base / 'source-alias'
        alias.symlink_to(self.root, target_is_directory=True)
        for root in (alias, alias / 'renderers/..'):
            with self.assertRaises(WorkflowError): required_rig_assets(root)
        real = self.base / 'real'
        real.mkdir()
        alias = self.base / 'ancestor-alias'
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(WorkflowError): required_rig_assets(alias / 'nested')

    def test_unsafe_staging_file_or_ancestor_does_not_write_outside(self):
        outside = self.base / 'outside-owned-fixture'
        outside.write_bytes(b'original sentinel')
        for kind in ('file-symlink', 'file-hardlink', 'file-directory', 'ancestor-symlink', 'root-symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.base) as tmp:
                out = Path(tmp)
                (out / 'assets/rig').mkdir(parents=True)
                target = out / self.specs[1]['staged_file']
                if kind == 'file-symlink': target.symlink_to(outside)
                elif kind == 'file-hardlink': os.link(outside, target)
                elif kind == 'file-directory': target.mkdir()
                elif kind == 'ancestor-symlink':
                    (out / 'assets/rig').rmdir()
                    (out / 'assets/rig').symlink_to(self.base, target_is_directory=True)
                else:
                    alias = self.base / 'staging-alias'
                    alias.symlink_to(out, target_is_directory=True)
                    out = alias
                with self.assertRaises(WorkflowError): stage_rig_assets(self.specs, out, self.root)
                self.assertEqual(outside.read_bytes(), b'original sentinel')
                self.assertFalse((Path(tmp) / self.specs[0]['staged_file']).exists())
                self.assertFalse((self.base / 'definition.json').exists())
                if kind == 'root-symlink': out.unlink()

    def test_staging_post_copy_corruption_rejects_pinned_hash(self):
        original = rig_assets._write_atomic
        def corrupt(root, relative, raw):
            original(root, relative, raw)
            (Path(root) / relative).write_bytes(b'corrupt copied bytes')
        with patch.object(rig_assets, '_write_atomic', side_effect=corrupt):
            with self.assertRaisesRegex(WorkflowError, 'pinned source hash'):
                stage_rig_assets(self.specs, self.out, self.root)

    def test_verifier_rejects_changed_source_even_when_old_staged_bytes_remain(self):
        self.stage()
        path = self.root / self.specs[1]['path']
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(WorkflowError): self.verify()

    def test_staged_hash_and_manifest_spec_cannot_be_rebased_to_corrupted_copy(self):
        self.stage()
        path = self.out / self.specs[1]['staged_file']
        path.write_bytes(b'rebased corrupt copy')
        self.payload['edit_plan']['rig_assets'][1]['sha256'] = _sha(path.read_bytes())
        with self.assertRaises(WorkflowError): self.verify()

    def test_staged_assets_rig_manifest_and_plan_binding_reject_tampering(self):
        self.stage()
        baseline = copy.deepcopy(self.payload)
        for target in ('rig_sha', 'definition_sha', 'rig_id', 'spec_bytes', 'duplicate_json', 'missing_rig', 'empty_rig', 'asset_hash'):
            with self.subTest(target=target):
                self.payload = copy.deepcopy(baseline)
                self.write_json('rig.json', self.payload['brief']['rig'])
                if target == 'rig_sha': self.payload['edit_plan']['rig_sha256'] = 'a' * 64
                elif target == 'definition_sha': self.payload['brief']['rig']['rig_sha256'] = 'a' * 64
                elif target == 'rig_id': self.payload['brief']['rig']['rig_id'] = 'other-rig'
                elif target == 'spec_bytes': self.write_json('rig.json', {**self.payload['brief']['rig'], 'changed': True})
                elif target == 'duplicate_json': (self.out / 'rig.json').write_text('{"rig_id":"x","rig_id":"y"}')
                elif target == 'missing_rig': (self.out / 'rig.json').unlink()
                elif target == 'empty_rig': self.payload['brief']['rig'] = {}
                else: self.payload['edit_plan']['rig_assets'][0]['sha256'] = 'a' * 64
                with self.assertRaises(WorkflowError): self.verify()

    def test_staged_file_links_special_files_and_ancestor_links_are_refused(self):
        self.stage()
        path = self.out / self.specs[0]['staged_file']
        original = path.read_bytes()
        outside = self.base / 'same-definition'
        outside.write_bytes(original)
        for kind in ('symlink', 'hardlink', 'directory', 'fifo'):
            with self.subTest(kind=kind):
                path.unlink()
                if kind == 'symlink': path.symlink_to(outside)
                elif kind == 'hardlink': os.link(outside, path)
                elif kind == 'directory': path.mkdir()
                else: os.mkfifo(path)
                with self.assertRaises(WorkflowError): self.verify()
                if kind == 'directory': path.rmdir()
                else: path.unlink()
                path.write_bytes(original)
        (self.out / 'assets').rename(self.out / 'real-assets')
        (self.out / 'assets').symlink_to(self.out / 'real-assets', target_is_directory=True)
        with self.assertRaises(WorkflowError): self.verify()

    def test_existing_receipt_qa_and_plan_are_bound_but_not_required_during_prepare(self):
        self.stage()
        self.verify()
        for name in ('render-engine.json', 'qa.json'):
            for field in ('rig_sha256', 'rig_definition_sha256'):
                record = self.binding()
                record[field] = 'a' * 64
                self.write_json(name, record)
                with self.assertRaises(WorkflowError): self.verify()
                (self.out / name).unlink()
            self.write_json(name, self.binding())
            self.verify()
        self.write_json('edit-plan.json', self.payload['edit_plan'])
        self.verify()
        self.write_json('edit-plan.json', {**self.payload['edit_plan'], 'changed': True})
        with self.assertRaises(WorkflowError): self.verify()

    def test_complete_synthetic_delivery_passes_without_claiming_media_or_human_qa(self):
        for _ in range(3):
            self.deliver()
            self.verify(delivery=True)
        self.assertEqual(json.loads((self.out / 'qa.json').read_text())['technical'], 'not_run')
        self.assertEqual(self.payload['brief']['rig']['provenance']['human_phonetic'], 'pending')

    def test_malformed_host_payload_fails_closed(self):
        for value in (None, [], {}, {'brief': None}, {'brief': []},
                      {'brief': {'rig': True}}, {'brief': {'rig': {}}},
                      {'brief': self.payload['brief'], 'edit_plan': []}):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                verify_rig_assets(value, self.out)

    def test_delivery_requires_all_bound_records_and_pinned_members(self):
        for name in ('rig.json', 'edit-plan.json', 'render-engine.json', 'qa.json', 'delivery.json', 'delivery.zip'):
            with self.subTest(name=name):
                self.deliver()
                (self.out / name).unlink()
                with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_delivery_receipt_qa_manifest_fields_and_member_hashes_fail_closed(self):
        for name in ('render-engine.json', 'qa.json', 'delivery.json'):
            for field in ('rig_sha256', 'rig_definition_sha256'):
                with self.subTest(name=name, field=field):
                    self.deliver()
                    value = json.loads((self.out / name).read_text())
                    value.pop(field)
                    self.write_json(name, value)
                    self.archive()
                    with self.assertRaises(WorkflowError): self.verify(delivery=True)
        self.deliver()
        value = json.loads((self.out / 'delivery.json').read_text())
        value['files'][self.specs[1]['staged_file']] = 'a' * 64
        self.write_json('delivery.json', value)
        self.archive()
        with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_zip_changed_missing_extra_or_renamed_members_are_rejected(self):
        rel = self.specs[1]['staged_file']
        for kind in ('changed', 'missing', 'extra', 'traversal', 'absolute', 'backslash'):
            with self.subTest(kind=kind):
                self.deliver()
                def mutate(raw):
                    if kind == 'changed': raw[rel] = b'x' * len(raw[rel])
                    elif kind == 'missing': raw.pop(rel)
                    elif kind == 'extra': raw['unexpected.txt'] = b'extra'
                    elif kind == 'traversal': raw['../definition.json'] = raw.pop(rel)
                    elif kind == 'absolute': raw['/definition.json'] = raw.pop(rel)
                    else: raw['assets\\rig\\rig-motion.mjs'] = raw.pop(rel)
                self.archive(mutate)
                with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_zip_duplicate_symlink_and_special_member_entries_are_rejected(self):
        for relative in (self.specs[0]['staged_file'], 'rig.json', 'qa.json', 'delivery.json'):
            for kind in ('duplicate', 'symlink', 'fifo', 'directory'):
                with self.subTest(relative=relative, kind=kind):
                    self.deliver()
                    path = self.out / 'delivery.zip'
                    with zipfile.ZipFile(path) as archive:
                        raw = {info.filename: archive.read(info) for info in archive.infolist()}
                    with warnings.catch_warnings(), zipfile.ZipFile(path, 'w') as archive:
                        warnings.simplefilter('ignore', UserWarning)
                        for name, data in raw.items():
                            if name != relative or kind == 'duplicate': archive.writestr(name, data)
                        info = zipfile.ZipInfo(relative)
                        info.create_system = 3
                        if kind == 'symlink': info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        elif kind == 'fifo': info.external_attr = (stat.S_IFIFO | 0o600) << 16
                        elif kind == 'directory': info.external_attr = (stat.S_IFDIR | 0o700) << 16
                        archive.writestr(info, raw[relative])
                    with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_zip_bytes_of_spec_plan_and_receipts_must_match_staged_bytes(self):
        for name in ('rig.json', 'edit-plan.json', 'render-engine.json', 'qa.json', 'delivery.json'):
            with self.subTest(name=name):
                self.deliver()
                self.archive(lambda raw: raw.update({name: raw[name] + b' '}))
                with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_delivery_files_map_and_duplicate_json_are_rejected(self):
        for kind in ('omit-required', 'bad-hash', 'include-manifest', 'unsafe-path', 'duplicate-json'):
            with self.subTest(kind=kind):
                self.deliver()
                value = json.loads((self.out / 'delivery.json').read_text())
                if kind == 'omit-required': value['files'].pop('rig.json')
                elif kind == 'bad-hash': value['files']['rig.json'] = True
                elif kind == 'include-manifest': value['files']['delivery.json'] = 'a' * 64
                elif kind == 'unsafe-path': value['files']['../bad'] = 'a' * 64
                else:
                    raw = canonical(value)
                    (self.out / 'delivery.json').write_text('{"files":{},' + raw[1:])
                if kind != 'duplicate-json': self.write_json('delivery.json', value)
                self.archive()
                with self.assertRaises(WorkflowError): self.verify(delivery=True)

    def test_filesystem_manifest_or_archive_symlink_and_hardlink_are_refused(self):
        for name in ('rig.json', 'render-engine.json', 'qa.json', 'edit-plan.json', 'delivery.json', 'delivery.zip'):
            for kind in ('symlink', 'hardlink'):
                with self.subTest(name=name, kind=kind):
                    self.deliver()
                    path = self.out / name
                    outside = self.base / 'owned-outside-copy'
                    outside.write_bytes(path.read_bytes())
                    original = outside.read_bytes()
                    path.unlink()
                    if kind == 'symlink': path.symlink_to(outside)
                    else: os.link(outside, path)
                    with self.assertRaises(WorkflowError): self.verify(delivery=True)
                    self.assertEqual(outside.read_bytes(), original)
                    path.unlink()
                    outside.unlink()

    def test_invalid_json_zip_and_io_failures_do_not_expose_paths(self):
        self.deliver()
        for name, raw in [('rig.json', b'not json'), ('qa.json', b'{"rig_sha256":NaN}'), ('delivery.zip', b'not a zip')]:
            original = (self.out / name).read_bytes()
            (self.out / name).write_bytes(raw)
            with self.assertRaises(WorkflowError) as caught: self.verify(delivery=True)
            self.assertNotIn(str(self.base), str(caught.exception))
            (self.out / name).write_bytes(original)


if __name__ == '__main__':
    unittest.main()
