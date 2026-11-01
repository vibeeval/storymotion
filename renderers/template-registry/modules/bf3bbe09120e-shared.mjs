// Independent B02 copy of proven B01 helpers; no product imports. Pure data in, bounded SVG out; no media or clocks.
export const VERSION = '1.0.0';
export const WIDTH = 1080;
export const HEIGHT = 1920;
export const FPS = 30;
export const COMMON_REQUIRED = ['title', 'duration', 'narration', 'cues'];

export class InputError extends Error {
  constructor(message) { super(`TEMPLATE_INPUT: ${message}`); this.name = 'InputError'; }
}
export function fail(message) { throw new InputError(message); }
export function keys(value, required, optional = [], name = 'object') {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail(`${name}: plain object required`);
  const own = Reflect.ownKeys(value);
  if (own.some(key => typeof key !== 'string'
      || !Object.getOwnPropertyDescriptor(value, key).enumerable
      || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), 'value'))
      || required.some(key => !Object.hasOwn(value, key))
      || own.some(key => !required.includes(key) && !optional.includes(key))) {
    fail(`${name}: expected fields ${required.join(', ')}`);
  }
}
export function number(value, name, low, high, integer = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < low || value > high
      || (integer && !Number.isInteger(value))) fail(`${name}: ${low}–${high}${integer ? ' integer' : ''} required`);
  return value;
}
export function choice(value, name, values) {
  if (typeof value !== 'string' || !values.includes(value)) fail(`${name}: ${values.join('/')} required`);
  return value;
}
export function text(value, name, maximum = 160) {
  if (typeof value !== 'string' || !value.trim() || [...value].length > maximum
      || [...value].some(c => /\p{C}/u.test(c) && c !== '\n' && c !== '\t')) fail(`${name}: bounded plain text required`);
  return value.normalize('NFC').replace(/\s+/gu, ' ').trim();
}
// Conservative advance estimates, not a claim of measured browser font boxes.
// Every word remains present or validation refuses the input.
export function textUnits(value) {
  return [...value].reduce((sum, c) => sum + (c === ' ' ? 0.36
    : /[MW@%ĞÖÜŞÇ]/u.test(c) ? 1.02
    : /[ilıİ1.,:;'!|]/u.test(c) ? 0.4
    : /[A-Z0-9]/u.test(c) ? 0.8
    : c.codePointAt(0) > 0x2FFF ? 1.15 : 0.7), 0);
}
export function fitText(value, {width = 900, maximum = 56, minimum = 28, maxLines = 3} = {}) {
  number(width, 'text width', 1, WIDTH);
  number(maximum, 'maximum font', 1, 120, true);
  number(minimum, 'minimum font', 1, maximum, true);
  number(maxLines, 'maximum lines', 1, 8, true);
  const normalized = text(value, 'layout text', 1500);
  for (let size = maximum; size >= minimum; size--) {
    const lines = []; let line = ''; let fits = true;
    for (const word of normalized.split(' ')) {
      if (textUnits(word) * size > width) { fits = false; break; }
      const candidate = line ? `${line} ${word}` : word;
      if (line && textUnits(candidate) * size > width) { lines.push(line); line = word; }
      else line = candidate;
    }
    if (line) lines.push(line);
    if (fits && lines.length <= maxLines) return {
      text: normalized, lines, fontSize: size, lineHeight: size * 1.24,
      width, height: size * 1.24 * lines.length,
    };
  }
  fail('text does not fit without losing words; shorten the input');
}
export function contrastRatio(first, second) {
  const luminance = color => {
    if (typeof color !== 'string' || !/^#[0-9A-Fa-f]{6}$/u.test(color)) fail('contrast: six-digit hex required');
    const channels = [1, 3, 5].map(index => Number.parseInt(color.slice(index, index + 2), 16) / 255)
      .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  };
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
export function palette(value, defaults, accentMinimum = 3) {
  const raw = value === undefined ? defaults : value;
  keys(raw, ['background', 'ink', 'muted', 'accent'], [], 'palette');
  const result = {};
  for (const [key, color] of Object.entries(raw)) {
    if (typeof color !== 'string' || !/^#[0-9A-Fa-f]{6}$/u.test(color)) fail(`palette.${key}: six-digit hex required`);
    result[key] = color.toUpperCase();
  }
  for (const [role, minimum] of [['ink', 4.5], ['muted', 4.5], ['accent', accentMinimum]]) {
    if (contrastRatio(result[role], result.background) < minimum) fail(`palette.${role}: contrast must be at least ${minimum} against background`);
  }
  return result;
}
export function validateBase(spec, id, required, optional, defaults) {
  keys(spec, ['id', 'version', 'parameters'], [], 'spec');
  if (spec.id !== id || spec.version !== VERSION) fail('unknown renderer ID or template version');
  const raw = spec.parameters;
  keys(raw, [...COMMON_REQUIRED, ...required], [...optional, 'palette'], 'parameters');
  const title = text(raw.title, 'title', 160);
  fitText(title, {maximum: 64, minimum: 38, maxLines: 4});
  const duration = number(raw.duration, 'duration', 3, 45);
  if (Math.abs(duration * FPS - Math.round(duration * FPS)) > 1e-7) fail('duration: use a 30 fps frame boundary');
  const narration = text(raw.narration, 'narration', 1500);
  if (!Array.isArray(raw.cues) || raw.cues.length < 1 || raw.cues.length > 24) fail('cues: 1–24 supplied cues required');
  let previous = 0;
  const cues = raw.cues.map((cue, i) => {
    keys(cue, ['start', 'end', 'text'], [], `cue ${i}`);
    const start = number(cue.start, 'cue start', 0, duration);
    const end = number(cue.end, 'cue end', 0, duration);
    const value = text(cue.text, 'cue text', 95);
    if (start < previous || end - start < 0.2 - 1e-9) fail('cues: ordered, nonoverlapping and at least 0.2 seconds required');
    fitText(value, {width: 890, maximum: 44, minimum: 30, maxLines: 3});
    previous = end;
    return {start, end, text: value};
  });
  if (cues.map(c => c.text).join(' ') !== narration) fail('cues must contain the whole narration in the same order');
  return {title, duration, narration, cues, palette: palette(raw.palette, defaults, 4.5)};
}
export function windowPair(value, name) {
  if (!Array.isArray(value) || value.length !== 2) fail(`${name}: two normalized times required`);
  const a = number(value[0], `${name} start`, 0, 1);
  const b = number(value[1], `${name} end`, 0, 1);
  if (b - a < 0.1 - 1e-9) fail(`${name}: at least 10% of duration required`);
  return [a, b];
}
export const defaulted = (value, fallback) => value === undefined ? fallback : value;
export const clamp = x => Math.max(0, Math.min(1, x));
export const smooth = x => { const p = clamp(x); return p * p * (3 - 2 * p); };
export const lerp = (a, b, p) => a + (b - a) * p;
export function phaseAt(seconds, duration, window) { return smooth((seconds / duration - window[0]) / (window[1] - window[0])); }
export function sampleTime(seconds, duration) { return Math.min(number(seconds, 'seconds', 0, Number.MAX_SAFE_INTEGER), duration); }
export function frameSeconds(frame, fps = FPS) { return number(frame, 'frame', 0, Number.MAX_SAFE_INTEGER, true) / number(fps, 'fps', 1, 120, true); }
export function activeCue(cues, seconds) { return cues.find(c => seconds >= c.start && seconds < c.end) ?? null; }
export function esc(value) { return String(value).replace(/[&<>"']/gu, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c])); }
export function fmt(value) { if (!Number.isFinite(value)) fail('nonfinite SVG coordinate'); return String(Number(value.toFixed(5))); }
export function svgText(value, {x = 90, y, width = 900, maximum = 56, minimum = 28, maxLines = 3, fill = '#18202A', anchor = 'start', weight = 600} = {}) {
  const fit = fitText(value, {width, maximum, minimum, maxLines});
  return `<text x="${fmt(x)}" y="${fmt(y)}" fill="${esc(fill)}" font-size="${fit.fontSize}" font-weight="${weight}" text-anchor="${anchor}" data-template-text="true" data-full-text="${esc(fit.text)}" data-slot-width="${width}" data-estimated-height="${fmt(fit.height)}">${fit.lines.map((line, i) => `<tspan x="${fmt(x)}" dy="${i === 0 ? 0 : fmt(fit.lineHeight)}">${esc(line)}</tspan>`).join('')}</text>`;
}
export function frameShell(id, p, seconds, body, options = {}) {
  const cue = options.captions === false ? null : activeCue(p.cues, seconds); const cueIndex = cue ? p.cues.indexOf(cue) : -1; const c = p.palette;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="${WIDTH}" height="${HEIGHT}" role="img" aria-label="${esc(p.title)}" data-renderer="${id}" data-seconds="${fmt(seconds)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${svgText(p.title, {y:165, maximum:64, minimum:38, maxLines:4, fill:c.ink})}${body}<path d="M90 1585H990" stroke="${c.muted}" stroke-width="1" opacity="0.45"/>${cue ? `<g id="family-cue-${cueIndex}" data-cue-start="${fmt(cue.start)}" data-cue-end="${fmt(cue.end)}">${svgText(cue.text, {x:95,y:1655,width:890,maximum:44,minimum:30,maxLines:3,fill:c.ink})}</g>` : ''}<text x="90" y="1840" fill="${c.muted}" font-size="20">YEREL ŞABLON · İNSAN İNCELEMESİ BEKLİYOR</text></g></svg>`;
}
export function deepFreeze(value) { if (value && typeof value === 'object') { for (const child of Object.values(value)) deepFreeze(child); Object.freeze(value); } return value; }
