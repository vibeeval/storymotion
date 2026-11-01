from pack_fixture_case import PackFixtureCase
"""Offline ingress/guard contracts. Sharp execution is mocked in this suite."""
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from storymotion.raster_io import MAX_BYTES, ROOT, normalize_raster, validate_normalized
from storymotion.security import WorkflowError


def chunk(kind, payload=b''):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)


def png(width=64, height=64, extra=b'', pixels=None):
    raw = pixels if pixels is not None else (b'\0' + bytes([220, 205, 180, 255]) * width) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
            extra + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND'))


def jpeg(width=64, height=64, extra=b''):
    # Structurally bounded header fixture only. Unit tests never claim it decodes.
    def segment(marker, payload):
        return b'\xff' + bytes([marker]) + struct.pack('>H', len(payload) + 2) + payload
    return (b'\xff\xd8' + extra + segment(0xc0, struct.pack('>BHHB', 8, height, width, 3) + b'\x01\x11\0\x02\x11\0\x03\x11\0') +
            segment(0xda, b'\x03\x01\0\x02\0\x03\0\0\x3f\0') + b'\x01\x02\xff\0\x03\xff\xd0\x04\xff\xd9')


class RasterIOTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.raster-unit-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.output = png()

    def fake_decode(self, argv, cwd=None, timeout=None):
        self.assertEqual(argv[:3], ['node', ROOT / 'tools/raster.mjs', 'normalize'])
        self.assertEqual(cwd, ROOT)
        self.assertEqual(timeout, 30)
        self.assertTrue(Path(argv[-2]).is_file())
        Path(argv[-1]).write_bytes(self.output)
        return json.dumps({'width': 64, 'height': 64, 'format': 'png'}).encode()

    def rejected_before_tool(self, data, container='png'):
        with patch('storymotion.engine.checked_process') as run:
            with self.assertRaises(WorkflowError):
                normalize_raster(data, container, self.directory)
            run.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_png_normalizes_and_preserves_separate_source_hash(self):
        original = png(extra=chunk(b'tEXt', b'Comment\0Neutral fixture metadata'))
        with patch('storymotion.engine.checked_process', side_effect=self.fake_decode) as run:
            result = normalize_raster(original, 'png', self.directory)
        self.assertEqual(set(result), {'file', 'sha256', 'source_sha256', 'width', 'height'})
        self.assertEqual(result['file'], self.directory / 'normalized.png')
        self.assertEqual(result['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(result['sha256'], hashlib.sha256(self.output).hexdigest())
        self.assertNotEqual(result['source_sha256'], result['sha256'])
        self.assertNotIn(b'Neutral fixture metadata', result['file'].read_bytes())
        self.assertEqual([p.name for p in self.directory.iterdir()], ['normalized.png'])
        run.assert_called_once()

    def test_jpeg_routes_only_to_fixed_jpeg_input(self):
        with patch('storymotion.engine.checked_process', side_effect=self.fake_decode) as run:
            result = normalize_raster(jpeg(), 'jpeg', self.directory)
        self.assertEqual(run.call_args.args[0][-2].name, 'selected.jpeg')
        self.assertEqual(result['width'], 64)

    def test_svg_and_html_rejected(self):
        for value in [b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'<!doctype html><script>alert(1)</script>']:
            with self.subTest(value=value[:10]):
                self.rejected_before_tool(value)

    def test_container_mismatches_and_unknown_types_rejected(self):
        for data, container in [(png(), 'jpeg'), (jpeg(), 'png'), (png(), 'jpg'), (png(), 'PNG'), (png(), 'webp')]:
            with self.subTest(container=container):
                self.rejected_before_tool(data, container)

    def test_empty_nonbytes_and_oversized_input_rejected(self):
        for data in [b'', bytearray(png()), 'not bytes', b'\x89PNG\r\n\x1a\n' + b'x' * MAX_BYTES]:
            with self.subTest(kind=type(data).__name__):
                self.rejected_before_tool(data)

    def test_png_crc_and_truncation_rejected(self):
        data = png()
        for malformed in [data[:-1], data[:-12], data[:30], data[:41] + bytes([data[41] ^ 1]) + data[42:]]:
            with self.subTest(length=len(malformed)):
                self.rejected_before_tool(malformed)

    def test_png_trailing_and_concatenated_containers_rejected(self):
        for tail in [b'\0', b'<html/>', png(), jpeg()]:
            self.rejected_before_tool(png() + tail)

    def test_png_invalid_truncated_and_trailing_deflate_rejected_before_decode(self):
        compressed = zlib.compress((b'\0' + bytes([220, 205, 180, 255]) * 64) * 64)
        for replacement in [b'bad zlib', compressed[:-2], compressed + b'junk', compressed + compressed]:
            self.rejected_before_tool(png().replace(chunk(b'IDAT', compressed), chunk(b'IDAT', replacement)))

    def test_png_dimensions_enforced_before_decode(self):
        for width, height in [(0, 64), (63, 64), (64, 63), (4097, 64), (4096, 4096), (0xffffffff, 64)]:
            header = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            self.rejected_before_tool(header)

    def test_apng_chunks_rejected(self):
        for kind in [b'acTL', b'fcTL', b'fdAT']:
            self.rejected_before_tool(png(extra=chunk(kind, b'\0' * 8)))

    def test_duplicate_header_unknown_critical_and_chunk_after_idat_rejected(self):
        ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 64, 64, 8, 6, 0, 0, 0))
        for extra in [ihdr, chunk(b'ABCD', b'anything')]:
            self.rejected_before_tool(png(extra=extra))
        data = png()[:-12] + chunk(b'tEXt', b'A\0B') + chunk(b'IDAT', b'x') + chunk(b'IEND')
        self.rejected_before_tool(data)

    def test_jpeg_trailing_truncation_and_multiple_frames_rejected(self):
        data = jpeg()
        for malformed in [data[:-1], data + b'\0', data + jpeg(), data[:15], b'\xff\xd8\xff\xd9']:
            self.rejected_before_tool(malformed, 'jpeg')

    def test_jpeg_mpo_and_unsupported_frame_rejected(self):
        mpf = b'\xff\xe2\0\x06MPF\0'
        self.rejected_before_tool(jpeg(extra=mpf), 'jpeg')
        self.rejected_before_tool(jpeg().replace(b'\xff\xc0', b'\xff\xc3', 1), 'jpeg')

    def test_jpeg_dimensions_and_bad_segment_lengths_rejected(self):
        self.rejected_before_tool(jpeg(4096, 4096), 'jpeg')
        self.rejected_before_tool(jpeg(63, 64), 'jpeg')
        self.rejected_before_tool(jpeg().replace(b'\xff\xc0\0\x11', b'\xff\xc0\xff\xff'), 'jpeg')

    def test_existing_output_or_source_not_overwritten(self):
        for name in ['normalized.png', 'selected.png']:
            target = self.directory / name
            target.write_bytes(b'keep')
            with patch('storymotion.engine.checked_process') as run, self.assertRaises(WorkflowError):
                normalize_raster(png(), 'png', self.directory)
            run.assert_not_called()
            self.assertEqual(target.read_bytes(), b'keep')
            target.unlink()

    def test_symlinked_directory_or_output_rejected(self):
        actual = self.directory / 'actual'
        actual.mkdir()
        link = self.directory / 'alias'
        link.symlink_to(actual, target_is_directory=True)
        with patch('storymotion.engine.checked_process') as run, self.assertRaises(WorkflowError):
            normalize_raster(png(), 'png', link)
        run.assert_not_called()
        target = actual / 'keep.png'
        target.write_bytes(png())
        (self.directory / 'normalized.png').symlink_to(target)
        with patch('storymotion.engine.checked_process') as run, self.assertRaises(WorkflowError):
            normalize_raster(png(), 'png', self.directory)
        run.assert_not_called()
        self.assertTrue(target.exists())

    def test_decode_failure_cleans_owned_files_and_hides_diagnostics(self):
        with patch('storymotion.engine.checked_process', side_effect=WorkflowError('private path /customer/secret; raw image')):
            with self.assertRaises(WorkflowError) as caught:
                normalize_raster(png(), 'png', self.directory)
        self.assertNotIn('/customer', str(caught.exception))
        self.assertNotIn('raw image', str(caught.exception))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_bad_tool_result_cleans_partial_output(self):
        for result in [b'not json', b'{}', b'x' * 1025, b'{"width":true,"height":64,"format":"png"}']:
            def invalid(argv, **kwargs):
                Path(argv[-1]).write_bytes(self.output)
                return result
            with patch('storymotion.engine.checked_process', side_effect=invalid), self.assertRaises(WorkflowError):
                normalize_raster(png(), 'png', self.directory)
            self.assertEqual(list(self.directory.iterdir()), [])

    def test_output_dimensions_and_metadata_are_not_trusted(self):
        for bad in [png(65, 64), png(extra=chunk(b'tEXt', b'private\0metadata')), b'not png']:
            self.output = bad
            with patch('storymotion.engine.checked_process', side_effect=self.fake_decode), self.assertRaises(WorkflowError):
                normalize_raster(png(), 'png', self.directory)
            self.assertEqual(list(self.directory.iterdir()), [])

    def test_output_symlink_is_rejected_without_reading_target(self):
        target = self.directory / 'keep.png'
        target.write_bytes(png())
        def invalid(argv, **kwargs):
            Path(argv[-1]).symlink_to(target)
            return b'{"width":64,"height":64,"format":"png"}'
        with patch('storymotion.engine.checked_process', side_effect=invalid), self.assertRaises(WorkflowError):
            normalize_raster(png(), 'png', self.directory)
        self.assertEqual(target.read_bytes(), png())
        self.assertFalse((self.directory / 'normalized.png').exists())

    def normalized_file(self, data=None):
        target = self.directory / 'normalized.png'
        target.write_bytes(png() if data is None else data)
        return target, hashlib.sha256(target.read_bytes()).hexdigest()

    def test_validate_normalized_binds_full_pixels_and_metadata(self):
        target, sha = self.normalized_file()
        self.assertEqual(validate_normalized(target, sha, 64, 64), {'sha256': sha, 'width': 64, 'height': 64})
        for wrong_sha, width, height in [('0' * 64, 64, 64), (sha, 65, 64), (sha.upper(), 64, 64), (sha, True, 64)]:
            with self.assertRaises(WorkflowError):
                validate_normalized(target, wrong_sha, width, height)

    def test_validate_normalized_rejects_bad_deflate_even_with_recomputed_hash(self):
        for raw in [b'', b'\0' * 64, (b'\x05' + b'\0' * 256) * 64, (b'\0' + b'\0' * 256) * 65]:
            target, sha = self.normalized_file(png(pixels=raw))
            with self.assertRaises(WorkflowError):
                validate_normalized(target, sha, 64, 64)
        data = png().replace(chunk(b'IDAT', zlib.compress((b'\0' + bytes([220, 205, 180, 255]) * 64) * 64)), chunk(b'IDAT', b'bad zlib'))
        target, sha = self.normalized_file(data)
        with self.assertRaises(WorkflowError):
            validate_normalized(target, sha, 64, 64)

    def test_validate_normalized_rejects_metadata_and_trailing_data(self):
        for data in [png(extra=chunk(b'tEXt', b'Author\0private')), png() + b'extra']:
            target, sha = self.normalized_file(data)
            with self.assertRaises(WorkflowError):
                validate_normalized(target, sha, 64, 64)

    def test_validate_normalized_rejects_symlink_file_and_ancestor(self):
        target, sha = self.normalized_file()
        alias = self.directory / 'alias.png'
        alias.symlink_to(target)
        with self.assertRaises(WorkflowError):
            validate_normalized(alias, sha, 64, 64)
        folder = self.directory / 'alias'
        folder.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(WorkflowError):
            validate_normalized(folder / target.name, sha, 64, 64)

    def test_validate_normalized_rejects_directory_and_parent_traversal(self):
        target, sha = self.normalized_file()
        for path in [self.directory, self.directory / 'other' / '..' / target.name]:
            with self.assertRaises(WorkflowError):
                validate_normalized(path, sha, 64, 64)


if __name__ == '__main__':
    unittest.main()
