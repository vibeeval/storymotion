"""Original deterministic PCM test-fixture generator; no voice or input media.

Recipe version 1, authored 2026-10-29. Reproducing an old hash does not claim
this was its historical generator. Writes only below this script directory.
"""
from pathlib import Path
import hashlib
import json
import wave

ROOT = Path(__file__).resolve().parent
RECIPE_VERSION = 1


def silence(path, rate, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = rate * seconds
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b'\0\0' * frames)
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), sample_rate=rate, channels=1,
                sample_width_bytes=2, frames=frames, duration_seconds=seconds,
                all_pcm_samples_zero=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    rows = [silence(ROOT/'output/fixtures/audio-retime/synthetic-20s.wav',8000,20),
            silence(ROOT/'intermediate/silence-4s-44100.wav',44100,4)]
    for row in rows:
        print(json.dumps(row))
    (ROOT/'WAV-GENERATION.json').write_text(json.dumps(dict(recipe_version=RECIPE_VERSION,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_input_media_used=False, fixtures=rows),indent=2)+'\n')


if __name__=='__main__':
    main()
