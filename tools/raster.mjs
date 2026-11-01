// Fixed local decode helper. No URL loading, external binaries, or provider calls.
import fs from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const MAX_BYTES = 8 * 1024 * 1024;
const MAX_PIXELS = 12_000_000;
const bounds = (width, height) => {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 64 || height < 64 ||
      width > 4096 || height > 4096 || width * height > MAX_PIXELS) throw new Error('bounds');
};
async function physical(file, directory = false) {
  if (!path.isAbsolute(file)) throw new Error('path');
  let cursor = path.parse(file).root;
  for (const part of path.relative(cursor, file).split(path.sep).filter(Boolean)) {
    cursor = path.join(cursor, part);
    if ((await fs.lstat(cursor)).isSymbolicLink()) throw new Error('link');
  }
  const info = await fs.lstat(file);
  if (directory ? !info.isDirectory() : !info.isFile()) throw new Error('type');
  return info;
}
try {
  const [operation, input, output, ...extra] = process.argv.slice(2);
  if (operation !== 'normalize' || !input || !output || extra.length ||
      !['selected.png', 'selected.jpeg'].includes(path.basename(input)) ||
      path.basename(output) !== 'normalized.png' || path.dirname(input) !== path.dirname(output)) throw new Error('arguments');
  await physical(path.dirname(input), true);
  const info = await physical(input);
  if (!info.size || info.size > MAX_BYTES) throw new Error('bytes');
  const data = await fs.readFile(input);
  if (data.length !== info.size || data.length > MAX_BYTES) throw new Error('bytes');
  const format = data.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) ? 'png' :
    data[0] === 255 && data[1] === 216 ? 'jpeg' : null;
  if (!format || path.extname(input) !== (format === 'png' ? '.png' : '.jpeg')) throw new Error('container');
  const decoder = sharp(data, {failOn: 'warning', limitInputPixels: MAX_PIXELS, animated: false, sequentialRead: true});
  const metadata = await decoder.metadata();
  bounds(metadata.width, metadata.height);
  if (metadata.format !== format || (metadata.pages ?? 1) !== 1 || metadata.pageHeight) throw new Error('pages');
  const result = await decoder.rotate().toColourspace('srgb').ensureAlpha()
    .png({compressionLevel: 9, adaptiveFiltering: false, palette: false}).toBuffer({resolveWithObject: true});
  bounds(result.info.width, result.info.height);
  if (result.data.length > MAX_BYTES || result.info.format !== 'png') throw new Error('output');
  await physical(path.dirname(output), true);
  await fs.writeFile(output, result.data, {flag: 'wx', mode: 0o600});
  process.stdout.write(JSON.stringify({width: result.info.width, height: result.info.height, format: 'png'}));
} catch {
  process.stderr.write('Raster normalization failed');
  process.exitCode = 1;
}
