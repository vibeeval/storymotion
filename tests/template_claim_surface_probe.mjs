// Internal test probe; not shipped. Checks the template claim-surface declaration
// against rendered text: undeclared caller numbers must not change rendered digits,
// declared hidden strings must never be rendered and declared paths must exist.
import {compileStaged} from '../renderers/template-registry/registry.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';

const NUMBER = /\d+(?:[.,]\d+)*(?:\s*%)?/gu;
let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const declaration = input.declaration;
const frames = input.frames;

function textNodes(tree) {
  const out = [];
  const visit = node => {
    if (node.tag === 'text') {
      let value = '';
      const walk = child => { if (child.tag === '#text') value += child.text; else child.children.forEach(walk); };
      node.children.forEach(walk);
      out.push(value.normalize('NFKC'));
    } else node.children.forEach(visit);
  };
  visit(tree);
  return out;
}

function signature(spec) {
  const compiled = compileStaged(spec), duration = compiled.spec.parameters.duration;
  const numbers = new Set(), texts = new Set();
  for (let i = 0; i <= frames; i++) {
    for (const value of textNodes(parseSvg(compiled.render(duration * i / frames)))) {
      texts.add(value);
      for (const match of value.match(NUMBER) ?? []) numbers.add(match);
    }
  }
  return {numbers: [...numbers].sort().join('|'), texts: [...texts].sort().join('\u241e'), list: [...texts]};
}

function leaves(value, path = [], out = []) {
  if (Array.isArray(value)) {
    out.push({path, value, array: true});
    value.forEach((child, i) => leaves(child, [...path, i], out));
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) leaves(child, [...path, key], out);
  } else out.push({path, value});
  return out;
}

function pattern(path) {
  let result = '';
  for (const key of path) result += typeof key === 'number' ? '[]' : (result ? '.' : '') + key;
  return result;
}

function setAt(object, path, value) {
  const copy = structuredClone(object);
  let target = copy;
  for (const key of path.slice(0, -1)) target = target[key];
  target[path.at(-1)] = value;
  return copy;
}

function numberCandidates(value) {
  const integer = Number.isInteger(value);
  const steps = integer ? [1, -1, 2, -2, 5, -5, 10, -10, 50, -50]
    : [0.5, -0.5, 1, -1, 0.25, -0.25, 0.1, -0.1, 0.05, -0.05, 2, -2, 5, -5, 10, -10];
  const shifted = steps.map(step => integer ? value + step : +(value + step).toFixed(6));
  const scaled = [1.5, 0.5, 2, 0.75].map(f => integer ? Math.round(value * f) : +(value * f).toFixed(6));
  return [...new Set([...shifted, ...scaled])].filter(candidate => candidate !== value);
}

function attempt(spec, path, candidates, base, compare) {
  let valid = 0;
  for (const candidate of candidates) {
    let changed;
    try { changed = signature({...spec, parameters: setAt(spec.parameters, path, candidate)}); }
    catch { continue; }
    valid++;
    if (compare(changed) !== compare(base)) return {valid, changed: true};
    if (valid >= 3) break;
  }
  return {valid, changed: false};
}

const violations = [], unperturbable = new Set();
const coverage = {numeric_checked: 0, numeric_unperturbable: 0, hidden_checked: 0, hidden_unperturbable: 0};
const seen = {};
for (const {family, spec} of input.cases) {
  const row = declaration.families[family];
  const common = declaration.common;
  const hidden = new Set([...common.hidden_strings, ...row.hidden_strings]);
  const declared = new Set([...row.guarded_numbers, ...Object.values(row.exempt_numbers).flat(), ...Object.values(common.exempt_numbers).flat()]);
  const base = signature(spec);
  seen[family] ??= new Set();
  for (const {path, value, array} of leaves(spec.parameters)) {
    const name = pattern(path);
    seen[family].add(name);
    if (array) {
      const scalars = value.length >= 2 && value.every(v => typeof v === 'number');
      if (!scalars || declared.has(name + '[]')) continue;
      const swapped = [...value];
      [swapped[0], swapped[1]] = [swapped[1], swapped[0]];
      const result = attempt(spec, path, [swapped, [...value].reverse()], base, s => s.numbers);
      if (result.changed) violations.push({family, path: name + '[]', kind: 'undeclared_order_changes_rendered_digits'});
    } else if (typeof value === 'number') {
      if (declared.has(name)) continue;
      const result = attempt(spec, path, numberCandidates(value), base, s => s.numbers);
      coverage[result.valid ? 'numeric_checked' : 'numeric_unperturbable']++;
      if (!result.valid) unperturbable.add(family + ':' + name);
      if (result.changed) violations.push({family, path: name, kind: 'undeclared_number_changes_rendered_digits'});
    } else if (typeof value === 'string' && hidden.has(name)) {
      const result = attempt(spec, path, [value + ' 7', value.slice(0, -1) + '7'], base, s => s.texts);
      coverage[result.valid ? 'hidden_checked' : 'hidden_unperturbable']++;
      if (result.changed) violations.push({family, path: name, kind: 'hidden_string_changes_rendered_text'});
      const needle = value.normalize('NFKC').toLocaleLowerCase('tr');
      if (needle.length >= 3 && base.list.some(text => text.toLocaleLowerCase('tr').includes(needle)))
        violations.push({family, path: name, kind: 'hidden_string_value_rendered'});
    }
  }
}
for (const [family, names] of Object.entries(seen)) {
  const row = declaration.families[family];
  for (const name of [...row.hidden_strings, ...row.guarded_numbers, ...Object.values(row.exempt_numbers).flat()])
    if (!names.has(name)) violations.push({family, path: name, kind: 'declared_path_absent_from_fixtures'});
}
process.stdout.write(JSON.stringify({violations, coverage, unperturbable: [...unperturbable].sort(), families: Object.keys(seen).length}));
