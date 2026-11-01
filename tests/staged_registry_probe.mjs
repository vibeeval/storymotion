// Internal test probe; not shipped. Executes the staged copies exactly as each
// engine loads them (Remotion: ESM registry import; HF: browser bundle global)
// and compares every frame with the source registry, including reverse seeks.
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';
import {compileStaged} from '../renderers/template-registry/registry.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';

let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const results = [];
for (const {dir, engine, spec} of JSON.parse(raw).cases) {
  try {
    const reference = compileStaged(spec), duration = reference.spec.parameters.duration;
    const times = [0, duration * 0.37, duration * 0.73, duration];
    const expected = times.map(t => reference.render(t));
    let render, parse;
    if (engine === 'remotion') {
      const staged = await import(pathToFileURL(dir + '/template-registry/registry.mjs').href);
      const tree = await import(pathToFileURL(dir + '/svg-tree.mjs').href);
      const compiled = staged.compileStaged(spec);
      render = t => compiled.render(t);parse = svg => tree.parseSvg(svg);
    } else {
      const context = vm.createContext({});
      vm.runInContext(readFileSync(dir + '/template-registry/bundle.js', 'utf8'), context);
      context.specJson = JSON.stringify(spec);
      vm.runInContext('globalThis.compiled = StoryMotionTemplates.compileStaged(JSON.parse(specJson));', context);
      render = t => vm.runInContext(`compiled.render(${JSON.stringify(t)})`, context);
      parse = svg => JSON.parse(vm.runInContext(`JSON.stringify(StoryMotionTemplates.parseSvg(${JSON.stringify(svg)}))`, context));
    }
    const forward = times.map(render), backward = [...times].reverse().map(render).reverse();
    const sameFrames = forward.every((svg, i) => svg === expected[i] && backward[i] === expected[i]);
    const sameTrees = expected.every(svg => JSON.stringify(parse(svg)) === JSON.stringify(parseSvg(svg)));
    results.push({dir, engine, ok: sameFrames && sameTrees, frames: times.length});
  } catch (error) {
    results.push({dir, engine, ok: false, error: String(error && error.message || error).slice(0, 200)});
  }
}
process.stdout.write(JSON.stringify({results}));
