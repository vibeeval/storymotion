from pack_fixture_case import PackFixtureCase
"""Pure synthetic annotations only; no audio bytes, acoustic or human QA claim."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from storymotion.audio_retime import script_sha
from storymotion.security import WorkflowError, canonical, digest
from storymotion.viseme import MAX_SPEC_BYTES, MOUTH_VALUES, RIG_ID, rig_descriptor, validate_rig


def descriptor_fixture():
    # Synthetic minimal descriptor identity, not a renderable licensed rig.
    return {'schema_version': 1, 'rig_id': RIG_ID, 'license': 'original_project_vectors',
            'mouths': {value: {'label': 'Synthetic ' + value, 'shapes': []} for value in sorted(MOUTH_VALUES)}}


def brief_fixture(account='sample-flow'):
    script = 'Özgün ses zamanlama provası.'
    audio_sha = hashlib.sha256(b'SYNTHETIC_IDENTITY_ONLY_NOT_AUDIO').hexdigest()
    timing = {'source_audio_sha256': audio_sha, 'source_script_sha256': script_sha(script),
              'audio_duration_seconds': 2.51, 'timeline_duration_seconds': 76 / 30,
              'words': [{'text': 'Özgün', 'start': .1, 'end': .6}], 'provenance': 'synthetic_test; not acoustic timing'}
    return {'brand': account, 'script': script, 'audio': {'sha256': audio_sha},
            'duration': 76 / 30, 'audio_timing': timing}


def rig_fixture(root, brief=None):
    brief = brief or brief_fixture()
    timing = brief['audio_timing']
    return {'schema_version': 1, 'account': brief['brand'], 'rig_id': RIG_ID, 'rig_sha256': rig_descriptor(root)['sha256'],
            'source_audio_sha256': brief['audio']['sha256'], 'source_script_sha256': script_sha(brief['script']),
            'source_timing_sha256': digest(timing), 'audio_duration_seconds': timing['audio_duration_seconds'],
            'timeline_duration_seconds': brief['duration'], 'fps': 30,
            'provenance': {'method': 'synthetic_test', 'tool': 'Original unit fixture', 'note': 'Invented manual intervals; no phonetic or visual acceptance',
                           'approved_by': 'Synthetic contract operator', 'rights_confirmed': True, 'human_phonetic': 'pending', 'human_visual': 'pending'},
            'mouthCues': [{'start': 0, 'end': .8, 'value': 'A'}, {'start': .8, 'end': 1.1, 'value': 'X'},
                          {'start': 1.1, 'end': timing['audio_duration_seconds'], 'value': 'E'}],
            'visual_tracks': {'blinks': [{'start': .2, 'end': .24}, {'start': 1, 'end': 1.4}],
                              'head': [{'time': 0, 'rotate': 0, 'x': 0, 'y': 0},
                                       {'time': 1, 'rotate': 2, 'x': 4, 'y': -2},
                                       {'time': brief['duration'], 'rotate': 0, 'x': 0, 'y': 0}]}}


class VisemeTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neutral-viseme-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'renderers').mkdir()
        self.file = self.root / 'renderers/neutral-rig.json'
        self.file.write_text(canonical(descriptor_fixture()))
        self.brief = brief_fixture()
        self.value = rig_fixture(self.root, self.brief)

    def validate(self, value=None, brief=None):
        return validate_rig(self.value if value is None else value, self.brief if brief is None else brief, self.root)

    def reject(self, mutate, brief=False):
        value = copy.deepcopy(self.brief if brief else self.value)
        mutate(value)
        with self.assertRaises(WorkflowError):
            self.validate(brief=value) if brief else self.validate(value)

    def test_valid_manual_cues_are_detached_and_never_self_certify_human_acceptance(self):
        before = copy.deepcopy(self.value)
        result = self.validate()
        self.assertEqual(result, before)
        self.assertEqual(self.value, before)
        result['mouthCues'][0]['value'] = 'H'
        result['visual_tracks']['head'][0]['x'] = 3
        self.assertEqual(self.value, before)
        self.assertEqual(result['provenance']['human_phonetic'], 'pending')
        self.assertEqual(result['provenance']['human_visual'], 'pending')

    def test_explicit_supported_profiles_and_provenance_methods_only(self):
        for account in ('sample-flow', 'sample-series'):
            brief = brief_fixture(account)
            for method in ('manual_annotation', 'external_phoneme_export', 'synthetic_test'):
                value = rig_fixture(self.root, brief)
                value['provenance']['method'] = method
                self.assertEqual(self.validate(value, brief)['account'], account)
        for account in ('sample-mechanism', 'sample-reflection', 'unregistered-presenter', '', None, [], {}):
            with self.subTest(account=account):
                brief = brief_fixture(account)
                value = rig_fixture(self.root, brief)
                with self.assertRaises(WorkflowError):self.validate(value, brief)
        self.reject(lambda v: v.update(account='sample-series'))
        self.reject(lambda v: v['provenance'].update(method='amplitude_guess'))

    def test_custom_pack_capability_and_matching_account_are_both_required(self):
        from storymotion import account_packs
        pack = account_packs.load_pack('sample-flow')
        pack.update(id='buyer-presenter', display_name='Buyer presenter')
        pack['profile']['id'] = pack['id']; pack['fixture']['brand'] = pack['id']
        folder = self.root / 'work/accountpacks'; folder.mkdir(parents=True)
        path = folder / 'buyer-presenter.json'; path.write_text(json.dumps(pack))
        with patch.object(account_packs, 'ROOT', self.root):
            brief = brief_fixture('buyer-presenter'); value = rig_fixture(self.root, brief)
            self.assertEqual(self.validate(value, brief)['account'], 'buyer-presenter')
            pack['capabilities']['rig_mode'] = None; path.write_text(json.dumps(pack))
            with self.assertRaises(WorkflowError):self.validate(value, brief)
            pack['capabilities']['rig_mode'] = 'inset'; path.write_text(json.dumps(pack))
            value['account'] = 'different-presenter'
            with self.assertRaises(WorkflowError):self.validate(value, brief)
            path.unlink(); value['account'] = 'buyer-presenter'
            with self.assertRaises(WorkflowError):self.validate(value, brief)

    def test_missing_and_extra_keys_fail_at_every_contract_level(self):
        paths = [(), ('provenance',), ('mouthCues', 0), ('visual_tracks',), ('visual_tracks', 'blinks', 0), ('visual_tracks', 'head', 0)]
        for path in paths:
            node = self.value
            for key in path:
                node = node[key]
            for field in node:
                def remove(value, path=path, field=field):
                    target = value
                    for part in path:
                        target = target[part]
                    del target[field]
                with self.subTest(path=path, field=field):
                    self.reject(remove)
            def add(value, path=path):
                target = value
                for part in path:
                    target = target[part]
                target['automatic_phonemes'] = True
            self.reject(add)

    def test_schema_and_fps_do_not_accept_bool_or_float_or_other_versions(self):
        for name, values in (('schema_version', [True, 1.0, '1', 2, None]), ('fps', [True, 30.0, '30', 24, 60, None])):
            for bad in values:
                with self.subTest(field=name, value=bad):
                    self.reject(lambda v: v.update({name: bad}))

    def test_all_source_hashes_are_exact_lowercase_and_match_current_audio_script_timing(self):
        for field in ('rig_sha256', 'source_audio_sha256', 'source_script_sha256', 'source_timing_sha256'):
            for bad in ('0' * 64, 'A' * 64, 'g' * 64, 'a' * 63, None, True, []):
                with self.subTest(field=field, kind=type(bad).__name__):
                    self.reject(lambda v: v.update({field: bad}))
        self.reject(lambda v: v.update(rig_id='private-rig'))
        self.reject(lambda b: b.update(script=b['script'] + ' Yeni söz.'), brief=True)
        self.reject(lambda b: b['audio'].update(sha256='f' * 64), brief=True)
        self.reject(lambda b: b['audio_timing']['words'][0].update(end=.7), brief=True)

    def test_new_audio_or_script_cannot_reuse_old_timing_even_with_updated_spec_hashes(self):
        for field in ('audio', 'script'):
            brief = copy.deepcopy(self.brief)
            value = copy.deepcopy(self.value)
            if field == 'audio':
                brief['audio']['sha256'] = 'f' * 64
                value['source_audio_sha256'] = 'f' * 64
            else:
                brief['script'] += ' Yeni söz.'
                value['source_script_sha256'] = script_sha(brief['script'])
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                self.validate(value, brief)

    def test_fresh_timing_requires_fresh_bound_annotation_hash(self):
        brief = copy.deepcopy(self.brief)
        brief['audio_timing']['words'][0]['start'] = .15
        with self.assertRaises(WorkflowError):
            self.validate(brief=brief)
        value = copy.deepcopy(self.value)
        value['source_timing_sha256'] = digest(brief['audio_timing'])
        self.assertEqual(self.validate(value, brief)['source_timing_sha256'], digest(brief['audio_timing']))

    def test_measured_audio_and_timeline_durations_must_match_exactly(self):
        for field in ('audio_duration_seconds', 'timeline_duration_seconds'):
            for bad in (0, .9, 91, True, '2.51', float('nan'), float('inf'), -float('inf'), 2.52):
                self.reject(lambda v: v.update({field: bad}))
        self.reject(lambda b: b.update(duration=3), brief=True)
        self.reject(lambda b: b['audio_timing'].update(audio_duration_seconds=2.52), brief=True)
        self.reject(lambda b: b.update(audio=None), brief=True)
        self.reject(lambda b: b.update(audio_timing=None), brief=True)

    def test_mouth_first_last_gap_overlap_empty_unsorted_and_out_of_audio_fail(self):
        mutations = [lambda v: v['mouthCues'][0].update(start=.001), lambda v: v['mouthCues'][-1].update(end=2.509),
                     lambda v: v['mouthCues'][-1].update(end=2.51 + 1e-12),
                     lambda v: v['mouthCues'][-1].update(end=3.01),
                     lambda v: v['mouthCues'][1].update(start=.8000000000000002),
                     lambda v: v['mouthCues'][1].update(start=.7999999999999998),
                     lambda v: v['mouthCues'][1].update(end=.8), lambda v: v['mouthCues'].reverse()]
        for mutate in mutations:
            self.reject(mutate)

    def test_mouth_intervals_have_no_frame_rounding_or_half_second_tolerance(self):
        value = copy.deepcopy(self.value)
        value['mouthCues'] = [{'start': 0, 'end': .00001, 'value': 'A'}, {'start': .00001, 'end': 2.51, 'value': 'X'}]
        self.assertEqual(self.validate(value)['mouthCues'][0]['end'], .00001)
        self.reject(lambda v: v['mouthCues'][-1].update(end=2.51 + 1 / 30))

    def test_explicit_pause_and_every_supported_shape_are_accepted_without_guessing(self):
        for value in sorted(MOUTH_VALUES):
            spec = copy.deepcopy(self.value)
            spec['mouthCues'] = [{'start': 0, 'end': 2.51, 'value': value}]
            self.assertEqual(self.validate(spec)['mouthCues'][0]['value'], value)
        for bad in ('I', 'REST', 'silence', '', 'a', None, True, [], {}):
            self.reject(lambda v: v['mouthCues'][0].update(value=bad))

    def test_mouth_counts_and_container_types_are_bounded(self):
        for bad in ([], None, {}, 'A'):
            self.reject(lambda v: v.update(mouthCues=bad))
        self.reject(lambda v: v.update(mouthCues=[{'start': 0, 'end': 2.51, 'value': 'X'}] * 2001))

    def test_maximum_cue_blink_and_head_counts_are_individually_usable_within_json_limit(self):
        brief = copy.deepcopy(self.brief)
        brief['duration'] = 80
        brief['audio_timing'].update(audio_duration_seconds=80, timeline_duration_seconds=80)
        value = rig_fixture(self.root, brief)
        value['mouthCues'] = [{'start': i / 25, 'end': (i + 1) / 25, 'value': 'X' if i % 2 else 'A'} for i in range(2000)]
        self.assertEqual(len(self.validate(value, brief)['mouthCues']), 2000)
        value['mouthCues'] = [{'start': 0, 'end': 80, 'value': 'X'}]
        value['visual_tracks']['blinks'] = [{'start': i, 'end': i + .04} for i in range(80)]
        self.assertEqual(len(self.validate(value, brief)['visual_tracks']['blinks']), 80)
        value['visual_tracks']['head'] = [{'time': i / 25, 'rotate': 0, 'x': 0, 'y': 0} for i in range(999)] + [
            {'time': 80, 'rotate': 0, 'x': 0, 'y': 0}]
        self.assertEqual(len(self.validate(value, brief)['visual_tracks']['head']), 1000)

    def test_nan_infinity_bool_strings_and_negative_times_fail_every_track(self):
        for bad in (float('nan'), float('inf'), -float('inf'), True, '0', -.001, None):
            for mutate in (lambda v: v['mouthCues'][0].update(start=bad),
                           lambda v: v['visual_tracks']['blinks'][0].update(start=bad),
                           lambda v: v['visual_tracks']['head'][0].update(time=bad)):
                self.reject(mutate)

    def test_blink_duration_decimal_edges_overlap_order_and_timeline_boundaries(self):
        # .24-.2 is below .04 in binary floating subtraction; decimal endpoints
        # nevertheless denote a supported exact forty-millisecond annotation.
        self.validate()
        for blinks in ([{'start': .2, 'end': .239999999999}], [{'start': .2, 'end': .600000000001}],
                       [{'start': .5, 'end': .6}, {'start': .55, 'end': .65}],
                       [{'start': .5, 'end': .6}, {'start': .2, 'end': .3}],
                       [{'start': self.brief['duration'] - .1, 'end': self.brief['duration'] + .001}],
                       [{'start': .2, 'end': .2}], None, {}, 'blink'):
            self.reject(lambda v: v['visual_tracks'].update(blinks=blinks))
        self.assertEqual(self.validate({**self.value, 'visual_tracks': {**self.value['visual_tracks'], 'blinks': []}})['visual_tracks']['blinks'], [])
        self.reject(lambda v: v['visual_tracks'].update(blinks=[{'start': .2, 'end': .24}] * 81))

    def test_head_first_last_strict_order_count_and_motion_limits(self):
        for mutate in (lambda v: v['visual_tracks']['head'][0].update(time=.001),
                       lambda v: v['visual_tracks']['head'][-1].update(time=2.51),
                       lambda v: v['visual_tracks']['head'][1].update(time=0),
                       lambda v: v['visual_tracks']['head'].reverse(),
                       lambda v: v['visual_tracks'].update(head=[]),
                       lambda v: v['visual_tracks'].update(head=[v['visual_tracks']['head'][0]]),
                       lambda v: v['visual_tracks'].update(head=[v['visual_tracks']['head'][0]] * 1001)):
            self.reject(mutate)
        for field, bound in (('rotate', 8), ('x', 12), ('y', 12)):
            for bad in (-bound - .001, bound + .001, True, float('inf'), '0'):
                self.reject(lambda v: v['visual_tracks']['head'][1].update({field: bad}))
            for accepted in (-bound, bound):
                value = copy.deepcopy(self.value)
                value['visual_tracks']['head'][1][field] = accepted
                self.assertEqual(self.validate(value)['visual_tracks']['head'][1][field], accepted)

    def test_human_pass_false_rights_or_unbounded_provenance_is_never_accepted(self):
        for field, values in (('rights_confirmed', [False, 1, 'true', None]),
                              ('human_phonetic', ['pass', True, None]), ('human_visual', ['pass', True, None]),
                              ('tool', ['', 'x' * 121, 'unsafe\nname']), ('note', ['', 'x' * 1001]),
                              ('approved_by', ['', ' ', 'x' * 201, 'invisible\u200bname'])):
            for bad in values:
                self.reject(lambda v: v['provenance'].update({field: bad}))

    def test_whole_canonical_utf8_size_is_limited_before_descriptor_io(self):
        huge = copy.deepcopy(self.value)
        huge['provenance']['note'] = 'ğ' * MAX_SPEC_BYTES
        with patch('storymotion.viseme.rig_descriptor', side_effect=AssertionError('No descriptor read')), self.assertRaises(WorkflowError):
            self.validate(huge)
        self.reject(lambda v: v['provenance'].update(note='api_key=sk-' + 'a' * 30))

    def test_descriptor_hash_is_raw_file_hash_and_cannot_select_another_asset(self):
        descriptor = rig_descriptor(self.root)
        self.assertEqual(descriptor['file'], 'renderers/neutral-rig.json')
        self.assertEqual(descriptor['sha256'], hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(descriptor['rig_id'], RIG_ID)
        self.file.write_text(canonical({**descriptor_fixture(), 'synthetic_revision': 2}))
        with self.assertRaises(WorkflowError):
            self.validate()
        self.value['rig_sha256'] = rig_descriptor(self.root)['sha256']
        self.validate()

    def test_descriptor_missing_bad_json_duplicate_wrong_identity_and_mouth_vocabulary_reject(self):
        for raw in ('not JSON', '{"schema_version":1,"schema_version":1}',
                    canonical({**descriptor_fixture(), 'rig_id': 'private-rig'}),
                    canonical({**descriptor_fixture(), 'license': 'unverified-third-party'}),
                    canonical({**descriptor_fixture(), 'mouths': {'A': {}}}), 'x' * 65_537):
            self.file.write_text(raw)
            with self.subTest(raw=raw[:20]), self.assertRaises(WorkflowError):
                rig_descriptor(self.root)
        self.file.unlink()
        with self.assertRaises(WorkflowError):
            rig_descriptor(self.root)

    def test_descriptor_file_parent_and_root_symlink_are_rejected_without_following(self):
        original = self.file.read_bytes()
        other = self.root / 'other.json'
        other.write_bytes(original)
        self.file.unlink()
        self.file.symlink_to(other)
        with self.assertRaises(WorkflowError):
            rig_descriptor(self.root)
        self.assertEqual(other.read_bytes(), original)
        self.file.unlink()
        self.file.write_bytes(original)
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(WorkflowError):
            rig_descriptor(alias)
        (self.root / 'renderers').rename(self.root / 'other-renderers')
        (self.root / 'renderers').symlink_to(self.root / 'other-renderers', target_is_directory=True)
        with self.assertRaises(WorkflowError):
            rig_descriptor(self.root)

    def test_descriptor_errors_do_not_expose_private_paths(self):
        self.file.unlink()
        with self.assertRaises(WorkflowError) as error:
            rig_descriptor(self.root)
        self.assertNotIn(str(self.root), str(error.exception))

    def test_current_bundled_descriptor_has_fixed_identity_and_raw_hash(self):
        root = Path(__file__).resolve().parents[1]
        result = rig_descriptor(root)
        self.assertEqual(result['rig_id'], RIG_ID)
        self.assertEqual(result['license'], 'original_project_vectors')
        self.assertEqual(result['sha256'], hashlib.sha256((root / result['file']).read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
