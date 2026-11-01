#!/usr/bin/env python3
"""New stdlib recipe for observed neutral geometry; no original bytes embedded.

This recipe is authored during the 2026-10-29 reconstruction. It is not a
historical creation record. It reads neither the production PNG nor any asset.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

WIDTH, HEIGHT = 800, 600
BACKGROUND = (244, 241, 232, 255)
GRID = (215, 214, 205, 255)
RED = (210, 55, 60, 255)
BLUE = (36, 95, 195, 255)
YELLOW = (242, 181, 28, 255)


def pixel(x, y):
    value = GRID if x % 100 < 2 or y % 100 < 2 else BACKGROUND
    if (x - 210) ** 2 + (y - 220) ** 2 < 80 ** 2:
        value = RED
    if 510 <= x < 670 and 140 <= y < 300:
        value = BLUE
    if 385 < y < 510 and 10 * abs(x - 430) < 7 * (y - 385):
        value = YELLOW
    return bytes(value)


def chunk(kind, data):
    return (struct.pack('>I', len(data)) + kind + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))


def generate():
    scanlines = b''.join(b'\x00' + b''.join(pixel(x, y) for x in range(WIDTH))
                         for y in range(HEIGHT))
    ihdr = struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 6, 0, 0, 0)
    compressed = zlib.compress(scanlines, 6)
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', compressed) + chunk(b'IEND', b''))
    return data, scanlines, compressed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('neutral-shapes.png'))
    args = parser.parse_args()
    data, scanlines, compressed = generate()
    with args.output.open('xb') as handle:
        handle.write(data)
    print(json.dumps({'output': str(args.output), 'width': WIDTH, 'height': HEIGHT,
                      'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'scanlines_sha256': hashlib.sha256(scanlines).hexdigest(),
                      'idat_bytes': len(compressed),
                      'zlib_compile_version': zlib.ZLIB_VERSION,
                      'zlib_runtime_version': zlib.ZLIB_RUNTIME_VERSION}, indent=2))


if __name__ == '__main__':
    main()
