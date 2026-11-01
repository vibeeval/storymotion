# Reproducing the technical fixtures

These recipes use neutral calculated geometry or zero PCM. They read no input image, recording, speaker or external media. A historical-byte match does not identify the historical creator. Current production evidence is in `../GENERATION.json`.

1. Run `python3 -B fixtures/recipes/generate_neutral_shapes.py --output /path/to/new/neutral-shapes.png` with a fresh output filename. The generator refuses to overwrite an existing output.
2. Run `python3 -B fixtures/recipes/generate_silence.py`. It writes the twenty-second mono 8kHz WAV below its own `output/` directory and the four-second mono 44.1kHz input WAV below `intermediate/`. Its generation record lists hashes and zero-sample details.
3. With an already installed LAME encoder, encode the four-second input WAV using `lame --silent --noreplaygain --cbr -b 128 --resample 44.1 -m m -q 2 INPUT.wav NEW-OUTPUT.mp3`. No encoder is installed or bundled by these recipes.
4. Validate WAV parameters and every PCM sample with stdlib `wave`; independently fully decode the MP3 and require 176400 zero mono samples at 44100Hz. Record UTC date, actual recipe/encoder hashes, encoder version/arguments, input PCM and output hashes. Replace candidate copies only after validation.

The current original fixtures are offered under the project MIT grant. The LAME/decoder runtime licenses remain separate; their executables are not distributed here. A silent technical fixture is not a natural-voice, creative, native or caller-media acceptance test.
