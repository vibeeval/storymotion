var StoryMotionTemplates = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target7, all) => {
    for (var name in all)
      __defProp(target7, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // renderers/template-registry/browser-entry.mjs
  var browser_entry_exports = {};
  __export(browser_entry_exports, {
    compileStaged: () => compileStaged,
    parseSvg: () => parseSvg,
    svgDom: () => svgDom
  });

  // renderers/template-registry/modules/ffc6796ae06a-contour-trace.mjs
  var ffc6796ae06a_contour_trace_exports = {};
  __export(ffc6796ae06a_contour_trace_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE,
    ID: () => ID,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA,
    SOURCE_ID: () => SOURCE_ID,
    render: () => render,
    renderFrame: () => renderFrame,
    sample: () => sample,
    sampleFrame: () => sampleFrame,
    traceGeometry: () => traceGeometry,
    validateSpec: () => validateSpec
  });

  // renderers/template-registry/modules/cabbfda44beb-shared.mjs
  var VERSION = "1.0.0";
  var WIDTH = 1080;
  var HEIGHT = 1920;
  var FPS = 30;
  var COMMON_REQUIRED = ["title", "duration", "narration", "cues"];
  var InputError = class extends Error {
    constructor(message) {
      super(`TEMPLATE_INPUT: ${message}`);
      this.name = "InputError";
    }
  };
  function fail(message) {
    throw new InputError(message);
  }
  function keys(value, required, optional = [], name = "object") {
    if (!value || typeof value !== "object" || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail(`${name}: plain object required`);
    const own = Reflect.ownKeys(value);
    if (own.some((key) => typeof key !== "string" || !Object.getOwnPropertyDescriptor(value, key).enumerable || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), "value")) || required.some((key) => !Object.hasOwn(value, key)) || own.some((key) => !required.includes(key) && !optional.includes(key))) {
      fail(`${name}: expected fields ${required.join(", ")}`);
    }
  }
  function number(value, name, low, high, integer = false) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high || integer && !Number.isInteger(value)) fail(`${name}: ${low}\u2013${high}${integer ? " integer" : ""} required`);
    return value;
  }
  function choice(value, name, values) {
    if (typeof value !== "string" || !values.includes(value)) fail(`${name}: ${values.join("/")} required`);
    return value;
  }
  function text(value, name, maximum = 160) {
    if (typeof value !== "string" || !value.trim() || [...value].length > maximum || [...value].some((c) => new RegExp("\\p{C}", "u").test(c) && c !== "\n" && c !== "	")) fail(`${name}: bounded plain text required`);
    return value.normalize("NFC").replace(/\s+/gu, " ").trim();
  }
  function textUnits(value) {
    return [...value].reduce((sum, c) => sum + (c === " " ? 0.36 : /[MW@%ĞÖÜŞÇ]/u.test(c) ? 1.02 : /[ilıİ1.,:;'!|]/u.test(c) ? 0.4 : /[A-Z0-9]/u.test(c) ? 0.8 : c.codePointAt(0) > 12287 ? 1.15 : 0.7), 0);
  }
  function fitText(value, { width = 900, maximum = 56, minimum = 28, maxLines = 3 } = {}) {
    number(width, "text width", 1, WIDTH);
    number(maximum, "maximum font", 1, 120, true);
    number(minimum, "minimum font", 1, maximum, true);
    number(maxLines, "maximum lines", 1, 8, true);
    const normalized2 = text(value, "layout text", 1500);
    for (let size = maximum; size >= minimum; size--) {
      const lines = [];
      let line5 = "";
      let fits = true;
      for (const word of normalized2.split(" ")) {
        if (textUnits(word) * size > width) {
          fits = false;
          break;
        }
        const candidate = line5 ? `${line5} ${word}` : word;
        if (line5 && textUnits(candidate) * size > width) {
          lines.push(line5);
          line5 = word;
        } else line5 = candidate;
      }
      if (line5) lines.push(line5);
      if (fits && lines.length <= maxLines) return {
        text: normalized2,
        lines,
        fontSize: size,
        lineHeight: size * 1.24,
        width,
        height: size * 1.24 * lines.length
      };
    }
    fail("text does not fit without losing words; shorten the input");
  }
  function contrastRatio(first, second) {
    const luminance = (color2) => {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail("contrast: six-digit hex required");
      const channels = [1, 3, 5].map((index) => Number.parseInt(color2.slice(index, index + 2), 16) / 255).map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const a = luminance(first), b = luminance(second);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }
  function palette(value, defaults, accentMinimum = 3) {
    const raw = value === void 0 ? defaults : value;
    keys(raw, ["background", "ink", "muted", "accent"], [], "palette");
    const result2 = {};
    for (const [key, color2] of Object.entries(raw)) {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail(`palette.${key}: six-digit hex required`);
      result2[key] = color2.toUpperCase();
    }
    for (const [role, minimum] of [["ink", 4.5], ["muted", 4.5], ["accent", accentMinimum]]) {
      if (contrastRatio(result2[role], result2.background) < minimum) fail(`palette.${role}: contrast must be at least ${minimum} against background`);
    }
    return result2;
  }
  function validateCueArray(value) {
    if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype) fail("cues: plain array required");
    const descriptors = Object.getOwnPropertyDescriptors(value);
    const length = descriptors.length;
    if (!length || !Object.hasOwn(length, "value") || !Number.isInteger(length.value) || length.value < 1 || length.value > 24) fail("cues: 1\u201324 supplied cues required");
    const own = Reflect.ownKeys(descriptors);
    for (const key of own) {
      if (key === "length") continue;
      const descriptor = descriptors[key];
      if (typeof key !== "string" || !/^(0|[1-9]\d*)$/u.test(key) || Number(key) >= length.value || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) fail("cues: dense enumerable data entries only");
    }
    if (own.length !== length.value + 1) fail("cues: sparse arrays are not allowed");
    return value;
  }
  function validateBase(spec, id, required, optional, defaults) {
    keys(spec, ["id", "version", "parameters"], [], "spec");
    if (spec.id !== id || spec.version !== VERSION) fail("unknown renderer ID or template version");
    const raw = spec.parameters;
    keys(raw, [...COMMON_REQUIRED, ...required], [...optional, "palette"], "parameters");
    validateCueArray(raw.cues);
    const title = text(raw.title, "title", 160);
    fitText(title, { maximum: 64, minimum: 38, maxLines: 4 });
    const duration = number(raw.duration, "duration", 3, 45);
    if (Math.abs(duration * FPS - Math.round(duration * FPS)) > 1e-7) fail("duration: use a 30 fps frame boundary");
    const narration = text(raw.narration, "narration", 1500);
    let previous = 0;
    const cues = raw.cues.map((cue, i) => {
      keys(cue, ["start", "end", "text"], [], `cue ${i}`);
      const start = number(cue.start, "cue start", 0, duration);
      const end = number(cue.end, "cue end", 0, duration);
      const value = text(cue.text, "cue text", 95);
      if (start < previous || end - start < 0.2 - 1e-9) fail("cues: ordered, nonoverlapping and at least 0.2 seconds required");
      fitText(value, { width: 890, maximum: 44, minimum: 30, maxLines: 3 });
      previous = end;
      return { start, end, text: value };
    });
    if (cues.map((c) => c.text).join(" ") !== narration) fail("cues must contain the whole narration in the same order");
    return { title, duration, narration, cues, palette: palette(raw.palette, defaults, id === "scan-hud" ? 4.5 : 3) };
  }
  function windowPair(value, name) {
    if (!Array.isArray(value) || value.length !== 2) fail(`${name}: two normalized times required`);
    const a = number(value[0], `${name} start`, 0, 1);
    const b = number(value[1], `${name} end`, 0, 1);
    if (b - a < 0.1 - 1e-9) fail(`${name}: at least 10% of duration required`);
    return [a, b];
  }
  var defaulted = (value, fallback) => value === void 0 ? fallback : value;
  var clamp = (x) => Math.max(0, Math.min(1, x));
  var smooth = (x) => {
    const p = clamp(x);
    return p * p * (3 - 2 * p);
  };
  var lerp = (a, b, p) => a + (b - a) * p;
  function phaseAt(seconds, duration, window) {
    return smooth((seconds / duration - window[0]) / (window[1] - window[0]));
  }
  function sampleTime(seconds, duration) {
    return Math.min(number(seconds, "seconds", 0, Number.MAX_SAFE_INTEGER), duration);
  }
  function motionTime(seconds, duration) {
    number(duration, "motion duration", 3, 45);
    const time2 = sampleTime(seconds, duration);
    const animationDuration = (Math.round(duration * FPS) - 18) / FPS;
    return time2 >= animationDuration ? duration : time2 / animationDuration * duration;
  }
  function activeCue(cues, seconds) {
    return cues.find((c) => seconds >= c.start && seconds < c.end) ?? null;
  }
  function esc(value) {
    return String(value).replace(/[&<>"']/gu, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]);
  }
  function fmt(value) {
    if (!Number.isFinite(value)) fail("nonfinite SVG coordinate");
    return String(Number(value.toFixed(5)));
  }
  function svgText(value, { x = 90, y, width = 900, maximum = 56, minimum = 28, maxLines = 3, fill = "#18202A", anchor = "start", weight = 600 } = {}) {
    const fit = fitText(value, { width, maximum, minimum, maxLines });
    return `<text x="${fmt(x)}" y="${fmt(y)}" fill="${esc(fill)}" font-size="${fit.fontSize}" font-weight="${weight}" text-anchor="${anchor}" data-template-text="true" data-full-text="${esc(fit.text)}" data-slot-width="${width}" data-estimated-height="${fmt(fit.height)}">${fit.lines.map((line5, i) => `<tspan x="${fmt(x)}" dy="${i === 0 ? 0 : fmt(fit.lineHeight)}">${esc(line5)}</tspan>`).join("")}</text>`;
  }
  function frameShell(id, p, seconds, body) {
    const cue = activeCue(p.cues, seconds);
    const cueIndex = cue ? p.cues.indexOf(cue) : -1;
    const c = p.palette;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="${WIDTH}" height="${HEIGHT}" role="img" aria-label="${esc(p.title)}" data-renderer="${id}" data-seconds="${fmt(seconds)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${svgText(p.title, { y: 165, maximum: 64, minimum: 38, maxLines: 4, fill: c.ink })}${body}<path d="M90 1585H990" stroke="${c.muted}" stroke-width="1" opacity="0.45"/>${cue ? `<g id="family-cue-${cueIndex}" data-cue-start="${fmt(cue.start)}" data-cue-end="${fmt(cue.end)}">${svgText(cue.text, { x: 95, y: 1655, width: 890, maximum: 44, minimum: 30, maxLines: 3, fill: c.ink })}</g>` : ""}<text x="90" y="1840" fill="${c.muted}" font-size="20">YEREL \u015EABLON \xB7 \u0130NSAN \u0130NCELEMES\u0130 BEKL\u0130YOR</text></g></svg>`;
  }

  // renderers/template-registry/modules/ffc6796ae06a-contour-trace.mjs
  var ID = "contour-trace";
  var SOURCE_ID = "source-mg-style-02-line-art";
  var DEFAULT_PALETTE = Object.freeze({ background: "#FAF6EC", ink: "#263A30", muted: "#647165", accent: "#9C4D30" });
  var PARAMETER_SCHEMA = Object.freeze({
    illustration: { enum: ["leaf", "vessel"] },
    width: { minimum: 240, maximum: 520 },
    height: { minimum: 300, maximum: 520 },
    stroke_width: { minimum: 2, maximum: 8 },
    hatch_spacing: { minimum: 10, maximum: 30 },
    draw_window: { normalized: true, minimumSpan: 0.1 },
    hatch_window: { normalized: true, minimumSpan: 0.1 },
    label: { maxLength: 110 }
  });
  function validateSpec(spec) {
    const p = validateBase(
      spec,
      ID,
      ["illustration", "label"],
      ["width", "height", "stroke_width", "hatch_spacing", "draw_window", "hatch_window"],
      DEFAULT_PALETTE
    );
    const raw = spec.parameters;
    p.illustration = choice(raw.illustration, "illustration", ["leaf", "vessel"]);
    p.label = text(raw.label, "illustration label", 110);
    fitText(p.label, { maximum: 38, minimum: 28, maxLines: 3 });
    p.width = number(defaulted(raw.width, 440), "width", 240, 520);
    p.height = number(defaulted(raw.height, 500), "height", 300, 520);
    p.stroke_width = number(defaulted(raw.stroke_width, 4), "stroke width", 2, 8);
    p.hatch_spacing = number(defaulted(raw.hatch_spacing, 18), "hatch spacing", 10, 30);
    p.draw_window = windowPair(defaulted(raw.draw_window, [0.04, 0.62]), "draw window");
    p.hatch_window = windowPair(defaulted(raw.hatch_window, [0.65, 0.96]), "hatch window");
    if (p.draw_window[1] > p.hatch_window[0]) fail("hatching must follow the completed contour");
    return { id: ID, version: VERSION, parameters: p };
  }
  function traceGeometry(p) {
    const w = p.width, h = p.height;
    const pair2 = (x, y) => `${fmt(x)} ${fmt(y)}`;
    let outline, mask;
    if (p.illustration === "leaf") {
      mask = `M${pair2(0, h / 2)}C${pair2(-w * 0.52, h * 0.3)} ${pair2(-w * 0.55, -h * 0.28)} ${pair2(0, -h / 2)}C${pair2(w * 0.55, -h * 0.28)} ${pair2(w * 0.52, h * 0.3)} ${pair2(0, h / 2)}Z`;
      outline = `${mask}C${pair2(w * 0.03, h * 0.16)} ${pair2(-w * 0.03, -h * 0.17)} ${pair2(0, -h / 2)}`;
    } else {
      mask = `M${pair2(-w * 0.18, -h / 2)}L${pair2(w * 0.18, -h / 2)}C${pair2(w * 0.23, -h * 0.35)} ${pair2(w * 0.08, -h * 0.32)} ${pair2(w * 0.26, -h * 0.1)}C${pair2(w * 0.6, h * 0.22)} ${pair2(w * 0.44, h * 0.48)} ${pair2(w * 0.26, h / 2)}L${pair2(-w * 0.26, h / 2)}C${pair2(-w * 0.44, h * 0.48)} ${pair2(-w * 0.6, h * 0.22)} ${pair2(-w * 0.26, -h * 0.1)}C${pair2(-w * 0.08, -h * 0.32)} ${pair2(-w * 0.23, -h * 0.35)} ${pair2(-w * 0.18, -h / 2)}Z`;
      outline = mask;
    }
    const hatches = [], bounds3 = { left: -w * 0.6, right: w * 0.6, top: -h / 2, bottom: h / 2 };
    for (let offset = bounds3.left + bounds3.top; offset <= bounds3.right + bounds3.bottom; offset += p.hatch_spacing) {
      const lowY = Math.max(bounds3.top, offset - bounds3.right), highY = Math.min(bounds3.bottom, offset - bounds3.left);
      if (highY - lowY > 1e-8) hatches.push({ x1: offset - highY, y1: highY, x2: offset - lowY, y2: lowY });
    }
    return { outline, mask, hatches, bounds: bounds3 };
  }
  function state(p, seconds) {
    const time2 = sampleTime(seconds, p.duration), motion = motionTime(time2, p.duration);
    const draw = phaseAt(motion, p.duration, p.draw_window);
    const hatch = phaseAt(motion, p.duration, p.hatch_window);
    return {
      seconds: time2,
      draw,
      hatch,
      constructionOpacity: (1 - draw) * 0.36,
      phase: draw < 1 ? "trace" : hatch < 1 ? "hatch" : "hold",
      geometry: traceGeometry(p)
    };
  }
  function sampleFrame(spec, seconds) {
    return state(validateSpec(spec).parameters, seconds);
  }
  function renderFrame(spec, seconds) {
    const p = validateSpec(spec).parameters, s = state(p, seconds), c = p.palette, g = s.geometry;
    const hatches = g.hatches.map((line5, i) => {
      const reveal = Math.max(0, Math.min(1, s.hatch * g.hatches.length - i));
      return `<path d="M${fmt(line5.x1)} ${fmt(line5.y1)}L${fmt(line5.x2)} ${fmt(line5.y2)}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt(1 - reveal)}"/>`;
    }).join("");
    const body = `<defs><clipPath id="ct-mask"><path d="${g.mask}"/></clipPath></defs><g transform="translate(540 930)" fill="none" stroke-linecap="round" stroke-linejoin="round"><g stroke="${c.muted}" stroke-width="1.5" opacity="${fmt(s.constructionOpacity)}"><path d="M${fmt(-p.width * 0.65)} 0H${fmt(p.width * 0.65)}M0 ${fmt(-p.height * 0.56)}V${fmt(p.height * 0.56)}"/><rect x="${fmt(-p.width * 0.6)}" y="${fmt(-p.height / 2)}" width="${fmt(p.width * 1.2)}" height="${fmt(p.height)}" stroke-dasharray="6 12"/></g><g clip-path="url(#ct-mask)" stroke="${c.accent}" stroke-width="${fmt(p.stroke_width * 0.38)}">${hatches}</g><path data-continuous-contour="true" d="${g.outline}" stroke="${c.ink}" stroke-width="${fmt(p.stroke_width)}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt(1 - s.draw)}"/></g>${svgText(p.label, { y: 1380, maximum: 38, minimum: 28, maxLines: 3, fill: c.ink })}`;
    return frameShell(ID, p, s.seconds, body);
  }
  var sample = sampleFrame;
  var render = renderFrame;

  // renderers/template-registry/modules/bcf766fc13eb-shape-morph.mjs
  var bcf766fc13eb_shape_morph_exports = {};
  __export(bcf766fc13eb_shape_morph_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE2,
    ID: () => ID2,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA2,
    POINT_COUNT: () => POINT_COUNT,
    SHAPES: () => SHAPES,
    SOURCE_ID: () => SOURCE_ID2,
    contourPoints: () => contourPoints,
    pointsPath: () => pointsPath,
    polygonRadius: () => polygonRadius,
    polygonVertices: () => polygonVertices,
    render: () => render2,
    renderFrame: () => renderFrame2,
    sample: () => sample2,
    sampleFrame: () => sampleFrame2,
    signedArea: () => signedArea,
    validateSpec: () => validateSpec2
  });
  var ID2 = "shape-morph";
  var SOURCE_ID2 = "source-mg-style-08-morph";
  var SHAPES = Object.freeze(["circle", "rounded-square", "triangle", "star"]);
  var POINT_COUNT = 120;
  var DEFAULT_PALETTE2 = Object.freeze({ background: "#F0EDF7", ink: "#30264B", muted: "#726687", accent: "#9160CF" });
  var PARAMETER_SCHEMA2 = Object.freeze({
    shapes: { minimumItems: 2, maximumItems: 4, item: { shape: { enum: SHAPES }, label: { maxLength: 65 } } },
    radius: { minimum: 160, maximum: 300 },
    star_inner: { minimum: 0.3, maximum: 0.65 },
    squareness: { minimum: 3, maximum: 8 },
    rotation: { minimum: -90, maximum: 90 },
    hold_fraction: { minimum: 0.1, maximum: 0.55 }
  });
  function validateSpec2(spec) {
    const p = validateBase(spec, ID2, ["shapes"], ["radius", "star_inner", "squareness", "rotation", "hold_fraction"], DEFAULT_PALETTE2);
    const raw = spec.parameters;
    if (!Array.isArray(raw.shapes) || raw.shapes.length < 2 || raw.shapes.length > 4) fail("shapes: 2\u20134 steps required");
    p.shapes = raw.shapes.map((item, i) => {
      keys(item, ["shape", "label"], [], `shape ${i}`);
      const shape = choice(item.shape, "shape", SHAPES), label5 = text(item.label, "shape label", 65);
      fitText(label5, { maximum: 38, minimum: 28, maxLines: 3 });
      return { shape, label: label5 };
    });
    if (p.shapes.some((item, i) => i > 0 && item.shape === p.shapes[i - 1].shape)) fail("adjacent shapes must differ");
    p.radius = number(defaulted(raw.radius, 250), "radius", 160, 300);
    p.star_inner = number(defaulted(raw.star_inner, 0.46), "star inner radius", 0.3, 0.65);
    p.squareness = number(defaulted(raw.squareness, 5), "rounded-square exponent", 3, 8);
    p.rotation = number(defaulted(raw.rotation, 0), "rotation", -90, 90);
    p.hold_fraction = number(defaulted(raw.hold_fraction, 0.2), "hold fraction", 0.1, 0.55);
    return { id: ID2, version: VERSION, parameters: p };
  }
  var cross = (a, b) => a.x * b.y - a.y * b.x;
  var direction = (angle) => ({ x: Math.sin(angle), y: -Math.cos(angle) });
  function polygonVertices(shape, inner = 0.46) {
    if (shape !== "triangle" && shape !== "star") fail("polygon shape required");
    number(inner, "star inner radius", 0.3, 0.65);
    const count = shape === "triangle" ? 3 : 10;
    return Array.from({ length: count }, (_, i) => {
      const d = direction(i * Math.PI * 2 / count), r = shape === "star" && i % 2 ? inner : 1;
      return { x: d.x * r, y: d.y * r };
    });
  }
  function polygonRadius(vertices, angle) {
    const ray = direction(angle);
    let nearest = Infinity;
    for (let i = 0; i < vertices.length; i++) {
      const a = vertices[i], b = vertices[(i + 1) % vertices.length], edge = { x: b.x - a.x, y: b.y - a.y };
      const denominator = cross(ray, edge);
      if (Math.abs(denominator) < 1e-12) continue;
      const radius = cross(a, edge) / denominator, along2 = cross(a, ray) / denominator;
      if (radius > 0 && along2 >= -1e-10 && along2 <= 1 + 1e-10) nearest = Math.min(nearest, radius);
    }
    if (!Number.isFinite(nearest)) fail("closed contour ray has no intersection");
    return nearest;
  }
  function contourPoints(shape, { radius = 250, star_inner = 0.46, squareness = 5, rotation = 0 } = {}) {
    choice(shape, "shape", SHAPES);
    number(radius, "radius", 160, 300);
    number(star_inner, "star inner radius", 0.3, 0.65);
    number(squareness, "rounded-square exponent", 3, 8);
    number(rotation, "rotation", -90, 90);
    const vertices = shape === "triangle" || shape === "star" ? polygonVertices(shape, star_inner) : null;
    const turn = rotation * Math.PI / 180;
    return Array.from({ length: POINT_COUNT }, (_, i) => {
      const angle = i * Math.PI * 2 / POINT_COUNT;
      let r = 1;
      if (shape === "rounded-square") {
        r = Math.pow(Math.abs(Math.sin(angle)) ** squareness + Math.abs(Math.cos(angle)) ** squareness, -1 / squareness) * Math.pow(2, 1 / squareness - 0.5);
      } else if (vertices) r = polygonRadius(vertices, angle);
      const d = direction(angle + turn);
      return { x: d.x * r * radius, y: d.y * r * radius };
    });
  }
  function signedArea(points) {
    return points.reduce((sum, a, i) => {
      const b = points[(i + 1) % points.length];
      return sum + a.x * b.y - b.x * a.y;
    }, 0) / 2;
  }
  function pointsPath(points) {
    if (!Array.isArray(points) || points.length !== POINT_COUNT) fail("fixed contour point count required");
    return points.map((p, i) => `${i ? "L" : "M"}${fmt(p.x)} ${fmt(p.y)}`).join("") + "Z";
  }
  function state2(p, seconds) {
    const time2 = sampleTime(seconds, p.duration), segments = p.shapes.length - 1;
    const position = motionTime(time2, p.duration) / p.duration * segments, index = Math.min(segments - 1, Math.floor(position));
    const local = position - index, blend = smooth((local - p.hold_fraction) / (1 - p.hold_fraction));
    const before = contourPoints(p.shapes[index].shape, p), after = contourPoints(p.shapes[index + 1].shape, p);
    const points = before.map((a, i) => ({ x: lerp(a.x, after[i].x, blend), y: lerp(a.y, after[i].y, blend) }));
    return {
      seconds: time2,
      fromIndex: index,
      toIndex: index + 1,
      fromShape: p.shapes[index].shape,
      toShape: p.shapes[index + 1].shape,
      blend,
      points,
      path: pointsPath(points),
      area: signedArea(points),
      activeIndex: blend < 0.5 ? index : index + 1,
      phase: blend === 0 || blend === 1 ? "hold" : "morph"
    };
  }
  function sampleFrame2(spec, seconds) {
    return state2(validateSpec2(spec).parameters, seconds);
  }
  function renderFrame2(spec, seconds) {
    const p = validateSpec2(spec).parameters, s = state2(p, seconds), c = p.palette;
    const rail = p.shapes.map((item, i) => {
      const x = 180 + i * 720 / (p.shapes.length - 1), active = i === s.activeIndex;
      return `<circle cx="${fmt(x)}" cy="1320" r="${active ? 12 : 6}" fill="${active ? c.accent : c.muted}"/><text x="${fmt(x)}" y="1280" text-anchor="middle" font-size="24" fill="${c.muted}">${i + 1}</text>`;
    }).join("");
    const body = `<g transform="translate(540 930)"><circle r="${fmt(p.radius + 30)}" fill="none" stroke="${c.muted}" opacity="0.2" stroke-dasharray="3 12"/><path data-contour-points="${POINT_COUNT}" d="${s.path}" fill="${c.accent}" fill-opacity="0.25" stroke="${c.ink}" stroke-width="5" stroke-linejoin="round"/><circle r="4" fill="${c.ink}"/></g><path d="M180 1320H900" stroke="${c.muted}" stroke-width="2"/>${rail}${svgText(p.shapes[s.activeIndex].label, { y: 1400, maximum: 38, minimum: 28, maxLines: 3, fill: c.ink })}`;
    return frameShell(ID2, p, s.seconds, body);
  }
  var sample2 = sampleFrame2;
  var render2 = renderFrame2;

  // renderers/template-registry/modules/5d1ce3e8bcfd-scan-hud.mjs
  var d1ce3e8bcfd_scan_hud_exports = {};
  __export(d1ce3e8bcfd_scan_hud_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE3,
    FINAL_HOLD_FRAMES: () => FINAL_HOLD_FRAMES,
    ID: () => ID3,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA3,
    RADAR_RADIUS: () => RADAR_RADIUS,
    SOURCE_ID: () => SOURCE_ID3,
    arcPath: () => arcPath,
    render: () => render3,
    renderFrame: () => renderFrame3,
    sample: () => sample3,
    sampleFrame: () => sampleFrame3,
    targetPoint: () => targetPoint,
    validateSpec: () => validateSpec3
  });
  var ID3 = "scan-hud";
  var SOURCE_ID3 = "source-mg-style-22-hud";
  var DEFAULT_PALETTE3 = Object.freeze({ background: "#101E2A", ink: "#E6F4E9", muted: "#8EAEAC", accent: "#7FE7C4" });
  var RADAR_RADIUS = 300;
  var FINAL_HOLD_FRAMES = 18;
  var PARAMETER_SCHEMA3 = Object.freeze({
    targets: { minimumItems: 2, maximumItems: 4, item: { id: { pattern: "^[a-z][a-z0-9-]{0,19}$" }, label: { maxLength: 65 }, bearing: { minimum: -170, maximum: 170 }, range: { minimum: 0.18, maximum: 0.92 }, value: { minimum: 0, maximum: "gauge_max" } } },
    range_rings: { minimum: 2, maximum: 5, integer: true },
    sweep_turns: { minimum: 1, maximum: 3, integer: true },
    lock_at: { minimum: 0.25, maximum: 0.5 },
    gauge_at: { minimum: 0.6, maximum: 0.8 },
    gauge_max: { minimum: 1, maximum: 1e3 },
    unit: { maxLength: 12 }
  });
  function validateSpec3(spec) {
    const p = validateBase(spec, ID3, ["targets"], ["range_rings", "sweep_turns", "lock_at", "gauge_at", "gauge_max", "unit"], DEFAULT_PALETTE3);
    const raw = spec.parameters;
    p.range_rings = number(defaulted(raw.range_rings, 3), "range rings", 2, 5, true);
    p.sweep_turns = number(defaulted(raw.sweep_turns, 1), "sweep turns", 1, 3, true);
    p.lock_at = number(defaulted(raw.lock_at, 0.4), "lock fraction", 0.25, 0.5);
    p.gauge_at = number(defaulted(raw.gauge_at, 0.65), "gauge fraction", 0.6, 0.8);
    if (p.gauge_at - p.lock_at < 0.1 - 1e-9) fail("gauge must follow a completed lock window");
    p.gauge_max = number(defaulted(raw.gauge_max, 100), "gauge maximum", 1, 1e3);
    p.unit = text(defaulted(raw.unit, "%"), "unit", 12);
    if (!Array.isArray(raw.targets) || raw.targets.length < 2 || raw.targets.length > 4) fail("targets: 2\u20134 targets required");
    const seen = /* @__PURE__ */ new Set();
    p.targets = raw.targets.map((item, i) => {
      keys(item, ["id", "label", "bearing", "range", "value"], [], `target ${i}`);
      if (typeof item.id !== "string" || !/^[a-z][a-z0-9-]{0,19}$/u.test(item.id) || seen.has(item.id)) fail("unique short target IDs required");
      seen.add(item.id);
      const label5 = text(item.label, "target label", 65);
      fitText(label5, { maximum: 32, minimum: 26, maxLines: 2 });
      return {
        id: item.id,
        label: label5,
        bearing: number(item.bearing, "bearing", -170, 170),
        range: number(item.range, "range", 0.18, 0.92),
        value: number(item.value, "target value", 0, p.gauge_max)
      };
    });
    const points = p.targets.map(targetPoint);
    for (let a = 0; a < points.length; a++) for (let b = a + 1; b < points.length; b++) {
      if (Math.hypot(points[a].x - points[b].x, points[a].y - points[b].y) < 70) fail("target markers require at least 70 pixels of separation");
    }
    return { id: ID3, version: VERSION, parameters: p };
  }
  function targetPoint(target7) {
    const angle = target7.bearing * Math.PI / 180, radius = target7.range * RADAR_RADIUS;
    return { x: Math.sin(angle) * radius, y: -Math.cos(angle) * radius };
  }
  function arcPath(radius, fraction) {
    number(radius, "arc radius", 1, 300);
    number(fraction, "arc fraction", 0, 1);
    const start = -120 * Math.PI / 180, end = start + 240 * Math.PI / 180 * fraction;
    const a = { x: Math.sin(start) * radius, y: -Math.cos(start) * radius }, b = { x: Math.sin(end) * radius, y: -Math.cos(end) * radius };
    return `M${fmt(a.x)} ${fmt(a.y)}A${fmt(radius)} ${fmt(radius)} 0 ${fraction > 0.75 ? 1 : 0} 1 ${fmt(b.x)} ${fmt(b.y)}`;
  }
  function state3(p, seconds) {
    const time2 = sampleTime(seconds, p.duration);
    const animationDuration = (Math.round(p.duration * FPS) - FINAL_HOLD_FRAMES) / FPS;
    const holding = time2 >= animationDuration;
    const position = Math.min(time2, animationDuration) / animationDuration * p.targets.length;
    const index = Math.min(p.targets.length - 1, Math.floor(position)), local = position - index, target7 = p.targets[index];
    const scan = smooth(local / p.lock_at), lock = smooth((local - p.lock_at) / 0.1);
    const gauge = smooth((local - p.gauge_at) / (1 - p.gauge_at));
    return {
      seconds: time2,
      animationDuration,
      finalHoldSeconds: FINAL_HOLD_FRAMES / FPS,
      holding,
      index,
      local,
      targetId: target7.id,
      target: targetPoint(target7),
      phase: local < p.lock_at ? "scan" : local < p.gauge_at ? "lock" : "gauge",
      scanAngle: target7.bearing - 360 * p.sweep_turns * (1 - scan),
      lockProgress: lock,
      reticleSize: 86 - 52 * lock,
      gaugeProgress: gauge,
      gaugeValue: target7.value * gauge,
      gaugeRatio: target7.value / p.gauge_max * gauge,
      completed: index + (local === 1 ? 1 : 0)
    };
  }
  function sampleFrame3(spec, seconds) {
    return state3(validateSpec3(spec).parameters, seconds);
  }
  function renderFrame3(spec, seconds) {
    const p = validateSpec3(spec).parameters, s = state3(p, seconds), c = p.palette;
    const rings = Array.from({ length: p.range_rings }, (_, i) => `<circle r="${fmt(RADAR_RADIUS * (i + 1) / p.range_rings)}"/>`).join("");
    const ticks = Array.from({ length: 24 }, (_, i) => {
      const angle = i * Math.PI / 12, r2 = i % 3 ? RADAR_RADIUS - 8 : RADAR_RADIUS - 18;
      return `<path d="M${fmt(Math.sin(angle) * r2)} ${fmt(-Math.cos(angle) * r2)}L${fmt(Math.sin(angle) * (RADAR_RADIUS + 5))} ${fmt(-Math.cos(angle) * (RADAR_RADIUS + 5))}"/>`;
    }).join("");
    const markers = p.targets.map((target7, i) => {
      const point4 = targetPoint(target7), active = i === s.index, done2 = i < s.completed;
      return `<g transform="translate(${fmt(point4.x)} ${fmt(point4.y)})" opacity="${done2 ? 1 : active ? 0.7 : 0.24}"><circle r="7" fill="${active ? c.accent : c.muted}"/><text x="14" y="-12" font-size="21" fill="${c.ink}">${i + 1}</text></g>`;
    }).join("");
    const r = s.reticleSize, arm2 = 16;
    const reticle = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, y]) => `M${fmt(x * (r - arm2))} ${fmt(y * r)}H${fmt(x * r)}V${fmt(y * (r - arm2))}`).join("");
    const status = s.phase === "scan" ? "TARAMA" : s.phase === "lock" ? "HEDEF K\u0130L\u0130D\u0130" : "\xD6L\xC7\xDCM";
    const body = `<text x="90" y="550" fill="${c.accent}" font-size="28">${status} \xB7 ${s.index + 1}/${p.targets.length}</text><g transform="translate(540 920)"><g fill="none" stroke="${c.muted}" stroke-width="1.5" opacity="0.55">${rings}${ticks}<path d="M-320 0H320M0 -320V320"/></g><g transform="rotate(${fmt(s.scanAngle)})" opacity="${s.phase === "scan" ? 0.8 : 0.22}"><path d="M0 0L-52 -295A300 300 0 0 1 0 -300Z" fill="${c.accent}" fill-opacity="0.15"/><path d="M0 0V-300" stroke="${c.accent}" stroke-width="3"/></g>${markers}<g transform="translate(${fmt(s.target.x)} ${fmt(s.target.y)})" fill="none" stroke="${c.accent}" stroke-width="4" opacity="${fmt(s.lockProgress)}"><path d="${reticle}"/><circle r="${fmt(22 + 10 * (1 - s.lockProgress))}" stroke-width="1.5"/></g></g>${svgText(p.targets[s.index].label, { y: 1295, maximum: 32, minimum: 26, maxLines: 2, fill: c.ink })}<g transform="translate(540 1460)" fill="none"><path d="${arcPath(82, 1)}" stroke="${c.muted}" stroke-width="9" opacity="0.4"/>${s.gaugeRatio > 0 ? `<path d="${arcPath(82, s.gaugeRatio)}" stroke="${c.accent}" stroke-width="9"/>` : ""}<text data-hud-gauge-value="true" y="8" text-anchor="middle" fill="${c.ink}" font-size="36">${s.holding ? esc(String(p.targets[s.index].value)) : fmt(Math.round(s.gaugeValue * 10) / 10)}</text><text y="45" text-anchor="middle" fill="${c.muted}" font-size="24">${esc(p.unit)}</text></g>`;
    return frameShell(ID3, p, s.seconds, body);
  }
  var sample3 = sampleFrame3;
  var render3 = renderFrame3;

  // renderers/template-registry/modules/93fb574edcf4-vector-mass-transfer.mjs
  var fb574edcf4_vector_mass_transfer_exports = {};
  __export(fb574edcf4_vector_mass_transfer_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE4,
    ID: () => ID4,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA4,
    SOURCE_ID: () => SOURCE_ID4,
    render: () => render4,
    renderFrame: () => renderFrame4,
    sample: () => sample4,
    sampleFrame: () => sampleFrame4,
    validateSpec: () => validateSpec4
  });

  // renderers/template-registry/modules/1239407120d9-shared.mjs
  var VERSION2 = "1.0.0";
  var WIDTH2 = 1080;
  var HEIGHT2 = 1920;
  var FPS2 = 30;
  var COMMON_REQUIRED2 = ["title", "duration", "narration", "cues"];
  var InputError2 = class extends Error {
    constructor(message) {
      super(`TEMPLATE_INPUT: ${message}`);
      this.name = "InputError";
    }
  };
  function fail2(message) {
    throw new InputError2(message);
  }
  function keys2(value, required, optional = [], name = "object") {
    if (!value || typeof value !== "object" || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail2(`${name}: plain object required`);
    const own = Reflect.ownKeys(value);
    if (own.some((key) => typeof key !== "string" || !Object.getOwnPropertyDescriptor(value, key).enumerable || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), "value")) || required.some((key) => !Object.hasOwn(value, key)) || own.some((key) => !required.includes(key) && !optional.includes(key))) {
      fail2(`${name}: expected fields ${required.join(", ")}`);
    }
  }
  function number2(value, name, low, high, integer = false) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high || integer && !Number.isInteger(value)) fail2(`${name}: ${low}\u2013${high}${integer ? " integer" : ""} required`);
    return value;
  }
  function choice2(value, name, values) {
    if (typeof value !== "string" || !values.includes(value)) fail2(`${name}: ${values.join("/")} required`);
    return value;
  }
  function text2(value, name, maximum = 160) {
    if (typeof value !== "string" || !value.trim() || [...value].length > maximum || [...value].some((c) => new RegExp("\\p{C}", "u").test(c) && c !== "\n" && c !== "	")) fail2(`${name}: bounded plain text required`);
    return value.normalize("NFC").replace(/\s+/gu, " ").trim();
  }
  function textUnits2(value) {
    return [...value].reduce((sum, c) => sum + (c === " " ? 0.36 : /[MW@%ĞÖÜŞÇ]/u.test(c) ? 1.02 : /[ilıİ1.,:;'!|]/u.test(c) ? 0.4 : /[A-Z0-9]/u.test(c) ? 0.8 : c.codePointAt(0) > 12287 ? 1.15 : 0.7), 0);
  }
  function fitText2(value, { width = 900, maximum = 56, minimum = 28, maxLines = 3 } = {}) {
    number2(width, "text width", 1, WIDTH2);
    number2(maximum, "maximum font", 1, 120, true);
    number2(minimum, "minimum font", 1, maximum, true);
    number2(maxLines, "maximum lines", 1, 8, true);
    const normalized2 = text2(value, "layout text", 1500);
    for (let size = maximum; size >= minimum; size--) {
      const lines = [];
      let line5 = "";
      let fits = true;
      for (const word of normalized2.split(" ")) {
        if (textUnits2(word) * size > width) {
          fits = false;
          break;
        }
        const candidate = line5 ? `${line5} ${word}` : word;
        if (line5 && textUnits2(candidate) * size > width) {
          lines.push(line5);
          line5 = word;
        } else line5 = candidate;
      }
      if (line5) lines.push(line5);
      if (fits && lines.length <= maxLines) return {
        text: normalized2,
        lines,
        fontSize: size,
        lineHeight: size * 1.24,
        width,
        height: size * 1.24 * lines.length
      };
    }
    fail2("text does not fit without losing words; shorten the input");
  }
  function contrastRatio2(first, second) {
    const luminance = (color2) => {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail2("contrast: six-digit hex required");
      const channels = [1, 3, 5].map((index) => Number.parseInt(color2.slice(index, index + 2), 16) / 255).map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const a = luminance(first), b = luminance(second);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }
  function palette2(value, defaults, accentMinimum = 3) {
    const raw = value === void 0 ? defaults : value;
    keys2(raw, ["background", "ink", "muted", "accent"], [], "palette");
    const result2 = {};
    for (const [key, color2] of Object.entries(raw)) {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail2(`palette.${key}: six-digit hex required`);
      result2[key] = color2.toUpperCase();
    }
    for (const [role, minimum] of [["ink", 4.5], ["muted", 4.5], ["accent", accentMinimum]]) {
      if (contrastRatio2(result2[role], result2.background) < minimum) fail2(`palette.${role}: contrast must be at least ${minimum} against background`);
    }
    return result2;
  }
  function validateCueArray2(value) {
    if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype) fail2("cues: plain array required");
    const descriptors = Object.getOwnPropertyDescriptors(value);
    const length = descriptors.length;
    if (!length || !Object.hasOwn(length, "value") || !Number.isInteger(length.value) || length.value < 1 || length.value > 24) fail2("cues: 1\u201324 supplied cues required");
    const own = Reflect.ownKeys(descriptors);
    for (const key of own) {
      if (key === "length") continue;
      const descriptor = descriptors[key];
      if (typeof key !== "string" || !/^(0|[1-9]\d*)$/u.test(key) || Number(key) >= length.value || !descriptor.enumerable || !Object.hasOwn(descriptor, "value")) fail2("cues: dense enumerable data entries only");
    }
    if (own.length !== length.value + 1) fail2("cues: sparse arrays are not allowed");
    return value;
  }
  function validateBase2(spec, id, required, optional, defaults) {
    keys2(spec, ["id", "version", "parameters"], [], "spec");
    if (spec.id !== id || spec.version !== VERSION2) fail2("unknown renderer ID or template version");
    const raw = spec.parameters;
    keys2(raw, [...COMMON_REQUIRED2, ...required], [...optional, "palette"], "parameters");
    validateCueArray2(raw.cues);
    const title = text2(raw.title, "title", 160);
    fitText2(title, { maximum: 64, minimum: 38, maxLines: 4 });
    const duration = number2(raw.duration, "duration", 3, 45);
    if (Math.abs(duration * FPS2 - Math.round(duration * FPS2)) > 1e-7) fail2("duration: use a 30 fps frame boundary");
    const narration = text2(raw.narration, "narration", 1500);
    let previous = 0;
    const cues = raw.cues.map((cue, i) => {
      keys2(cue, ["start", "end", "text"], [], `cue ${i}`);
      const start = number2(cue.start, "cue start", 0, duration);
      const end = number2(cue.end, "cue end", 0, duration);
      const value = text2(cue.text, "cue text", 95);
      if (start < previous || end - start < 0.2 - 1e-9) fail2("cues: ordered, nonoverlapping and at least 0.2 seconds required");
      fitText2(value, { width: 890, maximum: 44, minimum: 30, maxLines: 3 });
      previous = end;
      return { start, end, text: value };
    });
    if (cues.map((c) => c.text).join(" ") !== narration) fail2("cues must contain the whole narration in the same order");
    return { title, duration, narration, cues, palette: palette2(raw.palette, defaults, 4.5) };
  }
  function windowPair2(value, name) {
    if (!Array.isArray(value) || value.length !== 2) fail2(`${name}: two normalized times required`);
    const a = number2(value[0], `${name} start`, 0, 1);
    const b = number2(value[1], `${name} end`, 0, 1);
    if (b - a < 0.1 - 1e-9) fail2(`${name}: at least 10% of duration required`);
    return [a, b];
  }
  var defaulted2 = (value, fallback) => value === void 0 ? fallback : value;
  var clamp2 = (x) => Math.max(0, Math.min(1, x));
  var smooth2 = (x) => {
    const p = clamp2(x);
    return p * p * (3 - 2 * p);
  };
  var lerp2 = (a, b, p) => a + (b - a) * p;
  function phaseAt2(seconds, duration, window) {
    return smooth2((seconds / duration - window[0]) / (window[1] - window[0]));
  }
  function sampleTime2(seconds, duration) {
    return Math.min(number2(seconds, "seconds", 0, Number.MAX_SAFE_INTEGER), duration);
  }
  function motionTime2(seconds, duration) {
    number2(duration, "motion duration", 3, 45);
    const time2 = sampleTime2(seconds, duration);
    const animationDuration = (Math.round(duration * FPS2) - 18) / FPS2;
    return time2 >= animationDuration ? duration : time2 / animationDuration * duration;
  }
  function activeCue2(cues, seconds) {
    return cues.find((c) => seconds >= c.start && seconds < c.end) ?? null;
  }
  function esc2(value) {
    return String(value).replace(/[&<>"']/gu, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]);
  }
  function fmt2(value) {
    if (!Number.isFinite(value)) fail2("nonfinite SVG coordinate");
    return String(Number(value.toFixed(5)));
  }
  function svgText2(value, { x = 90, y, width = 900, maximum = 56, minimum = 28, maxLines = 3, fill = "#18202A", anchor = "start", weight = 600 } = {}) {
    const fit = fitText2(value, { width, maximum, minimum, maxLines });
    return `<text x="${fmt2(x)}" y="${fmt2(y)}" fill="${esc2(fill)}" font-size="${fit.fontSize}" font-weight="${weight}" text-anchor="${anchor}" data-template-text="true" data-full-text="${esc2(fit.text)}" data-slot-width="${width}" data-estimated-height="${fmt2(fit.height)}">${fit.lines.map((line5, i) => `<tspan x="${fmt2(x)}" dy="${i === 0 ? 0 : fmt2(fit.lineHeight)}">${esc2(line5)}</tspan>`).join("")}</text>`;
  }
  function frameShell2(id, p, seconds, body, options = {}) {
    const cue = options.captions === false ? null : activeCue2(p.cues, seconds);
    const cueIndex = cue ? p.cues.indexOf(cue) : -1;
    const c = p.palette;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH2} ${HEIGHT2}" width="${WIDTH2}" height="${HEIGHT2}" role="img" aria-label="${esc2(p.title)}" data-renderer="${id}" data-seconds="${fmt2(seconds)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${svgText2(p.title, { y: 165, maximum: 64, minimum: 38, maxLines: 4, fill: c.ink })}${body}<path d="M90 1585H990" stroke="${c.muted}" stroke-width="1" opacity="0.45"/>${cue ? `<g id="family-cue-${cueIndex}" data-cue-start="${fmt2(cue.start)}" data-cue-end="${fmt2(cue.end)}">${svgText2(cue.text, { x: 95, y: 1655, width: 890, maximum: 44, minimum: 30, maxLines: 3, fill: c.ink })}</g>` : ""}<text x="90" y="1840" fill="${c.muted}" font-size="20">YEREL \u015EABLON \xB7 \u0130NSAN \u0130NCELEMES\u0130 BEKL\u0130YOR</text></g></svg>`;
  }
  function deepFreeze(value) {
    if (value && typeof value === "object") {
      for (const child of Object.values(value)) deepFreeze(child);
      Object.freeze(value);
    }
    return value;
  }

  // renderers/template-registry/modules/93fb574edcf4-vector-mass-transfer.mjs
  var ID4 = "vector-mass-transfer";
  var SOURCE_ID4 = "source-mg-style-01-flat-vector";
  var DEFAULT_PALETTE4 = Object.freeze({ background: "#F5F1E8", ink: "#243D3C", muted: "#596761", accent: "#9B4431" });
  var PARAMETER_SCHEMA4 = Object.freeze({ stores: { minItems: 2, maxItems: 2, item: { label: { maxLength: 50 }, amount: { minimum: 0, maximum: 1e3 } } }, transfer_amount: { minimum: 1, maximum: "source amount" }, unit: { maxLength: 10 }, batches: { minimum: 2, maximum: 5, integer: true }, lift: { minimum: 60, maximum: 160 }, transfer_window: { normalized: true, minimumSpan: 0.3 } });
  function validateSpec4(spec) {
    const p = validateBase2(spec, ID4, ["stores", "transfer_amount", "unit"], ["batches", "lift", "transfer_window"], DEFAULT_PALETTE4), raw = spec.parameters;
    if (!Array.isArray(raw.stores) || raw.stores.length !== 2) fail2("stores: exactly two reservoirs required");
    p.stores = raw.stores.map((item, i) => {
      keys2(item, ["label", "amount"]);
      const label5 = text2(item.label, "store label", 50);
      fitText2(label5, { width: 380, maximum: 34, minimum: 28, maxLines: 3 });
      return { label: label5, amount: number2(item.amount, "store amount", i === 0 ? 1 : 0, 1e3) };
    });
    p.transfer_amount = number2(raw.transfer_amount, "transfer amount", 1, p.stores[0].amount);
    p.unit = text2(raw.unit, "unit", 10);
    fitText2(p.unit, { width: 380, maximum: 26, minimum: 24, maxLines: 1 });
    p.batches = number2(defaulted2(raw.batches, 3), "batches", 2, 5, true);
    p.lift = number2(defaulted2(raw.lift, 110), "lift", 60, 160);
    p.transfer_window = windowPair2(defaulted2(raw.transfer_window, [0.14, 0.84]), "transfer window");
    if (p.transfer_window[1] - p.transfer_window[0] < 0.3 - 1e-9) fail2("transfer window: at least 30% of clip required");
    return { id: ID4, version: VERSION2, parameters: p };
  }
  var WIDTH3 = 250;
  var BASE = 1260;
  var AREA_BUDGET = 96e3;
  function state4(p, seconds) {
    const time2 = sampleTime2(seconds, p.duration), u = clamp2((motionTime2(time2, p.duration) / p.duration - p.transfer_window[0]) / (p.transfer_window[1] - p.transfer_window[0]));
    const position = u * p.batches, index = Math.min(p.batches - 1, Math.floor(position)), local = position - index;
    const batch = p.transfer_amount / p.batches, depart = smooth2(local / 0.18), arrive = smooth2((local - 0.72) / 0.28), travel = smooth2((local - 0.18) / 0.54);
    const withdrawn = (index + depart) * batch, received = (index + arrive) * batch;
    const source = p.stores[0].amount - withdrawn, destination = p.stores[1].amount + received, transit = withdrawn - received, total = p.stores[0].amount + p.stores[1].amount;
    const unitArea = AREA_BUDGET / total, side = Math.sqrt(Math.max(0, transit * unitArea));
    const topSource = BASE - source * unitArea / WIDTH3, topDestination = BASE - destination * unitArea / WIDTH3;
    const parcel = { x: lerp2(295, 785, travel), y: lerp2(topSource, topDestination, travel) - side / 2 - p.lift * Math.sin(Math.PI * travel), side };
    const fills = [{ x: 170, y: topSource, width: WIDTH3, height: BASE - topSource }, { x: 660, y: topDestination, width: WIDTH3, height: BASE - topDestination }];
    return {
      seconds: time2,
      phase: u === 0 ? "before" : u === 1 ? "after" : "transfer",
      batchIndex: index,
      local,
      source,
      destination,
      transit,
      total,
      unitArea,
      areaTotal: (source + destination + transit) * unitArea,
      parcel,
      fills,
      progress: u
    };
  }
  function sample4(spec, seconds) {
    return state4(validateSpec4(spec).parameters, seconds);
  }
  var sampleFrame4 = sample4;
  function render4(spec, seconds) {
    const p = validateSpec4(spec).parameters, s = state4(p, seconds), c = p.palette;
    const fills = s.fills.map((box3, i) => `<rect x="${fmt2(box3.x)}" y="${fmt2(box3.y)}" width="${box3.width}" height="${fmt2(box3.height)}" fill="${c.accent}"/><path d="M${box3.x - 8} 1260H${box3.x + 258}" stroke="${c.ink}" stroke-width="4"/>${svgText2(p.stores[i].label, { x: 150 + i * 490, y: 620, width: 380, maximum: 34, minimum: 28, maxLines: 3, fill: c.ink })}<text x="${box3.x}" y="1335" fill="${c.ink}" font-size="48" font-weight="700">${fmt2(Math.round((i ? s.destination : s.source) * 100) / 100)}</text><text x="${box3.x}" y="1385" fill="${c.muted}" font-size="26">${esc2(p.unit)}</text>`).join("");
    const parcel = s.parcel.side > 1e-8 ? `<rect data-transit-area="${fmt2(s.transit * s.unitArea)}" x="${fmt2(s.parcel.x - s.parcel.side / 2)}" y="${fmt2(s.parcel.y - s.parcel.side / 2)}" width="${fmt2(s.parcel.side)}" height="${fmt2(s.parcel.side)}" fill="${c.accent}" stroke="${c.ink}" stroke-width="3"/>` : "";
    const body = `<path d="M170 1460H910" stroke="${c.muted}" stroke-width="1"/>${fills}${parcel}<text x="170" y="1510" fill="${c.muted}" font-size="28">TOPLAM ${fmt2(s.total)} ${esc2(p.unit)}</text>`;
    return frameShell2(ID4, p, s.seconds, body);
  }
  var renderFrame4 = render4;

  // renderers/template-registry/modules/b1d2640cfb89-cel-contour-boil.mjs
  var b1d2640cfb89_cel_contour_boil_exports = {};
  __export(b1d2640cfb89_cel_contour_boil_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE5,
    ID: () => ID5,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA5,
    SOURCE_ID: () => SOURCE_ID5,
    objectContour: () => objectContour,
    render: () => render5,
    renderFrame: () => renderFrame5,
    sample: () => sample5,
    sampleFrame: () => sampleFrame5,
    validateSpec: () => validateSpec5
  });

  // renderers/template-registry/modules/07c4eb72721d-geometry.mjs
  function path(points, closed = true) {
    if (!Array.isArray(points) || points.length < 2) return "";
    return points.map((p, i) => `${i ? "L" : "M"}${fmt2(p.x)} ${fmt2(p.y)}`).join("") + (closed ? "Z" : "");
  }
  function area(points) {
    return Math.abs(points.reduce((sum, p, i) => {
      const q = points[(i + 1) % points.length];
      return sum + p.x * q.y - p.y * q.x;
    }, 0) / 2);
  }
  function bounds(points) {
    if (!points.length) fail2("nonempty geometry required");
    return { left: Math.min(...points.map((p) => p.x)), right: Math.max(...points.map((p) => p.x)), top: Math.min(...points.map((p) => p.y)), bottom: Math.max(...points.map((p) => p.y)) };
  }
  function rotate(point4, degrees, pivot = { x: 0, y: 0 }) {
    const a = degrees * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return { x: pivot.x + point4.x * c - point4.y * s, y: pivot.y + point4.x * s + point4.y * c };
  }
  function clipHalfPlane(points, nx, ny, limit, keepLess = true) {
    const output = [], value = (p) => nx * p.x + ny * p.y - limit, inside = (v) => keepLess ? v <= 1e-9 : v >= -1e-9;
    for (let i = 0; i < points.length; i++) {
      const a = points[i], b = points[(i + 1) % points.length], va = value(a), vb = value(b), ia = inside(va), ib = inside(vb);
      if (ia) output.push({ ...a });
      if (ia !== ib) {
        const t = va / (va - vb);
        output.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
      }
    }
    return output.filter((p, i, all) => i === 0 || Math.hypot(p.x - all[i - 1].x, p.y - all[i - 1].y) > 1e-8);
  }

  // renderers/template-registry/modules/b1d2640cfb89-cel-contour-boil.mjs
  var ID5 = "cel-contour-boil";
  var SOURCE_ID5 = "source-mg-style-05-cel-boil";
  var DEFAULT_PALETTE5 = Object.freeze({ background: "#F4F0E5", ink: "#3A332D", muted: "#696051", accent: "#53613E" });
  var PARAMETER_SCHEMA5 = Object.freeze({ object: { enum: ["kettle", "watering-can"] }, label: { maxLength: 110 }, hold_frames: { enum: [2, 3] }, boil_amount: { minimum: 0.5, maximum: 3 }, stroke_width: { minimum: 3, maximum: 7 }, tilt_degrees: { minimum: -18, maximum: 18 }, action_window: { normalized: true, minimumSpan: 0.3 } });
  function validateSpec5(spec) {
    const p = validateBase2(spec, ID5, ["object", "label"], ["hold_frames", "boil_amount", "stroke_width", "tilt_degrees", "action_window"], DEFAULT_PALETTE5), r = spec.parameters;
    p.object = choice2(r.object, "object", ["kettle", "watering-can"]);
    p.label = text2(r.label, "label", 110);
    fitText2(p.label, { maximum: 38, minimum: 28, maxLines: 3 });
    p.hold_frames = number2(defaulted2(r.hold_frames, 2), "held frames", 2, 3, true);
    p.boil_amount = number2(defaulted2(r.boil_amount, 1.6), "ink breathing", 0.5, 3);
    p.stroke_width = number2(defaulted2(r.stroke_width, 5), "stroke width", 3, 7);
    p.tilt_degrees = number2(defaulted2(r.tilt_degrees, -12), "tilt degrees", -18, 18);
    p.action_window = windowPair2(defaulted2(r.action_window, [0.12, 0.88]), "action window");
    if (p.action_window[1] - p.action_window[0] < 0.3 - 1e-9) fail2("action window: at least 30% of clip required");
    return { id: ID5, version: VERSION2, parameters: p };
  }
  function objectContour(p, cel) {
    return Array.from({ length: 64 }, (_, i) => {
      const angle = i * Math.PI / 32, dx = Math.cos(angle), dy = Math.sin(angle);
      const r = p.object === "kettle" ? 1 / Math.hypot(dx / 175, dy / 205) : 1 / Math.pow(Math.abs(dx / 170) ** 6 + Math.abs(dy / 145) ** 6, 1 / 6);
      const jitter = p.boil_amount * (Math.sin(i * 0.71 + cel * 1.63) + 0.5 * Math.sin(i * 1.21 - cel * 0.93)) / 1.5;
      return { x: dx * (r + jitter), y: dy * (r + jitter) };
    });
  }
  function state5(p, seconds) {
    const time2 = sampleTime2(seconds, p.duration), frame = Math.floor(motionTime2(time2, p.duration) * 30 + 1e-8), cel = Math.floor(frame / p.hold_frames), heldSeconds = cel * p.hold_frames / 30;
    const u = (heldSeconds / p.duration - p.action_window[0]) / (p.action_window[1] - p.action_window[0]);
    const pose2 = smooth2(u / 0.3) * (1 - smooth2((u - 0.72) / 0.28)), angle = p.tilt_degrees * pose2, contour = objectContour(p, cel);
    const extremities = [{ x: -320, y: -240 }, { x: 320, y: -240 }, { x: 320, y: 210 }, { x: -320, y: 210 }];
    const world = [...contour, ...extremities].map((point4) => rotate(point4, angle, { x: 540, y: 940 }));
    return { seconds: time2, frame, cel, heldSeconds, angle, phase: pose2 === 0 ? "rest" : "tilt", contour, path: path(contour), area: area(contour), bounds: bounds(world) };
  }
  function sample5(spec, seconds) {
    return state5(validateSpec5(spec).parameters, seconds);
  }
  var sampleFrame5 = sample5;
  function render5(spec, seconds) {
    const p = validateSpec5(spec).parameters, s = state5(p, seconds), c = p.palette;
    const anatomy = p.object === "kettle" ? '<path d="M-135 -75L-315 -125L-250 -20L-140 55Z"/><path d="M135 -130C320 -185 320 150 130 120M145 -90C255 -125 255 105 145 80" fill="none"/><path d="M-90 -200Q0 -225 90 -200L75 -184H-75Z"/><path d="M-20 -220Q0 -240 20 -220V-210H-20Z"/>' : '<path d="M-145 65L-320 -180L-280 -220L-90 -70Z"/><path d="M140 -105C315 -200 315 160 140 110M150 -65C250 -110 250 100 150 65" fill="none"/><path d="M-75 -140Q-85 -235 40 -235Q125 -225 105 -145" fill="none"/><path d="M-70 -145H70" fill="none"/>';
    const body = `<path d="M180 1260H900" stroke="${c.muted}" stroke-width="2"/><g transform="translate(540 940) rotate(${fmt2(s.angle)})" fill="${c.background}" stroke="${c.ink}" stroke-width="${fmt2(p.stroke_width)}" stroke-linejoin="round" stroke-linecap="round">${anatomy}<path data-held-cel="${s.cel}" d="${s.path}"/><path d="M-105 75Q0 125 105 75" stroke="${c.accent}" fill="none"/></g>${svgText2(p.label, { y: 1375, maximum: 38, minimum: 28, maxLines: 3, fill: c.ink })}`;
    return frameShell2(ID5, p, s.seconds, body);
  }
  var renderFrame5 = render5;

  // renderers/template-registry/modules/691f4dcd3ea2-cutout-pin-assembly.mjs
  var f4dcd3ea2_cutout_pin_assembly_exports = {};
  __export(f4dcd3ea2_cutout_pin_assembly_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE6,
    ID: () => ID6,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA6,
    SOURCE_ID: () => SOURCE_ID6,
    panelGeometry: () => panelGeometry,
    render: () => render6,
    renderFrame: () => renderFrame6,
    sample: () => sample6,
    sampleFrame: () => sampleFrame6,
    validateSpec: () => validateSpec6
  });
  var ID6 = "cutout-pin-assembly";
  var SOURCE_ID6 = "source-mg-style-06-collage";
  var DEFAULT_PALETTE6 = Object.freeze({ background: "#F4EDE2", ink: "#352F2C", muted: "#6D5E53", accent: "#93452E" });
  var PARAMETER_SCHEMA6 = Object.freeze({ pieces: { minItems: 2, maxItems: 4, item: { shape: { enum: ["arch", "ticket", "wedge"] }, label: { maxLength: 45 }, hinge: { enum: ["left", "right"] }, final_angle: { minimum: -6, maximum: 6 } } }, fold_angle: { minimum: 24, maximum: 32 }, assembly_window: { normalized: true, minimumSpan: 0.3 } });
  function validateSpec6(spec) {
    const p = validateBase2(spec, ID6, ["pieces"], ["fold_angle", "assembly_window"], DEFAULT_PALETTE6), r = spec.parameters;
    if (!Array.isArray(r.pieces) || r.pieces.length < 2 || r.pieces.length > 4) fail2("pieces: 2\u20134 original panels required");
    p.pieces = r.pieces.map((item) => {
      keys2(item, ["shape", "label", "hinge", "final_angle"]);
      const label5 = text2(item.label, "piece label", 45);
      fitText2(label5, { width: 320, maximum: 30, minimum: 26, maxLines: 2 });
      return { shape: choice2(item.shape, "piece shape", ["arch", "ticket", "wedge"]), label: label5, hinge: choice2(item.hinge, "hinge", ["left", "right"]), final_angle: number2(item.final_angle, "final angle", -6, 6) };
    });
    p.fold_angle = number2(defaulted2(r.fold_angle, 28), "fold angle", 24, 32);
    p.assembly_window = windowPair2(defaulted2(r.assembly_window, [0.08, 0.84]), "assembly window");
    if (p.assembly_window[1] - p.assembly_window[0] < 0.3 - 1e-9) fail2("assembly window: at least 30% required");
    return { id: ID6, version: VERSION2, parameters: p };
  }
  function panelGeometry(shape, hinge) {
    const sign = hinge === "left" ? 1 : -1, points = shape === "ticket" ? [{ x: -26, y: -26 }, { x: 370, y: -26 }, { x: 394, y: -2 }, { x: 394, y: 130 }, { x: 370, y: 154 }, { x: -2, y: 154 }, { x: -26, y: 130 }] : shape === "wedge" ? [{ x: -26, y: 24 }, { x: 394, y: -26 }, { x: 394, y: 154 }, { x: -26, y: 154 }] : [{ x: -26, y: 70 }, { x: -26, y: -26 }, { x: 394, y: -26 }, { x: 394, y: 154 }, { x: -26, y: 154 }];
    const mirrored = points.map((p) => ({ x: p.x * sign, y: p.y }));
    const outline = shape === "arch" ? `M${fmt2(-26 * sign)} 154V70Q${fmt2(-26 * sign)} -26 ${fmt2(70 * sign)} -26H${fmt2(298 * sign)}Q${fmt2(394 * sign)} -26 ${fmt2(394 * sign)} 70V154Z` : path(mirrored);
    return { outline, points: mirrored, sign };
  }
  function state6(p, seconds) {
    const time2 = sampleTime2(seconds, p.duration), start = p.assembly_window[0], span = p.assembly_window[1] - start, u = motionTime2(seconds, p.duration) / p.duration;
    const pieces = p.pieces.map((piece, i) => {
      const progress = smooth2((u - start - i * span * 0.16) / (span * 0.45)), sign = piece.hinge === "left" ? 1 : -1;
      const angle = piece.final_angle + sign * p.fold_angle * (1 - progress), pivot = { x: sign === 1 ? 350 : 730, y: 660 + i * 160 };
      const geometry = panelGeometry(piece.shape, piece.hinge), world = geometry.points.map((point4) => rotate(point4, angle, pivot));
      const shadow = world.map((point4) => ({ x: point4.x + 7, y: point4.y + 8 }));
      return { index: i, progress, angle, pivot, geometry, world, bounds: bounds([...world, ...shadow]), labelOpacity: smooth2((progress - 0.72) / 0.28) };
    });
    return { seconds: time2, phase: pieces.every((piece) => piece.progress === 1) ? "assembled" : pieces.every((piece) => piece.progress === 0) ? "waiting" : "assembly", pieces };
  }
  function sample6(spec, seconds) {
    return state6(validateSpec6(spec).parameters, seconds);
  }
  var sampleFrame6 = sample6;
  function render6(spec, seconds) {
    const p = validateSpec6(spec).parameters, s = state6(p, seconds), c = p.palette;
    const layers = s.pieces.map((piece) => {
      const { pivot, angle, geometry, index } = piece, labelX = geometry.sign === 1 ? 20 : -340;
      return `<g transform="translate(${pivot.x + 7} ${pivot.y + 8}) rotate(${fmt2(angle)})" opacity="0.18"><path d="${geometry.outline}" fill="${c.muted}"/></g><g transform="translate(${pivot.x} ${pivot.y}) rotate(${fmt2(angle)})"><path d="${geometry.outline}" fill="${c.background}" stroke="${c.ink}" stroke-width="4" stroke-linejoin="round"/><path d="M${geometry.sign * 24} 118H${geometry.sign * 330}" stroke="${c.accent}" stroke-width="5"/><g opacity="${fmt2(piece.labelOpacity)}">${svgText2(p.pieces[index].label, { x: labelX, y: 56, width: 320, maximum: 30, minimum: 26, maxLines: 2, fill: c.ink })}</g></g><circle data-fixed-pin="${index}" cx="${pivot.x}" cy="${pivot.y}" r="12" fill="${c.accent}" stroke="${c.ink}" stroke-width="2"/>`;
    }).join("");
    return frameShell2(ID6, p, s.seconds, `<path d="M240 1510H840" stroke="${c.muted}" stroke-width="2"/>${layers}`);
  }
  var renderFrame6 = render6;

  // renderers/template-registry/modules/e3d757d8a6a6-caption-impact-rig.mjs
  var e3d757d8a6a6_caption_impact_rig_exports = {};
  __export(e3d757d8a6a6_caption_impact_rig_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE7,
    ID: () => ID7,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA7,
    SOURCE_ID: () => SOURCE_ID7,
    layoutCaption: () => layoutCaption,
    render: () => render7,
    renderFrame: () => renderFrame7,
    sample: () => sample7,
    sampleFrame: () => sampleFrame7,
    validateSpec: () => validateSpec7
  });
  var ID7 = "caption-impact-rig";
  var SOURCE_ID7 = "source-mg-style-18-hanazi";
  var DEFAULT_PALETTE7 = Object.freeze({ background: "#F6F0E8", ink: "#352B2C", muted: "#6B5B5D", accent: "#A03838" });
  var PARAMETER_SCHEMA7 = Object.freeze({ focus: { maxLength: 28, uniqueWholeExpressionInOneCue: true }, punctuation: { enum: ["!", "?", "."] }, impact_fraction: { minimum: 0.18, maximum: 0.65 }, impact_seconds: { minimum: 0.12, maximum: 0.4 }, cue_end_margin: 0.1, terminal_hold_seconds: 0.6 });
  function layoutCaption(value, focus = null) {
    const index = focus === null ? -1 : value.indexOf(focus), tokens = [];
    const words2 = [...value.matchAll(/\S+/gu)].map((match) => ({ text: match[0], start: match.index, end: match.index + match[0].length }));
    if (index < 0) tokens.push(...words2.map((word) => ({ text: word.text, focus: false })));
    else {
      const first = words2.findIndex((word) => word.end > index);
      let last = first;
      while (last + 1 < words2.length && words2[last + 1].start < index + focus.length) last++;
      tokens.push(...words2.slice(0, first).map((word) => ({ text: word.text, focus: false })));
      tokens.push({ text: value.slice(words2[first].start, words2[last].end), focus: true });
      tokens.push(...words2.slice(last + 1).map((word) => ({ text: word.text, focus: false })));
    }
    for (let size = 76; size >= 48; size--) {
      const rows = [];
      let row = [], width = 0, valid = true;
      for (const token2 of tokens) {
        const advance = textUnits2(token2.text) * size;
        if (advance > 740) {
          valid = false;
          break;
        }
        const gap = row.length ? textUnits2(" ") * size : 0;
        if (row.length && width + gap + advance > 740) {
          rows.push(row);
          row = [];
          width = 0;
        }
        const actualGap = row.length ? textUnits2(" ") * size : 0;
        row.push({ ...token2, x: width + actualGap, width: advance });
        width += actualGap + advance;
      }
      if (row.length) rows.push(row);
      if (valid && rows.length <= 5) return { fontSize: size, lineHeight: size * 1.24, rows: rows.map((row2) => ({ text: row2.map((token2) => token2.text).join(" "), tokens: row2 })) };
    }
    fail2("caption/focus cannot fit without splitting or losing words");
  }
  function validateSpec7(spec) {
    const p = validateBase2(spec, ID7, ["focus", "punctuation"], ["impact_fraction", "impact_seconds"], DEFAULT_PALETTE7), r = spec.parameters;
    p.focus = text2(r.focus, "focus", 28);
    p.punctuation = choice2(r.punctuation, "punctuation", ["!", "?", "."]);
    const index = p.narration.indexOf(p.focus), after = index + p.focus.length;
    if (index < 0 || p.narration.indexOf(p.focus, index + 1) >= 0 || /[\p{L}\p{N}]/u.test(p.narration[index - 1] ?? "") || /[\p{L}\p{N}]/u.test(p.narration[after] ?? "")) fail2("focus must occur exactly once as a whole expression");
    const cueIndex = p.cues.findIndex((cue2) => cue2.text.includes(p.focus));
    if (cueIndex < 0) fail2("focus must fit wholly inside one supplied cue");
    p.impact_fraction = number2(defaulted2(r.impact_fraction, 0.3), "impact fraction", 0.18, 0.65);
    p.impact_seconds = number2(defaulted2(r.impact_seconds, 0.18), "impact seconds", 0.12, 0.4);
    const cue = p.cues[cueIndex];
    if ((cue.end - cue.start) * (1 - p.impact_fraction) - p.impact_seconds < 0.1 - 1e-9) fail2("focus cue needs 0.1 second reading hold after impact");
    const holdStart = (Math.round(p.duration * 30) - 18) / 30, impactEnd = cue.start + (cue.end - cue.start) * p.impact_fraction + p.impact_seconds;
    if (impactEnd > holdStart + 1e-9) fail2("focus impact must finish before the final 0.6 second hold; move emphasis earlier or extend duration");
    if (cue.end > holdStart + 1e-9 && cue.end < p.duration - 1e-9) fail2("focus cue cannot disappear during the final 0.6 second hold");
    p.cues.forEach((cue2, i) => layoutCaption(cue2.text, i === cueIndex ? p.focus : null));
    return { id: ID7, version: VERSION2, parameters: p };
  }
  function state7(p, seconds) {
    const time2 = sampleTime2(seconds, p.duration), cue = activeCue2(p.cues, time2), cueIndex = cue ? p.cues.indexOf(cue) : -1;
    const focusCueIndex = p.cues.findIndex((cue2) => cue2.text.includes(p.focus)), focusCue = p.cues[focusCueIndex];
    const impactStart = focusCue.start + (focusCue.end - focusCue.start) * p.impact_fraction;
    const activeFocus = cueIndex === focusCueIndex, impact = activeFocus ? smooth2((time2 - impactStart) / p.impact_seconds) : 0;
    const layout = cue ? layoutCaption(cue.text, activeFocus ? p.focus : null) : null;
    return {
      seconds: time2,
      cueIndex,
      focusCueIndex,
      impactStart,
      impact,
      layout,
      phase: !cue ? "gap" : !activeFocus || time2 < impactStart ? "reading" : impact < 1 ? "impact" : "emphasis"
    };
  }
  function sample7(spec, seconds) {
    return state7(validateSpec7(spec).parameters, seconds);
  }
  var sampleFrame7 = sample7;
  function render7(spec, seconds) {
    const p = validateSpec7(spec).parameters, s = state7(p, seconds), c = p.palette;
    let body = "";
    if (s.layout) {
      const y0 = 790, rows = s.layout.rows.map((row, i) => {
        const y = y0 + i * s.layout.lineHeight;
        return `<text x="100" y="${fmt2(y)}" fill="${c.ink}" font-size="${s.layout.fontSize}" font-weight="550" data-template-text="true" data-full-text="${esc2(row.text)}" data-slot-width="740">${row.tokens.map((token2, j) => `<tspan x="${fmt2(100 + token2.x)}" font-weight="${token2.focus ? 800 : 550}" fill="${token2.focus && s.impact > 0 ? c.accent : c.ink}">${esc2(token2.text)}${j < row.tokens.length - 1 ? " " : ""}</tspan>`).join("")}</text>`;
      }).join("");
      const lines = s.layout.rows.flatMap((row, i) => row.tokens.filter((t) => t.focus).map((token2) => `<path d="M${fmt2(100 + token2.x)} ${fmt2(y0 + i * s.layout.lineHeight + 14)}H${fmt2(100 + token2.x + token2.width * s.impact)}" stroke="${c.accent}" stroke-width="7"/>`)).join("");
      const cue = p.cues[s.cueIndex];
      body = `<g id="family-cue-${s.cueIndex}" data-cue-start="${fmt2(cue.start)}" data-cue-end="${fmt2(cue.end)}">${rows}${lines}<text x="${fmt2(920 + 10 * (1 - s.impact))}" y="1150" fill="${c.accent}" font-size="190" font-weight="800" text-anchor="middle" opacity="${fmt2(s.impact)}">${esc2(p.punctuation)}</text></g>`;
    }
    return frameShell2(ID7, p, s.seconds, body, { captions: false });
  }
  var renderFrame7 = render7;

  // renderers/template-registry/modules/f5239a9fb835-sticker-peel-callout.mjs
  var f5239a9fb835_sticker_peel_callout_exports = {};
  __export(f5239a9fb835_sticker_peel_callout_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE8,
    ID: () => ID8,
    PANEL: () => PANEL,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA8,
    SOURCE_ID: () => SOURCE_ID8,
    peelGeometry: () => peelGeometry,
    render: () => render8,
    renderFrame: () => renderFrame8,
    sample: () => sample8,
    sampleFrame: () => sampleFrame8,
    validateSpec: () => validateSpec8
  });
  var ID8 = "sticker-peel-callout";
  var SOURCE_ID8 = "source-mg-style-19-paperclip";
  var DEFAULT_PALETTE8 = Object.freeze({ background: "#EDF1F3", ink: "#253643", muted: "#5A6771", accent: "#345C86" });
  var PANEL = Object.freeze({ x: 170, y: 740, width: 740, height: 460 });
  var PARAMETER_SCHEMA8 = Object.freeze({ headline: { maxLength: 80 }, reveal_label: { maxLength: 12 }, note: { maxLength: 120 }, side: { enum: ["left", "right"] }, peel_depth: { minimum: 260, maximum: 350 }, curl: { minimum: 0.08, maximum: 0.18 }, peel_window: { normalized: true, minimumSpan: 0.3 } });
  function validateSpec8(spec) {
    const p = validateBase2(spec, ID8, ["headline", "reveal_label", "note", "side"], ["peel_depth", "curl", "peel_window"], DEFAULT_PALETTE8), r = spec.parameters;
    p.headline = text2(r.headline, "sticker headline", 80);
    fitText2(p.headline, { width: 470, maximum: 48, minimum: 34, maxLines: 4 });
    p.reveal_label = text2(r.reveal_label, "reveal label", 12);
    fitText2(p.reveal_label, { width: 140, maximum: 28, minimum: 24, maxLines: 1 });
    p.note = text2(r.note, "note", 120);
    fitText2(p.note, { width: 800, maximum: 36, minimum: 28, maxLines: 3 });
    p.side = choice2(r.side, "peel side", ["left", "right"]);
    p.peel_depth = number2(defaulted2(r.peel_depth, 310), "peel depth", 260, 350);
    p.curl = number2(defaulted2(r.curl, 0.12), "curl", 0.08, 0.18);
    p.peel_window = windowPair2(defaulted2(r.peel_window, [0.16, 0.76]), "peel window");
    if (p.peel_window[1] - p.peel_window[0] < 0.3 - 1e-9) fail2("peel window: at least 30% required");
    return { id: ID8, version: VERSION2, parameters: p };
  }
  function peelGeometry(depth, side, curl = 0.12) {
    const { width: w, height: h } = PANEL, rectangle = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h }, { x: 0, y: h }], limit = w - depth;
    const front = clipHalfPlane(rectangle, 1, -1, limit), removed = depth > 1e-8 ? clipHalfPlane(rectangle, 1, -1, limit, false) : [];
    const back = removed.map((p) => ({ x: p.y + limit, y: p.x - limit }));
    const mirror = (p) => ({ x: side === "left" ? w - p.x : p.x, y: p.y });
    const crease = [{ x: limit, y: 0 }, { x: w - depth / 2 - depth * curl, y: depth / 2 + depth * curl }, { x: w, y: depth }].map(mirror);
    return {
      front: front.map(mirror),
      removed: removed.map(mirror),
      back: back.map(mirror),
      crease,
      frontArea: area(front),
      removedArea: area(removed),
      backArea: area(back),
      panelArea: w * h,
      bounds: bounds([...front, ...removed, ...back].map(mirror))
    };
  }
  function state8(p, seconds) {
    const time2 = sampleTime2(seconds, p.duration), progress = phaseAt2(motionTime2(time2, p.duration), p.duration, p.peel_window), depth = p.peel_depth * progress;
    return { seconds: time2, progress, depth, phase: progress === 0 ? "front" : progress === 1 ? "revealed" : "peel", noteOpacity: smooth2((progress - 0.55) / 0.45), geometry: peelGeometry(depth, p.side, p.curl) };
  }
  function sample8(spec, seconds) {
    return state8(validateSpec8(spec).parameters, seconds);
  }
  var sampleFrame8 = sample8;
  function render8(spec, seconds) {
    const p = validateSpec8(spec).parameters, s = state8(p, seconds), c = p.palette, g = s.geometry, right = p.side === "right";
    const [a, q, b] = g.crease, headlineX = right ? 50 : 220, tipX = right ? 910 : 170, railX = right ? 960 : 120, noteX = right ? 110 : 170;
    const crease = s.depth > 1e-8 ? `<path d="M${fmt2(a.x)} ${fmt2(a.y)}Q${fmt2(q.x)} ${fmt2(q.y)} ${fmt2(b.x)} ${fmt2(b.y)}" fill="none" stroke="${c.accent}" stroke-width="3"/>` : "";
    const body = `<defs><clipPath id="sp-front"><path d="${path(g.front)}"/></clipPath><clipPath id="sp-under"><path d="${path(g.removed)}"/></clipPath></defs><g transform="translate(${PANEL.x} ${PANEL.y})"><rect width="740" height="460" fill="${c.background}" stroke="${c.muted}" stroke-width="2"/><g clip-path="url(#sp-under)">${svgText2(p.reveal_label, { x: right ? 576 : 24, y: 54, width: 140, maximum: 28, minimum: 24, maxLines: 1, fill: c.ink })}</g><g clip-path="url(#sp-front)"><rect width="740" height="460" fill="${c.background}"/>${svgText2(p.headline, { x: headlineX, y: 184, width: 470, maximum: 48, minimum: 34, maxLines: 4, fill: c.ink })}</g><path data-front-face="true" d="${path(g.front)}" fill="none" stroke="${c.ink}" stroke-width="4"/>${g.back.length ? `<path data-back-face="true" d="${path(g.back)}" fill="${c.background}" stroke="${c.ink}" stroke-width="3"/><path d="${path(g.back)}" fill="${c.muted}" opacity="0.14"/>` : ""}${crease}</g><g opacity="${fmt2(s.noteOpacity)}"><path d="M${tipX} 740H${railX}V1310H${noteX}" fill="none" stroke="${c.accent}" stroke-width="3"/><circle cx="${tipX}" cy="740" r="6" fill="${c.accent}"/>${svgText2(p.note, { x: noteX, y: 1380, width: 800, maximum: 36, minimum: 28, maxLines: 3, fill: c.ink })}</g>`;
    return frameShell2(ID8, p, s.seconds, body);
  }
  var renderFrame8 = render8;

  // renderers/template-registry/modules/4ff5ac61f8ea-iso-room-route.mjs
  var ff5ac61f8ea_iso_room_route_exports = {};
  __export(ff5ac61f8ea_iso_room_route_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE9,
    ID: () => ID9,
    METADATA: () => METADATA,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA9,
    SOURCE_ID: () => SOURCE_ID9,
    render: () => render9,
    sample: () => sample9,
    validateSpec: () => validateSpec9
  });

  // renderers/template-registry/modules/bf3bbe09120e-shared.mjs
  var VERSION3 = "1.0.0";
  var WIDTH4 = 1080;
  var FPS3 = 30;
  var COMMON_REQUIRED3 = ["title", "duration", "narration", "cues"];
  var InputError3 = class extends Error {
    constructor(message) {
      super(`TEMPLATE_INPUT: ${message}`);
      this.name = "InputError";
    }
  };
  function fail3(message) {
    throw new InputError3(message);
  }
  function keys3(value, required, optional = [], name = "object") {
    if (!value || typeof value !== "object" || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail3(`${name}: plain object required`);
    const own = Reflect.ownKeys(value);
    if (own.some((key) => typeof key !== "string" || !Object.getOwnPropertyDescriptor(value, key).enumerable || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), "value")) || required.some((key) => !Object.hasOwn(value, key)) || own.some((key) => !required.includes(key) && !optional.includes(key))) {
      fail3(`${name}: expected fields ${required.join(", ")}`);
    }
  }
  function number3(value, name, low, high, integer = false) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high || integer && !Number.isInteger(value)) fail3(`${name}: ${low}\u2013${high}${integer ? " integer" : ""} required`);
    return value;
  }
  function choice3(value, name, values) {
    if (typeof value !== "string" || !values.includes(value)) fail3(`${name}: ${values.join("/")} required`);
    return value;
  }
  function text3(value, name, maximum = 160) {
    if (typeof value !== "string" || !value.trim() || [...value].length > maximum || [...value].some((c) => new RegExp("\\p{C}", "u").test(c) && c !== "\n" && c !== "	")) fail3(`${name}: bounded plain text required`);
    return value.normalize("NFC").replace(/\s+/gu, " ").trim();
  }
  function textUnits3(value) {
    return [...value].reduce((sum, c) => sum + (c === " " ? 0.36 : /[MW@%ĞÖÜŞÇ]/u.test(c) ? 1.02 : /[ilıİ1.,:;'!|]/u.test(c) ? 0.4 : /[A-Z0-9]/u.test(c) ? 0.8 : c.codePointAt(0) > 12287 ? 1.15 : 0.7), 0);
  }
  function fitText3(value, { width = 900, maximum = 56, minimum = 28, maxLines = 3 } = {}) {
    number3(width, "text width", 1, WIDTH4);
    number3(maximum, "maximum font", 1, 120, true);
    number3(minimum, "minimum font", 1, maximum, true);
    number3(maxLines, "maximum lines", 1, 8, true);
    const normalized2 = text3(value, "layout text", 1500);
    for (let size = maximum; size >= minimum; size--) {
      const lines = [];
      let line5 = "";
      let fits = true;
      for (const word of normalized2.split(" ")) {
        if (textUnits3(word) * size > width) {
          fits = false;
          break;
        }
        const candidate = line5 ? `${line5} ${word}` : word;
        if (line5 && textUnits3(candidate) * size > width) {
          lines.push(line5);
          line5 = word;
        } else line5 = candidate;
      }
      if (line5) lines.push(line5);
      if (fits && lines.length <= maxLines) return {
        text: normalized2,
        lines,
        fontSize: size,
        lineHeight: size * 1.24,
        width,
        height: size * 1.24 * lines.length
      };
    }
    fail3("text does not fit without losing words; shorten the input");
  }
  function contrastRatio3(first, second) {
    const luminance = (color2) => {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail3("contrast: six-digit hex required");
      const channels = [1, 3, 5].map((index) => Number.parseInt(color2.slice(index, index + 2), 16) / 255).map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    const a = luminance(first), b = luminance(second);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }
  function palette3(value, defaults, accentMinimum = 3) {
    const raw = value === void 0 ? defaults : value;
    keys3(raw, ["background", "ink", "muted", "accent"], [], "palette");
    const result2 = {};
    for (const [key, color2] of Object.entries(raw)) {
      if (typeof color2 !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(color2)) fail3(`palette.${key}: six-digit hex required`);
      result2[key] = color2.toUpperCase();
    }
    for (const [role, minimum] of [["ink", 4.5], ["muted", 4.5], ["accent", accentMinimum]]) {
      if (contrastRatio3(result2[role], result2.background) < minimum) fail3(`palette.${role}: contrast must be at least ${minimum} against background`);
    }
    return result2;
  }
  function validateBase3(spec, id, required, optional, defaults) {
    keys3(spec, ["id", "version", "parameters"], [], "spec");
    if (spec.id !== id || spec.version !== VERSION3) fail3("unknown renderer ID or template version");
    const raw = spec.parameters;
    keys3(raw, [...COMMON_REQUIRED3, ...required], [...optional, "palette"], "parameters");
    const title = text3(raw.title, "title", 160);
    fitText3(title, { maximum: 64, minimum: 38, maxLines: 4 });
    const duration = number3(raw.duration, "duration", 3, 45);
    if (Math.abs(duration * FPS3 - Math.round(duration * FPS3)) > 1e-7) fail3("duration: use a 30 fps frame boundary");
    const narration = text3(raw.narration, "narration", 1500);
    if (!Array.isArray(raw.cues) || raw.cues.length < 1 || raw.cues.length > 24) fail3("cues: 1\u201324 supplied cues required");
    let previous = 0;
    const cues = raw.cues.map((cue, i) => {
      keys3(cue, ["start", "end", "text"], [], `cue ${i}`);
      const start = number3(cue.start, "cue start", 0, duration);
      const end = number3(cue.end, "cue end", 0, duration);
      const value = text3(cue.text, "cue text", 95);
      if (start < previous || end - start < 0.2 - 1e-9) fail3("cues: ordered, nonoverlapping and at least 0.2 seconds required");
      fitText3(value, { width: 890, maximum: 44, minimum: 30, maxLines: 3 });
      previous = end;
      return { start, end, text: value };
    });
    if (cues.map((c) => c.text).join(" ") !== narration) fail3("cues must contain the whole narration in the same order");
    return { title, duration, narration, cues, palette: palette3(raw.palette, defaults, 4.5) };
  }
  var clamp3 = (x) => Math.max(0, Math.min(1, x));
  var smooth3 = (x) => {
    const p = clamp3(x);
    return p * p * (3 - 2 * p);
  };
  var lerp3 = (a, b, p) => a + (b - a) * p;
  function sampleTime3(seconds, duration) {
    return Math.min(number3(seconds, "seconds", 0, Number.MAX_SAFE_INTEGER), duration);
  }
  function activeCue3(cues, seconds) {
    return cues.find((c) => seconds >= c.start && seconds < c.end) ?? null;
  }
  function esc3(value) {
    return String(value).replace(/[&<>"']/gu, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]);
  }
  function fmt3(value) {
    if (!Number.isFinite(value)) fail3("nonfinite SVG coordinate");
    return String(Number(value.toFixed(5)));
  }
  function svgText3(value, { x = 90, y, width = 900, maximum = 56, minimum = 28, maxLines = 3, fill = "#18202A", anchor = "start", weight = 600 } = {}) {
    const fit = fitText3(value, { width, maximum, minimum, maxLines });
    return `<text x="${fmt3(x)}" y="${fmt3(y)}" fill="${esc3(fill)}" font-size="${fit.fontSize}" font-weight="${weight}" text-anchor="${anchor}" data-template-text="true" data-full-text="${esc3(fit.text)}" data-slot-width="${width}" data-estimated-height="${fmt3(fit.height)}">${fit.lines.map((line5, i) => `<tspan x="${fmt3(x)}" dy="${i === 0 ? 0 : fmt3(fit.lineHeight)}">${esc3(line5)}</tspan>`).join("")}</text>`;
  }
  function deepFreeze2(value) {
    if (value && typeof value === "object") {
      for (const child of Object.values(value)) deepFreeze2(child);
      Object.freeze(value);
    }
    return value;
  }

  // renderers/template-registry/modules/f2b8a056cce3-shared.mjs
  var PALETTES = { paper: { background: "#F4F0E7", ink: "#24343B", muted: "#59646B", accent: "#85432E" }, night: { background: "#111D29", ink: "#F2EFE7", muted: "#B5C6D2", accent: "#F0AF95" }, blue: { background: "#EAF0F4", ink: "#253D50", muted: "#526875", accent: "#315D87" } };
  function meta(name, kind, layout_id, motion_grammar, typographic_hierarchy) {
    return Object.freeze({ name, kind, layout_id, motion_grammar, typographic_hierarchy, original_implementation: true, native_verified: false, independent_accepted: false, ui_verified: false, product_integrated: false, strategy: "original_implementation_not_source_code_port" });
  }
  function base(spec, id, required, defaults, palette4) {
    keys3(spec, ["id", "version", "parameters"], [], "spec");
    keys3(spec.parameters, ["title", "duration", "narration", "cues", ...required], ["palette"], "parameters");
    list(spec.parameters.cues, 1, 24, "cues");
    return validateBase3(spec, id, required, [], palette4);
  }
  function list(v, min, max, name) {
    if (!Array.isArray(v) || Object.getPrototypeOf(v) !== Array.prototype || v.length < min || v.length > max || Array.from({ length: v.length }, (_, i) => Object.hasOwn(v, i)).some((x) => !x) || Reflect.ownKeys(v).some((k) => k !== "length" && (typeof k !== "string" || !/^\d+$/u.test(k) || Number(k) >= v.length || !Object.getOwnPropertyDescriptor(v, k).enumerable || !Object.hasOwn(Object.getOwnPropertyDescriptor(v, k), "value")))) fail3(`${name}: dense plain array length ${min}..${max} required`);
    return v;
  }
  function point(v, name, lo = 0, hi = 1) {
    keys3(v, ["x", "y"], [], name);
    return { x: number3(v.x, `${name}.x`, lo, hi), y: number3(v.y, `${name}.y`, lo, hi) };
  }
  function permutation(v, values, name) {
    list(v, values.length, values.length, name);
    if (v.some((x) => !values.includes(x)) || new Set(v).size !== values.length) fail3(`${name}: exact permutation required`);
    return [...v];
  }
  function copy(v, name, max, width = 800, size = 34, lines = 3) {
    const s = text3(v, name, max);
    fitText3(s, { width, maximum: size, minimum: 28, maxLines: lines });
    return s;
  }
  function done(id, p) {
    return { id, version: VERSION3, parameters: p };
  }
  function time(p, seconds) {
    const t = sampleTime3(seconds, p.duration), active = p.duration - 0.75;
    return { seconds: t, active, u: clamp3(t / active), held: t >= active };
  }
  var ease = (u, start = 0, end = 1) => smooth3((u - start) / (end - start));
  function along(points, u) {
    const f = clamp3(u) * (points.length - 1), i = Math.min(points.length - 2, Math.floor(f)), p = f - i;
    return { x: lerp3(points[i].x, points[i + 1].x, p), y: lerp3(points[i].y, points[i + 1].y, p) };
  }
  function iso(x, y, z = 0, origin = { x: 540, y: 940 }, scale = 72) {
    return { x: origin.x + (x - y) * scale, y: origin.y + (x + y) * scale * 0.5 - z };
  }
  var path2 = (points, close = false) => points.map((p, i) => `${i ? "L" : "M"}${fmt3(p.x)} ${fmt3(p.y)}`).join("") + (close ? "Z" : "");
  var polygon = (points, fill, stroke = "none", width = 2) => `<path d="${path2(points, true)}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`;
  var line = (a, b, color2, width = 2, extra = "") => `<path d="${path2([a, b])}" fill="none" stroke="${color2}" stroke-width="${width}" ${extra}/>`;
  function label(value, x, y, width = 800, size = 36, fill = "#24343B", lines = 3, anchor = "start") {
    return svgText3(value, { x, y, width, maximum: size, minimum: 28, maxLines: lines, fill, anchor });
  }
  function page(id, p, t, body, { layout = "rail", headline: headline2 = null } = {}) {
    const c = p.palette, cue = activeCue3(p.cues, t), i = cue ? p.cues.indexOf(cue) : -1;
    const title = layout === "center" ? svgText3(p.title, { x: 540, y: 175, width: 860, maximum: 54, minimum: 38, maxLines: 4, fill: c.ink, anchor: "middle" }) : svgText3(p.title, { x: 105, y: 160, width: 850, maximum: layout === "side" ? 52 : 60, minimum: 38, maxLines: 4, fill: c.ink });
    const guide = layout === "side" ? `<path d="M88 115V1490" stroke="${c.accent}" stroke-width="7"/>` : layout === "center" ? `<path d="M405 490H675" stroke="${c.accent}" stroke-width="4"/>` : `<path d="M105 490H375" stroke="${c.accent}" stroke-width="5"/>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc3(p.title)}" data-renderer="${id}" data-seconds="${fmt3(t)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${title}${guide}<g id="motion-body">${body}</g><path d="M100 1580H980" stroke="${c.muted}" stroke-width="1"/>${cue ? `<g id="family-cue-${i}" data-cue="true">${label(cue.text, 100, 1650, 880, 42, c.ink, 3)}</g>` : ""}<text x="100" y="1840" fill="${c.muted}" font-size="20">\xD6ZG\xDCN YEREL KOD \xB7 G\xD6RSEL \u0130NCELEME BEKL\u0130YOR</text></g></svg>`;
  }

  // renderers/template-registry/modules/4ff5ac61f8ea-iso-room-route.mjs
  var ID9 = "iso-room-route";
  var SOURCE_ID9 = "source-mg-style-03-isometric";
  var DEFAULT_PALETTE9 = PALETTES.paper;
  var METADATA = meta("Kap\u0131lardan ge\xE7en izometrik oda", "room", "axonometric-room", "hinged walls, ordered door crossings, depth occlusion", "left title / spatial object / lower room key");
  var PARAMETER_SCHEMA9 = { room_layout: { width: [2, 4], depth: [2, 4], height: [70, 150] }, door_order: { permutation: ["west", "east"] }, carrier_route: { minItems: 2, maxItems: 4, point: [0, 1] }, unfold_angle: [60, 90], room_label: { maxLength: 75 } };
  function validateSpec9(spec) {
    const p = base(spec, ID9, ["room_layout", "door_order", "carrier_route", "unfold_angle", "room_label"], {}, DEFAULT_PALETTE9), r = spec.parameters;
    keys3(r.room_layout, ["width", "depth", "height"]);
    p.room_layout = { width: number3(r.room_layout.width, "room width", 2, 4), depth: number3(r.room_layout.depth, "room depth", 2, 4), height: number3(r.room_layout.height, "wall height", 70, 150) };
    p.door_order = permutation(r.door_order, ["west", "east"], "doors");
    p.carrier_route = list(r.carrier_route, 2, 4, "route").map((v, i) => point(v, `route ${i}`));
    p.unfold_angle = number3(r.unfold_angle, "unfold angle", 60, 90);
    p.room_label = copy(r.room_label, "room label", 75, 800, 34, 2);
    return done(ID9, p);
  }
  function state9(p, seconds) {
    const q = time(p, seconds), r = p.room_layout, opening = ease(q.u, 0, 0.28), angle = p.unfold_angle * opening, z = r.height * Math.sin(angle * Math.PI / 180), d = r.depth * 0.5, w = r.width, first = p.door_order[0], door = (x) => ({ x: x === "west" ? 0 : w, y: d });
    const waypoints = [{ x: first === "west" ? -0.5 : w + 0.5, y: d }, door(first), ...p.carrier_route.map((v) => ({ x: v.x * w, y: v.y * r.depth })), door(p.door_order[1]), { x: first === "west" ? w + 0.5 : -0.5, y: d }], routeProgress = ease(q.u, 0.3, 0.86), world = along(waypoints, routeProgress), carrier = iso(world.x, world.y, 18), floor = [iso(0, 0), iso(w, 0), iso(w, r.depth), iso(0, r.depth)];
    const walls = ["west", "east"].map((side, i) => {
      const x = side === "west" ? 0 : w, progress = ease(q.u, i * 0.07, 0.28), height = z * progress;
      return { side, height, parts: [[0, d - 0.38], [d + 0.38, r.depth]].map(([a, b]) => [iso(x, a), iso(x, b), iso(x, b, height), iso(x, a, height)]), lintel: [iso(x, d - 0.38, height * 0.72), iso(x, d + 0.38, height * 0.72), iso(x, d + 0.38, height), iso(x, d - 0.38, height)] };
    });
    return { ...q, opening, angle, routeProgress, world, carrier, floor, walls, carrierLayer: world.x > w ? "foreground" : "behind-east-wall", waypoints };
  }
  var sample9 = (spec, seconds) => state9(validateSpec9(spec).parameters, seconds);
  function render9(spec, seconds) {
    const p = validateSpec9(spec).parameters, s = state9(p, seconds), c = p.palette, wall = (w) => w.parts.map((v) => polygon(v, c.background, c.ink, 3)).join("") + polygon(w.lintel, c.background, c.ink, 3), a = s.carrier, carrier = polygon([{ x: a.x - 17, y: a.y }, { x: a.x, y: a.y - 10 }, { x: a.x + 17, y: a.y }, { x: a.x, y: a.y + 10 }], c.accent, c.ink, 2) + `<path d="M${a.x - 17} ${a.y}v24l17 10 17-10v-24" fill="${c.accent}" stroke="${c.ink}" stroke-width="2"/>`;
    let body = polygon(s.floor, c.background, c.muted, 3) + wall(s.walls[0]);
    body += s.carrierLayer === "foreground" ? wall(s.walls[1]) + carrier : carrier + wall(s.walls[1]);
    body += label(p.room_label, 130, 1430, 800, 34, c.ink, 2);
    return page(ID9, p, s.seconds, body);
  }

  // renderers/template-registry/modules/85165292ba5d-perspective-neon-run.mjs
  var ba5d_perspective_neon_run_exports = {};
  __export(ba5d_perspective_neon_run_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE10,
    ID: () => ID10,
    METADATA: () => METADATA2,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA10,
    SOURCE_ID: () => SOURCE_ID10,
    render: () => render10,
    sample: () => sample10,
    validateSpec: () => validateSpec10
  });
  var ID10 = "perspective-neon-run";
  var SOURCE_ID10 = "source-mg-style-10-synthwave";
  var DEFAULT_PALETTE10 = PALETTES.night;
  var METADATA2 = meta("Perspektifte ilerleyen \xE7izgiler", "depth-grid", "perspective-wedge", "receding depth rows and scheduled horizon contours", "horizon header / receding road / caption strip");
  var PARAMETER_SCHEMA10 = { grid_speed: [0.4, 1.4], horizon_height: [620, 820], pulse_cues: { minItems: 2, maxItems: 4, at: [0.1, 0.8], strength: [0.2, 1] }, neon_width: [2, 6] };
  function validateSpec10(spec) {
    const p = base(spec, ID10, ["grid_speed", "horizon_height", "pulse_cues", "neon_width"], {}, DEFAULT_PALETTE10), r = spec.parameters;
    p.grid_speed = number3(r.grid_speed, "grid speed", 0.4, 1.4);
    p.horizon_height = number3(r.horizon_height, "horizon", 620, 820);
    p.neon_width = number3(r.neon_width, "contour width", 2, 6);
    let prior = -1;
    p.pulse_cues = list(r.pulse_cues, 2, 4, "pulses").map((v) => {
      keys3(v, ["at", "strength"]);
      const at2 = number3(v.at, "pulse time", 0.1, 0.8), strength = number3(v.strength, "pulse strength", 0.2, 1);
      if (at2 <= prior) fail3("pulses must have increasing times");
      prior = at2;
      return { at: at2, strength };
    });
    return done(ID10, p);
  }
  function state10(p, seconds) {
    const q = time(p, seconds), offset = q.u * p.grid_speed * 1.7, depths = Array.from({ length: 12 }, (_, i) => (i / 12 + offset) % 1).sort((a, b) => a - b), rows = depths.map((depth) => {
      const perspective = 0.12 + 0.88 * depth * depth;
      return { depth, left: 540 - 370 * perspective, right: 540 + 370 * perspective, y: lerp3(p.horizon_height, 1450, perspective) };
    }), pulses = p.pulse_cues.map((v) => {
      const local = (q.u - v.at) / 0.16, power = local > 0 && local < 1 ? Math.sin(Math.PI * local) * v.strength : 0;
      return { power, rx: 210 + power * 80, ry: 35 + power * 65 };
    });
    return { ...q, offset, rows, pulses, horizon: p.horizon_height };
  }
  var sample10 = (spec, seconds) => state10(validateSpec10(spec).parameters, seconds);
  function render10(spec, seconds) {
    const p = validateSpec10(spec).parameters, s = state10(p, seconds), c = p.palette;
    let body = polygon([{ x: 496, y: s.horizon }, { x: 584, y: s.horizon }, { x: 910, y: 1450 }, { x: 170, y: 1450 }], c.background, c.accent, p.neon_width);
    for (let i = 1; i < 6; i++) body += line({ x: 496 + i * 88 / 6, y: s.horizon }, { x: 170 + i * 740 / 6, y: 1450 }, c.muted, 2);
    body += s.rows.map((r) => line({ x: r.left, y: r.y }, { x: r.right, y: r.y }, c.accent, p.neon_width)).join("") + s.pulses.map((v) => `<ellipse cx="540" cy="${s.horizon - 30}" rx="${fmt3(v.rx)}" ry="${fmt3(v.ry)}" fill="none" stroke="${c.ink}" stroke-width="${p.neon_width}" opacity="${fmt3(0.2 + v.power * 0.8)}"/>`).join("");
    return page(ID10, p, s.seconds, body, { layout: "center" });
  }

  // renderers/template-registry/modules/b205d5e0ed2f-aurora-refraction-panels.mjs
  var b205d5e0ed2f_aurora_refraction_panels_exports = {};
  __export(b205d5e0ed2f_aurora_refraction_panels_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE11,
    ID: () => ID11,
    METADATA: () => METADATA3,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA11,
    SOURCE_ID: () => SOURCE_ID11,
    render: () => render11,
    sample: () => sample11,
    validateSpec: () => validateSpec11
  });
  var ID11 = "aurora-refraction-panels";
  var SOURCE_ID11 = "source-mg-style-12-aurora-glass";
  var DEFAULT_PALETTE11 = PALETTES.blue;
  var METADATA3 = meta("K\u0131r\u0131lan alan ve a\xE7\u0131l\u0131 paneller", "vector-refraction", "staggered-panels", "seeded analytic ribbons displaced inside tilted masks", "spine title / diagonal labels / field behind panels");
  var PARAMETER_SCHEMA11 = { field_seed: [1, 999], flow_rate: [0.3, 1.2], panel_tilt: [-18, 18], refraction_amount: [12, 36], panels: { minItems: 2, maxItems: 3, labelMaxLength: 42 } };
  function validateSpec11(spec) {
    const p = base(spec, ID11, ["field_seed", "flow_rate", "panel_tilt", "refraction_amount", "panels"], {}, DEFAULT_PALETTE11), r = spec.parameters;
    p.field_seed = number3(r.field_seed, "field seed", 1, 999, true);
    p.flow_rate = number3(r.flow_rate, "flow", 0.3, 1.2);
    p.panel_tilt = number3(r.panel_tilt, "tilt", -18, 18);
    p.refraction_amount = number3(r.refraction_amount, "refraction", 12, 36);
    p.panels = list(r.panels, 2, 3, "panels").map((v) => copy(v, "panel label", 42, 350, 32, 2));
    return done(ID11, p);
  }
  function labelLayoutAurora(p,name){
   const fit=fitText3(name,{width:350,maximum:32,minimum:28,maxLines:2}),angle=Math.abs(p.panel_tilt)*Math.PI/180;
   const width=Math.max(...fit.lines.map(line=>textUnits3(line)*fit.fontSize)),glyphHeight=fit.fontSize*1.4;
   // Tilt adds width*sin(angle) to a line's screen-space height. Reserve that
   // clearance at the configured maximum angle; text stays on its panel.
   const leading=glyphHeight+width*Math.tan(angle)+12/Math.cos(angle);
   return{lines:fit.lines,fontSize:fit.fontSize,leading,height:glyphHeight+(fit.lines.length-1)*leading};
  }
  function state11(p,seconds){const q=time(p,seconds),phase=q.u*p.flow_rate*Math.PI*2,tilt=p.panel_tilt*Math.sin(Math.PI*q.u),bands=Array.from({length:3},(_,j)=>Array.from({length:13},(_,i)=>({x:100+i*73,y:690+j*230+Math.sin(i*.52+phase+p.field_seed*.17+j)*55}))),panels=p.panels.map((name,i)=>({x:145+i*185,y:550+i*330,width:405,height:280,tilt:tilt*(i%2?-1:1),shift:p.refraction_amount*Math.sin(phase+i*.7),label:name,labelLayoutAurora:labelLayoutAurora(p,name)}));return{...q,phase,tilt,blur:Math.abs(tilt)/6,bands,panels};}
  var sample11=(spec,seconds)=>state11(validateSpec11(spec).parameters,seconds);
  function render11(spec,seconds){const p=validateSpec11(spec).parameters,s=state11(p,seconds),c=p.palette,ribbons=(shift=0)=>s.bands.map((band,j)=>`<polyline points="${band.map(v=>`${fmt3(v.x+shift)},${fmt3(v.y)}`).join(' ')}" fill="none" stroke="${j%2?c.muted:c.accent}" stroke-width="${28+j*10}" stroke-linejoin="round" opacity="0.42"/>`).join('');let body=`<defs><filter id="arp-blur" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="${fmt3(s.blur)}"/></filter></defs><g filter="url(#arp-blur)">${ribbons()}</g>`;body+=s.panels.map((v,i)=>{
   const label=v.labelLayoutAurora,cy=v.y+v.height/2,plateHeight=Math.max(100,label.height+20);
   const lines=label.lines.map((line,j)=>`<text data-motion-role="panel-label-line" x="${v.x+26}" y="${fmt3(cy-(label.lines.length-1)*label.leading/2+label.fontSize*.35+j*label.leading)}" fill="${c.ink}" font-size="${label.fontSize}" font-weight="600">${esc3(line)}</text>`).join('');
   return`<defs><clipPath id="arp-${i}"><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12"/></clipPath></defs><g transform="rotate(${fmt3(v.tilt)} ${v.x+v.width/2} ${v.y+v.height/2})"><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12" fill="${c.background}" opacity="0.86"/><g clip-path="url(#arp-${i})"><g filter="url(#arp-blur)">${ribbons(v.shift)}</g></g><rect x="${v.x}" y="${v.y}" width="${v.width}" height="${v.height}" rx="12" fill="none" stroke="${c.ink}" stroke-width="2"/><rect x="${v.x+16}" y="${fmt3(cy-plateHeight/2)}" width="370" height="${fmt3(plateHeight)}" fill="${c.background}"/>${lines}</g>`;
   }).join('');return page(ID11,p,s.seconds,body,{layout:'side'});}

  // renderers/template-registry/modules/e55f7e8780df-deco-radial-reveal.mjs
  var e55f7e8780df_deco_radial_reveal_exports = {};
  __export(e55f7e8780df_deco_radial_reveal_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE12,
    ID: () => ID12,
    METADATA: () => METADATA4,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA12,
    SOURCE_ID: () => SOURCE_ID12,
    render: () => render12,
    sample: () => sample12,
    validateSpec: () => validateSpec12
  });
  var ID12 = "deco-radial-reveal";
  var SOURCE_ID12 = "source-lemo-style-art-deco";
  var DEFAULT_PALETTE12 = PALETTES.paper;
  var METADATA4 = meta("Eksen etraf\u0131nda a\xE7\u0131lan dekoratif \xE7er\xE7eve", "radial-frame", "symmetric-fan", "paired ray fan, ordered radial sweep, closing frame", "centered headline / paired fan / small context title");
  var PARAMETER_SCHEMA12 = { ray_count: { minimum: 8, maximum: 20, even: true }, fan_angle: [100, 160], frame_inset: [100, 160], reveal_order: { enum: ["center-out", "edge-in"] }, headline: { maxLength: 70 } };
  function validateSpec12(spec) {
    const p = base(spec, ID12, ["ray_count", "fan_angle", "frame_inset", "reveal_order", "headline"], {}, DEFAULT_PALETTE12), r = spec.parameters;
    p.ray_count = number3(r.ray_count, "rays", 8, 20, true);
    if (p.ray_count % 2) fail3("ray count must be even");
    p.fan_angle = number3(r.fan_angle, "fan angle", 100, 160);
    p.frame_inset = number3(r.frame_inset, "inset", 100, 160);
    p.reveal_order = choice3(r.reveal_order, "order", ["center-out", "edge-in"]);
    p.headline = copy(r.headline, "headline", 70, 680, 48, 4);
    return done(ID12, p);
  }
  function state12(p, seconds) {
    const q = time(p, seconds), pairs = p.ray_count / 2, rays = [];
    for (let i = 0; i < pairs; i++) {
      const rank = p.reveal_order === "center-out" ? i : pairs - 1 - i, amount = ease(q.u, rank * 0.025, 0.52 + rank * 0.025), angle = (i + 0.5) / pairs * p.fan_angle / 2 * Math.PI / 180;
      for (const sign of [-1, 1]) rays.push({ pair: i, sign, amount, a: { x: 540 + sign * Math.sin(angle) * 75, y: 1100 - Math.cos(angle) * 75 }, b: { x: 540 + sign * Math.sin(angle) * (75 + amount * 370), y: 1100 - Math.cos(angle) * (75 + amount * 370) } });
    }
    const frame = ease(q.u, 0.58, 0.88), inset = p.frame_inset;
    return { ...q, rays, frame, corners: [{ x: inset, y: 1135 }, { x: 1080 - inset, y: 1135 }, { x: 1080 - inset, y: 1480 }, { x: inset, y: 1480 }] };
  }
  var sample12 = (spec, seconds) => state12(validateSpec12(spec).parameters, seconds);
  function render12(spec, seconds) {
    const p = validateSpec12(spec).parameters, s = state12(p, seconds), c = p.palette;
    let body = s.rays.map((r) => line(r.a, r.b, r.pair % 2 ? c.muted : c.accent, r.pair % 2 ? 2 : 4)).join("");
    body += `<path d="M${p.frame_inset} 1135H${1080 - p.frame_inset}V1480H${p.frame_inset}Z" fill="none" stroke="${c.ink}" stroke-width="3" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt3(1 - s.frame)}"/>`;
    body += label(p.headline, 540, 1220, 680, 48, c.ink, 4, "middle");
    return page(ID12, p, s.seconds, body, { layout: "center" });
  }

  // renderers/template-registry/modules/919eef0c64a3-terminal-raster.mjs
  var eef0c64a3_terminal_raster_exports = {};
  __export(eef0c64a3_terminal_raster_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE13,
    ID: () => ID13,
    METADATA: () => METADATA5,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA13,
    SOURCE_ID: () => SOURCE_ID13,
    render: () => render13,
    sample: () => sample13,
    validateSpec: () => validateSpec13
  });
  var ID13 = "terminal-raster";
  var SOURCE_ID13 = "source-lemo-style-ascii-crt";
  var DEFAULT_PALETTE13 = PALETTES.night;
  var METADATA5 = meta("Sabit h\xFCcreli yaz\u0131 terminali", "text-buffer", "terminal-buffer", "prefix typing, whole-row scrolling, deterministic sweep", "terminal masthead / cell raster / status count");
  var PARAMETER_SCHEMA13 = { lines: { minItems: 2, maxItems: 4, maxLength: 50 }, columns: [24, 28], typing_cadence: [0.02, 0.045], scroll_rows: [0, 2], scan_period: [0.4, 1.2] };
  function buffer(p) {
    const cells = [];
    let row = 0;
    for (const value of p.lines) {
      const chars = [...value];
      for (let i = 0; i < chars.length; i++) cells.push({ char: chars[i], row: row + Math.floor(i / p.columns), column: i % p.columns, index: cells.length });
      row += Math.ceil(chars.length / p.columns);
    }
    return { cells, rows: row };
  }
  function validateSpec13(spec) {
    const p = base(spec, ID13, ["lines", "columns", "typing_cadence", "scroll_rows", "scan_period"], {}, DEFAULT_PALETTE13), r = spec.parameters;
    p.lines = list(r.lines, 2, 4, "terminal lines").map((v) => copy(v, "terminal line", 50, 800, 30, 3));
    p.columns = number3(r.columns, "columns", 24, 28, true);
    p.typing_cadence = number3(r.typing_cadence, "cadence", 0.02, 0.045);
    p.scroll_rows = number3(r.scroll_rows, "scroll rows", 0, 2, true);
    p.scan_period = number3(r.scan_period, "scan period", 0.4, 1.2);
    const b = buffer(p);
    if (b.rows > 7 || p.scroll_rows > Math.max(0, b.rows - 3) || b.rows - p.scroll_rows > 5) fail3("terminal buffer/scroll must show every row within five-row viewport");
    if (b.cells.length * p.typing_cadence + p.scroll_rows * 0.16 > p.duration - 0.75) fail3("typing and scroll need a final 0.75 second hold");
    return done(ID13, p);
  }
  function state13(p, seconds) {
    const q = time(p, seconds), b = buffer(p), revealed = Math.min(b.cells.length, Math.floor(Math.min(q.seconds, q.active) / p.typing_cadence + 1e-8)), typedEnd = b.cells.length * p.typing_cadence, scroll = Math.min(p.scroll_rows, Math.max(0, Math.floor((Math.min(q.seconds, q.active) - typedEnd) / 0.16 + 1e-8))), visible = b.cells.slice(0, revealed).filter((v) => v.row >= scroll && v.row < scroll + 5).map((v) => ({ ...v, x: 130 + v.column * 30, y: 760 + (v.row - scroll) * 100 })), sweep = 650 + q.u * q.active / p.scan_period % 1 * 550;
    return { ...q, revealed, total: b.cells.length, scroll, rows: b.rows, visible, sweep, prefix: b.cells.slice(0, revealed).map((v) => v.char).join("") };
  }
  var sample13 = (spec, seconds) => state13(validateSpec13(spec).parameters, seconds);
  function render13(spec, seconds) {
    const p = validateSpec13(spec).parameters, s = state13(p, seconds), c = p.palette;
    let body = `<rect x="110" y="650" width="860" height="600" rx="8" fill="${c.background}" stroke="${c.muted}" stroke-width="3"/><path d="M130 ${fmt3(s.sweep)}H950" stroke="${c.accent}" stroke-width="3" opacity="0.6"/>`;
    body += s.visible.map((v) => `<text x="${v.x}" y="${v.y}" fill="${c.ink}" font-size="28" xml:space="preserve">${esc3(v.char)}</text>`).join("");
    body += label(`${s.revealed} / ${s.total} h\xFCcre \xB7 ${s.scroll} sat\u0131r kayd\u0131r\u0131ld\u0131`, 130, 1380, 800, 32, c.accent, 2);
    return page(ID13, p, s.seconds, body, { layout: "side" });
  }

  // renderers/template-registry/modules/3528802a33d8-split-counter-flip.mjs
  var a33d8_split_counter_flip_exports = {};
  __export(a33d8_split_counter_flip_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE14,
    ID: () => ID14,
    METADATA: () => METADATA6,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA14,
    SOURCE_ID: () => SOURCE_ID14,
    render: () => render14,
    sample: () => sample14,
    validateSpec: () => validateSpec14
  });
  var ID14 = "split-counter-flip";
  var SOURCE_ID14 = "source-lemo-style-countdown";
  var DEFAULT_PALETTE14 = PALETTES.paper;
  var METADATA6 = meta("Yar\u0131m y\xFCzeyli say\u0131 sayac\u0131", "split-flap", "counter-and-ratio", "milestone digit hinges and complementary panel exchange", "large four-digit counter / two ratio panels");
  var PARAMETER_SCHEMA14 = { start_value: [0, 9999], end_value: [0, 9999], milestones: { minItems: 2, maxItems: 4, at: [0.15, 0.78], ratio: [0.32, 0.68] }, flap_duration: [0.12, 0.4], panel_labels: { exactItems: 2, maxLength: 35 } };
  function validateSpec14(spec) {
    const p = base(spec, ID14, ["start_value", "end_value", "milestones", "flap_duration", "panel_labels"], {}, DEFAULT_PALETTE14), r = spec.parameters;
    p.start_value = number3(r.start_value, "start value", 0, 9999, true);
    p.end_value = number3(r.end_value, "end value", 0, 9999, true);
    if (p.start_value === p.end_value) fail3("counter end must differ");
    p.flap_duration = number3(r.flap_duration, "flap duration", 0.12, 0.4);
    p.panel_labels = list(r.panel_labels, 2, 2, "panel labels").map((v) => copy(v, "panel label", 35, 220, 32, 3));
    let prior = 0, value = p.start_value, sign = Math.sign(p.end_value - p.start_value);
    p.milestones = list(r.milestones, 2, 4, "milestones").map((v) => {
      keys3(v, ["at", "value", "ratio"]);
      const at2 = number3(v.at, "milestone at", 0.15, 0.78), next = number3(v.value, "milestone value", 0, 9999, true), ratio = number3(v.ratio, "ratio", 0.32, 0.68);
      if ((at2 - prior) * (p.duration - 0.75) < p.flap_duration || sign * (next - value) <= 0 || sign * (p.end_value - next) < 0) fail3("milestones must have separated times and monotone values");
      prior = at2;
      value = next;
      return { at: at2, value: next, ratio };
    });
    if (value !== p.end_value) fail3("last milestone must equal end value");
    return done(ID14, p);
  }
  function state14(p, seconds) {
    const q = time(p, seconds);
    let old = p.start_value, next = old, ratio = 0.5, priorRatio = 0.5, progress = 1, event = -1;
    for (let i = 0; i < p.milestones.length; i++) {
      const v = p.milestones[i];
      if (q.u >= v.at) {
        next = v.value;
        progress = clamp3((Math.min(q.seconds, q.active) - v.at * q.active) / p.flap_duration);
        event = i;
        ratio = lerp3(priorRatio, v.ratio, smooth3(progress));
        if (progress < 1) break;
        old = next;
        priorRatio = v.ratio;
      }
    }
    const previous = event >= 0 ? event === 0 ? p.start_value : p.milestones[event - 1].value : p.start_value, digits = String(previous).padStart(4, "0").split("").map((old2, i) => ({ old: old2, next: String(next).padStart(4, "0")[i], hinge: Math.abs(Math.cos(progress * Math.PI)), progress }));
    return { ...q, event, progress, previous, next, value: progress === 1 ? next : previous, digits, ratio, panelWidths: [780 * ratio, 780 * (1 - ratio)] };
  }
  var sample14 = (spec, seconds) => state14(validateSpec14(spec).parameters, seconds);
  function render14(spec,seconds){const p=validateSpec14(spec).parameters,s=state14(p,seconds),c=p.palette;let body=s.digits.map((v,i)=>{
   const x=180+i*190,digit=v.progress<.5?v.old:v.next,hinge=v.old===v.next?1:v.hinge;
   // One complete digit face folds toward the center seam, changes at the
   // edge-on midpoint, then opens. Unchanged digits keep their readable face.
   // Separate clipped text copies would retain coincident full glyph boxes and
   // could present the new upper half with the previous lower half.
   return`<g data-motion-role="counter-cell"><rect x="${x}" y="740" width="150" height="210" rx="10" fill="${c.background}" stroke="${c.ink}" stroke-width="3"/><g data-motion-role="counter-face" transform="translate(0 845) scale(1 ${fmt3(hinge)}) translate(0 -845)"><rect x="${x+2}" y="742" width="146" height="101" fill="${c.background}"/><rect x="${x+2}" y="847" width="146" height="101" fill="${c.background}"/><text data-motion-role="counter-digit" x="${x+75}" y="905" fill="${c.ink}" font-size="140" font-weight="700" text-anchor="middle">${digit}</text></g><path d="M${x} 845h150" stroke="${c.accent}" stroke-width="3"/></g>`;
   }).join('');body+=s.panelWidths.map((w,i)=>{const x=i?140+s.panelWidths[0]+20:140;return`<rect x="${fmt3(x)}" y="1090" width="${fmt3(w)}" height="220" fill="none" stroke="${c.accent}" stroke-width="3"/>${label(p.panel_labels[i],x+20,1160,220,32,c.ink,3)}`;}).join('');return page(ID14,p,s.seconds,body,{layout:'center'});}

  // renderers/template-registry/modules/c346a4b44e9b-spotlight-product-reveal.mjs
  var c346a4b44e9b_spotlight_product_reveal_exports = {};
  __export(c346a4b44e9b_spotlight_product_reveal_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE15,
    ID: () => ID15,
    METADATA: () => METADATA7,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA15,
    SOURCE_ID: () => SOURCE_ID15,
    render: () => render15,
    sample: () => sample15,
    validateSpec: () => validateSpec15
  });
  var ID15 = "spotlight-product-reveal";
  var SOURCE_ID15 = "source-lemo-style-dark-keynote";
  var DEFAULT_PALETTE15 = PALETTES.night;
  var METADATA7 = meta("A\xE7\u0131kl\u0131kla bulunan \xF6zg\xFCn nesne", "aperture-product", "silhouette-and-metric-rail", "moving aperture, complete reveal, registered metric leaders", "quiet header / original silhouette / measurement rail");
  var PARAMETER_SCHEMA15 = { silhouette: { kind: ["vessel", "console"], width: [280, 500], height: [300, 480] }, spotlight_path: { minItems: 2, maxItems: 4, point: [0, 1] }, metric_regions: { minItems: 2, maxItems: 3, position: [0.15, 0.85], labelMaxLength: 35, valueMaxLength: 12 }, reveal_duration: [0.8, 3] };
  function validateSpec15(spec) {
    const p = base(spec, ID15, ["silhouette", "spotlight_path", "metric_regions", "reveal_duration"], {}, DEFAULT_PALETTE15), r = spec.parameters;
    keys3(r.silhouette, ["kind", "width", "height"]);
    p.silhouette = { kind: choice3(r.silhouette.kind, "silhouette", ["vessel", "console"]), width: number3(r.silhouette.width, "width", 280, 500), height: number3(r.silhouette.height, "height", 300, 480) };
    p.spotlight_path = list(r.spotlight_path, 2, 4, "spotlight").map((v, i) => point(v, `spotlight ${i}`));
    p.metric_regions = list(r.metric_regions, 2, 3, "metrics").map((v) => {
      keys3(v, ["x", "y", "label", "value"]);
      const a = point({ x: v.x, y: v.y }, "region", 0.15, 0.85), name = copy(v.label, "metric label", 35, 700, 30, 2), value = copy(v.value, "metric value", 12, 200, 30, 1);
      copy(name + " \xB7 " + value, "metric row", 50, 790, 30, 2);
      return { ...a, label: name, value };
    });
    p.reveal_duration = number3(r.reveal_duration, "reveal duration", 0.8, 3);
    if (p.reveal_duration > (p.duration - 0.75) * 0.65) fail3("reveal needs time for metric reading");
    return done(ID15, p);
  }
  function state15(p, seconds) {
    const q = time(p, seconds), w = p.silhouette.width, h = p.silhouette.height, box3 = { x: 540 - w / 2, y: 930 - h / 2, width: w, height: h }, reveal = ease(Math.min(q.seconds, q.active) / p.reveal_duration), v = along(p.spotlight_path, reveal), aperture = { x: box3.x + v.x * w, y: box3.y + v.y * h, r: 125 + 35 * Math.sin(Math.PI * reveal) }, cover = Math.max(...[[box3.x, box3.y], [box3.x + w, box3.y], [box3.x, box3.y + h], [box3.x + w, box3.y + h]].map(([x, y]) => Math.hypot(x - aperture.x, y - aperture.y))) + 5, grow = ease(reveal, 0.6, 1), radius = aperture.r + (Math.max(aperture.r, cover) - aperture.r) * grow, metrics = p.metric_regions.map((v2, i) => ({ ...v2, anchor: { x: box3.x + v2.x * w, y: box3.y + v2.y * h }, amount: ease(q.u, p.reveal_duration / q.active + i * 0.05, 0.88) }));
    return { ...q, box: box3, reveal, aperture: { ...aperture, r: radius }, metrics, fullyVisible: Math.min(q.seconds, q.active) >= p.reveal_duration };
  }
  var sample15 = (spec, seconds) => state15(validateSpec15(spec).parameters, seconds);
  function render15(spec, seconds) {
    const p = validateSpec15(spec).parameters, s = state15(p, seconds), c = p.palette, b = s.box, shape = p.silhouette.kind === "console" ? `<path d="M${b.x + 35} ${b.y}H${b.x + b.width - 35}L${b.x + b.width} ${b.y + b.height}H${b.x}Z"/>` : `<path d="M${b.x + b.width * 0.25} ${b.y}H${b.x + b.width * 0.75}V${b.y + b.height * 0.2}Q${b.x + b.width} ${b.y + b.height * 0.35} ${b.x + b.width * 0.88} ${b.y + b.height}H${b.x + b.width * 0.12}Q${b.x} ${b.y + b.height * 0.35} ${b.x + b.width * 0.25} ${b.y + b.height * 0.2}Z"/>`;
    let body = `<defs><clipPath id="spr-aperture"><circle cx="${fmt3(s.aperture.x)}" cy="${fmt3(s.aperture.y)}" r="${fmt3(s.aperture.r)}"/></clipPath></defs><g fill="none" stroke="${c.muted}" stroke-width="3">${shape}</g><g fill="${c.accent}" stroke="${c.ink}" stroke-width="3" clip-path="url(#spr-aperture)">${shape}</g>`;
    body += s.metrics.map((v, i) => `<g opacity="${fmt3(v.amount)}">${line(v.anchor, { x: 120, y: 1280 + i * 80 }, c.ink, 2)}<circle cx="${fmt3(v.anchor.x)}" cy="${fmt3(v.anchor.y)}" r="7" fill="${c.ink}"/>${label(v.label + " \xB7 " + v.value, 140, 1300 + i * 80, 790, 30, c.ink, 2)}</g>`).join("");
    return page(ID15, p, s.seconds, body);
  }

  // renderers/template-registry/modules/d36dce2821fa-iris-silhouette-chase.mjs
  var d36dce2821fa_iris_silhouette_chase_exports = {};
  __export(d36dce2821fa_iris_silhouette_chase_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE16,
    ID: () => ID16,
    METADATA: () => METADATA8,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA16,
    SOURCE_ID: () => SOURCE_ID16,
    render: () => render16,
    sample: () => sample16,
    validateSpec: () => validateSpec16
  });
  var ID16 = "iris-silhouette-chase";
  var SOURCE_ID16 = "source-lemo-style-spy-titles";
  var DEFAULT_PALETTE16 = PALETTES.paper;
  var METADATA8 = meta("Hareketli iris ve soyut iz", "abstract-iris", "tracked-aperture", "shape transit, tracking iris and angled mask handoff", "circular aperture / inset beat / upper context");
  var PARAMETER_SCHEMA16 = { silhouette_paths: { minItems: 2, maxItems: 3, enum: ["spindle", "wedge", "lozenge"] }, iris_targets: { matchingItems: true, point: [0.15, 0.85] }, mask_angles: { matchingItems: true, range: [-35, 35] }, title_cues: { matchingItems: true, maxLength: 45 } };
  function validateSpec16(spec) {
    const p = base(spec, ID16, ["silhouette_paths", "iris_targets", "mask_angles", "title_cues"], {}, DEFAULT_PALETTE16), r = spec.parameters;
    p.silhouette_paths = list(r.silhouette_paths, 2, 3, "silhouettes").map((v) => choice3(v, "abstract shape", ["spindle", "wedge", "lozenge"]));
    const n = p.silhouette_paths.length;
    p.iris_targets = list(r.iris_targets, n, n, "iris targets").map((v) => point(v, "iris target", 0.15, 0.85));
    p.mask_angles = list(r.mask_angles, n, n, "mask angles").map((v) => number3(v, "mask angle", -35, 35));
    p.title_cues = list(r.title_cues, n, n, "title beats").map((v) => copy(v, "title beat", 45, 820, 38, 2));
    return done(ID16, p);
  }
  function state16(p, seconds) {
    const q = time(p, seconds), n = p.silhouette_paths.length, index = Math.min(n - 1, Math.floor(q.u * n)), local = q.u * n - index, previous = p.iris_targets[Math.max(0, index - 1)], target7 = p.iris_targets[index], k = smooth3(local), iris = { x: 280 + 520 * lerp3(previous.x, target7.x, k), y: 830 + 380 * lerp3(previous.y, target7.y, k), r: 195 + 50 * Math.sin(Math.PI * local) }, shapeX = iris.x - 340 + 680 * local, angle = lerp3(p.mask_angles[Math.max(0, index - 1)], p.mask_angles[index], k);
    return { ...q, index, local, iris, shape: p.silhouette_paths[index], shapeX, angle, title: p.title_cues[index], titleOpacity: index === n - 1 ? smooth3(local) : Math.sin(Math.PI * local) };
  }
  var sample16 = (spec, seconds) => state16(validateSpec16(spec).parameters, seconds);
  function render16(spec, seconds) {
    const p = validateSpec16(spec).parameters, s = state16(p, seconds), c = p.palette;
    const shape = s.shape === "spindle" ? `<path d="M-100 0Q0 -250 100 0Q0 250 -100 0Z"/>` : s.shape === "wedge" ? `<path d="M-140 -150L160 0L-110 170Z"/>` : `<path d="M0 -195L125 0L0 195L-125 0Z"/>`;
    let body = `<defs><clipPath id="isc-iris"><circle cx="${fmt3(s.iris.x)}" cy="${fmt3(s.iris.y)}" r="${fmt3(s.iris.r)}"/></clipPath><clipPath id="isc-angle"><rect x="${fmt3(s.iris.x - 235)}" y="${fmt3(s.iris.y - 180)}" width="470" height="360" transform="rotate(${fmt3(s.angle)} ${fmt3(s.iris.x)} ${fmt3(s.iris.y)})"/></clipPath></defs><circle cx="${fmt3(s.iris.x)}" cy="${fmt3(s.iris.y)}" r="${fmt3(s.iris.r)}" fill="none" stroke="${c.ink}" stroke-width="5"/><g clip-path="url(#isc-iris)"><g clip-path="url(#isc-angle)"><path d="M100 ${fmt3(s.iris.y - 145)}H980V${fmt3(s.iris.y + 145)}H100Z" fill="${c.muted}" opacity="0.16"/><g transform="translate(${fmt3(s.shapeX)} ${fmt3(s.iris.y)}) rotate(${fmt3(s.angle)})" fill="${c.accent}">${shape}</g></g></g><g opacity="${fmt3(s.titleOpacity)}">${label(s.title, 130, 1430, 820, 38, c.ink, 2)}</g>`;
    return page(ID16, p, s.seconds, body, { layout: "center" });
  }

  // renderers/template-registry/modules/bc1bbb0f9f88-baseline-type-reflow.mjs
  var bc1bbb0f9f88_baseline_type_reflow_exports = {};
  __export(bc1bbb0f9f88_baseline_type_reflow_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE17,
    ID: () => ID17,
    METADATA: () => METADATA9,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA17,
    SOURCE_ID: () => SOURCE_ID17,
    render: () => render17,
    sample: () => sample17,
    validateSpec: () => validateSpec17
  });
  var ID17 = "baseline-type-reflow";
  var SOURCE_ID17 = "source-lemo-style-swiss-motion";
  var DEFAULT_PALETTE17 = PALETTES.paper;
  var METADATA9 = meta("Ortak tabanda yeniden akan yaz\u0131", "measured-type", "two-to-one-type", "measured word anchor reflow with size and tracking endpoints", "asymmetric rule / two columns / final single passage");
  var PARAMETER_SCHEMA17 = { copy: { maxLength: 150 }, column_ratios: { exactItems: 2, range: [0.35, 0.65], sum: 1 }, baseline_step: [60, 76], type_scale: [0.85, 1.1], tracking_curve: { exactItems: 2, range: [-0.5, 1.5] } };
  function wordLayout(p,size,tracking,widths){
   const tokens=[];let column=0,row=0,x=0;
   for(const word of p.copy.split(' ')){
    const width=textUnits3(word)*size+Math.max(0,[...word].length-1)*tracking,gap=x?size*.36+tracking:0;
    if(width>widths[column])return null;
    if(x&&x+gap+width>widths[column]){row++;x=0;}
    if(row>=9){column++;row=0;x=0;}
    if(column>=widths.length||width>widths[column])return null;
    const actualGap=x?size*.36+tracking:0;
    tokens.push({word,x:110+(column?widths[0]+36:0)+x+actualGap,y:730+row*p.baseline_step,width,column,row});
    x+=actualGap+width;
   }
   return tokens;
  }
  function packed(p,amount){
   const size=lerp3(38,50,amount)*p.type_scale,tracking=lerp3(...p.tracking_curve,amount),first=lerp3(850*p.column_ratios[0]-18,850,amount);
   let tokens=wordLayout(p,size,tracking,amount===1?[850]:[first,850-first-36]);
   // Line breaks change atomically. Never interpolate individual words through
   // another row. When a shrinking second column cannot hold its words, merge
   // into the full field; bounded advances never exceed the validated endpoint.
   if(!tokens&&amount>0&&amount<1)tokens=wordLayout(p,size,tracking,[850]);
   if(!tokens)fail3('copy exceeds its measured columns or registered baseline field');
   return{tokens,size,tracking};
  }
  function validateSpec17(spec) {
    const p = base(spec, ID17, ["copy", "column_ratios", "baseline_step", "type_scale", "tracking_curve"], {}, DEFAULT_PALETTE17), r = spec.parameters;
    p.copy = copy(r.copy, "copy", 150, 850, 38, 8);
    p.column_ratios = list(r.column_ratios, 2, 2, "column ratios").map((v) => number3(v, "column ratio", 0.35, 0.65));
    if (Math.abs(p.column_ratios[0] + p.column_ratios[1] - 1) > 1e-9) fail3("column ratios must sum to one");
    p.baseline_step = number3(r.baseline_step, "baseline step", 60, 76);
    p.type_scale = number3(r.type_scale, "type scale", 0.85, 1.1);
    p.tracking_curve = list(r.tracking_curve, 2, 2, "tracking curve").map((v) => number3(v, "tracking", -0.5, 1.5));
    if (p.baseline_step < 50 * p.type_scale * 1.24) fail3("baseline spacing must clear the largest type");
    packed(p, 0);
    packed(p, 1);
    return done(ID17, p);
  }
  function state17(p,seconds){const q=time(p,seconds),amount=ease(q.u,.12,.85),a=packed(p,0),b=packed(p,1),current=packed(p,amount),tokens=current.tokens.map((v,i)=>({word:v.word,x:v.x,y:v.y,width:v.width,from:a.tokens[i],to:b.tokens[i]}));return{...q,amount,fontSize:current.size,tracking:current.tracking,tokens,anchor:{x:110,y:730}};}
  var sample17 = (spec, seconds) => state17(validateSpec17(spec).parameters, seconds);
  function render17(spec, seconds) {
    const p = validateSpec17(spec).parameters, s = state17(p, seconds), c = p.palette;
    let body = Array.from({ length: 10 }, (_, i) => line({ x: 110, y: 730 + i * p.baseline_step }, { x: 960, y: 730 + i * p.baseline_step }, c.muted, 1, 'opacity="0.25"')).join("");
    body += s.tokens.map((v) => `<text data-motion-role="reflow-word" x="${fmt3(v.x)}" y="${fmt3(v.y)}" fill="${c.ink}" font-size="${fmt3(s.fontSize)}" letter-spacing="${fmt3(s.tracking)}" font-weight="550">${esc3(v.word)}</text>`).join("");
    return page(ID17, p, s.seconds, body, { layout: "side" });
  }

  // renderers/template-registry/modules/f3a7cd528c4a-dimension-construction.mjs
  var f3a7cd528c4a_dimension_construction_exports = {};
  __export(f3a7cd528c4a_dimension_construction_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE18,
    ID: () => ID18,
    METADATA: () => METADATA10,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA18,
    SOURCE_ID: () => SOURCE_ID18,
    render: () => render18,
    sample: () => sample18,
    validateSpec: () => validateSpec18
  });
  var ID18 = "dimension-construction";
  var SOURCE_ID18 = "source-lemo-style-blueprint";
  var DEFAULT_PALETTE18 = PALETTES.blue;
  var METADATA10 = meta("Kay\u0131tl\u0131 \xF6l\xE7\xFCler ve kesit \xE7izimi", "orthographic-section", "dimensioned-elevation", "ordered construction strokes and registered section plane", "wide drawing title / orthographic plate / dimension rails");
  var PARAMETER_SCHEMA18 = { dimension_values: { width: [160, 360], height: [140, 280], depth: [80, 150] }, section_position: [0.2, 0.8], construction_order: { permutation: ["outline", "axes", "dimension"] }, part_count: [2, 4] };
  function numericLabels(p) {
    return [["W \xB7 Geni\u015Flik", p.dimension_values.width], ["H \xB7 Y\xFCkseklik", p.dimension_values.height], ["D \xB7 Derinlik", p.dimension_values.depth]].map(([name, value], i) => label(`${name} ${value} mm`, 100, 1400 + i * 60, 880, 34, p.palette.ink, 1)).join("");
  }
  function validateSpec18(spec) {
    const p = base(spec, ID18, ["dimension_values", "section_position", "construction_order", "part_count"], {}, DEFAULT_PALETTE18), r = spec.parameters;
    keys3(r.dimension_values, ["width", "height", "depth"]);
    p.dimension_values = { width: number3(r.dimension_values.width, "width", 160, 360), height: number3(r.dimension_values.height, "height", 140, 280), depth: number3(r.dimension_values.depth, "depth", 80, 150) };
    p.section_position = number3(r.section_position, "section position", 0.2, 0.8);
    p.construction_order = permutation(r.construction_order, ["outline", "axes", "dimension"], "construction order");
    p.part_count = number3(r.part_count, "part count", 2, 4, true);
    numericLabels(p);
    return done(ID18, p);
  }
  function state18(p, seconds) {
    const q = time(p, seconds), scale = 1.55, width = p.dimension_values.width * scale, height = p.dimension_values.height * scale, box3 = { x: 540 - width / 2, y: 980 - height / 2, width, height }, depthScale = 0.7, depthSpan = p.dimension_values.depth * depthScale, depthBox = { x: box3.x + width + 25, y: box3.y, width: depthSpan, height }, layers = Object.fromEntries(p.construction_order.map((id, i) => [id, ease(q.u, i * 0.16, 0.35 + i * 0.16)])), section = ease(q.u, 0.46, 0.84), sectionX = box3.x + box3.width * p.section_position * section, parts = Array.from({ length: p.part_count }, (_, i) => ({ x: box3.x, y: box3.y + i * height / p.part_count, width, height: height / p.part_count }));
    return { ...q, scale, depthScale, depthSpan, depthBox, box: box3, layers, section, sectionX, parts, dimensionSpan: width, verticalSpan: height };
  }
  var sample18 = (spec, seconds) => state18(validateSpec18(spec).parameters, seconds);
  function render18(spec, seconds) {
    const p = validateSpec18(spec).parameters, s = state18(p, seconds), c = p.palette, b = s.box, d = s.depthBox;
    const stroke = (path6, color2, width, amount) => `<path d="${path6}" fill="none" stroke="${color2}" stroke-width="${width}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt3(1 - amount)}"/>`;
    let body = stroke("M180 980H960M540 650V1330", c.muted, 2, s.layers.axes);
    body += stroke(`M${fmt3(b.x)} ${fmt3(b.y)}h${fmt3(b.width)}v${fmt3(b.height)}h${fmt3(-b.width)}Z`, c.ink, 3, s.layers.outline);
    body += stroke(`M${fmt3(d.x)} ${fmt3(d.y)}h${fmt3(d.width)}v${fmt3(d.height)}h${fmt3(-d.width)}Z`, c.ink, 3, s.layers.outline);
    body += s.parts.slice(1).map((v) => stroke(`M${fmt3(v.x)} ${fmt3(v.y)}h${fmt3(v.width)}`, c.ink, 3, s.layers.outline)).join("");
    body += stroke(`M${fmt3(b.x)} 1320H${fmt3(b.x + b.width)}M${fmt3(b.x)} 1308v24M${fmt3(b.x + b.width)} 1308v24M210 ${fmt3(b.y)}V${fmt3(b.y + b.height)}M198 ${fmt3(b.y)}h24M198 ${fmt3(b.y + b.height)}h24M${fmt3(d.x)} 1320h${fmt3(d.width)}`, c.accent, 3, s.layers.dimension);
    body += `<g opacity="${fmt3(s.layers.dimension)}">${label("W", 540, 1305, 400, 28, c.ink, 1, "middle")}${label("H", 110, 980, 140, 28, c.ink, 1)}${label("D", d.x + d.width / 2, 1305, 150, 28, c.ink, 1, "middle")}${numericLabels(p)}</g>`;
    body += line({ x: s.sectionX, y: b.y - 30 }, { x: s.sectionX, y: b.y + b.height + 30 }, c.accent, 4) + `<g opacity="${fmt3(s.section)}">${label("\xD6n g\xF6r\xFCn\xFC\u015F ve yan kesit ayn\u0131 y\xFCksekli\u011Fe kay\u0131tl\u0131d\u0131r.", 150, 600, 780, 30, c.ink, 2)}</g>`;
    return page(ID18, p, s.seconds, body);
  }

  // renderers/template-registry/modules/20995b5e308b-board-pin-routing.mjs
  var b5e308b_board_pin_routing_exports = {};
  __export(b5e308b_board_pin_routing_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE19,
    ID: () => ID19,
    METADATA: () => METADATA11,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA19,
    SOURCE_ID: () => SOURCE_ID19,
    render: () => render19,
    sample: () => sample19,
    validateSpec: () => validateSpec19
  });
  var ID19 = "board-pin-routing";
  var SOURCE_ID19 = "source-lemo-style-briefing-board";
  var DEFAULT_PALETTE19 = PALETTES.paper;
  var METADATA11 = meta("Pimlere gerilen inceleme panosu", "tension-board", "registered-cards", "fixed pins, thread de-slacking, inspection traversal", "board title / fixed cards and threads / inspection key");
  var PARAMETER_SCHEMA19 = { pin_positions: { minItems: 2, maxItems: 4, point: [0.1, 0.9], labelMaxLength: 30 }, thread_routes: { minItems: 1, maxItems: 5 }, card_count: [2, 4], inspection_order: { permutation: "all pin indices" } };
  function validateSpec19(spec) {
    const p = base(spec, ID19, ["pin_positions", "thread_routes", "card_count", "inspection_order"], {}, DEFAULT_PALETTE19), r = spec.parameters;
    p.pin_positions = list(r.pin_positions, 2, 4, "pins").map((v) => {
      keys3(v, ["x", "y", "label"]);
      return { ...point({ x: v.x, y: v.y }, "pin", 0.1, 0.9), label: copy(v.label, "card label", 30, 230, 32, 2) };
    });
    p.card_count = number3(r.card_count, "card count", 2, 4, true);
    if (p.card_count !== p.pin_positions.length) fail3("card count must equal pin count");
    for (let i = 0; i < p.card_count; i++) for (let j = i + 1; j < p.card_count; j++) {
      const a = p.pin_positions[i], b = p.pin_positions[j];
      if (Math.abs(a.x - b.x) * 760 < 290 && Math.abs(a.y - b.y) * 650 < 150) fail3("cards must have nonoverlapping registered slots");
    }
    const seen = /* @__PURE__ */ new Set();
    p.thread_routes = list(r.thread_routes, 1, 5, "threads").map((v) => {
      keys3(v, ["from", "to"]);
      const from = number3(v.from, "thread from", 0, p.card_count - 1, true), to = number3(v.to, "thread to", 0, p.card_count - 1, true), key = `${from}-${to}`;
      if (from === to || seen.has(key)) fail3("thread route must be unique with distinct endpoints");
      seen.add(key);
      return { from, to };
    });
    p.inspection_order = permutation(r.inspection_order, Array.from({ length: p.card_count }, (_, i) => i), "inspection");
    return done(ID19, p);
  }
  function state19(p, seconds) {
    const q = time(p, seconds), pins = p.pin_positions.map((v) => ({ ...v, x: 160 + v.x * 760, y: 680 + v.y * 650 })), threads = p.thread_routes.map((v, i) => {
      const amount = ease(q.u, i * 0.04, 0.48 + i * 0.04), a = pins[v.from], b = pins[v.to];
      return { from: v.from, to: v.to, a, b, control: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 + 75 * (1 - amount) }, slack: 75 * (1 - amount) };
    }), inspection = along(p.inspection_order.map((i) => pins[i]), ease(q.u, 0.62, 0.9));
    return { ...q, pins, threads, inspection };
  }
  var sample19 = (spec, seconds) => state19(validateSpec19(spec).parameters, seconds);
  function render19(spec, seconds) {
    const p = validateSpec19(spec).parameters, s = state19(p, seconds), c = p.palette;
    let body = `<rect x="100" y="600" width="880" height="900" fill="none" stroke="${c.muted}" stroke-width="2"/>`;
    body += s.threads.map((v) => `<path d="M${fmt3(v.a.x)} ${fmt3(v.a.y)}Q${fmt3(v.control.x)} ${fmt3(v.control.y)} ${fmt3(v.b.x)} ${fmt3(v.b.y)}" fill="none" stroke="${c.accent}" stroke-width="5"/>`).join("");
    body += s.pins.map((v, i) => `<rect x="${fmt3(v.x - 135)}" y="${fmt3(v.y - 60)}" width="270" height="120" fill="${c.background}" stroke="${c.ink}" stroke-width="2"/>${label(v.label, v.x - 115, v.y + 10, 230, 32, c.ink, 2)}<circle cx="${fmt3(v.x)}" cy="${fmt3(v.y - 52)}" r="9" fill="${c.accent}"/>`).join("");
    body += `<rect x="${fmt3(s.inspection.x - 144)}" y="${fmt3(s.inspection.y - 70)}" width="288" height="140" rx="10" fill="none" stroke="${c.accent}" stroke-width="5"/>`;
    return page(ID19, p, s.seconds, body, { layout: "side" });
  }

  // renderers/template-registry/modules/55d03e84a019-bead-transfer-counts.mjs
  var d03e84a019_bead_transfer_counts_exports = {};
  __export(d03e84a019_bead_transfer_counts_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE20,
    ID: () => ID20,
    METADATA: () => METADATA12,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA20,
    SOURCE_ID: () => SOURCE_ID20,
    render: () => render20,
    sample: () => sample20,
    validateSpec: () => validateSpec20
  });
  var ID20 = "bead-transfer-counts";
  var SOURCE_ID20 = "source-lemo-style-data-physical";
  var DEFAULT_PALETTE20 = PALETTES.paper;
  var METADATA12 = meta("Tanelerle korunan say\u0131m", "physical-count", "bins-and-inventory", "stable bead identities, departure arcs, slot settling", "physical bins / count labels / conservation equation");
  var PARAMETER_SCHEMA20 = { bin_values: { minItems: 2, maxItems: 3, count: [1, 8], totalMaximum: 18, labelMaxLength: 30 }, transfer_order: { minItems: 1, maxItems: 4, count: [1, 5] }, bead_unit: [1, 50], settle_duration: [0.2, 0.6] };
  function validateSpec20(spec) {
    const p = base(spec, ID20, ["bin_values", "transfer_order", "bead_unit", "settle_duration"], {}, DEFAULT_PALETTE20), r = spec.parameters;
    p.bin_values = list(r.bin_values, 2, 3, "bins").map((v) => {
      keys3(v, ["label", "count"]);
      return { label: copy(v.label, "bin label", 30, 210, 30, 2), count: number3(v.count, "bead count", 1, 8, true) };
    });
    if (p.bin_values.reduce((s, v) => s + v.count, 0) > 18) fail3("at most eighteen beads");
    const inventory = p.bin_values.map((v) => v.count);
    p.transfer_order = list(r.transfer_order, 1, 4, "transfers").map((v) => {
      keys3(v, ["from", "to", "count"]);
      const from = number3(v.from, "source bin", 0, inventory.length - 1, true), to = number3(v.to, "destination bin", 0, inventory.length - 1, true), count = number3(v.count, "transfer count", 1, 5, true);
      if (from === to || inventory[from] < count) fail3("transfer cannot overdraw or target its source");
      inventory[from] -= count;
      inventory[to] += count;
      return { from, to, count };
    });
    p.bead_unit = number3(r.bead_unit, "bead unit", 1, 50, true);
    p.settle_duration = number3(r.settle_duration, "settle duration", 0.2, 0.6);
    if (p.settle_duration > (p.duration - 0.75) / p.transfer_order.length * 0.35) fail3("settle duration exceeds available transfer slot");
    return done(ID20, p);
  }
  function slot(bin, index, count) {
    const center = count === 2 ? 300 + bin * 480 : 240 + bin * 300;
    return { x: center - 72 + index % 4 * 48, y: 1240 - Math.floor(index / 4) * 48 };
  }
  function state20(p, seconds) {
    const q = time(p, seconds), bins = p.bin_values.map(() => []);
    let nextId = 0;
    for (let i = 0; i < bins.length; i++) for (let j = 0; j < p.bin_values[i].count; j++) bins[i].push(nextId++);
    const n = p.transfer_order.length, index = q.u === 1 ? n : Math.floor(q.u * n), local = q.u * n - index;
    for (let i = 0; i < index; i++) {
      const v = p.transfer_order[i], moving2 = bins[v.from].splice(-v.count);
      bins[v.to].push(...moving2);
    }
    const beads = [];
    let moving = [], event = null;
    if (index < n) {
      event = p.transfer_order[index];
      moving = bins[event.from].slice(-event.count);
    }
    for (let bin = 0; bin < bins.length; bin++) for (let i = 0; i < bins[bin].length; i++) if (!moving.includes(bins[bin][i])) beads.push({ id: bins[bin][i], owner: bin, ...slot(bin, i, bins.length), progress: 1 });
    if (event) {
      const end = 1 - p.settle_duration / (q.active / n), sourceStart = bins[event.from].length - event.count, destinationStart = bins[event.to].length;
      moving.forEach((id, i) => {
        const begin = moving.length === 1 ? 0 : i / (moving.length - 1) * 0.15, progress = smooth3((local - begin) / (end - begin)), a = slot(event.from, sourceStart + i, bins.length), b = slot(event.to, destinationStart + i, bins.length);
        beads.push({ id, owner: progress === 0 ? event.from : progress === 1 ? event.to : -1, x: lerp3(a.x, b.x, progress), y: lerp3(a.y, b.y, progress) - 135 * Math.sin(Math.PI * progress), progress });
      });
    }
    beads.sort((a, b) => a.id - b.id);
    const inventory = bins.map((_, i) => beads.filter((v) => v.owner === i).length), transit = beads.filter((v) => v.owner < 0).length;
    return { ...q, index, local, beads, inventory, transit, total: nextId, quantity: nextId * p.bead_unit };
  }
  var sample20 = (spec, seconds) => state20(validateSpec20(spec).parameters, seconds);
  function render20(spec, seconds) {
    const p = validateSpec20(spec).parameters, s = state20(p, seconds), c = p.palette, n = p.bin_values.length;
    let body = p.bin_values.map((v, i) => {
      const x = n === 2 ? 300 + i * 480 : 240 + i * 300;
      return `<path d="M${x - 110} 970V1305H${x + 110}V970" fill="none" stroke="${c.ink}" stroke-width="4"/>${label(String(s.inventory[i] * p.bead_unit), x - 105, 1360, 210, 38, c.ink, 1)}${label(v.label, x - 105, 1410, 210, 30, c.ink, 2)}`;
    }).join("");
    body += s.beads.map((v) => `<circle data-bead="${v.id}" cx="${fmt3(v.x)}" cy="${fmt3(v.y)}" r="16" fill="${v.owner < 0 ? c.muted : c.accent}" stroke="${c.ink}" stroke-width="2"/>`).join("") + label(`Toplam ${s.quantity} \xB7 Yolda ${s.transit * p.bead_unit}`, 135, 1510, 810, 32, c.ink, 1);
    return page(ID20, p, s.seconds, body);
  }

  // renderers/template-registry/modules/71dc1665fa7e-scale-morph-charts.mjs
  var dc1665fa7e_scale_morph_charts_exports = {};
  __export(dc1665fa7e_scale_morph_charts_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE21,
    ID: () => ID21,
    METADATA: () => METADATA13,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA21,
    SOURCE_ID: () => SOURCE_ID21,
    render: () => render21,
    sample: () => sample21,
    validateSpec: () => validateSpec21
  });
  var ID21 = "scale-morph-charts";
  var SOURCE_ID21 = "source-lemo-style-dataviz";
  var DEFAULT_PALETTE21 = PALETTES.blue;
  var METADATA13 = meta("Sabit \xF6l\xE7ekte de\u011Fi\u015Fen veri bi\xE7imi", "registered-chart", "plot-and-domain", "same datum anchors across dots, line and area modes", "numeric domain / registered plot / two axis labels");
  var PARAMETER_SCHEMA21 = { series_values: { minItems: 3, maxItems: 6, range: [0, 100] }, chart_sequence: { minItems: 2, maxItems: 3, enum: ["dots", "line", "area"], first: "dots", unique: true }, domain_bounds: { exactItems: 2, range: [0, 120] }, axis_labels: { exactItems: 2, maxLength: 20 } };
  function quarterTicks(bounds3) {
    const decimals = bounds3.map((value) => {
      const [coefficient, power = "0"] = String(value).split("e"), fraction = coefficient.split(".")[1] ?? "";
      return { integer: BigInt(coefficient.replace(".", "")), places: fraction.length - Number(power) };
    });
    const places = Math.max(0, ...decimals.map((v) => v.places)), [a, b] = decimals.map((v) => v.integer * 10n ** BigInt(places - v.places));
    return Array.from({ length: 5 }, (_, i) => {
      const digits = ((a * BigInt(4 - i) + b * BigInt(i)) * 25n).toString().padStart(places + 3, "0");
      return (digits.slice(0, -places - 2) + "." + digits.slice(-places - 2)).replace(/\.?0+$/u, "");
    });
  }
  function numericLabels2(p) {
    try {
      return quarterTicks(p.domain_bounds).map((value, i) => label(value, 250, 1390 - i * 155, 155, 28, p.palette.muted, 1, "end")).join("");
    } catch (error) {
      if (error.name === "InputError") fail3("domain_bounds: exact tick labels need shorter decimals (155px axis slot, minimum 28px)");
      throw error;
    }
  }
  function validateSpec21(spec) {
    const p = base(spec, ID21, ["series_values", "chart_sequence", "domain_bounds", "axis_labels"], {}, DEFAULT_PALETTE21), r = spec.parameters;
    p.domain_bounds = list(r.domain_bounds, 2, 2, "domain").map((v) => number3(v, "domain bound", 0, 120));
    if (p.domain_bounds[1] - p.domain_bounds[0] < 10) fail3("domain must have at least ten units");
    p.series_values = list(r.series_values, 3, 6, "series").map((v) => number3(v, "datum", Math.max(0, p.domain_bounds[0]), Math.min(100, p.domain_bounds[1])));
    p.chart_sequence = list(r.chart_sequence, 2, 3, "chart sequence").map((v) => choice3(v, "chart mode", ["dots", "line", "area"]));
    if (p.chart_sequence[0] !== "dots" || new Set(p.chart_sequence).size !== p.chart_sequence.length) fail3("chart starts with dots and uses unique modes");
    p.axis_labels = list(r.axis_labels, 2, 2, "axis labels").map((v) => copy(v, "axis label", 20, 620, 30, 1));
    numericLabels2(p);
    return done(ID21, p);
  }
  function state21(p, seconds) {
    const q = time(p, seconds), n = p.chart_sequence.length - 1, k = Math.min(n - 1, Math.floor(q.u * n)), local = q.u * n - k, amount = ease(local, 0.1, 0.9), from = p.chart_sequence[k], to = p.chart_sequence[k + 1], weight = (mode) => (from === mode ? 1 : 0) * (1 - amount) + (to === mode ? 1 : 0) * amount, points = p.series_values.map((value, i) => ({ value, x: 270 + i * 630 / (p.series_values.length - 1), y: 1380 - (value - p.domain_bounds[0]) / (p.domain_bounds[1] - p.domain_bounds[0]) * 620 }));
    return { ...q, from, to, amount, points, lineFraction: weight("line") + weight("area"), areaFraction: weight("area"), domain: [...p.domain_bounds] };
  }
  var sample21 = (spec, seconds) => state21(validateSpec21(spec).parameters, seconds);
  function render21(spec, seconds) {
    const p = validateSpec21(spec).parameters, s = state21(p, seconds), c = p.palette;
    let body = line({ x: 270, y: 730 }, { x: 270, y: 1380 }, c.ink, 3) + line({ x: 270, y: 1380 }, { x: 930, y: 1380 }, c.ink, 3);
    for (let i = 0; i <= 4; i++) {
      const y = 1380 - i * 155;
      body += line({ x: 270, y }, { x: 930, y }, c.muted, 1, 'opacity="0.25"');
    }
    body += numericLabels2(p) + `<path d="${path2([{ x: s.points[0].x, y: 1380 }, ...s.points, { x: s.points.at(-1).x, y: 1380 }], true)}" fill="${c.accent}" opacity="${fmt3(s.areaFraction * 0.2)}"/><path d="${path2(s.points)}" fill="none" stroke="${c.accent}" stroke-width="5" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt3(1 - s.lineFraction)}"/>`;
    body += s.points.map((v) => `<circle cx="${fmt3(v.x)}" cy="${fmt3(v.y)}" r="9" fill="${c.ink}"/>`).join("") + label(p.axis_labels[0], 285, 680, 620, 30, c.ink, 1) + label(p.axis_labels[1], 280, 1470, 620, 30, c.ink, 1);
    return page(ID21, p, s.seconds, body);
  }

  // renderers/template-registry/modules/b37cccf12fab-iso-transport-network.mjs
  var b37cccf12fab_iso_transport_network_exports = {};
  __export(b37cccf12fab_iso_transport_network_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE22,
    ID: () => ID22,
    METADATA: () => METADATA14,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA22,
    SOURCE_ID: () => SOURCE_ID22,
    render: () => render22,
    sample: () => sample22,
    validateSpec: () => validateSpec22
  });
  var ID22 = "iso-transport-network";
  var SOURCE_ID22 = "source-lemo-style-iso-infographic";
  var DEFAULT_PALETTE22 = PALETTES.blue;
  var METADATA14 = meta("\u0130zometrik kanallarda korunan paketler", "branch-flow", "isometric-junctions", "depth sorted channels and conserved branched packet routing", "route header / extruded junction network / inventories");
  var PARAMETER_SCHEMA22 = { node_positions: { minItems: 3, maxItems: 5, point: [0.1, 0.9], labelMaxLength: 18 }, flow_values: { minItems: 2, maxItems: 4, packets: [1, 6] }, route_order: { permutation: "all flow indices" }, packet_unit: [1, 100] };
  function validateSpec22(spec) {
    const p = base(spec, ID22, ["node_positions", "flow_values", "route_order", "packet_unit"], {}, DEFAULT_PALETTE22), r = spec.parameters;
    p.node_positions = list(r.node_positions, 3, 5, "nodes").map((v) => {
      keys3(v, ["x", "y", "label"]);
      return { ...point({ x: v.x, y: v.y }, "node", 0.1, 0.9), label: copy(v.label, "node label", 18, 850 / r.node_positions.length - 12, 28, 2) };
    });
    const n = p.node_positions.length, seen = /* @__PURE__ */ new Set();
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const a = iso(p.node_positions[i].x * 3, p.node_positions[i].y * 3, 0, { x: 540, y: 820 }, 110), b = iso(p.node_positions[j].x * 3, p.node_positions[j].y * 3, 0, { x: 540, y: 820 }, 110);
      if (Math.hypot(a.x - b.x, a.y - b.y) < 100) fail3("junction pads need distinct separated positions");
    }
    p.flow_values = list(r.flow_values, 2, 4, "flows").map((v) => {
      keys3(v, ["from", "to", "packets"]);
      const from = number3(v.from, "from", 0, n - 1, true), to = number3(v.to, "to", 0, n - 1, true), packets = number3(v.packets, "packets", 1, 6, true), key = `${from}-${to}`;
      if (to <= from || seen.has(key)) fail3("unique forward acyclic routes required");
      seen.add(key);
      return { from, to, packets };
    });
    p.route_order = permutation(r.route_order, p.flow_values.map((_, i) => i), "route order");
    const stock = Array(n).fill(0);
    stock[0] = p.flow_values.filter((v) => v.from === 0).reduce((s, v) => s + v.packets, 0);
    if (stock[0] < 1 || stock[0] > 16) fail3("root must supply 1..16 packets");
    for (const i of p.route_order) {
      const v = p.flow_values[i];
      if (stock[v.from] < v.packets) fail3("route order cannot overdraw a junction");
      stock[v.from] -= v.packets;
      stock[v.to] += v.packets;
    }
    p.packet_unit = number3(r.packet_unit, "packet unit", 1, 100, true);
    return done(ID22, p);
  }
  function state22(p, seconds) {
    const q = time(p, seconds), nodes = p.node_positions.map((v2) => ({ ...v2, ...iso(v2.x * 3, v2.y * 3, 0, { x: 540, y: 820 }, 110) })), total = p.flow_values.filter((v2) => v2.from === 0).reduce((s, v2) => s + v2.packets, 0), bins = nodes.map(() => []);
    bins[0] = Array.from({ length: total }, (_, i) => i);
    const n = p.route_order.length, index = q.u === 1 ? n : Math.floor(q.u * n), local = q.u * n - index;
    for (let k = 0; k < index; k++) {
      const v2 = p.flow_values[p.route_order[k]];
      bins[v2.to].push(...bins[v2.from].splice(-v2.packets));
    }
    const v = index < n ? p.flow_values[p.route_order[index]] : null, moving = v ? bins[v.from].slice(-v.packets) : [], slot2 = (node, j) => ({ x: nodes[node].x + j % 4 * 10 - 15, y: nodes[node].y - Math.floor(j / 4) * 9 - 12 }), packets = [];
    for (let bin = 0; bin < bins.length; bin++) bins[bin].forEach((id, j) => {
      if (!moving.includes(id)) packets.push({ id, owner: bin, ...slot2(bin, j) });
    });
    if (v) moving.forEach((id, j) => {
      const progress = smooth3((local - j * 0.025) / (0.78 - j * 0.025)), a = slot2(v.from, bins[v.from].length - v.packets + j), b = slot2(v.to, bins[v.to].length + j);
      packets.push({ id, owner: progress === 0 ? v.from : progress === 1 ? v.to : -1, x: lerp3(a.x, b.x, progress), y: lerp3(a.y, b.y, progress) - 22 * Math.sin(Math.PI * progress) });
    });
    packets.sort((a, b) => a.id - b.id);
    const inventories = nodes.map((_, i) => packets.filter((v2) => v2.owner === i).length), transit = packets.filter((v2) => v2.owner < 0).length;
    return { ...q, index, local, nodes, packets, inventories, transit, total, quantity: total * p.packet_unit, channels: p.flow_values.map((v2) => ({ ...v2, a: nodes[v2.from], b: nodes[v2.to] })).sort((a, b) => a.a.y + a.b.y - (b.a.y + b.b.y)) };
  }
  var sample22 = (spec, seconds) => state22(validateSpec22(spec).parameters, seconds);
  function render22(spec, seconds) {
    const p = validateSpec22(spec).parameters, s = state22(p, seconds), c = p.palette;
    let body = s.channels.map((v) => line({ x: v.a.x, y: v.a.y + 8 }, { x: v.b.x, y: v.b.y + 8 }, c.muted, 22) + line(v.a, v.b, c.ink, 18) + line(v.a, v.b, c.background, 12) + line(v.a, v.b, c.accent, 3)).join("");
    body += s.nodes.map((v, i) => polygon([{ x: v.x - 46, y: v.y }, { x: v.x, y: v.y - 24 }, { x: v.x + 46, y: v.y }, { x: v.x, y: v.y + 24 }], c.background, c.ink, 3) + `<path d="M${fmt3(v.x - 46)} ${fmt3(v.y)}v14l46 24 46-24v-14" fill="none" stroke="${c.ink}" stroke-width="3"/>` + label(String(s.inventories[i] * p.packet_unit), v.x, v.y + 80, 140, 30, c.ink, 1, "middle")).join("");
    body += s.packets.map((v) => `<rect data-packet="${v.id}" x="${fmt3(v.x - 4)}" y="${fmt3(v.y - 4)}" width="8" height="8" fill="${c.accent}" stroke="${c.ink}" stroke-width="1"/>`).join("") + p.node_positions.map((v, i) => label(v.label, 110 + i * 850 / s.nodes.length, 1390, 850 / s.nodes.length - 12, 28, c.ink, 2)).join("") + label(`Toplam ${s.quantity} \xB7 Yolda ${s.transit * p.packet_unit}`, 130, 1520, 800, 30, c.ink, 1);
    return page(ID22, p, s.seconds, body);
  }

  // renderers/template-registry/modules/97accaca81a3-constrained-part-section.mjs
  var accaca81a3_constrained_part_section_exports = {};
  __export(accaca81a3_constrained_part_section_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE23,
    ID: () => ID23,
    METADATA: () => METADATA15,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA23,
    SOURCE_ID: () => SOURCE_ID23,
    render: () => render23,
    sample: () => sample23,
    validateSpec: () => validateSpec23
  });
  var ID23 = "constrained-part-section";
  var SOURCE_ID23 = "source-lemo-style-teardown";
  var DEFAULT_PALETTE23 = PALETTES.paper;
  var METADATA15 = meta("K\u0131s\u0131tlara d\xF6nen par\xE7al\u0131 kesit", "constrained-assembly", "sectioned-parts", "unit-axis separation, traveling section, exact assembly return", "left title rail / original sectioned stack / assembly key");
  var PARAMETER_SCHEMA23 = { part_geometry: { minItems: 2, maxItems: 4, width: [140, 260], height: [60, 110], depth: [40, 80], labelMaxLength: 24 }, assembly_axes: { matchingItems: true, unitVectors: true }, section_plane: [0.2, 0.8], explosion_distance: [60, 150] };
  function validateSpec23(spec) {
    const p = base(spec, ID23, ["part_geometry", "assembly_axes", "section_plane", "explosion_distance"], {}, DEFAULT_PALETTE23), r = spec.parameters;
    p.part_geometry = list(r.part_geometry, 2, 4, "parts").map((v) => {
      keys3(v, ["width", "height", "depth", "label"]);
      const width = number3(v.width, "part width", 140, 260), height = number3(v.height, "part height", 60, 110), depth = number3(v.depth, "part depth", 40, 80), label5 = copy(v.label, "part label", 24, width - 20, 28, 2);
      return { width, height, depth, label: label5 };
    });
    p.assembly_axes = list(r.assembly_axes, p.part_geometry.length, p.part_geometry.length, "axes").map((v) => {
      const a = point(v, "axis", -1, 1);
      if (Math.abs(Math.hypot(a.x, a.y) - 1) > 1e-6) fail3("assembly axes must be unit vectors");
      return a;
    });
    p.section_plane = number3(r.section_plane, "section plane", 0.2, 0.8);
    p.explosion_distance = number3(r.explosion_distance, "explosion", 60, 150);
    return done(ID23, p);
  }
  function state23(p, seconds) {
    const q = time(p, seconds), separation = ease(q.u, 0, 0.3) * (1 - ease(q.u, 0.62, 0.9)), section = ease(q.u, 0.28, 0.72), sectionOpacity = ease(q.u, 0.2, 0.35) * (1 - ease(q.u, 0.78, 0.9)), parts = p.part_geometry.map((v, i) => {
      const translation = separation === 0 ? { x: 0, y: 0 } : { x: p.assembly_axes[i].x * p.explosion_distance * separation, y: p.assembly_axes[i].y * p.explosion_distance * separation }, center = { x: 540 + translation.x, y: 800 + i * 140 + translation.y }, x = center.x - v.width / 2, y = center.y - v.height / 2, sectionX = x + v.width * p.section_plane * section;
      return { ...v, index: i, translation, center, x, y, sectionX, bounds: { left: x, right: x + v.width + v.depth * 0.5, top: y - v.depth * 0.25, bottom: y + v.height } };
    });
    return { ...q, separation, section, sectionOpacity, parts };
  }
  var sample23 = (spec, seconds) => state23(validateSpec23(spec).parameters, seconds);
  function render23(spec, seconds) {
    const p = validateSpec23(spec).parameters, s = state23(p, seconds), c = p.palette;
    let body = s.parts.map((v) => polygon([{ x: v.x, y: v.y }, { x: v.x + v.depth * 0.5, y: v.y - v.depth * 0.25 }, { x: v.x + v.width + v.depth * 0.5, y: v.y - v.depth * 0.25 }, { x: v.x + v.width, y: v.y }], c.background, c.muted, 2) + `<rect x="${fmt3(v.x)}" y="${fmt3(v.y)}" width="${v.width}" height="${v.height}" fill="${c.background}" stroke="${c.ink}" stroke-width="3"/><g opacity="${fmt3(s.sectionOpacity)}">${line({ x: v.sectionX, y: v.y - v.depth * 0.25 - 8 }, { x: v.sectionX, y: v.y + v.height + 8 }, c.accent, 5)}</g>` + label(v.label, v.x + 10, v.y + 36, v.width - 20, 28, c.ink, 2)).join("");
    body += label("Par\xE7alar kendi montaj eksenlerine d\xF6ner.", 160, 1480, 800, 32, c.ink, 2);
    return page(ID23, p, s.seconds, body, { layout: "side" });
  }

  // renderers/template-registry/modules/f2c18f83429e-engraved-hatch-growth.mjs
  var f2c18f83429e_engraved_hatch_growth_exports = {};
  __export(f2c18f83429e_engraved_hatch_growth_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE24,
    ID: () => ID24,
    METADATA: () => METADATA16,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA24,
    SOURCE_ID: () => SOURCE_ID24,
    render: () => render24,
    sample: () => sample24,
    validateSpec: () => validateSpec24
  });

  // renderers/template-registry/modules/9d0e9a74193b-shared.mjs
  var HOLD = 0.8;
  function lerp4(a, b, t) {
    return t <= 0 ? a : t >= 1 ? b : a + (b - a) * t;
  }
  function arr(v, n, lo = 1, hi = 16) {
    if (!Array.isArray(v) || Object.getPrototypeOf(v) !== Array.prototype || v.length < lo || v.length > hi || Reflect.ownKeys(v).length !== v.length + 1) fail3(`${n}: dense ordinary array ${lo}..${hi}`);
    for (let i = 0; i < v.length; i++) {
      const d = Object.getOwnPropertyDescriptor(v, String(i));
      if (!d || !d.enumerable || !Object.hasOwn(d, "value")) fail3(`${n}: dense data elements required`);
    }
    return v;
  }
  function pt(v, n = "point") {
    arr(v, n, 2, 2);
    return v.map((x, i) => number3(x, `${n}.${i}`, 0, 1));
  }
  function pts(v, n = "points", lo = 2, hi = 12) {
    return arr(v, n, lo, hi).map((x, i) => pt(x, `${n}.${i}`));
  }
  function nums(v, n, lo, hi, min = 1, max = 16) {
    return arr(v, n, min, max).map((x, i) => number3(x, `${n}.${i}`, lo, hi));
  }
  function order(v, n, length) {
    arr(v, n, length, length);
    const a = v.map((x, i) => number3(x, `${n}.${i}`, 0, length - 1, true));
    if (new Set(a).size !== length) fail3(`${n}: permutation required`);
    return a;
  }
  function words(v, n, values, min = 1, max = 8) {
    return arr(v, n, min, max).map((x, i) => choice3(x, `${n}.${i}`, values));
  }
  function color(v, n) {
    if (typeof v !== "string" || !/^#[0-9a-f]{6}$/i.test(v)) fail3(`${n}: hex color`);
    return v.toUpperCase();
  }
  function colors(v, n, min = 2, max = 5) {
    return arr(v, n, min, max).map((x, i) => color(x, `${n}.${i}`));
  }
  function label2(v, n = "label") {
    const t = text3(v, n, 48);
    fitText3(t, { width: 260, maximum: 34, minimum: 28, maxLines: 3 });
    return t;
  }
  var TITLE_LAYOUT = {
    "engraved-hatch-growth": "specimen",
    "single-path-identity": "folio",
    "pictogram-limb-transition": "side",
    "perspective-pen-wash": "folio",
    "stroke-erase-explanation": "board",
    "crayon-stroke-fill": "poster",
    "halftone-evidence-lens": "specimen",
    "paint-ridge-deposition": "folio",
    "ink-diffusion-front": "side",
    "ink-drum-misregister": "press",
    "pigment-pool-drying": "folio",
    "paper-lightbox-parallax": "lightbox",
    "page-hinge-popups": "board",
    "negative-space-cut": "side",
    "screenprint-layer-pull": "press",
    "lead-cell-lightpass": "lightbox",
    "woodblock-wave-layers": "poster",
    "carved-groove-print": "folio"
  };
  function base2(spec, id, fields, palette4) {
    keys3(spec, ["id", "version", "parameters"], [], "spec");
    keys3(spec.parameters, ["title", "duration", "narration", "cues", ...fields], ["palette"], "parameters");
    arr(spec.parameters.cues, "cues", 1, 24);
    for (const c of spec.parameters.cues) keys3(c, ["start", "end", "text"], [], "cue");
    const p = validateBase3(spec, id, fields, [], palette4), slot2 = layouts[TITLE_LAYOUT[id]];
    if (!slot2) fail3("title layout missing");
    fitText3(p.title, { width: slot2.w, maximum: slot2.size, minimum: 38, maxLines: slot2.lines });
    return p;
  }
  function schema(fields) {
    return deepFreeze2({ type: "object", additionalProperties: false, required: ["title", "duration", "narration", "cues", ...Object.keys(fields)], properties: { title: { type: "string", maxLength: 160 }, duration: { type: "number", minimum: 3, maximum: 45, multipleOf: 1 / 30 }, narration: { type: "string", maxLength: 1500 }, cues: { type: "array", minItems: 1, maxItems: 24, items: { type: "object", additionalProperties: false, required: ["start", "end", "text"], properties: { start: { type: "number", minimum: 0 }, end: { type: "number", minimum: 0 }, text: { type: "string", maxLength: 95 } } } }, palette: { type: "object", additionalProperties: false, required: ["background", "ink", "muted", "accent"], properties: Object.fromEntries(["background", "ink", "muted", "accent"].map((k) => [k, { type: "string", pattern: "^#[0-9A-Fa-f]{6}$" }])) }, ...fields } });
  }
  var N = (lo, hi, integer = false) => ({ type: integer ? "integer" : "number", minimum: lo, maximum: hi });
  var A = (items, lo = 1, hi = 16) => ({ type: "array", minItems: lo, maxItems: hi, items });
  var E = (values) => ({ type: "string", enum: values });
  var O = (fields) => ({ type: "object", additionalProperties: false, required: Object.keys(fields), properties: fields });
  var P = A(N(0, 1), 2, 2);
  var L = { type: "string", maxLength: 48 };
  var C = { type: "string", pattern: "^#[0-9A-Fa-f]{6}$" };
  function clock(p, seconds) {
    const t = sampleTime3(seconds, p.duration);
    return clamp3(t / (p.duration - HOLD));
  }
  var phase = (u, a = 0, b = 1) => smooth3((u - a) / (b - a));
  var xy = ([x, y]) => [150 + 780 * x, 520 + 860 * y];
  function line2(a, b, stroke, width = 3, opacity = 1) {
    return `<path d="M${a.map(fmt3).join(" ")}L${b.map(fmt3).join(" ")}" fill="none" stroke="${stroke}" stroke-width="${fmt3(width)}" opacity="${fmt3(opacity)}" stroke-linecap="round"/>`;
  }
  function path3(points, close = false) {
    return "M" + points.map((p, i) => (i ? "L" : "") + p.map(fmt3).join(" ")).join("") + (close ? "Z" : "");
  }
  var poly = (points, fill, stroke = "none", width = 1, opacity = 1) => `<path d="${path3(points, true)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(width)}" opacity="${fmt3(opacity)}" stroke-linejoin="round"/>`;
  var circ = (x, y, rad2, fill, stroke = "none", sw = 1, opacity = 1) => `<circle cx="${fmt3(x)}" cy="${fmt3(y)}" r="${fmt3(rad2)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(sw)}" opacity="${fmt3(opacity)}"/>`;
  var rect = (x, y, w, h, fill, stroke = "none", sw = 1, rx = 0) => `<rect x="${fmt3(x)}" y="${fmt3(y)}" width="${fmt3(w)}" height="${fmt3(h)}" rx="${fmt3(rx)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(sw)}"/>`;
  function captionLabel(t, x, y, fill, width = 260) {
    return svgText3(t, { x, y, width, maximum: 34, minimum: 28, maxLines: 3, fill, weight: 500 });
  }
  var layouts = { specimen: { x: 90, y: 190, w: 900, size: 58, lines: 3 }, folio: { x: 90, y: 1430, w: 900, size: 52, lines: 3 }, board: { x: 90, y: 180, w: 900, size: 62, lines: 3 }, poster: { x: 120, y: 220, w: 840, size: 72, lines: 3 }, lightbox: { x: 110, y: 235, w: 860, size: 54, lines: 3 }, press: { x: 90, y: 200, w: 820, size: 58, lines: 3 }, side: { x: 100, y: 250, w: 840, size: 56, lines: 3 } };
  function shell(id, p, seconds, body, layout = "specimen") {
    const a = layouts[layout];
    if (!a) fail3("layout");
    const t = sampleTime3(seconds, p.duration);
    const cue = activeCue3(p.cues, t === p.duration ? t - 1e-9 : t);
    const c = p.palette;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc3(p.title)}" data-family="${id}" data-layout="${layout}" data-duration="${fmt3(p.duration)}"><rect width="1080" height="1920" fill="${c.background}"/><g font-family="Schibsted, sans-serif">${layout === "press" ? rect(65, 465, 950, 1e3, "none", c.muted, 2) : layout === "lightbox" ? rect(95, 480, 890, 960, "none", c.muted, 3, 20) : layout === "specimen" ? line2([90, 440], [990, 440], c.muted, 1) : layout === "folio" ? line2([90, 1355], [990, 1355], c.muted, 1) : ""}${svgText3(p.title, { x: a.x, y: a.y, width: a.w, maximum: a.size, minimum: 38, maxLines: a.lines, fill: c.ink, weight: layout === "poster" ? 800 : 600 })}${body}${cue ? svgText3(cue.text, { x: 95, y: 1690, width: 890, maximum: 44, minimum: 30, maxLines: 3, fill: c.ink, weight: 500 }) : ""}</g></svg>`;
  }
  function polar(cx, cy, rx, ry, count = 32) {
    return Array.from({ length: count }, (_, i) => [cx + Math.cos(i / count * 2 * Math.PI) * rx, cy + Math.sin(i / count * 2 * Math.PI) * ry]);
  }

  // renderers/template-registry/modules/f2c18f83429e-engraved-hatch-growth.mjs
  var ID24 = "engraved-hatch-growth";
  var SOURCE_ID24 = "source-lemo-style-engraving";
  var DEFAULT_PALETTE24 = Object.freeze({ "background": "#F5EAD6", "ink": "#2A2B26", "muted": "#5B5147", "accent": "#724833" });
  var METADATA16 = Object.freeze({ "name": "Grav\xFCr tarama levhas\u0131", "kind": "contour_hatching", "layout_id": "specimen-plate", "motion_grammar": "curved contour hatch then angled crosshatch accumulation", "typographic_hierarchy": "Serif etkisi taklit edilmeden ince ba\u015Fl\u0131k ve levha de\u011Ferleri", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA24 = schema({ shape_set: A(O({ shape: E(["oval", "leaf", "vessel"]), value: N(1, 100), label: L }), 2, 4), hatch_density: N(6, 22, true), crosshatch_angle: N(15, 75), reveal_order: A(N(0, 3, true), 2, 4) });
  function validateParameters(spec) {
    const p = base2(spec, ID24, ["shape_set", "hatch_density", "crosshatch_angle", "reveal_order"], DEFAULT_PALETTE24), q = spec.parameters;
    p.shape_set = arr(q.shape_set, "shape_set", 2, 4).map((s) => {
      keys3(s, ["shape", "value", "label"]);
      return { shape: choice3(s.shape, "shape", ["oval", "leaf", "vessel"]), value: number3(s.value, "value", 1, 100), label: label2(s.label) };
    });
    p.hatch_density = number3(q.hatch_density, "hatch_density", 6, 22, true);
    p.crosshatch_angle = number3(q.crosshatch_angle, "crosshatch_angle", 15, 75);
    p.reveal_order = order(q.reveal_order, "reveal_order", p.shape_set.length);
    return p;
  }
  function state24(p, u) {
    const plates = p.shape_set.map((s, i) => {
      const rank = p.reveal_order.indexOf(i), v = phase(u, rank * 0.12, 0.65 + rank * 0.08), n = Math.round(p.hatch_density * (0.4 + 0.6 * s.value / 100)), cx = i % 2 ? 755 : 325, cy = 650 + Math.floor(i / 2) * 455, rx = 145, ry = s.shape === "vessel" ? 125 : 145;
      const outline = polar(cx, cy, rx, ry).map(([x, y], j) => s.shape === "leaf" ? [x, y + (x - cx) * 0.18] : s.shape === "vessel" ? [cx + (x - cx) * (0.72 + 0.2 * Math.sin(j / 32 * 2 * Math.PI)), y] : [x, y]);
      const hatches = Array.from({ length: n }, (_, k) => {
        const yy = -ry + 2 * ry * (k + 1) / (n + 1), xx = rx * Math.sqrt(Math.max(0, 1 - yy * yy / ry ** 2)), g = phase(v, k / (n * 1.3), Math.min(1, (k + 3) / (n * 1.3)));
        return { a: [cx - xx, cy + yy], b: [cx - xx + 2 * xx * g, cy + yy], bend: (1 - yy * yy / ry ** 2) * 14 * g, reveal: g };
      });
      const cross3 = Array.from({ length: Math.ceil(n * 0.55) }, (_, k) => {
        const angle = p.crosshatch_angle * Math.PI / 180, yy = -ry * 0.75 + k * ry * 1.5 / (Math.ceil(n * 0.55) - 1), g = phase(v, 0.55 + k / (n * 2), Math.min(1, 0.8 + k / (n * 2)));
        return { a: [cx - 130 * Math.cos(angle) - yy * Math.sin(angle), cy - 130 * Math.sin(angle) + yy * Math.cos(angle)], b: [cx + (-130 + 260 * g) * Math.cos(angle) - yy * Math.sin(angle), cy + (-130 + 260 * g) * Math.sin(angle) + yy * Math.cos(angle)], reveal: g };
      });
      return { cx, cy, outline, hatches, cross: cross3, label: s.label, value: s.value };
    });
    return { progress: u, plates };
  }
  function sample24(spec, seconds) {
    const p = validateParameters(spec);
    return state24(p, clock(p, seconds));
  }
  function render24(spec, seconds) {
    const p = validateParameters(spec), s = state24(p, clock(p, seconds)), c = p.palette;
    const body = s.plates.map((v, i) => `<defs><clipPath id="eg-${i}">${poly(v.outline, "#FFFFFF")}</clipPath></defs>${poly(v.outline, "none", c.ink, 2)}<g clip-path="url(#eg-${i})">${v.hatches.map((h) => `<path d="M${h.a.map(fmt3).join(" ")}Q${fmt3((h.a[0] + h.b[0]) / 2)} ${fmt3(h.a[1] - h.bend)} ${h.b.map(fmt3).join(" ")}" stroke="${c.ink}" stroke-width="2" fill="none"/>`).join("")}${v.cross.map((h) => line2(h.a, h.b, c.accent, 1.7)).join("")}</g>${captionLabel(v.label, v.cx - 130, v.cy + 185, c.ink)}`).join("");
    return shell(ID24, p, seconds, body, "specimen");
  }
  function validateSpec24(spec) {
    return { id: ID24, version: "1.0.0", parameters: validateParameters(spec) };
  }

  // renderers/template-registry/modules/5c7b47b37de1-single-path-identity.mjs
  var c7b47b37de1_single_path_identity_exports = {};
  __export(c7b47b37de1_single_path_identity_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE25,
    ID: () => ID25,
    METADATA: () => METADATA17,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA25,
    SOURCE_ID: () => SOURCE_ID25,
    render: () => render25,
    sample: () => sample25,
    validateSpec: () => validateSpec25
  });
  var ID25 = "single-path-identity";
  var SOURCE_ID25 = "source-lemo-style-one-line";
  var DEFAULT_PALETTE25 = Object.freeze({ "background": "#FAF7F0", "ink": "#1B292C", "muted": "#495554", "accent": "#176C67" });
  var METADATA17 = Object.freeze({ "name": "Tek \xE7izgide kimlik", "kind": "continuous_path_morph", "layout_id": "open-folio", "motion_grammar": "fixed-node visible continuous morph with deliberate object holds", "typographic_hierarchy": "Alt folio ba\u015Fl\u0131\u011F\u0131 ve \xE7izgiye b\u0131rak\u0131lm\u0131\u015F geni\u015F negatif alan", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA25 = schema({ object_sequence: A(E(["loop", "leaf", "cup", "arch"]), 2, 4), path_control_points: A(P, 8, 8), transition_duration: N(0.25, 2), line_weight: N(3, 14) });
  function validateParameters2(spec) {
    const p = base2(spec, ID25, ["object_sequence", "path_control_points", "transition_duration", "line_weight"], DEFAULT_PALETTE25), q = spec.parameters;
    p.object_sequence = words(q.object_sequence, "object_sequence", ["loop", "leaf", "cup", "arch"], 2, 4);
    p.path_control_points = pts(q.path_control_points, "path_control_points", 8, 8);
    p.transition_duration = number3(q.transition_duration, "transition_duration", 0.25, Math.min(2, (p.duration - 0.8) / (p.object_sequence.length - 1)));
    p.line_weight = number3(q.line_weight, "line_weight", 3, 14);
    return p;
  }
  var shapes = { loop: [[0.5, 0], [0.85, 0.15], [1, 0.5], [0.85, 0.85], [0.5, 1], [0.15, 0.85], [0, 0.5], [0.15, 0.15]], leaf: [[0.1, 0.9], [0.15, 0.4], [0.4, 0.15], [0.9, 0.1], [0.85, 0.6], [0.6, 0.85], [0.35, 0.88], [0.1, 0.9]], cup: [[0.1, 0.2], [0.75, 0.2], [0.9, 0.35], [0.85, 0.6], [0.68, 0.65], [0.6, 0.9], [0.2, 0.9], [0.1, 0.2]], arch: [[0.1, 0.95], [0.1, 0.45], [0.25, 0.1], [0.5, 0], [0.75, 0.1], [0.9, 0.45], [0.9, 0.95], [0.1, 0.95]] };
  function state25(p, u) {
    const n = p.object_sequence.length, segment2 = (p.duration - 0.8) / (n - 1), time2 = u * (p.duration - 0.8), i = Math.min(n - 2, Math.floor(time2 / segment2)), a = phase(time2 - i * segment2, segment2 - p.transition_duration, segment2), from = shapes[p.object_sequence[i]], to = shapes[p.object_sequence[i + 1]], points = from.map((v, k) => [280 + 520 * lerp4(v[0], to[k][0], a) + (p.path_control_points[k][0] - 0.5) * 70, 550 + 650 * lerp4(v[1], to[k][1], a) + (p.path_control_points[k][1] - 0.5) * 70]);
    return { progress: u, segment: i, blend: a, points, pen_lifts: 0, object: p.object_sequence[a < 0.5 ? i : i + 1] };
  }
  function sample25(spec, seconds) {
    const p = validateParameters2(spec);
    return state25(p, clock(p, seconds));
  }
  function render25(spec, seconds) {
    const p = validateParameters2(spec), s = state25(p, clock(p, seconds)), c = p.palette;
    return shell(ID25, p, seconds, `<path d="${path3(s.points)}" fill="none" stroke="${c.ink}" stroke-width="${fmt3(p.line_weight)}" stroke-linecap="round" stroke-linejoin="round"/>${circ(...s.points[0], 8, c.accent)}${captionLabel({ loop: "Halka", leaf: "Yaprak", cup: "Fincan", arch: "Kemer" }[s.object], 170, 1280, c.muted, 740)}`, "folio");
  }
  function validateSpec25(spec) {
    return { id: ID25, version: "1.0.0", parameters: validateParameters2(spec) };
  }

  // renderers/template-registry/modules/88d7125cd46e-pictogram-limb-transition.mjs
  var d7125cd46e_pictogram_limb_transition_exports = {};
  __export(d7125cd46e_pictogram_limb_transition_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE26,
    ID: () => ID26,
    METADATA: () => METADATA18,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA26,
    SOURCE_ID: () => SOURCE_ID26,
    render: () => render26,
    sample: () => sample26,
    validateSpec: () => validateSpec26
  });
  var ID26 = "pictogram-limb-transition";
  var SOURCE_ID26 = "source-lemo-style-pictogram-motion";
  var DEFAULT_PALETTE26 = Object.freeze({ "background": "#F6F3EB", "ink": "#192B43", "muted": "#485366", "accent": "#8F2D43" });
  var METADATA18 = Object.freeze({ "name": "Eklemlenen anlam", "kind": "jointed_pictogram", "layout_id": "action-triptych", "motion_grammar": "constant-length limbs articulate while persistent parts transfer", "typographic_hierarchy": "Ba\u015Fl\u0131k ve yan eylem listesi; merkezde tek b\xFCy\xFCk eklem geometrisi", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA26 = schema({ icon_sequence: A(E(["stand", "reach", "carry", "step"]), 2, 4), joint_angles: A(O({ left_arm: N(-85, 85), right_arm: N(-85, 85), left_leg: N(-55, 55), right_leg: N(-55, 55) }), 2, 4), transfer_parts: A(E(["head", "hand", "foot"]), 1, 3), action_cues: A(N(0, 1), 2, 4) });
  function validateParameters3(spec) {
    const p = base2(spec, ID26, ["icon_sequence", "joint_angles", "transfer_parts", "action_cues"], DEFAULT_PALETTE26), q = spec.parameters;
    p.icon_sequence = words(q.icon_sequence, "icon_sequence", ["stand", "reach", "carry", "step"], 2, 4);
    p.joint_angles = arr(q.joint_angles, "joint_angles", p.icon_sequence.length, p.icon_sequence.length).map((v) => {
      keys3(v, ["left_arm", "right_arm", "left_leg", "right_leg"]);
      return Object.fromEntries(Object.keys(v).map((k) => [k, number3(v[k], k, k.includes("arm") ? -85 : -55, k.includes("arm") ? 85 : 55)]));
    });
    p.transfer_parts = words(q.transfer_parts, "transfer_parts", ["head", "hand", "foot"], 1, 3);
    if (new Set(p.transfer_parts).size !== p.transfer_parts.length) throw new Error("TEMPLATE_INPUT: duplicate transfer");
    p.action_cues = nums(q.action_cues, "action_cues", 0, 1, p.icon_sequence.length, p.icon_sequence.length);
    if (p.action_cues[0] !== 0 || p.action_cues.at(-1) !== 1 || p.action_cues.some((v, i) => i && v <= p.action_cues[i - 1])) throw new Error("TEMPLATE_INPUT: action_cues must increase from0to1");
    return p;
  }
  var joint = (root, ang, len) => [root[0] + Math.sin(ang * Math.PI / 180) * len, root[1] + Math.cos(ang * Math.PI / 180) * len];
  function pose(v) {
    const shoulder = [590, 760], hip = [590, 1010];
    return { head: [590, 650], shoulder, hip, left_arm: joint(shoulder, v.left_arm, 220), right_arm: joint(shoulder, v.right_arm, 220), left_leg: joint(hip, v.left_leg, 240), right_leg: joint(hip, v.right_leg, 240) };
  }
  function state26(p, u) {
    let k = p.action_cues.findIndex((v2, i) => i && u <= v2) - 1;
    if (k < 0) k = p.action_cues.length - 2;
    const f = phase(u, p.action_cues[k], p.action_cues[k + 1]), v = Object.fromEntries(Object.keys(p.joint_angles[k]).map((n) => [n, lerp4(p.joint_angles[k][n], p.joint_angles[k + 1][n], f)])), j = pose(v), from = pose(p.joint_angles[k]), to = pose(p.joint_angles[k + 1]);
    const tokens = p.transfer_parts.map((id, i) => {
      const key = id === "hand" ? "right_arm" : id === "foot" ? "left_leg" : "head", a = from[key], b = to[key];
      return { id, x: lerp4(a[0], b[0], f) + i * 12, y: lerp4(a[1], b[1], f) - Math.sin(Math.PI * f) * 70 };
    });
    return { progress: u, pose_index: k, blend: f, joints: j, tokens, angles: v };
  }
  function sample26(spec, seconds) {
    const p = validateParameters3(spec);
    return state26(p, clock(p, seconds));
  }
  function render26(spec, seconds) {
    const p = validateParameters3(spec), s = state26(p, clock(p, seconds)), j = s.joints, c = p.palette;
    return shell(ID26, p, seconds, `${p.icon_sequence.map((v, i) => captionLabel({ stand: "Dur", reach: "Uzan", carry: "Ta\u015F\u0131", step: "Ad\u0131m" }[v], 100, 650 + i * 145, i === s.pose_index ? c.accent : c.muted, 250)).join("")}${line2(j.shoulder, j.hip, c.ink, 28)}${circ(...j.head, 65, "none", c.ink, 16)}${["left_arm", "right_arm"].map((k) => line2(j.shoulder, j[k], c.ink, 21)).join("")}${["left_leg", "right_leg"].map((k) => line2(j.hip, j[k], c.ink, 22)).join("")}${s.tokens.map((v) => circ(v.x, v.y, 18, c.accent, c.background, 3)).join("")}`, "side");
  }
  function validateSpec26(spec) {
    return { id: ID26, version: "1.0.0", parameters: validateParameters3(spec) };
  }

  // renderers/template-registry/modules/79c39820654d-perspective-pen-wash.mjs
  var c39820654d_perspective_pen_wash_exports = {};
  __export(c39820654d_perspective_pen_wash_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE27,
    ID: () => ID27,
    METADATA: () => METADATA19,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA27,
    SOURCE_ID: () => SOURCE_ID27,
    render: () => render27,
    sample: () => sample27,
    validateSpec: () => validateSpec27
  });
  var ID27 = "perspective-pen-wash";
  var SOURCE_ID27 = "source-lemo-style-urban-sketch";
  var DEFAULT_PALETTE27 = Object.freeze({ "background": "#F8F5EC", "ink": "#25303D", "muted": "#535A61", "accent": "#386F82" });
  var METADATA19 = Object.freeze({ "name": "Perspektif defteri", "kind": "perspective_sketch_wash", "layout_id": "sketch-notebook", "motion_grammar": "convergent construction rays grow before bounded wash expansion", "typographic_hierarchy": "Alt folio ba\u015Fl\u0131\u011F\u0131; \xFCstte ince mimari \xE7izgi ve k\u0131lavuz a\xE7\u0131klamas\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA27 = schema({ vanishing_points: A(P, 2, 2), structure_lines: A(O({ origin: P, vanishing: N(0, 1, true), depth: N(0.15, 0.8) }), 2, 8), wash_regions: A(A(P, 3, 6), 1, 4), bleed_amount: N(0, 0.12) });
  function validateParameters4(spec) {
    const p = base2(spec, ID27, ["vanishing_points", "structure_lines", "wash_regions", "bleed_amount"], DEFAULT_PALETTE27), q = spec.parameters;
    p.vanishing_points = pts(q.vanishing_points, "vanishing_points", 2, 2);
    if (p.vanishing_points[0][0] > 0.4 || p.vanishing_points[1][0] < 0.6) throw new Error("TEMPLATE_INPUT: separate left/right vanishing points");
    p.structure_lines = arr(q.structure_lines, "structure_lines", 2, 8).map((v) => {
      keys3(v, ["origin", "vanishing", "depth"]);
      return { origin: pt(v.origin), vanishing: number3(v.vanishing, "vanishing", 0, 1, true), depth: number3(v.depth, "depth", 0.15, 0.8) };
    });
    p.wash_regions = arr(q.wash_regions, "wash_regions", 1, 4).map((v) => pts(v, "wash", 3, 6));
    p.bleed_amount = number3(q.bleed_amount, "bleed_amount", 0, 0.12);
    return p;
  }
  function state27(p, u) {
    const vp = p.vanishing_points.map(xy), guides = p.structure_lines.map((s, i) => {
      const a = xy(s.origin), v = vp[s.vanishing], g = phase(u, 0, 0.3), b = a.map((x, j) => lerp4(x, v[j], s.depth)), draw = phase(u, 0.18 + i * 0.025, 0.58 + i * 0.025);
      return { a, vanishing: v, b, end: a.map((x, j) => lerp4(x, b[j], draw)), guide_end: a.map((x, j) => lerp4(x, v[j], g)), depth: s.depth };
    });
    const wash = p.wash_regions.map((points, i) => {
      const c = [points.reduce((a, v) => a + v[0], 0) / points.length, points.reduce((a, v) => a + v[1], 0) / points.length], g = phase(u, 0.5 + i * 0.03, 0.94), amount = 1 + p.bleed_amount * g;
      return { points: points.map((v) => xy([Math.max(0, Math.min(1, c[0] + (v[0] - c[0]) * amount)), Math.max(0, Math.min(1, c[1] + (v[1] - c[1]) * amount))])), coverage: g };
    });
    return { progress: u, vanishing: vp, guides, wash };
  }
  function sample27(spec, seconds) {
    const p = validateParameters4(spec);
    return state27(p, clock(p, seconds));
  }
  function render27(spec, seconds) {
    const p = validateParameters4(spec), s = state27(p, clock(p, seconds)), c = p.palette;
    return shell(ID27, p, seconds, `${s.wash.map((w) => poly(w.points, c.accent, "none", 1, w.coverage * 0.23)).join("")}${s.guides.map((g) => line2(g.a, g.guide_end, c.muted, 1, 0.35) + line2(g.a, g.end, c.ink, 3)).join("")}${s.vanishing.map((v, i) => circ(...v, 7, c.accent) + captionLabel("Ka\xE7\u0131\u015F " + (i + 1), Math.max(90, Math.min(830, v[0] - 35)), v[1] + 45, c.muted, 200)).join("")}`, "folio");
  }
  function validateSpec27(spec) {
    return { id: ID27, version: "1.0.0", parameters: validateParameters4(spec) };
  }

  // renderers/template-registry/modules/a3cd84f26709-stroke-erase-explanation.mjs
  var a3cd84f26709_stroke_erase_explanation_exports = {};
  __export(a3cd84f26709_stroke_erase_explanation_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE28,
    ID: () => ID28,
    METADATA: () => METADATA20,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA28,
    SOURCE_ID: () => SOURCE_ID28,
    render: () => render28,
    sample: () => sample28,
    validateSpec: () => validateSpec28
  });
  var ID28 = "stroke-erase-explanation";
  var SOURCE_ID28 = "source-lemo-style-whiteboard";
  var DEFAULT_PALETTE28 = Object.freeze({ "background": "#F9FCF8", "ink": "#1A3430", "muted": "#4B5D54", "accent": "#216A4E" });
  var METADATA20 = Object.freeze({ "name": "Sil ve yeniden a\xE7\u0131kla", "kind": "ordered_erasure_redraw", "layout_id": "correction-board", "motion_grammar": "ordered strokes then bounded moving eraser then corrected strokes", "typographic_hierarchy": "\xDCst a\xE7\u0131klama ve \xFC\xE7 ayr\u0131 i\u015Flem s\xFCtunu", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA28 = schema({ stroke_order: A(N(0, 2, true), 3, 3), diagram_values: A(N(10, 100), 3, 3), erase_regions: A(O({ node_index: N(0, 2, true), width: N(0.5, 1) }), 1, 3), redraw_cues: A(N(0.65, 0.85), 1, 3) });
  function validateParameters5(spec) {
    const p = base2(spec, ID28, ["stroke_order", "diagram_values", "erase_regions", "redraw_cues"], DEFAULT_PALETTE28), q = spec.parameters;
    p.stroke_order = order(q.stroke_order, "stroke_order", 3);
    p.diagram_values = nums(q.diagram_values, "diagram_values", 10, 100, 3, 3);
    p.erase_regions = arr(q.erase_regions, "erase_regions", 1, 3).map((v) => {
      keys3(v, ["node_index", "width"]);
      return { node_index: number3(v.node_index, "node_index", 0, 2, true), width: number3(v.width, "width", 0.5, 1) };
    });
    if (new Set(p.erase_regions.map((v) => v.node_index)).size !== p.erase_regions.length) throw new Error("TEMPLATE_INPUT: duplicate erase node");
    p.redraw_cues = nums(q.redraw_cues, "redraw_cues", 0.65, 0.85, p.erase_regions.length, p.erase_regions.length);
    return p;
  }
  function state28(p, u) {
    return { progress: u, nodes: p.diagram_values.map((v, i) => {
      const r = p.stroke_order.indexOf(i), erase = p.erase_regions.findIndex((a) => a.node_index === i), e = erase < 0 ? 0 : phase(u, 0.35 + erase * 0.04, 0.58 + erase * 0.04), d = erase < 0 ? 0 : phase(u, p.redraw_cues[erase], Math.min(0.98, p.redraw_cues[erase] + 0.12)), width = erase < 0 ? 0 : p.erase_regions[erase].width * 220;
      return { x: 180 + i * 300, value: v, draw: phase(u, r * 0.07, 0.18 + r * 0.07), erase_width: width * e, target_erase_width: width, redraw: d, corrected_value: Math.round(v * 0.65), has_correction: erase >= 0 };
    }) };
  }
  function sample28(spec, seconds) {
    const p = validateParameters5(spec);
    return state28(p, clock(p, seconds));
  }
  function render28(spec, seconds) {
    const p = validateParameters5(spec), s = state28(p, clock(p, seconds)), c = p.palette;
    return shell(ID28, p, seconds, s.nodes.map((n, i) => `<defs><mask id="wb-${i}">${rect(n.x - 15, 585, 250, 610, "#FFFFFF")}${rect(n.x, 600, n.erase_width, 570, "#000000")}</mask></defs>${line2([n.x, 1150], [n.x + 220, 1150], c.muted, 2)}<g mask="url(#wb-${i})">${line2([n.x + 100, 1150], [n.x + 100, 1150 - n.value * 4 * n.draw], c.ink, 35)}</g>${n.has_correction ? line2([n.x + 100, 1150], [n.x + 100, 1150 - n.corrected_value * 4 * n.redraw], c.accent, 35) : ""}${n.erase_width > 0 && n.erase_width < n.target_erase_width ? rect(n.x + n.erase_width - 18, 630, 36, 480, c.muted) : ""}${captionLabel("Ad\u0131m " + (i + 1), n.x - 10, 1280, c.ink, 250)}`).join(""), "board");
  }
  function validateSpec28(spec) {
    return { id: ID28, version: "1.0.0", parameters: validateParameters5(spec) };
  }

  // renderers/template-registry/modules/2089f297372a-crayon-stroke-fill.mjs
  var f297372a_crayon_stroke_fill_exports = {};
  __export(f297372a_crayon_stroke_fill_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE29,
    ID: () => ID29,
    METADATA: () => METADATA21,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA29,
    SOURCE_ID: () => SOURCE_ID29,
    render: () => render29,
    sample: () => sample29,
    validateSpec: () => validateSpec29
  });
  var ID29 = "crayon-stroke-fill";
  var SOURCE_ID29 = "source-lemo-style-crayon-book";
  var DEFAULT_PALETTE29 = Object.freeze({ "background": "#FFF8E8", "ink": "#342B37", "muted": "#66534D", "accent": "#B03831" });
  var METADATA21 = Object.freeze({ "name": "Wax izleriyle resim", "kind": "directional_wax_fill", "layout_id": "storybook-spread", "motion_grammar": "directional clipped rough-edged wax strokes accumulate in ordered regions", "typographic_hierarchy": "Geni\u015F resim alan\u0131 ve k\u0131sa kitap sayfas\u0131 ba\u015Fl\u0131\u011F\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA29 = schema({ outline_set: A(O({ center: P, radii: P, label: L }), 2, 4), stroke_width: N(5, 18), hatch_direction: N(-70, 70), fill_order: A(N(0, 3, true), 2, 4) });
  function validateParameters6(spec) {
    const p = base2(spec, ID29, ["outline_set", "stroke_width", "hatch_direction", "fill_order"], DEFAULT_PALETTE29), q = spec.parameters;
    p.outline_set = arr(q.outline_set, "outline_set", 2, 4).map((v) => {
      keys3(v, ["center", "radii", "label"]);
      const center = pt(v.center), radii = nums(v.radii, "radii", 0.07, 0.23, 2, 2);
      if (center.some((x, i) => x - radii[i] < 0.02 || x + radii[i] > 0.98)) throw new Error("TEMPLATE_INPUT: outline outside drawing");
      return { center, radii, label: label2(v.label) };
    });
    p.stroke_width = number3(q.stroke_width, "stroke_width", 5, 18);
    p.hatch_direction = number3(q.hatch_direction, "hatch_direction", -70, 70);
    p.fill_order = order(q.fill_order, "fill_order", p.outline_set.length);
    return p;
  }
  function state29(p, u) {
    return { progress: u, regions: p.outline_set.map((o, i) => {
      const [cx, cy] = xy(o.center), rx = o.radii[0] * 780, ry = o.radii[1] * 860, n = 18, rank = p.fill_order.indexOf(i), g = phase(u, rank * 0.1, 0.65 + rank * 0.08), a = p.hatch_direction * Math.PI / 180;
      const strokes = Array.from({ length: n }, (_, k) => {
        const v = phase(g, k / 23, (k + 4) / 23), y = -ry + 2 * ry * (k + 0.5) / n, jitter = Math.sin((k + 1) * (i + 3) * 1.73) * p.stroke_width * 0.18;
        return { points: [[-rx, y + jitter], [-rx + 2 * rx * v, y - jitter]].map(([x, y2]) => [cx + x * Math.cos(a) - y2 * Math.sin(a), cy + x * Math.sin(a) + y2 * Math.cos(a)]), width: p.stroke_width * (0.78 + 0.22 * Math.sin(k * 1.21) ** 2), reveal: v };
      });
      return { cx, cy, rx, ry, strokes, label: o.label };
    }) };
  }
  function sample29(spec, seconds) {
    const p = validateParameters6(spec);
    return state29(p, clock(p, seconds));
  }
  function render29(spec, seconds) {
    const p = validateParameters6(spec), s = state29(p, clock(p, seconds)), c = p.palette;
    return shell(ID29, p, seconds, s.regions.map((v, i) => `<defs><clipPath id="wax-${i}"><ellipse cx="${fmt3(v.cx)}" cy="${fmt3(v.cy)}" rx="${fmt3(v.rx)}" ry="${fmt3(v.ry)}"/></clipPath></defs><ellipse cx="${fmt3(v.cx)}" cy="${fmt3(v.cy)}" rx="${fmt3(v.rx)}" ry="${fmt3(v.ry)}" fill="none" stroke="${c.ink}" stroke-width="3"/><g clip-path="url(#wax-${i})">${v.strokes.map((z, k) => line2(...z.points, k % 3 ? c.accent : c.muted, z.width, 0.72) + line2(...z.points, c.background, 1, 0.28)).join("")}</g>${captionLabel(v.label, v.cx - v.rx, v.cy + v.ry + 45, c.ink, Math.max(260, v.rx * 2))}`).join(""), "poster");
  }
  function validateSpec29(spec) {
    return { id: ID29, version: "1.0.0", parameters: validateParameters6(spec) };
  }

  // renderers/template-registry/modules/d8086956379e-halftone-evidence-lens.mjs
  var d8086956379e_halftone_evidence_lens_exports = {};
  __export(d8086956379e_halftone_evidence_lens_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE30,
    ID: () => ID30,
    METADATA: () => METADATA22,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA30,
    SOURCE_ID: () => SOURCE_ID30,
    render: () => render30,
    sample: () => sample30,
    validateSpec: () => validateSpec30
  });
  var ID30 = "halftone-evidence-lens";
  var SOURCE_ID30 = "source-lemo-style-halftone-dossier";
  var DEFAULT_PALETTE30 = Object.freeze({ "background": "#F2EBDD", "ink": "#242323", "muted": "#5D524B", "accent": "#8E3028" });
  var METADATA22 = Object.freeze({ "name": "Nokta merce\u011Fi", "kind": "halftone_resolution_lens", "layout_id": "dossier-lens", "motion_grammar": "coarse print resolves into fine dots under a tracked lens; focal connections follow", "typographic_hierarchy": "\u0130nce dosya ba\u015Fl\u0131\u011F\u0131, kart odaklar\u0131 ve diyagonal ba\u011Flant\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA30 = schema({ dot_pitch: N(25, 55), evidence_regions: A(O({ center: P, size: P, focus: P, label: L }), 2, 4), lens_path: A(P, 2, 5), connection_order: A(N(0, 3, true), 2, 4) });
  function validateParameters7(spec) {
    const p = base2(spec, ID30, ["dot_pitch", "evidence_regions", "lens_path", "connection_order"], DEFAULT_PALETTE30), q = spec.parameters;
    p.dot_pitch = number3(q.dot_pitch, "dot_pitch", 25, 55);
    p.evidence_regions = arr(q.evidence_regions, "evidence_regions", 2, 4).map((v) => {
      keys3(v, ["center", "size", "focus", "label"]);
      const center = pt(v.center), size = nums(v.size, "size", 0.18, 0.38, 2, 2);
      if (center.some((x, i) => x - size[i] / 2 < 0 || x + size[i] / 2 > 1)) throw new Error("TEMPLATE_INPUT: evidence outside sheet");
      return { center, size, focus: pt(v.focus), label: label2(v.label) };
    });
    p.lens_path = pts(q.lens_path, "lens_path", 2, 5);
    p.connection_order = order(q.connection_order, "connection_order", p.evidence_regions.length);
    return p;
  }
  function state30(p, u) {
    const z = phase(u, 0, 0.75) * (p.lens_path.length - 1), k = Math.min(p.lens_path.length - 2, Math.floor(z)), f = z - k, lens = xy(p.lens_path[k].map((v, i) => lerp4(v, p.lens_path[k + 1][i], f))), cards = p.evidence_regions.map((v) => {
      const [cx, cy] = xy(v.center), w = v.size[0] * 780, h = v.size[1] * 860, x = cx - w / 2, y = cy - h / 2, focus = [x + w * v.focus[0], y + h * v.focus[1]], coarse = [], fine = [];
      for (let yy = y + p.dot_pitch / 2; yy < y + h; yy += p.dot_pitch) for (let xx = x + p.dot_pitch / 2; xx < x + w; xx += p.dot_pitch) coarse.push({ x: xx, y: yy, r: p.dot_pitch * (0.15 + 0.13 * Math.sin(xx * 0.017 + yy * 0.011) ** 2) });
      const pitch = p.dot_pitch / 3;
      for (let yy = y + pitch / 2; yy < y + h; yy += pitch) for (let xx = x + pitch / 2; xx < x + w; xx += pitch) if (Math.hypot(xx - lens[0], yy - lens[1]) < 95) fine.push({ x: xx, y: yy, r: pitch * (0.16 + 0.18 * Math.sin(xx * 0.021 + yy * 0.013) ** 2) });
      return { x, y, w, h, focus, coarse, fine, label: v.label };
    });
    const links = p.connection_order.slice(1).map((to, i) => {
      const a = cards[p.connection_order[i]].focus, b = cards[to].focus, g = phase(u, 0.68 + i * 0.06, 0.86 + i * 0.05);
      return { a, b, end: a.map((v, j) => lerp4(v, b[j], g)), reveal: g };
    });
    return { progress: u, lens, cards, links, fine_pitch: p.dot_pitch / 3, coarse_pitch: p.dot_pitch };
  }
  function sample30(spec, seconds) {
    const p = validateParameters7(spec);
    return state30(p, clock(p, seconds));
  }
  function render30(spec, seconds) {
    const p = validateParameters7(spec), s = state30(p, clock(p, seconds)), c = p.palette;
    const body = s.cards.map((v) => rect(v.x - 10, v.y - 10, v.w + 20, v.h + 20, "none", c.muted, 2) + v.coarse.map((d) => circ(d.x, d.y, d.r, c.muted)).join("") + v.fine.map((d) => circ(d.x, d.y, d.r, c.ink)).join("") + line2([v.focus[0] - 16, v.focus[1]], [v.focus[0] + 16, v.focus[1]], c.accent, 2) + line2([v.focus[0], v.focus[1] - 16], [v.focus[0], v.focus[1] + 16], c.accent, 2) + captionLabel(v.label, v.x, v.y + v.h + 48, c.ink, Math.max(v.w, 260))).join("") + s.links.map((v) => line2(v.a, v.end, c.accent, 3)).join("") + circ(...s.lens, 101, "none", c.accent, 4) + line2([s.lens[0] + 75, s.lens[1] + 75], [s.lens[0] + 123, s.lens[1] + 123], c.accent, 12);
    return shell(ID30, p, seconds, body, "specimen");
  }
  function validateSpec30(spec) {
    return { id: ID30, version: "1.0.0", parameters: validateParameters7(spec) };
  }

  // renderers/template-registry/modules/48952e440b89-paint-ridge-deposition.mjs
  var e440b89_paint_ridge_deposition_exports = {};
  __export(e440b89_paint_ridge_deposition_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE31,
    ID: () => ID31,
    METADATA: () => METADATA23,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA31,
    SOURCE_ID: () => SOURCE_ID31,
    render: () => render31,
    sample: () => sample31,
    validateSpec: () => validateSpec31
  });
  var ID31 = "paint-ridge-deposition";
  var SOURCE_ID31 = "source-lemo-style-impasto";
  var DEFAULT_PALETTE31 = Object.freeze({ "background": "#F6F1E7", "ink": "#2D3129", "muted": "#58604F", "accent": "#744930" });
  var METADATA23 = Object.freeze({ "name": "Boya s\u0131rtlar\u0131n\u0131n birikimi", "kind": "directional_relief_deposition", "layout_id": "ridge-study", "motion_grammar": "ordered overlapping brush dabs deposit relief; directional highlight follows ridge normals", "typographic_hierarchy": "Alt b\xFCy\xFCk konu ad\u0131, \xFCstte geni\u015F renk/kal\u0131nl\u0131k levhas\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA31 = schema({ dab_paths: A(A(P, 2, 6), 2, 4), paint_thickness: N(4, 22), light_angle: N(0, 360), layer_order: A(N(0, 3, true), 2, 4) });
  function validateParameters8(spec) {
    const p = base2(spec, ID31, ["dab_paths", "paint_thickness", "light_angle", "layer_order"], DEFAULT_PALETTE31), q = spec.parameters;
    p.dab_paths = arr(q.dab_paths, "dab_paths", 2, 4).map((v) => pts(v, "dab path", 2, 6));
    p.paint_thickness = number3(q.paint_thickness, "paint_thickness", 4, 22);
    p.light_angle = number3(q.light_angle, "light_angle", 0, 360);
    p.layer_order = order(q.layer_order, "layer_order", p.dab_paths.length);
    return p;
  }
  function state31(p, u) {
    const light = [Math.cos(p.light_angle * Math.PI / 180), Math.sin(p.light_angle * Math.PI / 180)], dabs = [];
    for (const [i, pp] of p.dab_paths.entries()) {
      const points = pp.map(xy), rank = p.layer_order.indexOf(i), grow = phase(u, rank * 0.12, 0.6 + rank * 0.1);
      for (let k = 0; k < 18; k++) {
        const z = k / 17 * (points.length - 1), j = Math.min(points.length - 2, Math.floor(z)), a = points[j], b = points[j + 1], q = z - j, c = a.map((v, h) => lerp4(v, b[h], q)), len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, tx2 = (b[0] - a[0]) / len, ty = (b[1] - a[1]) / len, nx = -ty, ny = tx2, g = phase(grow, k / 22, (k + 4) / 22), width = 18 + p.paint_thickness * 0.7, height = p.paint_thickness * g, points2 = [[-27, -width], [28, -width * 0.7], [32, width * 0.7], [-24, width]].map(([x, y]) => [c[0] + tx2 * x * g + nx * y * g, c[1] + ty * x * g + ny * y * g]);
        dabs.push({ layer: i, index: k, center: c, points: points2, reveal: g, height, highlight_a: [c[0] - tx2 * 22 * g + nx * width * 0.35 * light[0], c[1] - ty * 22 * g + ny * width * 0.35 * light[1] - height * 0.35], highlight_b: [c[0] + tx2 * 24 * g + nx * width * 0.35 * light[0], c[1] + ty * 24 * g + ny * width * 0.35 * light[1] - height * 0.35], shade: Math.abs(nx * light[0] + ny * light[1]) });
      }
    }
    dabs.sort((a, b) => p.layer_order.indexOf(a.layer) - p.layer_order.indexOf(b.layer) || a.index - b.index);
    return { progress: u, light, dabs, deposited: dabs.filter((v) => v.reveal === 1).length };
  }
  function sample31(spec, seconds) {
    const p = validateParameters8(spec);
    return state31(p, clock(p, seconds));
  }
  function render31(spec, seconds) {
    const p = validateParameters8(spec), s = state31(p, clock(p, seconds)), c = p.palette;
    return shell(ID31, p, seconds, s.dabs.map((v) => poly(v.points, v.layer % 2 ? c.muted : c.accent, c.ink, 1) + line2(v.highlight_a, v.highlight_b, c.background, Math.max(1, v.height * 0.26), v.reveal * (0.35 + 0.45 * v.shade))).join(""), "folio");
  }
  function validateSpec31(spec) {
    return { id: ID31, version: "1.0.0", parameters: validateParameters8(spec) };
  }

  // renderers/template-registry/modules/6afde3da0ca7-ink-diffusion-front.mjs
  var afde3da0ca7_ink_diffusion_front_exports = {};
  __export(afde3da0ca7_ink_diffusion_front_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE32,
    ID: () => ID32,
    METADATA: () => METADATA24,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA32,
    SOURCE_ID: () => SOURCE_ID32,
    render: () => render32,
    sample: () => sample32,
    validateSpec: () => validateSpec32
  });
  var ID32 = "ink-diffusion-front";
  var SOURCE_ID32 = "source-lemo-style-ink-wash";
  var DEFAULT_PALETTE32 = Object.freeze({ "background": "#F5F5EC", "ink": "#182625", "muted": "#505E5A", "accent": "#375C60" });
  var METADATA24 = Object.freeze({ "name": "M\xFCrekkebin yay\u0131lma cephesi", "kind": "path_seeded_diffusion", "layout_id": "ink-scroll", "motion_grammar": "anisotropic path fronts spread by sqrt-time; edge concentration dries separately", "typographic_hierarchy": "Asimetrik ba\u015Fl\u0131k ve uzun dikey m\xFCrekkep alan\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA32 = schema({ brush_paths: A(A(P, 2, 6), 1, 4), water_amount: N(0.1, 1), diffusion_radius: N(20, 100), dry_time: N(0.4, 0.65) });
  function validateParameters9(spec) {
    const p = base2(spec, ID32, ["brush_paths", "water_amount", "diffusion_radius", "dry_time"], DEFAULT_PALETTE32), q = spec.parameters;
    p.brush_paths = arr(q.brush_paths, "brush_paths", 1, 4).map((v) => pts(v, "brush path", 2, 6));
    p.water_amount = number3(q.water_amount, "water_amount", 0.1, 1);
    p.diffusion_radius = number3(q.diffusion_radius, "diffusion_radius", 20, 100);
    p.dry_time = number3(q.dry_time, "dry_time", 0.4, 0.65);
    return p;
  }
  function state32(p, u) {
    const growth = phase(u, 0, 0.7), dry = phase(u, p.dry_time, 0.98), fronts = [];
    p.brush_paths.forEach((pa, i) => {
      const points = pa.map(xy);
      for (let k = 0; k < 10; k++) {
        const z = k / 9 * (points.length - 1), j = Math.min(points.length - 2, Math.floor(z)), q = z - j, c = points[j].map((v, h) => lerp4(v, points[j + 1][h], q)), radius = 6 + p.diffusion_radius * Math.sqrt(growth * p.water_amount), a = Math.atan2(points[j + 1][1] - points[j][1], points[j + 1][0] - points[j][0]);
        const contour = Array.from({ length: 24 }, (_, m) => {
          const angle = m / 24 * Math.PI * 2, noise = 1 + 0.08 * Math.sin(m * 1.8 + i * 2 + k * 0.3), x = Math.cos(angle) * radius * 1.4 * noise, y = Math.sin(angle) * radius * 0.68 * noise;
          return [Math.max(140, Math.min(940, c[0] + x * Math.cos(a) - y * Math.sin(a))), Math.max(500, Math.min(1395, c[1] + x * Math.sin(a) + y * Math.cos(a)))];
        });
        fronts.push({ center: c, radius, contour, edge_concentration: 0.15 + 0.65 * dry, body_density: (0.4 - 0.2 * p.water_amount) * growth });
      }
    });
    return { progress: u, growth, dry, fronts };
  }
  function sample32(spec, seconds) {
    const p = validateParameters9(spec);
    return state32(p, clock(p, seconds));
  }
  function render32(spec, seconds) {
    const p = validateParameters9(spec), s = state32(p, clock(p, seconds)), c = p.palette;
    return shell(ID32, p, seconds, s.fronts.map((v) => poly(v.contour, c.accent, c.ink, 1 + s.dry * 2, v.body_density) + poly(v.contour, "none", c.ink, 1.4, v.edge_concentration)).join(""), "side");
  }
  function validateSpec32(spec) {
    return { id: ID32, version: "1.0.0", parameters: validateParameters9(spec) };
  }

  // renderers/template-registry/modules/8feb6c9fcea1-ink-drum-misregister.mjs
  var feb6c9fcea1_ink_drum_misregister_exports = {};
  __export(feb6c9fcea1_ink_drum_misregister_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE33,
    ID: () => ID33,
    METADATA: () => METADATA25,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA33,
    SOURCE_ID: () => SOURCE_ID33,
    render: () => render33,
    sample: () => sample33,
    validateSpec: () => validateSpec33
  });
  var ID33 = "ink-drum-misregister";
  var SOURCE_ID33 = "source-lemo-style-risograph";
  var DEFAULT_PALETTE33 = Object.freeze({ "background": "#FFF3DF", "ink": "#242337", "muted": "#5A4B57", "accent": "#863940" });
  var METADATA25 = Object.freeze({ "name": "Riso kay\u0131t provas\u0131", "kind": "spot_drum_registration", "layout_id": "riso-proof", "motion_grammar": "separate spot-color dot screens print with explicit misregistration offsets", "typographic_hierarchy": "K\xF6\u015Feli prova ba\u015Fl\u0131\u011F\u0131 ve bask\u0131 kay\u0131t i\u015Faretleri", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA33 = schema({ spot_colors: A(C, 2, 4), registration_offsets: A(A(N(-14, 14), 2, 2), 2, 4), dot_frequency: N(8, 18, true), print_order: A(N(0, 3, true), 2, 4) });
  function validateParameters10(spec) {
    const p = base2(spec, ID33, ["spot_colors", "registration_offsets", "dot_frequency", "print_order"], DEFAULT_PALETTE33), q = spec.parameters;
    p.spot_colors = colors(q.spot_colors, "spot_colors", 2, 4);
    p.registration_offsets = arr(q.registration_offsets, "registration_offsets", p.spot_colors.length, p.spot_colors.length).map((v) => nums(v, "offset", -14, 14, 2, 2));
    p.dot_frequency = number3(q.dot_frequency, "dot_frequency", 8, 18, true);
    p.print_order = order(q.print_order, "print_order", p.spot_colors.length);
    return p;
  }
  function state33(p, u) {
    const layers = p.spot_colors.map((color2, i) => {
      const rank = p.print_order.indexOf(i), coverage = phase(u, rank * 0.17, 0.35 + rank * 0.17), offset = p.registration_offsets[i], dots = [], pitch = 660 / p.dot_frequency;
      for (let row = 0; row < p.dot_frequency; row++) for (let col = 0; col < p.dot_frequency; col++) {
        const x = 210 + (col + 0.5) * pitch + offset[0], y = 560 + (row + 0.5) * pitch + offset[1], nx = (x - 540) / 330, ny = (y - 890) / 330;
        const inShape = i % 3 === 0 ? nx * nx + ny * ny < 0.9 : i % 3 === 1 ? Math.abs(nx + ny * 0.6) < 0.48 : Math.abs(nx) < 0.6 && Math.abs(ny) < 0.7;
        if (inShape && row / p.dot_frequency < coverage) dots.push({ x, y, r: pitch * (0.24 + 0.06 * Math.sin(row + col + i) ** 2) });
      }
      return { color: color2, offset, coverage, dots, rank };
    }).sort((a, b) => a.rank - b.rank);
    return { progress: u, layers, completed: layers.filter((x) => x.coverage === 1).length };
  }
  function sample33(spec, seconds) {
    const p = validateParameters10(spec);
    return state33(p, clock(p, seconds));
  }
  function render33(spec, seconds) {
    const p = validateParameters10(spec), s = state33(p, clock(p, seconds)), c = p.palette;
    const marks = [[180, 520], [900, 520], [180, 1270], [900, 1270]].map((v) => line2([v[0] - 12, v[1]], [v[0] + 12, v[1]], c.ink, 2) + line2([v[0], v[1] - 12], [v[0], v[1] + 12], c.ink, 2)).join("");
    return shell(ID33, p, seconds, marks + s.layers.map((v) => `<g opacity="0.8">${v.dots.map((d) => circ(d.x, d.y, d.r, v.color)).join("")}</g>`).join(""), "press");
  }
  function validateSpec33(spec) {
    return { id: ID33, version: "1.0.0", parameters: validateParameters10(spec) };
  }

  // renderers/template-registry/modules/f694a6ac3510-pigment-pool-drying.mjs
  var f694a6ac3510_pigment_pool_drying_exports = {};
  __export(f694a6ac3510_pigment_pool_drying_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE34,
    ID: () => ID34,
    METADATA: () => METADATA26,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA34,
    SOURCE_ID: () => SOURCE_ID34,
    render: () => render34,
    sample: () => sample34,
    validateSpec: () => validateSpec34
  });
  var ID34 = "pigment-pool-drying";
  var SOURCE_ID34 = "source-lemo-style-watercolor";
  var DEFAULT_PALETTE34 = Object.freeze({ "background": "#F2F5EB", "ink": "#213B40", "muted": "#4D5C57", "accent": "#236875" });
  var METADATA26 = Object.freeze({ "name": "Pigment havuzu ve kuruma", "kind": "pool_mass_deposition", "layout_id": "pigment-map", "motion_grammar": "bounded pools expand then pigment mass migrates into a drying rim", "typographic_hierarchy": "Alt atlas ba\u015Fl\u0131\u011F\u0131 ve \xFCstte serbest havuzlar\u0131n etiketleri", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA34 = schema({ pool_centers: A(O({ center: P, radius: N(0.07, 0.18), load: N(0.2, 1), label: L }), 2, 4), pigment_colors: A(C, 2, 4), wetness: N(0.15, 1), dry_duration: N(0.15, 0.45) });
  function validateParameters11(spec) {
    const p = base2(spec, ID34, ["pool_centers", "pigment_colors", "wetness", "dry_duration"], DEFAULT_PALETTE34), q = spec.parameters;
    p.pool_centers = arr(q.pool_centers, "pool_centers", 2, 4).map((v) => {
      keys3(v, ["center", "radius", "load", "label"]);
      return { center: pt(v.center), radius: number3(v.radius, "radius", 0.07, 0.18), load: number3(v.load, "load", 0.2, 1), label: label2(v.label) };
    });
    p.pigment_colors = colors(q.pigment_colors, "pigment_colors", p.pool_centers.length, p.pool_centers.length);
    p.wetness = number3(q.wetness, "wetness", 0.15, 1);
    p.dry_duration = number3(q.dry_duration, "dry_duration", 0.15, 0.45);
    return p;
  }
  function state34(p, u) {
    const spread = phase(u, 0, 0.5), dry = phase(u, 0.5, 0.5 + p.dry_duration), pools = p.pool_centers.map((v, i) => {
      const center = xy(v.center), radius = v.radius * 780 * (0.3 + 0.7 * Math.sqrt(spread * p.wetness)), edge_mass = v.load * 0.55 * dry, core_mass = v.load - edge_mass, contour = Array.from({ length: 36 }, (_, j) => {
        const a = j / 36 * Math.PI * 2, r = radius * (1 + 0.05 * Math.sin(j * 0.9 + i * 2) + 0.03 * Math.cos(j * 1.6));
        return [Math.max(145, Math.min(935, center[0] + Math.cos(a) * r)), Math.max(510, Math.min(1330, center[1] + Math.sin(a) * r))];
      });
      return { center, radius, contour, edge_mass, core_mass, total_mass: v.load, color: p.pigment_colors[i], label: v.label };
    });
    return { progress: u, spread, dry, pools };
  }
  function sample34(spec, seconds) {
    const p = validateParameters11(spec);
    return state34(p, clock(p, seconds));
  }
  function render34(spec, seconds) {
    const p = validateParameters11(spec), s = state34(p, clock(p, seconds)), c = p.palette;
    return shell(ID34, p, seconds, s.pools.map((v) => poly(v.contour, v.color, v.color, 2 + v.edge_mass * 14, 0.12 + 0.28 * v.core_mass) + poly(v.contour, "none", v.color, 1 + v.edge_mass * 10, 0.2 + 0.6 * s.dry) + captionLabel(v.label, Math.max(130, Math.min(670, v.center[0] - 100)), Math.min(1300, v.center[1] + v.radius + 45), c.ink, 260)).join(""), "folio");
  }
  function validateSpec34(spec) {
    return { id: ID34, version: "1.0.0", parameters: validateParameters11(spec) };
  }

  // renderers/template-registry/modules/9db6c476432e-paper-lightbox-parallax.mjs
  var db6c476432e_paper_lightbox_parallax_exports = {};
  __export(db6c476432e_paper_lightbox_parallax_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE35,
    ID: () => ID35,
    METADATA: () => METADATA27,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA35,
    SOURCE_ID: () => SOURCE_ID35,
    render: () => render35,
    sample: () => sample35,
    validateSpec: () => validateSpec35
  });
  var ID35 = "paper-lightbox-parallax";
  var SOURCE_ID35 = "source-lemo-style-paper-lantern";
  var DEFAULT_PALETTE35 = Object.freeze({ "background": "#162D38", "ink": "#FFF4D8", "muted": "#D4D8C9", "accent": "#F3C36F" });
  var METADATA27 = Object.freeze({ "name": "Ka\u011F\u0131t katman\u0131nda i\xE7 \u0131\u015F\u0131k", "kind": "layer_light_parallax", "layout_id": "lightbox-window", "motion_grammar": "depth-proportional cut-sheet parallax with opposite-direction cast shadows", "typographic_hierarchy": "Koyu pencere \xE7evresi ve k\u0131sa \xFCst b\xF6l\xFCm ba\u015Fl\u0131\u011F\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA35 = schema({ layer_shapes: A(O({ aperture: E(["oval", "arch", "diamond"]), scale: N(0.5, 0.94), label: L }), 3, 5), layer_depths: A(N(0.1, 1), 3, 5), light_path: A(P, 2, 5), camera_offset: P });
  function validateParameters12(spec) {
    const p = base2(spec, ID35, ["layer_shapes", "layer_depths", "light_path", "camera_offset"], DEFAULT_PALETTE35), q = spec.parameters;
    p.layer_shapes = arr(q.layer_shapes, "layer_shapes", 3, 5).map((v) => {
      keys3(v, ["aperture", "scale", "label"]);
      return { aperture: choice3(v.aperture, "aperture", ["oval", "arch", "diamond"]), scale: number3(v.scale, "scale", 0.5, 0.94), label: label2(v.label) };
    });
    p.layer_depths = nums(q.layer_depths, "layer_depths", 0.1, 1, p.layer_shapes.length, p.layer_shapes.length);
    if (p.layer_depths.some((x, i) => i && x <= p.layer_depths[i - 1])) throw new Error("TEMPLATE_INPUT: increasing depths");
    p.light_path = pts(q.light_path, "light_path", 2, 5);
    p.camera_offset = pt(q.camera_offset);
    return p;
  }
  function hole(shape, cx, cy, scale) {
    const rx = 305 * scale, ry = 325 * scale;
    if (shape === "diamond") return [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]];
    if (shape === "arch") return [[cx - rx, cy + ry], [cx - rx, cy], ...Array.from({ length: 17 }, (_, i) => [cx - rx * Math.cos(i / 16 * Math.PI), cy - ry * Math.sin(i / 16 * Math.PI)]), [cx + rx, cy + ry]];
    return polar(cx, cy, rx, ry, 32);
  }
  function state35(p, u) {
    const g = phase(u), z = g * (p.light_path.length - 1), k = Math.min(p.light_path.length - 2, Math.floor(z)), f = z - k, light = xy(p.light_path[k].map((v, i) => lerp4(v, p.light_path[k + 1][i], f))), camera = p.camera_offset.map((v) => (v - 0.5) * 120 * g), layers = p.layer_shapes.map((v, i) => {
      const depth = p.layer_depths[i], offset = camera.map((x) => x * depth), cx = 540 + offset[0], cy = 960 + offset[1], shadow = [(540 - light[0]) * depth * 0.12, (960 - light[1]) * depth * 0.12];
      return { depth, offset, shadow, hole: hole(v.aperture, cx, cy, v.scale), label: v.label };
    });
    return { progress: u, light, camera, layers };
  }
  function sample35(spec, seconds) {
    const p = validateParameters12(spec);
    return state35(p, clock(p, seconds));
  }
  function render35(spec, seconds) {
    const p = validateParameters12(spec), s = state35(p, clock(p, seconds)), c = p.palette;
    const body = rect(140, 530, 800, 860, c.accent) + s.layers.map((v, i) => `<defs><mask id="lb-${i}">${rect(120, 510, 840, 900, "#FFFFFF")}${poly(v.hole, "#000000")}</mask></defs><g transform="translate(${v.shadow.map(fmt3).join(" ")})" opacity="0.35" mask="url(#lb-${i})">${rect(140, 530, 800, 860, "#000000")}</g><g mask="url(#lb-${i})">${rect(140 + v.offset[0], 530 + v.offset[1], 800, 860, i % 2 ? c.muted : c.background)}</g>`).join("") + circ(...s.light, 13, c.ink) + captionLabel("Katman derinli\u011Fi g\xF6r\xFCn\xFCr olur", 150, 1510, c.ink, 780);
    return shell(ID35, p, seconds, body, "lightbox");
  }
  function validateSpec35(spec) {
    return { id: ID35, version: "1.0.0", parameters: validateParameters12(spec) };
  }

  // renderers/template-registry/modules/c59afdf2fe07-page-hinge-popups.mjs
  var c59afdf2fe07_page_hinge_popups_exports = {};
  __export(c59afdf2fe07_page_hinge_popups_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE36,
    ID: () => ID36,
    METADATA: () => METADATA28,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA36,
    SOURCE_ID: () => SOURCE_ID36,
    render: () => render36,
    sample: () => sample36,
    validateSpec: () => validateSpec36
  });
  var ID36 = "page-hinge-popups";
  var SOURCE_ID36 = "source-lemo-style-paper-popup";
  var DEFAULT_PALETTE36 = Object.freeze({ "background": "#F8F0DB", "ink": "#313F42", "muted": "#545B51", "accent": "#8A3B30" });
  var METADATA28 = Object.freeze({ "name": "Sayfadan y\xFCkselen mente\u015Feler", "kind": "linked_paper_hinges", "layout_id": "hinge-book", "motion_grammar": "page opening drives linked rigid panels with parent-tip hinge constraints", "typographic_hierarchy": "\xDCst sol ba\u015Fl\u0131k ve a\xE7\u0131k sayfa merkezinde tek pop-up yap\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA36 = schema({ fold_angles: A(N(15, 80), 2, 5), page_angle: N(50, 145), hinge_links: A(N(-1, 3, true), 2, 5), popup_height: N(120, 300) });
  function validateParameters13(spec) {
    const p = base2(spec, ID36, ["fold_angles", "page_angle", "hinge_links", "popup_height"], DEFAULT_PALETTE36), q = spec.parameters;
    p.fold_angles = nums(q.fold_angles, "fold_angles", 15, 80, 2, 5);
    p.page_angle = number3(q.page_angle, "page_angle", 50, 145);
    p.hinge_links = nums(q.hinge_links, "hinge_links", -1, p.fold_angles.length - 2, p.fold_angles.length, p.fold_angles.length);
    if (p.hinge_links.some((v, i) => !Number.isInteger(v) || v >= i)) throw new Error("TEMPLATE_INPUT: hinge parent must precede child");
    p.popup_height = number3(q.popup_height, "popup_height", 120, 300);
    return p;
  }
  var project = ([x, y, z]) => [540 + x * 0.82 - y * 0.24, 1190 + y * 0.4 - z];
  function state36(p, u) {
    const g = phase(u, 0, 0.9), page3 = p.page_angle * g, panels = [];
    for (let i = 0; i < p.fold_angles.length; i++) {
      const parent = p.hinge_links[i], root = parent < 0 ? [0, i * 30, 0] : panels[parent].tip, angle = p.fold_angles[i] * g * Math.sin(p.page_angle * Math.PI / 360), length = p.popup_height * (0.65 + i * 0.05) / Math.sqrt(p.fold_angles.length), sign = i % 2 ? 1 : -1, tip = [root[0] + sign * Math.cos(angle * Math.PI / 180) * length, root[1], root[2] + Math.sin(angle * Math.PI / 180) * length], corners2 = [project(root), project(tip), project([tip[0], tip[1] + 100, tip[2]]), project([root[0], root[1] + 100, root[2]])];
      panels.push({ parent, root: [...root], tip, length, angle, corners: corners2 });
    }
    return { progress: u, page_angle: page3, panels };
  }
  function sample36(spec, seconds) {
    const p = validateParameters13(spec);
    return state36(p, clock(p, seconds));
  }
  function render36(spec, seconds) {
    const p = validateParameters13(spec), s = state36(p, clock(p, seconds)), c = p.palette, spread = 150 + 230 * Math.sin(s.page_angle * Math.PI / 360);
    return shell(ID36, p, seconds, poly([[540, 1180], [540 - spread, 1030], [540 - spread, 1340], [540, 1420]], c.muted, c.ink, 2) + poly([[540, 1180], [540 + spread, 1030], [540 + spread, 1340], [540, 1420]], c.background, c.ink, 2) + s.panels.map((v, i) => poly(v.corners, i % 2 ? c.accent : c.background, c.ink, 3) + line2(v.corners[0], v.corners[3], c.muted, 5)).join(""), "board");
  }
  function validateSpec36(spec) {
    return { id: ID36, version: "1.0.0", parameters: validateParameters13(spec) };
  }

  // renderers/template-registry/modules/90ca2481eb30-negative-space-cut.mjs
  var ca2481eb30_negative_space_cut_exports = {};
  __export(ca2481eb30_negative_space_cut_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE37,
    ID: () => ID37,
    METADATA: () => METADATA29,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA37,
    SOURCE_ID: () => SOURCE_ID37,
    render: () => render37,
    sample: () => sample37,
    validateSpec: () => validateSpec37
  });
  var ID37 = "negative-space-cut";
  var SOURCE_ID37 = "source-lemo-style-papercut-red";
  var DEFAULT_PALETTE37 = Object.freeze({ "background": "#FFF4E3", "ink": "#422E2F", "muted": "#6A4A48", "accent": "#9B282E" });
  var METADATA29 = Object.freeze({ "name": "Negatif alanda simetri", "kind": "folded_negative_cut", "layout_id": "cutting-sheet", "motion_grammar": "bounded symmetric holes cut into a connected sheet then unfold in mirrored sectors", "typographic_hierarchy": "Yan kenara yasl\u0131 ba\u015Fl\u0131k ve tek k\u0131rm\u0131z\u0131 kesim levhas\u0131", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA37 = schema({ cut_paths: A(A(P, 3, 6), 2, 5), fold_count: N(1, 4, true), unfold_angle: N(60, 180), sheet_thickness: N(2, 12) });
  function validateParameters14(spec) {
    const p = base2(spec, ID37, ["cut_paths", "fold_count", "unfold_angle", "sheet_thickness"], DEFAULT_PALETTE37), q = spec.parameters;
    p.cut_paths = arr(q.cut_paths, "cut_paths", 2, 5).map((v) => pts(v, "cut path", 3, 6));
    p.fold_count = number3(q.fold_count, "fold_count", 1, 4, true);
    p.unfold_angle = number3(q.unfold_angle, "unfold_angle", 60, 180);
    p.sheet_thickness = number3(q.sheet_thickness, "sheet_thickness", 2, 12);
    return p;
  }
  function state37(p, u) {
    const cut = phase(u, 0, 0.5), unfold = phase(u, 0.35, 0.95), cuts2 = [];
    for (let sector = 0; sector < p.fold_count * 2; sector++) {
      const a = (sector / (p.fold_count * 2 - 1) - 0.5) * p.unfold_angle * unfold * Math.PI / 180, mirror = sector % 2 ? -1 : 1;
      for (let k = 0; k < p.cut_paths.length; k++) {
        const polygon3 = p.cut_paths[k].map(([x, y]) => {
          const xx = (35 + x * 190) * mirror * cut, yy = (y - 0.5) * 160 * cut;
          return [540 + xx * Math.cos(a) - yy * Math.sin(a), 955 + xx * Math.sin(a) + yy * Math.cos(a)];
        });
        cuts2.push({ sector, path_index: k, angle: a, mirror, polygon: polygon3 });
      }
    }
    return { progress: u, cut, unfold, cuts: cuts2, copies: p.fold_count * 2, border_connected: true };
  }
  function sample37(spec, seconds) {
    const p = validateParameters14(spec);
    return state37(p, clock(p, seconds));
  }
  function render37(spec, seconds) {
    const p = validateParameters14(spec), s = state37(p, clock(p, seconds)), c = p.palette;
    return shell(ID37, p, seconds, `<defs><mask id="negative-sheet">${rect(190, 575, 700, 785, "#FFFFFF")}${s.cuts.map((v) => poly(v.polygon, "#000000")).join("")}</mask></defs>${rect(190 + p.sheet_thickness, 575 + p.sheet_thickness, 700, 785, c.muted)}<g mask="url(#negative-sheet)">${rect(190, 575, 700, 785, c.accent)}</g>`, "side");
  }
  function validateSpec37(spec) {
    return { id: ID37, version: "1.0.0", parameters: validateParameters14(spec) };
  }

  // renderers/template-registry/modules/45c58325ff8c-screenprint-layer-pull.mjs
  var c58325ff8c_screenprint_layer_pull_exports = {};
  __export(c58325ff8c_screenprint_layer_pull_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE38,
    ID: () => ID38,
    METADATA: () => METADATA30,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA38,
    SOURCE_ID: () => SOURCE_ID38,
    render: () => render38,
    sample: () => sample38,
    validateSpec: () => validateSpec38
  });
  var ID38 = "screenprint-layer-pull";
  var SOURCE_ID38 = "source-lemo-style-silkscreen-poster";
  var DEFAULT_PALETTE38 = Object.freeze({ "background": "#F4EEDD", "ink": "#1D3839", "muted": "#455D53", "accent": "#925026" });
  var METADATA30 = Object.freeze({ "name": "Stencil bask\u0131 \xE7eki\u015Fi", "kind": "directional_stencil_transfer", "layout_id": "press-poster", "motion_grammar": "discrete stencil masks fill only behind a directional squeegee in ordered color passes", "typographic_hierarchy": "B\xFCy\xFCk manifesto ba\u015Fl\u0131\u011F\u0131 ve bask\u0131 \xE7er\xE7evesi", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA38 = schema({ stencil_shapes: A(O({ shape: E(["sun", "arch", "ridge"]), center: P, size: P, label: L }), 2, 4), spot_colors: A(C, 2, 4), pass_order: A(N(0, 3, true), 2, 4), pull_direction: E(["up", "down", "left", "right"]) });
  function validateParameters15(spec) {
    const p = base2(spec, ID38, ["stencil_shapes", "spot_colors", "pass_order", "pull_direction"], DEFAULT_PALETTE38), q = spec.parameters;
    p.stencil_shapes = arr(q.stencil_shapes, "stencil_shapes", 2, 4).map((v) => {
      keys3(v, ["shape", "center", "size", "label"]);
      return { shape: choice3(v.shape, "shape", ["sun", "arch", "ridge"]), center: pt(v.center), size: nums(v.size, "size", 0.1, 0.4, 2, 2), label: label2(v.label) };
    });
    p.spot_colors = colors(q.spot_colors, "spot_colors", p.stencil_shapes.length, p.stencil_shapes.length);
    p.pass_order = order(q.pass_order, "pass_order", p.stencil_shapes.length);
    p.pull_direction = choice3(q.pull_direction, "pull_direction", ["up", "down", "left", "right"]);
    return p;
  }
  function state38(p, u) {
    const layers = p.stencil_shapes.map((v, i) => {
      const center = xy(v.center), rx = v.size[0] * 780, ry = v.size[1] * 860;
      let polygon3 = v.shape === "sun" ? polar(...center, rx, ry, 28) : v.shape === "arch" ? [[center[0] - rx, center[1] + ry], [center[0] - rx, center[1]], ...Array.from({ length: 17 }, (_, i2) => [center[0] - rx * Math.cos(i2 / 16 * Math.PI), center[1] - ry * Math.sin(i2 / 16 * Math.PI)]), [center[0] + rx, center[1] + ry]] : [[center[0] - rx, center[1] + ry], [center[0] - rx * 0.3, center[1] - ry], [center[0] + rx * 0.1, center[1] - ry * 0.3], [center[0] + rx, center[1] + ry]];
      polygon3 = polygon3.map(([x, y]) => [Math.max(155, Math.min(925, x)), Math.max(535, Math.min(1385, y))]);
      const rank = p.pass_order.indexOf(i), coverage = phase(u, rank * 0.16, 0.36 + rank * 0.17);
      let box3 = p.pull_direction === "down" ? [150, 530, 780, 860 * coverage] : p.pull_direction === "up" ? [150, 1390 - 860 * coverage, 780, 860 * coverage] : p.pull_direction === "right" ? [150, 530, 780 * coverage, 860] : [930 - 780 * coverage, 530, 780 * coverage, 860];
      return { index: i, rank, polygon: polygon3, coverage, box: box3, color: p.spot_colors[i] };
    }).sort((a, b) => a.rank - b.rank);
    const moving = layers.find((v) => v.coverage > 0 && v.coverage < 1) || layers.at(-1);
    return { progress: u, layers, squeegee: moving.box, direction: p.pull_direction };
  }
  function sample38(spec, seconds) {
    const p = validateParameters15(spec);
    return state38(p, clock(p, seconds));
  }
  function render38(spec, seconds) {
    const p = validateParameters15(spec), s = state38(p, clock(p, seconds)), c = p.palette;
    const [x, y, w, h] = s.squeegee, horizontal = ["up", "down"].includes(s.direction);
    return shell(ID38, p, seconds, s.layers.map((v) => `<defs><clipPath id="stencil-${v.index}">${poly(v.polygon, "#FFFFFF")}</clipPath></defs>${poly(v.polygon, "none", c.muted, 1)}<g clip-path="url(#stencil-${v.index})">${rect(...v.box, v.color)}</g>`).join("") + rect(horizontal ? 150 : s.direction === "left" ? x : x + w - 14, horizontal ? s.direction === "up" ? y : y + h - 14 : 530, horizontal ? 780 : 14, horizontal ? 14 : 860, c.ink), "press");
  }
  function validateSpec38(spec) {
    return { id: ID38, version: "1.0.0", parameters: validateParameters15(spec) };
  }

  // renderers/template-registry/modules/98136c29def5-lead-cell-lightpass.mjs
  var c29def5_lead_cell_lightpass_exports = {};
  __export(c29def5_lead_cell_lightpass_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE39,
    ID: () => ID39,
    METADATA: () => METADATA31,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA39,
    SOURCE_ID: () => SOURCE_ID39,
    render: () => render39,
    sample: () => sample39,
    validateSpec: () => validateSpec39
  });
  var ID39 = "lead-cell-lightpass";
  var SOURCE_ID39 = "source-lemo-style-stained-glass";
  var DEFAULT_PALETTE39 = Object.freeze({ "background": "#182633", "ink": "#F9EACD", "muted": "#C5CCCA", "accent": "#E2B05F" });
  var METADATA31 = Object.freeze({ "name": "Kur\u015Fun h\xFCcrede \u0131\u015F\u0131k", "kind": "lead_bounded_transmission", "layout_id": "lead-window", "motion_grammar": "convex panes seat into fixed lead boundaries; moving backlight scales bounded transmission", "typographic_hierarchy": "Koyu \xE7er\xE7eve ve mozaik h\xFCcrelerden olu\u015Fan tek pencere", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA39 = schema({ cell_polygons: A(A(P, 3, 6), 3, 7), lead_width: N(4, 18), light_path: A(P, 2, 5), transmission_values: A(N(0.1, 1), 3, 7) });
  function validateParameters16(spec) {
    const p = base2(spec, ID39, ["cell_polygons", "lead_width", "light_path", "transmission_values"], DEFAULT_PALETTE39), q = spec.parameters;
    p.cell_polygons = arr(q.cell_polygons, "cell_polygons", 3, 7).map((v) => {
      const a = pts(v, "polygon", 3, 6), cross3 = a.map((x, i) => {
        const y = a[(i + 1) % a.length], z = a[(i + 2) % a.length];
        return (y[0] - x[0]) * (z[1] - y[1]) - (y[1] - x[1]) * (z[0] - y[0]);
      });
      if (cross3.some((x) => Math.abs(x) < 1e-6) || !(cross3.every((x) => x > 0) || cross3.every((x) => x < 0))) throw new Error("TEMPLATE_INPUT: nondegenerate convex cell required");
      return a;
    });
    p.lead_width = number3(q.lead_width, "lead_width", 4, 18);
    p.light_path = pts(q.light_path, "light_path", 2, 5);
    p.transmission_values = nums(q.transmission_values, "transmission_values", 0.1, 1, p.cell_polygons.length, p.cell_polygons.length);
    return p;
  }
  function state39(p, u) {
    const z = phase(u, 0.15, 0.95) * (p.light_path.length - 1), k = Math.min(p.light_path.length - 2, Math.floor(z)), f = z - k, light = xy(p.light_path[k].map((v, i) => lerp4(v, p.light_path[k + 1][i], f))), cells = p.cell_polygons.map((v, i) => {
      const seat = phase(u, i * 0.045, 0.3 + i * 0.045), points = v.map(xy).map(([x, y]) => [x, y - (1 - seat) * 130]), centroid = [points.reduce((a, v2) => a + v2[0], 0) / points.length, points.reduce((a, v2) => a + v2[1], 0) / points.length], brightness = 0.28 + 0.72 * Math.exp(-(Math.hypot(centroid[0] - light[0], centroid[1] - light[1]) ** 2) / 18e4);
      return { points, seat, centroid, lead: p.lead_width, transmitted: brightness * p.transmission_values[i], maximum_transmission: p.transmission_values[i] };
    });
    return { progress: u, light, cells };
  }
  function sample39(spec, seconds) {
    const p = validateParameters16(spec);
    return state39(p, clock(p, seconds));
  }
  function render39(spec, seconds) {
    const p = validateParameters16(spec), s = state39(p, clock(p, seconds)), c = p.palette;
    return shell(ID39, p, seconds, rect(140, 515, 800, 890, c.ink) + s.cells.map((v, i) => poly(v.points, i % 3 === 0 ? c.accent : i % 3 === 1 ? c.muted : c.ink, "none", 0, 0.18 + 0.82 * v.transmitted) + poly(v.points, "none", c.background, v.lead, 1)).join("") + circ(...s.light, 14, c.ink, c.background, 3), "lightbox");
  }
  function validateSpec39(spec) {
    return { id: ID39, version: "1.0.0", parameters: validateParameters16(spec) };
  }

  // renderers/template-registry/modules/814534e3c09b-woodblock-wave-layers.mjs
  var e3c09b_woodblock_wave_layers_exports = {};
  __export(e3c09b_woodblock_wave_layers_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE40,
    ID: () => ID40,
    METADATA: () => METADATA32,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA40,
    SOURCE_ID: () => SOURCE_ID40,
    render: () => render40,
    sample: () => sample40,
    validateSpec: () => validateSpec40
  });
  var ID40 = "woodblock-wave-layers";
  var SOURCE_ID40 = "source-lemo-style-ukiyoe";
  var DEFAULT_PALETTE40 = Object.freeze({ "background": "#F3EFDC", "ink": "#173B4F", "muted": "#4B5B61", "accent": "#1C617C" });
  var METADATA32 = Object.freeze({ "name": "Dalga bloklar\u0131n\u0131n kayd\u0131", "kind": "contour_woodblock_passes", "layout_id": "wave-triptych", "motion_grammar": "contour-led color block printing then depth-separated lateral travel with registered foam", "typographic_hierarchy": "Al\xE7ak horizon ve geni\u015F dalga k\xFCtleleri; \xFCst sa\u011Fa a\xE7\u0131lan ba\u015Fl\u0131k", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA40 = schema({ wave_contours: A(O({ amplitude: N(20, 85), frequency: N(1, 4), phase: N(0, 6.28), level: N(0.15, 0.75) }), 2, 4), color_blocks: A(C, 2, 4), plane_depths: A(N(0.1, 1), 2, 4), print_order: A(N(0, 3, true), 2, 4) });
  function validateParameters17(spec) {
    const p = base2(spec, ID40, ["wave_contours", "color_blocks", "plane_depths", "print_order"], DEFAULT_PALETTE40), q = spec.parameters;
    p.wave_contours = arr(q.wave_contours, "wave_contours", 2, 4).map((v) => {
      keys3(v, ["amplitude", "frequency", "phase", "level"]);
      return { amplitude: number3(v.amplitude, "amplitude", 20, 85), frequency: number3(v.frequency, "frequency", 1, 4), phase: number3(v.phase, "phase", 0, 6.28), level: number3(v.level, "level", 0.15, 0.75) };
    });
    p.color_blocks = colors(q.color_blocks, "color_blocks", p.wave_contours.length, p.wave_contours.length);
    p.plane_depths = nums(q.plane_depths, "plane_depths", 0.1, 1, p.wave_contours.length, p.wave_contours.length);
    if (p.plane_depths.some((v, i) => i && v <= p.plane_depths[i - 1])) throw new Error("TEMPLATE_INPUT: increasing depth");
    p.print_order = order(q.print_order, "print_order", p.wave_contours.length);
    return p;
  }
  function state40(p, u) {
    const travel = phase(u, 0.4, 0.96), layers = p.wave_contours.map((v, i) => {
      const depth = p.plane_depths[i], offset = depth * 45 * travel, contour = Array.from({ length: 33 }, (_, j) => [150 + j / 32 * 780 + offset, 625 + v.level * 620 + Math.sin(j / 32 * Math.PI * 2 * v.frequency + v.phase + travel * depth * 0.45) * v.amplitude]), rank = p.print_order.indexOf(i), coverage = phase(u, rank * 0.12, 0.45 + rank * 0.12), foam = [6, 12, 20, 27].map((k) => ({ point: [...contour[k]], index: k, radius: 4 + depth * 3 }));
      return { contour, depth, offset, coverage, foam, color: p.color_blocks[i], index: i };
    });
    return { progress: u, travel, layers };
  }
  function sample40(spec, seconds) {
    const p = validateParameters17(spec);
    return state40(p, clock(p, seconds));
  }
  function render40(spec, seconds) {
    const p = validateParameters17(spec), s = state40(p, clock(p, seconds)), c = p.palette;
    return shell(ID40, p, seconds, s.layers.map((v) => `<defs><clipPath id="wave-${v.index}">${rect(140, 520, 840 * v.coverage, 900, "#FFFFFF")}</clipPath></defs><g clip-path="url(#wave-${v.index})">${poly([...v.contour, [v.contour.at(-1)[0], 1380], [v.contour[0][0], 1380]], v.color, c.ink, 2)}${v.foam.map((f) => circ(...f.point, f.radius, c.background)).join("")}</g>`).join(""), "poster");
  }
  function validateSpec40(spec) {
    return { id: ID40, version: "1.0.0", parameters: validateParameters17(spec) };
  }

  // renderers/template-registry/modules/f1f65e5b2121-carved-groove-print.mjs
  var f1f65e5b2121_carved_groove_print_exports = {};
  __export(f1f65e5b2121_carved_groove_print_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE41,
    ID: () => ID41,
    METADATA: () => METADATA33,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA41,
    SOURCE_ID: () => SOURCE_ID41,
    render: () => render41,
    sample: () => sample41,
    validateSpec: () => validateSpec41
  });
  var ID41 = "carved-groove-print";
  var SOURCE_ID41 = "source-lemo-style-woodcut";
  var DEFAULT_PALETTE41 = Object.freeze({ "background": "#F4E5C8", "ink": "#332919", "muted": "#62503B", "accent": "#75452C" });
  var METADATA33 = Object.freeze({ "name": "Oyuk ve relief transferi", "kind": "negative_groove_transfer", "layout_id": "relief-proof", "motion_grammar": "ordered grooves remove relief; pressure-bounded transfer preserves mirrored negative cuts", "typographic_hierarchy": "\u0130ki kolon: solda oyulan blok, sa\u011Fda bask\u0131; b\xFCy\xFCk alt ba\u015Fl\u0131k", "original_implementation": true, "native_verified": false, "independent_accepted": false, "ui_verified": false, "implementation_strategy": "original_implementation_not_source_code_port" });
  var PARAMETER_SCHEMA41 = schema({ groove_paths: A(A(P, 2, 6), 2, 6), groove_width: N(4, 18), ink_pressure: N(0.2, 1), print_order: A(N(0, 5, true), 2, 6) });
  function validateParameters18(spec) {
    const p = base2(spec, ID41, ["groove_paths", "groove_width", "ink_pressure", "print_order"], DEFAULT_PALETTE41), q = spec.parameters;
    p.groove_paths = arr(q.groove_paths, "groove_paths", 2, 6).map((v) => pts(v, "groove", 2, 6));
    p.groove_width = number3(q.groove_width, "groove_width", 4, 18);
    p.ink_pressure = number3(q.ink_pressure, "ink_pressure", 0.2, 1);
    p.print_order = order(q.print_order, "print_order", p.groove_paths.length);
    return p;
  }
  function state41(p, u) {
    const grooves = p.groove_paths.map((v, i) => {
      const rank = p.print_order.indexOf(i), cut = phase(u, rank * 0.035, 0.35 + rank * 0.035), z = cut * (v.length - 1), k = Math.min(v.length - 2, Math.floor(z)), partial = [...v.slice(0, k + 1), v[k].map((x, j) => lerp4(x, v[k + 1][j], z - k))];
      return { cut, source: partial.map(([x, y]) => [140 + x * 350, 620 + y * 600]), proof: partial.map(([x, y]) => [940 - x * 350, 620 + y * 600]) };
    });
    const transfer = phase(u, 0.6, 0.98), contact_height = 640 * p.ink_pressure * transfer;
    return { progress: u, grooves, transfer, contact_height, pressure: p.ink_pressure, width: p.groove_width };
  }
  function sample41(spec, seconds) {
    const p = validateParameters18(spec);
    return state41(p, clock(p, seconds));
  }
  function render41(spec, seconds) {
    const p = validateParameters18(spec), s = state41(p, clock(p, seconds)), c = p.palette;
    const cuts2 = s.grooves.map((g) => `<path d="${path3(g.proof)}" stroke="#000000" stroke-width="${fmt3(p.groove_width)}" fill="none" stroke-linecap="round"/>`).join("");
    return shell(ID41, p, seconds, rect(115, 590, 400, 680, c.accent) + s.grooves.map((g) => `<path d="${path3(g.source)}" stroke="${c.background}" stroke-width="${fmt3(p.groove_width)}" fill="none" stroke-linecap="round"/>`).join("") + `<defs><mask id="relief-proof">${rect(565, 590, 400, 680, "#FFFFFF")}${cuts2}</mask></defs>` + rect(565, 590, 400, 680, c.background, c.muted, 2) + `<g mask="url(#relief-proof)">${rect(580, 610, 370, s.contact_height, c.ink)}</g>` + captionLabel("Oyulan blok", 125, 1320, c.ink, 350) + captionLabel("Aynalanan bask\u0131", 575, 1320, c.ink, 350), "folio");
  }
  function validateSpec41(spec) {
    return { id: ID41, version: "1.0.0", parameters: validateParameters18(spec) };
  }

  // renderers/template-registry/modules/b47c644108ee-stud-lock-assembly.mjs
  var b47c644108ee_stud_lock_assembly_exports = {};
  __export(b47c644108ee_stud_lock_assembly_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE42,
    ID: () => ID42,
    METADATA: () => METADATA34,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA42,
    SOURCE_ID: () => SOURCE_ID42,
    render: () => render42,
    sample: () => sample42,
    validateSpec: () => validateSpec42
  });

  // renderers/template-registry/modules/09764466d2b7-common.mjs
  var DEFAULT = Object.freeze({ background: "#F3F2E9", ink: "#202F35", muted: "#526169", accent: "#80522F" });
  var DARK = Object.freeze({ background: "#17232D", ink: "#F2F2E5", muted: "#BACBCE", accent: "#EAC66E" });
  function base3(spec, id, required, optional, colors2 = DEFAULT) {
    keys3(spec, ["id", "version", "parameters"], [], "spec");
    keys3(spec.parameters, ["title", "duration", "narration", "cues", ...required], [...optional, "palette"], "parameters");
    list2(spec.parameters.cues, "cues", 1, 24, (v) => v);
    if (Object.hasOwn(spec.parameters, "palette") && spec.parameters.palette === void 0) fail3("palette: explicit undefined is not a color object");
    return validateBase3(spec, id, required, optional, colors2);
  }
  var result = (id, p) => deepFreeze2({ id, version: VERSION3, parameters: p });
  function list2(value, name, min, max, map) {
    if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype || value.length < min || value.length > max) fail3(name + ": bounded plain array required");
    const names2 = Reflect.ownKeys(value);
    if (names2.length !== value.length + 1 || names2.some((k) => typeof k !== "string" || k !== "length" && !/^(0|[1-9][0-9]*)$/.test(k))) fail3(name + ": dense array without extra properties required");
    for (let i = 0; i < value.length; i++) {
      const d = Object.getOwnPropertyDescriptor(value, String(i));
      if (!d || !Object.hasOwn(d, "value")) fail3(name + ": array data items required");
    }
    return value.map(map);
  }
  function label3(value, name = "label", maximum = 65, width = 840, lines = 3) {
    const s = text3(value, name, maximum);
    fitText3(s, { width, maximum: 40, minimum: 28, maxLines: lines });
    return s;
  }
  function point2(value, name = "point", low = 0, high = 1) {
    keys3(value, ["x", "y"], [], name);
    return { x: number3(value.x, name + ".x", low, high), y: number3(value.y, name + ".y", low, high) };
  }
  function ordered(values, name, min, max) {
    const a = list2(values, name, min, max, (v) => number3(v, name, 0, 1));
    if (a.some((v, i) => i && v <= a[i - 1])) fail3(name + ": strictly increasing required");
    return a;
  }
  function context(spec, seconds) {
    const p = spec.parameters, t = sampleTime3(seconds, p.duration), active = p.duration - 0.8;
    return { p, t, u: clamp3(t / active), active, hold: t >= active };
  }
  function metadata(name, kind, layout, motion, hierarchy) {
    return deepFreeze2({ name, kind, layout_id: layout, motion_grammar: motion, typographic_hierarchy: hierarchy, original_implementation: true, strategy: "original_implementation_not_source_code_port", source_code_copied: false, native_verified: false, ui_verified: false, independent_accepted: false, product_registered: false });
  }
  var rect2 = (x, y, w, h, fill, rx = 0, stroke = "none", sw = 0) => `<rect x="${fmt3(x)}" y="${fmt3(y)}" width="${fmt3(w)}" height="${fmt3(h)}" rx="${fmt3(rx)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(sw)}"/>`;
  var circle = (x, y, r, fill, stroke = "none", sw = 0) => `<circle cx="${fmt3(x)}" cy="${fmt3(y)}" r="${fmt3(r)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(sw)}"/>`;
  var line3 = (x1, y1, x2, y2, color2, width = 4) => `<line x1="${fmt3(x1)}" y1="${fmt3(y1)}" x2="${fmt3(x2)}" y2="${fmt3(y2)}" stroke="${color2}" stroke-width="${fmt3(width)}" stroke-linecap="round"/>`;
  var polygon2 = (points, fill, stroke = "none", width = 0) => `<polygon points="${points.map((p) => fmt3(p.x) + "," + fmt3(p.y)).join(" ")}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(width)}" stroke-linejoin="round"/>`;
  var txt = (value, x, y, width = 880, size = 40, fill = "#202F35", lines = 3, anchor = "start") => svgText3(value, { x, y, width, maximum: size, minimum: 28, maxLines: lines, fill, anchor });
  function page2(id, p, t, body, { layout = "workbench", note = "\xD6zg\xFCn geometri \xB7 inceleme bekliyor" } = {}) {
    const c = p.palette, head = { workbench: [90, 158, 900, 62, 4, "start"], arcade: [90, 150, 900, 56, 4, "start"], theatre: [540, 182, 900, 66, 3, "middle"], technical: [80, 145, 920, 58, 4, "start"], triptych: [90, 165, 900, 60, 3, "start"] }[layout];
    if (!head) fail3("unknown fixed layout");
    const cue = activeCue3(p.cues, t);
    let headerFont = head[3];
    while (headerFont > 28 && fitText3(p.title, { width: head[2], maximum: headerFont, minimum: 28, maxLines: head[4] }).height > 225) headerFont--;
    const header = txt(p.title, head[0], head[1], head[2], headerFont, c.ink, head[4], head[5]);
    const accentRule = layout === "arcade" ? rect2(90, 440, 900, 12, c.accent) : layout === "technical" ? line3(80, 430, 1e3, 430, c.muted, 2) : layout === "theatre" ? line3(360, 448, 720, 448, c.accent, 5) : line3(90, 440, 990, 440, c.muted, 2);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc3(p.title)}" data-renderer="${id}" data-seconds="${fmt3(t)}" data-layout="${layout}">${rect2(0, 0, 1080, 1920, c.background)}<g font-family="sans-serif">${header}${accentRule}<g id="graphic">${body}</g><g id="captions">${cue ? txt(cue.text, 90, 1680, 900, 42, c.ink, 3) : ""}</g>${txt(note, 90, 1850, 900, 28, c.muted, 1)}</g></svg>`;
  }
  function route(points, u) {
    const lengths = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
    const total = lengths.reduce((a, b) => a + b, 0);
    if (total < 1e-9) return { ...points[0], segment: 0, local: 0 };
    let d = clamp3(u) * total;
    for (let i = 0; i < lengths.length; i++) {
      if (d <= lengths[i] || i === lengths.length - 1) {
        const q = lengths[i] ? d / lengths[i] : 0;
        return { x: lerp3(points[i].x, points[i + 1].x, q), y: lerp3(points[i].y, points[i + 1].y, q), segment: i, local: q };
      }
      d -= lengths[i];
    }
    return { ...points.at(-1), segment: lengths.length - 1, local: 1 };
  }
  function joint2(origin, length, degrees) {
    const a = degrees * Math.PI / 180;
    return { x: origin.x + Math.sin(a) * length, y: origin.y + Math.cos(a) * length };
  }
  function rig(shoulder, elbow, hip = 0, knee = 0) {
    const neck = { x: 0, y: 0 }, pelvis = { x: 0, y: 70 }, armStart = { x: 24, y: 18 }, armMid = joint2(armStart, 48, shoulder), hand = joint2(armMid, 44, shoulder + elbow), legStart = { x: 14, y: 70 }, legMid = joint2(legStart, 56, hip), foot = joint2(legMid, 50, hip + knee);
    return { neck, pelvis, armStart, armMid, hand, legStart, legMid, foot };
  }
  function pair(value, name, low, high) {
    return list2(value, name, 2, 2, (v) => number3(v, name, low, high));
  }
  function rotateY(v, degrees) {
    const a = degrees * Math.PI / 180;
    return { x: v.x * Math.cos(a) + v.z * Math.sin(a), y: v.y, z: -v.x * Math.sin(a) + v.z * Math.cos(a) };
  }
  function project2(v, degrees, cx = 540, cy = 1150, scale = 1) {
    const r = rotateY(v, degrees);
    return { x: cx + r.x * scale, y: cy - r.y * scale + r.z * 0.24 * scale };
  }

  // renderers/template-registry/modules/b47c644108ee-stud-lock-assembly.mjs
  var ID42 = "stud-lock-assembly";
  var SOURCE_ID42 = "source-lemo-style-brick-toy";
  var DEFAULT_PALETTE42 = DEFAULT;
  var METADATA34 = metadata("Ge\xE7meli blok montaj\u0131", "blocks", "assembly-bench", "ordered descent \u2192 stud contact \u2192 compression \u2192 settled support", "left headline / central lattice / build legend");
  var PARAMETER_SCHEMA42 = { blocks: { minItems: 2, maxItems: 6, item: { slot: [0, 4], level: [0, 2], span: [1, 2], label: { maxLength: 40 } } }, stud_grid: [2, 4], assembly_order: "permutation of block indices", contact_compression: [0.02, 0.14], snap_height: [80, 200] };
  function validateSpec42(spec) {
    const p = base3(spec, ID42, ["blocks", "assembly_order"], ["stud_grid", "contact_compression", "snap_height"], DEFAULT_PALETTE42), r = spec.parameters;
    p.stud_grid = number3(Object.hasOwn(r, "stud_grid") ? r.stud_grid : 3, "stud_grid", 2, 4, true);
    p.contact_compression = number3(Object.hasOwn(r, "contact_compression") ? r.contact_compression : 0.08, "contact_compression", 0.02, 0.14);
    p.snap_height = number3(Object.hasOwn(r, "snap_height") ? r.snap_height : 150, "snap_height", 80, 200);
    p.blocks = list2(r.blocks, "blocks", 2, 6, (b, i) => {
      keys3(b, ["slot", "level", "span", "label"]);
      const v = { slot: number3(b.slot, "slot", 0, 4, true), level: number3(b.level, "level", 0, 2, true), span: number3(b.span, "span", 1, 2, true), label: label3(b.label, "block label", 40, 400, 2) };
      if (v.slot + v.span > 5) fail3("block exceeds five-column lattice");
      return v;
    });
    p.assembly_order = list2(r.assembly_order, "assembly_order", p.blocks.length, p.blocks.length, (v) => number3(v, "assembly index", 0, p.blocks.length - 1, true));
    if (new Set(p.assembly_order).size !== p.blocks.length) fail3("assembly order must be a permutation");
    const occupied = /* @__PURE__ */ new Set();
    for (const index of p.assembly_order) {
      const b = p.blocks[index];
      for (let x = b.slot; x < b.slot + b.span; x++) {
        if (occupied.has(b.level + ":" + x)) fail3("overlapping lattice cells");
        if (b.level && !occupied.has(b.level - 1 + ":" + x)) fail3("raised block requires support already assembled");
        occupied.add(b.level + ":" + x);
      }
    }
    return result(ID42, p);
  }
  function sample42(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec42(spec), seconds), position = u * p.blocks.length;
    const blocks = p.blocks.map((b, index) => {
      const order2 = p.assembly_order.indexOf(index), q = clamp3(position - order2), approach = smooth3(q / 0.72), contact = q > 0.72 && q < 1 ? Math.sin((q - 0.72) / 0.28 * Math.PI) : 0, sy = 1 - p.contact_compression * contact;
      return { index, order: order2, label: b.label, width: b.span * 132, x: 210 + b.slot * 132 + (1 - approach) * (order2 % 2 ? -90 : 90), y: 1360 - b.level * 96 - p.snap_height * (1 - approach), targetX: 210 + b.slot * 132, targetY: 1360 - b.level * 96, scaleY: sy, scaleX: 1 / sy, visible: position >= order2, settled: q === 1, studs: b.span * p.stud_grid };
    });
    return { seconds: t, progress: u, hold, settledCount: blocks.filter((b) => b.settled).length, blocks };
  }
  function render42(spec, seconds) {
    const n = validateSpec42(spec), p = n.parameters, s = sample42(n, seconds), c = p.palette;
    let body = txt("Par\xE7alar s\u0131rayla kendi deste\u011Fine oturur.", 90, 535, 900, 38, c.muted, 2) + line3(165, 1470, 950, 1470, c.ink, 5);
    for (let i = 0; i < 16; i++) body += circle(185 + i * 48, 1462, 8, c.muted);
    for (const b of [...s.blocks].sort((a, b2) => a.order - b2.order)) {
      if (!b.visible) continue;
      body += `<g transform="translate(${fmt3(b.x)} ${fmt3(b.y)}) scale(${fmt3(b.scaleX)} ${fmt3(b.scaleY)})">${rect2(0, 0, b.width - 8, 84, c.accent, 8, c.ink, 4)}`;
      for (let k = 0; k < b.studs; k++) body += rect2(8 + k * (b.width - 24) / b.studs, -15, (b.width - 32) / b.studs, 18, c.accent, 3, c.ink, 3);
      body += `</g>`;
    }
    body += txt(s.settledCount + " / " + p.blocks.length + " par\xE7a yerinde", 90, 1570, 900, 40, c.ink, 1);
    return page2(ID42, p, s.seconds, body, { layout: "workbench" });
  }

  // renderers/template-registry/modules/58bb7abca301-pixel-depth-diorama.mjs
  var bb7abca301_pixel_depth_diorama_exports = {};
  __export(bb7abca301_pixel_depth_diorama_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE43,
    ID: () => ID43,
    METADATA: () => METADATA35,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA43,
    SOURCE_ID: () => SOURCE_ID43,
    render: () => render43,
    sample: () => sample43,
    validateSpec: () => validateSpec43
  });
  var ID43 = "pixel-depth-diorama";
  var SOURCE_ID43 = "source-lemo-style-hd-2d";
  var DEFAULT_PALETTE43 = DARK;
  var METADATA35 = metadata("Piksel derinlik sahnesi", "planes", "depth-strip", "pixel-snapped route / proportional parallax / light-dependent occlusion", "broad scene window / actor plane / depth readout");
  var PARAMETER_SCHEMA43 = { plane_depths: { length: 3, strictIncreasing: true }, actor_route: { minItems: 2, maxItems: 5, xy: [0.12, 0.88] }, light_position: { length: 2, xy: [-1, 1] }, pixel_scale: [8, 18], camera_travel: [80, 200], actor_label: { maxLength: 65 } };
  function validateSpec43(spec) {
    const p = base3(spec, ID43, ["plane_depths", "actor_route", "light_position", "actor_label"], ["pixel_scale", "camera_travel"], DEFAULT_PALETTE43), r = spec.parameters;
    p.plane_depths = ordered(r.plane_depths, "plane_depths", 3, 3);
    if (p.plane_depths[0] < 0.1) fail3("plane depth below .1");
    p.actor_route = list2(r.actor_route, "actor_route", 2, 5, (v) => point2(v, "route", 0.12, 0.88));
    p.light_position = list2(r.light_position, "light_position", 2, 2, (v) => {
      const a = point2(v, "light", -1, 1);
      if (a.y > -0.2) fail3("light must be above scene");
      return a;
    });
    p.pixel_scale = number3(Object.hasOwn(r, "pixel_scale") ? r.pixel_scale : 12, "pixel_scale", 8, 18, true);
    p.camera_travel = number3(Object.hasOwn(r, "camera_travel") ? r.camera_travel : 150, "camera_travel", 80, 200);
    p.actor_label = label3(r.actor_label, "actor label", 65, 840, 2);
    return result(ID43, p);
  }
  function sample43(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec43(spec), seconds), q = smooth3(u), snap = (v) => Math.round(v / p.pixel_scale) * p.pixel_scale, offsets = p.plane_depths.map((depth) => ({ depth, raw: -q * p.camera_travel * depth, pixels: snap(-q * p.camera_travel * depth) })), a = route(p.actor_route, q), actor = { x: snap(175 + a.x * 800 + offsets[1].raw), y: snap(700 + a.y * 620) }, light = { x: p.light_position[0].x + (p.light_position[1].x - p.light_position[0].x) * q, y: p.light_position[0].y + (p.light_position[1].y - p.light_position[0].y) * q }, occluderX = 650 + offsets[2].pixels;
    return { seconds: t, progress: u, hold, layerOrder: ["background", "actor", "foreground"], offsets, actor, light, occluderX, occluded: Math.abs(actor.x - occluderX) < 75, shadowX: snap(actor.x + (actor.x - (540 + light.x * 360)) * 0.16 / Math.abs(light.y)), shadowWidth: 90 + Math.abs(light.x) * 35 };
  }
  function render43(spec, seconds) {
    const n = validateSpec43(spec), p = n.parameters, s = sample43(n, seconds), c = p.palette, px = p.pixel_scale;
    let body = txt(p.actor_label, 90, 530, 900, 38, c.ink, 2) + rect2(90, 650, 900, 790, c.background, 0, c.muted, 3);
    body += `<defs><clipPath id="pixel-window">${rect2(92, 652, 896, 786, "white")}</clipPath></defs><g clip-path="url(#pixel-window)"><g>`;
    for (let i = 0; i < 5; i++) body += rect2(125 + i * 180 + s.offsets[0].pixels, 780 - i % 2 * 80, 126, 540 + i % 2 * 80, c.muted);
    body += `</g>`;
    body += rect2(120, 1290, 840, 20, c.ink) + `<ellipse cx="${fmt3(s.shadowX)}" cy="1320" rx="${fmt3(s.shadowWidth)}" ry="18" fill="${c.muted}"/>`;
    body += `<g transform="translate(${s.actor.x} ${s.actor.y})">${rect2(-2 * px, -7 * px, 4 * px, 3 * px, c.accent)}${rect2(-px, -4 * px, 2 * px, 3 * px, c.ink)}${rect2(-2 * px, -px, px, px, c.accent)}${rect2(px, -px, px, px, c.accent)}${rect2(-px, -6 * px, px * 0.45, px * 0.45, c.background)}${rect2(px * 0.5, -6 * px, px * 0.45, px * 0.45, c.background)}</g>`;
    body += rect2(s.occluderX - 40, 900, 80, 470, c.ink) + rect2(s.occluderX - 100, 880, 200, 70, c.accent) + `</g>` + txt("Arka / karakter / \xF6n plan: " + p.plane_depths.join(" / "), 90, 1550, 900, 34, c.ink, 2);
    return page2(ID43, p, s.seconds, body, { layout: "arcade", note: "\xD6zg\xFCn piksel geometri \xB7 2,5D vekt\xF6r yorumu" });
  }

  // renderers/template-registry/modules/bec6fd07b754-microgame-state-loop.mjs
  var bec6fd07b754_microgame_state_loop_exports = {};
  __export(bec6fd07b754_microgame_state_loop_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE44,
    ID: () => ID44,
    METADATA: () => METADATA36,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA44,
    SOURCE_ID: () => SOURCE_ID44,
    collisions: () => collisions,
    render: () => render44,
    sample: () => sample44,
    slab: () => slab,
    validateSpec: () => validateSpec44
  });
  var ID44 = "microgame-state-loop";
  var SOURCE_ID44 = "source-lemo-style-microgame";
  var DEFAULT_PALETTE44 = DARK;
  var METADATA36 = metadata("Tek turluk mikro oyun", "obstacles", "scoreboard-game", "swept collision \u2192 block/penalty \u2192 goal result \u2192 finite reset", "score first / obstacle field / result strip");
  var PARAMETER_SCHEMA44 = { obstacle_layout: { minItems: 1, maxItems: 4 }, avatar_route: { minItems: 2, maxItems: 6 }, collision_rules: { enum: ["block", "penalty"] }, goal_state: { enum: ["finish", "clean-finish"] }, avatar_radius: [0.02, 0.05], goal: { xy: [0.08, 0.92] } };
  function validateSpec44(spec) {
    const p = base3(spec, ID44, ["obstacle_layout", "avatar_route", "collision_rules", "goal_state", "goal"], ["avatar_radius"], DEFAULT_PALETTE44), r = spec.parameters;
    p.avatar_radius = number3(Object.hasOwn(r, "avatar_radius") ? r.avatar_radius : 0.03, "avatar_radius", 0.02, 0.05);
    p.collision_rules = choice3(r.collision_rules, "collision_rules", ["block", "penalty"]);
    p.goal_state = choice3(r.goal_state, "goal_state", ["finish", "clean-finish"]);
    p.goal = point2(r.goal, "goal", 0.08, 0.92);
    p.avatar_route = list2(r.avatar_route, "avatar_route", 2, 6, (v) => point2(v, "avatar point", 0.08, 0.92));
    p.obstacle_layout = list2(r.obstacle_layout, "obstacle_layout", 1, 4, (v) => {
      keys3(v, ["x", "y", "width", "height"]);
      const b = { x: number3(v.x, "obstacle x", 0.1, 0.8), y: number3(v.y, "obstacle y", 0.1, 0.8), width: number3(v.width, "obstacle width", 0.06, 0.3), height: number3(v.height, "obstacle height", 0.06, 0.3) };
      if (b.x + b.width > 0.95 || b.y + b.height > 0.95) fail3("obstacle outside play field");
      return b;
    });
    if (p.avatar_route.slice(1).some((v, i) => Math.hypot(v.x - p.avatar_route[i].x, v.y - p.avatar_route[i].y) < 0.03)) fail3("route steps too short");
    return result(ID44, p);
  }
  function slab(a, b, box3, radius) {
    let entry = 0, exit = 1;
    for (const [key, low, high] of [["x", box3.x - radius, box3.x + box3.width + radius], ["y", box3.y - radius, box3.y + box3.height + radius]]) {
      const d = b[key] - a[key];
      if (Math.abs(d) < 1e-12) {
        if (a[key] < low || a[key] > high) return null;
      } else {
        let x = (low - a[key]) / d, y = (high - a[key]) / d;
        if (x > y) [x, y] = [y, x];
        entry = Math.max(entry, x);
        exit = Math.min(exit, y);
        if (entry > exit) return null;
      }
    }
    return entry >= 0 && entry <= 1 ? entry : null;
  }
  function collisions(p) {
    const lengths = p.avatar_route.slice(1).map((b, i) => Math.hypot(b.x - p.avatar_route[i].x, b.y - p.avatar_route[i].y)), total = lengths.reduce((a, b) => a + b, 0), events = [];
    let before = 0;
    for (let i = 0; i < lengths.length; i++) {
      p.obstacle_layout.forEach((box3, index) => {
        const hit = slab(p.avatar_route[i], p.avatar_route[i + 1], box3, p.avatar_radius);
        if (hit !== null) events.push({ obstacle: index, at: (before + hit * lengths[i]) / total });
      });
      before += lengths[i];
    }
    return events.sort((a, b) => a.at - b.at || a.obstacle - b.obstacle).filter((event, i, all) => all.findIndex((e) => e.obstacle === event.obstacle) === i);
  }
  function sample44(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec44(spec), seconds), events = collisions(p), travel = clamp3(u / 0.78), first = events[0]?.at ?? 1, progress = p.collision_rules === "block" ? Math.min(travel, first) : travel, where = route(p.avatar_route, progress), hits = events.filter((e) => e.at <= progress + 1e-10), blocked = p.collision_rules === "block" && hits.length > 0, reached = !blocked && progress >= 1 && Math.hypot(where.x - p.goal.x, where.y - p.goal.y) <= 0.065, success = reached && (p.goal_state === "finish" || hits.length === 0), phase2 = u < 0.78 ? blocked ? "blocked" : "play" : u < 0.9 ? "result" : "reset", reset = u >= 0.9, avatar = reset ? { ...p.avatar_route[0] } : { x: where.x, y: where.y };
    return { seconds: t, progress: u, hold, routeProgress: progress, avatar, events, collisionCount: hits.length, score: reached ? Math.max(0, 100 - hits.length * 30) : 0, success, blocked, phase: hold ? "hold" : phase2, reset, goalReached: reached };
  }
  function render44(spec, seconds) {
    const n = validateSpec44(spec), p = n.parameters, s = sample44(n, seconds), c = p.palette;
    let body = txt("Puan " + s.score + " \xB7 \xC7arp\u0131\u015Fma " + s.collisionCount, 90, 535, 900, 44, c.ink, 1) + rect2(150, 650, 780, 780, c.background, 16, c.muted, 4);
    for (const b of p.obstacle_layout) body += rect2(150 + b.x * 780, 650 + b.y * 780, b.width * 780, b.height * 780, c.muted, 0, c.ink, 3);
    body += circle(150 + p.goal.x * 780, 650 + p.goal.y * 780, 40, "none", c.accent, 6) + circle(150 + s.avatar.x * 780, 650 + s.avatar.y * 780, p.avatar_radius * 780, c.accent, c.ink, 3);
    body += circle(144 + s.avatar.x * 780, 644 + s.avatar.y * 780, 4, c.background) + circle(156 + s.avatar.x * 780, 644 + s.avatar.y * 780, 4, c.background);
    body += txt(s.progress < 0.78 ? "Engeller ve yol ger\xE7ek oyun durumunu belirler." : s.success ? "Hedef tamamland\u0131; tur ba\u015Flang\u0131ca d\xF6nd\xFC." : "Bu tur hedef ko\u015Fulunu kar\u015F\u0131lamad\u0131.", 90, 1540, 900, 38, c.ink, 2);
    return page2(ID44, p, s.seconds, body, { layout: "arcade" });
  }

  // renderers/template-registry/modules/8c6cd87e211a-limited-pose-acting.mjs
  var c6cd87e211a_limited_pose_acting_exports = {};
  __export(c6cd87e211a_limited_pose_acting_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE45,
    ID: () => ID45,
    METADATA: () => METADATA37,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA45,
    SOURCE_ID: () => SOURCE_ID45,
    render: () => render45,
    sample: () => sample45,
    validateSpec: () => validateSpec45
  });
  var ID45 = "limited-pose-acting";
  var SOURCE_ID45 = "source-lemo-style-midcentury-toon";
  var DEFAULT_PALETTE45 = DEFAULT;
  var METADATA37 = metadata("Tutulan pozlarla oyunculuk", "poses", "theatre-poster", "held drawings \u2192 three stepped inbetweens \u2192 exact final pose", "centered stage title / large silhouette / pose annotation");
  var PARAMETER_SCHEMA45 = { pose_sequence: { minItems: 2, maxItems: 4, pose: ["rest", "point", "shrug", "wave"], labelMax: 65 }, expression_cues: { enum: ["neutral", "curious", "smile"] }, hold_frames: [2, 8], smear_length: [20, 90] };
  var POSES = { rest: { shoulder: 8, elbow: 4, hip: 0, knee: 0 }, point: { shoulder: 76, elbow: 5, hip: -10, knee: 16 }, shrug: { shoulder: 120, elbow: 85, hip: 8, knee: 8 }, wave: { shoulder: 170, elbow: 45, hip: -8, knee: 14 } };
  function validateSpec45(spec) {
    const p = base3(spec, ID45, ["pose_sequence", "expression_cues"], ["hold_frames", "smear_length"]), r = spec.parameters;
    p.pose_sequence = list2(r.pose_sequence, "pose_sequence", 2, 4, (v) => {
      keys3(v, ["pose", "label"]);
      return { pose: choice3(v.pose, "pose", ["rest", "point", "shrug", "wave"]), label: label3(v.label) };
    });
    p.expression_cues = list2(r.expression_cues, "expression_cues", p.pose_sequence.length, p.pose_sequence.length, (v) => choice3(v, "expression", ["neutral", "curious", "smile"]));
    p.hold_frames = number3(Object.hasOwn(r, "hold_frames") ? r.hold_frames : 6, "hold_frames", 2, 8, true);
    p.smear_length = number3(Object.hasOwn(r, "smear_length") ? r.smear_length : 50, "smear_length", 20, 90);
    return result(ID45, p);
  }
  function sample45(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec45(spec), seconds), span = (p.duration - 0.8) / (p.pose_sequence.length - 1), position = u * (p.pose_sequence.length - 1), index = Math.min(p.pose_sequence.length - 2, Math.floor(position)), local = clamp3(position - index), gate = Math.min(0.7, p.hold_frames / (30 * span)), q = local <= gate ? 0 : Math.min(1, Math.floor((local - gate) / (1 - gate) * 3 + 1e-9) / 3), from = POSES[p.pose_sequence[index].pose], to = POSES[p.pose_sequence[index + 1].pose], angles = Object.fromEntries(Object.keys(from).map((k) => [k, from[k] + (to[k] - from[k]) * q])), bones = rig(angles.shoulder, angles.elbow, angles.hip, angles.knee), previous = rig(from.shoulder, from.elbow, from.hip, from.knee), active = q === 1 ? index + 1 : index;
    return { seconds: t, progress: u, hold, index: active, transition: q, held: q === 0 || q === 1, angles, bones, expression: p.expression_cues[active], smear: q > 0 && q < 1 ? { x: bones.hand.x, y: bones.hand.y, dx: Math.sign(bones.hand.x - previous.hand.x) * p.smear_length, dy: Math.sign(bones.hand.y - previous.hand.y) * p.smear_length * 0.35 } : null };
  }
  function render45(spec, seconds) {
    const n = validateSpec45(spec), p = n.parameters, s = sample45(n, seconds), c = p.palette, b = s.bones;
    let actor = line3(0, 0, 0, 70, c.ink, 32) + circle(0, -48, 48, c.accent, c.ink, 4) + line3(b.armStart.x, b.armStart.y, b.armMid.x, b.armMid.y, c.ink, 15) + line3(b.armMid.x, b.armMid.y, b.hand.x, b.hand.y, c.ink, 13) + circle(b.hand.x, b.hand.y, 12, c.accent) + line3(b.legStart.x, b.legStart.y, b.legMid.x, b.legMid.y, c.ink, 17) + line3(b.legMid.x, b.legMid.y, b.foot.x, b.foot.y, c.ink, 16) + line3(-16, 70, -32, 174, c.ink, 16) + line3(b.foot.x - 9, b.foot.y, b.foot.x + 13, b.foot.y, c.ink, 10);
    actor += circle(-14, -57, 4, c.background) + circle(14, -57, 4, c.background);
    actor += s.expression === "curious" ? circle(0, -32, 6, c.background) : line3(-13, -29, 13, s.expression === "smile" ? -24 : -29, c.background, 4);
    if (s.smear) actor += line3(s.smear.x - s.smear.dx, s.smear.y - s.smear.dy, s.smear.x, s.smear.y, c.accent, 6);
    const body = rect2(110, 640, 860, 810, c.background, 34, c.muted, 2) + `<g transform="translate(490 970) scale(2.05)">${actor}</g>` + txt(p.pose_sequence[s.index].label, 540, 1530, 880, 42, c.ink, 2, "middle");
    return page2(ID45, p, s.seconds, body, { layout: "theatre" });
  }

  // renderers/template-registry/modules/ef2e8afd0528-tile-quest-state.mjs
  var ef2e8afd0528_tile_quest_state_exports = {};
  __export(ef2e8afd0528_tile_quest_state_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE46,
    ID: () => ID46,
    METADATA: () => METADATA38,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA46,
    SOURCE_ID: () => SOURCE_ID46,
    render: () => render46,
    sample: () => sample46,
    validateSpec: () => validateSpec46
  });
  var ID46 = "tile-quest-state";
  var SOURCE_ID46 = "source-lemo-style-pixel-rpg";
  var DEFAULT_PALETTE46 = DEFAULT;
  var METADATA38 = metadata("Karo g\xF6rev rotas\u0131", "tiles", "quest-board", "adjacent legal tile steps \u2192 collect key \u2192 unlock gate \u2192 destination hold", "quest heading / collision board / inventory and dialogue");
  var PARAMETER_SCHEMA46 = { tile_map: { rows: [4, 6], columns: [4, 6], symbols: ".#" }, avatar_route: { minItems: 2, maxItems: 16, integerXY: true }, quest_order: { key_at: "route index", door_at: "later route index" }, dialogue_cues: { minItems: 2, maxItems: 4, at: "route index", textMax: 95 } };
  function validateSpec46(spec) {
    const p = base3(spec, ID46, ["tile_map", "avatar_route", "quest_order", "dialogue_cues"], []), r = spec.parameters;
    p.tile_map = list2(r.tile_map, "tile_map", 4, 6, (v) => text3(v, "tile row", 6));
    const width = p.tile_map[0].length;
    if (width < 4 || p.tile_map.some((v) => v.length !== width || !/^[.#]+$/.test(v))) fail3("rectangular 4\u20136 tile map required");
    p.avatar_route = list2(r.avatar_route, "avatar_route", 2, 16, (v) => {
      keys3(v, ["x", "y"]);
      return { x: number3(v.x, "tile x", 0, width - 1, true), y: number3(v.y, "tile y", 0, p.tile_map.length - 1, true) };
    });
    if (p.avatar_route.some((v, i) => p.tile_map[v.y][v.x] === "#" || i && Math.abs(v.x - p.avatar_route[i - 1].x) + Math.abs(v.y - p.avatar_route[i - 1].y) !== 1)) fail3("route must use adjacent open tiles");
    if (new Set(p.avatar_route.map((v) => v.x + ":" + v.y)).size !== p.avatar_route.length) fail3("quest route must not revisit tiles");
    keys3(r.quest_order, ["key_at", "door_at"]);
    p.quest_order = { key_at: number3(r.quest_order.key_at, "key_at", 1, p.avatar_route.length - 2, true), door_at: number3(r.quest_order.door_at, "door_at", 2, p.avatar_route.length - 1, true) };
    if (p.quest_order.key_at >= p.quest_order.door_at) fail3("key must precede gate");
    p.dialogue_cues = list2(r.dialogue_cues, "dialogue_cues", 2, 4, (v) => {
      keys3(v, ["at", "text"]);
      return { at: number3(v.at, "dialogue at", 0, p.avatar_route.length - 1, true), text: label3(v.text, "dialogue text", 95, 900, 3) };
    });
    if (p.dialogue_cues.some((v, i) => i && v.at <= p.dialogue_cues[i - 1].at)) fail3("dialogue indices must increase");
    return result(ID46, p);
  }
  function sample46(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec46(spec), seconds), position = u * (p.avatar_route.length - 1), index = Math.min(p.avatar_route.length - 1, Math.floor(position + 1e-10)), tile = p.avatar_route[index], keyCollected = index >= p.quest_order.key_at, doorUnlocked = keyCollected && index >= p.quest_order.door_at, dialogue = p.dialogue_cues.filter((v) => v.at <= index).at(-1)?.text ?? "";
    return { seconds: t, progress: u, hold, index, tile: { ...tile }, keyCollected, doorUnlocked, goalReached: index === p.avatar_route.length - 1, dialogue };
  }
  function render46(spec, seconds) {
    const n = validateSpec46(spec), p = n.parameters, s = sample46(n, seconds), c = p.palette, cell = 720 / Math.max(p.tile_map.length, p.tile_map[0].length), ox = (1080 - cell * p.tile_map[0].length) / 2, oy = 640;
    let body = "";
    p.tile_map.forEach((row, y) => [...row].forEach((v, x) => {
      body += rect2(ox + x * cell, oy + y * cell, cell - 4, cell - 4, v === "#" ? c.ink : c.background, 0, c.muted, 2);
    }));
    const key = p.avatar_route[p.quest_order.key_at], door = p.avatar_route[p.quest_order.door_at];
    if (!s.keyCollected) body += circle(ox + (key.x + 0.5) * cell, oy + (key.y + 0.5) * cell, cell * 0.18, "none", c.accent, 8) + line3(ox + (key.x + 0.5) * cell, oy + (key.y + 0.65) * cell, ox + (key.x + 0.5) * cell, oy + (key.y + 0.85) * cell, c.accent, 8);
    body += rect2(ox + (door.x + 0.24) * cell, oy + (door.y + 0.1) * cell, cell * 0.52, cell * 0.8, s.doorUnlocked ? "none" : c.muted, 0, c.accent, 5);
    body += rect2(ox + (s.tile.x + 0.26) * cell, oy + (s.tile.y + 0.24) * cell, cell * 0.48, cell * 0.55, c.accent) + rect2(ox + (s.tile.x + 0.34) * cell, oy + (s.tile.y + 0.33) * cell, cell * 0.08, cell * 0.08, c.background) + rect2(ox + (s.tile.x + 0.58) * cell, oy + (s.tile.y + 0.33) * cell, cell * 0.08, cell * 0.08, c.background);
    body += txt(s.keyCollected ? "Anahtar \xE7antada \xB7 " + (s.doorUnlocked ? "Kap\u0131 a\xE7\u0131k" : "Kap\u0131ya ilerle") : "Anahtar\u0131 bul, sonra kap\u0131ya ula\u015F.", 90, 555, 900, 38, c.ink, 2) + txt(s.dialogue || "Yolculuk ba\u015Fl\u0131yor.", 90, 1480, 900, 38, c.ink, 3);
    return page2(ID46, p, s.seconds, body, { layout: "arcade" });
  }

  // renderers/template-registry/modules/1dcbc8bd22a1-rubber-limb-cycle.mjs
  var dcbc8bd22a1_rubber_limb_cycle_exports = {};
  __export(dcbc8bd22a1_rubber_limb_cycle_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE47,
    ID: () => ID47,
    METADATA: () => METADATA39,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA47,
    SOURCE_ID: () => SOURCE_ID47,
    render: () => render47,
    sample: () => sample47,
    validateSpec: () => validateSpec47
  });
  var ID47 = "rubber-limb-cycle";
  var SOURCE_ID47 = "source-lemo-style-rubber-hose";
  var DEFAULT_PALETTE47 = DEFAULT;
  var METADATA39 = metadata("Esnek uzuv y\xFCr\xFCy\xFC\u015F\xFC", "curved_limbs", "walking-strip", "alternating planted feet \u2192 curved swing limbs \u2192 area-preserving contact squash", "wide walk strip / oversized character / contact diagram");
  var PARAMETER_SCHEMA47 = { stride: [40, 110], limb_curvature: [0.1, 0.7], contact_cues: { length: 3, first: 0, last: 1, middle: [0.3, 0.7] }, cycles: [1, 3], squash_amount: [0.05, 0.22] };
  function validateSpec47(spec) {
    const p = base3(spec, ID47, ["stride", "limb_curvature", "contact_cues"], ["cycles", "squash_amount"]), r = spec.parameters;
    p.stride = number3(r.stride, "stride", 40, 110);
    p.limb_curvature = number3(r.limb_curvature, "limb_curvature", 0.1, 0.7);
    p.contact_cues = ordered(r.contact_cues, "contact_cues", 3, 3);
    if (p.contact_cues[0] !== 0 || p.contact_cues[2] !== 1 || p.contact_cues[1] < 0.3 || p.contact_cues[1] > 0.7) throw new RangeError("contacts must be [0, middle .3\u2013.7, 1]");
    p.cycles = number3(Object.hasOwn(r, "cycles") ? r.cycles : 2, "cycles", 1, 3, true);
    p.squash_amount = number3(Object.hasOwn(r, "squash_amount") ? r.squash_amount : 0.12, "squash_amount", 0.05, 0.22);
    return result(ID47, p);
  }
  function sample47(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec47(spec), seconds), z = u * p.cycles, k = Math.floor(z), raw = z - k, split = p.contact_cues[1], half = raw < split ? 0 : 1, q = half === 0 ? raw / split : (raw - split) / (1 - split), bodyX = 330 + (k + (half + q) / 2) * p.stride, baseX = 330 + k * p.stride, ground = 1300, left = half === 0 ? { x: baseX + p.stride / 4, y: ground, contact: true } : { x: baseX + p.stride / 4 + p.stride * q, y: ground - 62 * Math.sin(Math.PI * q), contact: false }, right = half === 1 ? { x: baseX + 3 * p.stride / 4, y: ground, contact: true } : { x: baseX - p.stride / 4 + p.stride * q, y: ground - 62 * Math.sin(Math.PI * q), contact: false }, pulse = Math.max(0, 1 - q / 0.2), scaleY = 1 - p.squash_amount * pulse, scaleX = 1 / scaleY, hip = { x: bodyX, y: 1070 }, bow = p.limb_curvature * 100;
    return { seconds: t, progress: u, hold, cycle: k, half, phase: q, bodyX, hip, left, right, scaleX, scaleY, ground, bow, armSwing: Math.sin((half + q) * Math.PI) * 48 };
  }
  function limb(hip, foot, bow, color2) {
    return `<path d="M ${fmt3(hip.x)} ${fmt3(hip.y)} C ${fmt3(hip.x + bow)} ${fmt3(hip.y + 100)} ${fmt3(foot.x - bow)} ${fmt3(foot.y - 85)} ${fmt3(foot.x)} ${fmt3(foot.y)}" fill="none" stroke="${color2}" stroke-width="20" stroke-linecap="round"/>`;
  }
  function render47(spec, seconds) {
    const n = validateSpec47(spec), p = n.parameters, s = sample47(n, seconds), c = p.palette;
    let body = line3(120, s.ground + 18, 960, s.ground + 18, c.muted, 3) + limb({ x: s.hip.x - 18, y: s.hip.y }, s.left, s.bow, c.ink) + limb({ x: s.hip.x + 18, y: s.hip.y }, s.right, -s.bow, c.ink);
    body += line3(s.left.x - 20, s.left.y, s.left.x + 24, s.left.y, c.accent, 15) + line3(s.right.x - 20, s.right.y, s.right.x + 24, s.right.y, c.accent, 15);
    body += `<g transform="translate(${fmt3(s.bodyX)} 1070) scale(${fmt3(s.scaleX)} ${fmt3(s.scaleY)})">${rect2(-56, -120, 112, 150, c.accent, 46, c.ink, 4)}${circle(0, -160, 55, c.background, c.ink, 5)}${circle(-15, -171, 6, c.ink)}${circle(15, -171, 6, c.ink)}${line3(-13, -143, 13, -143, c.ink, 4)}</g>`;
    body += `<path d="M ${fmt3(s.bodyX - 48)} 990 Q ${fmt3(s.bodyX - 110)} ${fmt3(1030 + s.armSwing)} ${fmt3(s.bodyX - 90)} 1100 M ${fmt3(s.bodyX + 48)} 990 Q ${fmt3(s.bodyX + 110)} ${fmt3(1030 - s.armSwing)} ${fmt3(s.bodyX + 90)} 1100" fill="none" stroke="${c.ink}" stroke-width="16" stroke-linecap="round"/>`;
    body += txt("Temas aya\u011F\u0131 zeminde sabit kal\u0131r; g\xF6vde onun \xFCzerinden ilerler.", 90, 1470, 900, 42, c.ink, 3) + txt("Sol " + (s.left.contact ? "temas" : "sal\u0131n\u0131m") + " \xB7 Sa\u011F " + (s.right.contact ? "temas" : "sal\u0131n\u0131m"), 90, 560, 900, 38, c.muted, 2);
    return page2(ID47, p, s.seconds, body, { layout: "workbench" });
  }

  // renderers/template-registry/modules/c770ac3b9d21-cel-pose-camera.mjs
  var c770ac3b9d21_cel_pose_camera_exports = {};
  __export(c770ac3b9d21_cel_pose_camera_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE48,
    ID: () => ID48,
    METADATA: () => METADATA40,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA48,
    SOURCE_ID: () => SOURCE_ID48,
    render: () => render48,
    sample: () => sample48,
    validateSpec: () => validateSpec48
  });
  var ID48 = "cel-pose-camera";
  var SOURCE_ID48 = "source-lemo-style-cel-anime-80s";
  var DEFAULT_PALETTE48 = DARK;
  var METADATA40 = metadata("Katmanl\u0131 sel pozu", "cel_poses", "multiplane-triptych", "frame-held cel keys / independent mouth cues / continuous depth-weighted camera push", "top title / three-plane stage / mouth cue strip");
  var PARAMETER_SCHEMA48 = { pose_order: { minItems: 2, maxItems: 4, enum: ["ready", "reach", "guard", "resolve"] }, hold_frames: [2, 8], mouth_cues: { minItems: 2, maxItems: 4, shape: ["closed", "open", "wide"] }, plane_depths: { length: 3, strictlyIncreasing: [0.1, 1] }, push: [0.04, 0.28] };
  var POSES2 = { ready: [4, 8, 0, 0], reach: [77, 6, -8, 15], guard: [135, 100, 8, 20], resolve: [-20, 28, -12, 16] };
  function validateSpec48(spec) {
    const p = base3(spec, ID48, ["pose_order", "mouth_cues", "plane_depths"], ["hold_frames", "push"], DEFAULT_PALETTE48), r = spec.parameters;
    p.pose_order = list2(r.pose_order, "pose_order", 2, 4, (v) => choice3(v, "pose", ["ready", "reach", "guard", "resolve"]));
    p.hold_frames = number3(Object.hasOwn(r, "hold_frames") ? r.hold_frames : 4, "hold_frames", 2, 8, true);
    p.push = number3(Object.hasOwn(r, "push") ? r.push : 0.16, "push", 0.04, 0.28);
    p.plane_depths = ordered(r.plane_depths, "plane_depths", 3, 3);
    if (p.plane_depths[0] < 0.1) fail3("plane depth below .1");
    p.mouth_cues = list2(r.mouth_cues, "mouth_cues", 2, 4, (v) => {
      keys3(v, ["start", "end", "shape"]);
      const a = { start: number3(v.start, "mouth start", 0, 1), end: number3(v.end, "mouth end", 0, 1), shape: choice3(v.shape, "mouth shape", ["closed", "open", "wide"]) };
      if (a.end - a.start < 0.05) fail3("mouth cue too short");
      return a;
    });
    if (p.mouth_cues.some((v, i) => i && v.start < p.mouth_cues[i - 1].end)) fail3("mouth cues overlap");
    return result(ID48, p);
  }
  function sample48(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec48(spec), seconds), frame = Math.floor(Math.min(t, p.duration - 0.8) * 30 + 1e-8), heldFrame = Math.floor(frame / p.hold_frames) * p.hold_frames, poseU = clamp3(heldFrame / (30 * (p.duration - 0.8))), index = Math.min(p.pose_order.length - 1, Math.floor(poseU * p.pose_order.length)), shape = hold ? "closed" : p.mouth_cues.find((v) => u >= v.start && u < v.end)?.shape ?? "closed", bones = rig(...POSES2[p.pose_order[index]]);
    return { seconds: t, progress: u, hold, heldFrame, index, pose: p.pose_order[index], bones, mouth: shape, zoom: 1 + p.push * u, planes: p.plane_depths.map((depth) => ({ depth, offset: -p.push * 180 * depth * u })), cameraTarget: { x: 540, y: 1080 } };
  }
  function render48(spec, seconds) {
    const n = validateSpec48(spec), p = n.parameters, s = sample48(n, seconds), c = p.palette, b = s.bones;
    let scene = "";
    for (let i = 0; i < 4; i++) scene += rect2(170 + i * 220 + s.planes[0].offset, 760, 100, 480, c.muted);
    scene += polygon2([{ x: 160 + s.planes[0].offset, y: 1120 }, { x: 480 + s.planes[0].offset, y: 800 }, { x: 840 + s.planes[0].offset, y: 1190 }], c.background, c.muted, 3);
    let actor = line3(0, 0, 0, 70, c.accent, 32) + polygon2([{ x: -42, y: -82 }, { x: 37, y: -87 }, { x: 48, y: -21 }, { x: -35, y: -15 }], c.background, c.ink, 4) + line3(b.armStart.x, b.armStart.y, b.armMid.x, b.armMid.y, c.accent, 15) + line3(b.armMid.x, b.armMid.y, b.hand.x, b.hand.y, c.accent, 14) + line3(b.legStart.x, b.legStart.y, b.legMid.x, b.legMid.y, c.ink, 17) + line3(b.legMid.x, b.legMid.y, b.foot.x, b.foot.y, c.ink, 15) + line3(-14, 70, -35, 170, c.ink, 17) + line3(-22, -56, -8, -56, c.ink, 5) + line3(12, -56, 27, -56, c.ink, 5);
    actor += s.mouth === "closed" ? line3(-7, -34, 11, -34, c.ink, 3) : rect2(-10, -37, s.mouth === "wide" ? 27 : 16, s.mouth === "wide" ? 10 : 18, c.ink, 3);
    scene += `<g transform="translate(${fmt3(530 + s.planes[1].offset)} 950) scale(1.7)">${actor}</g>` + rect2(100 + s.planes[2].offset, 1250, 1e3, 80, c.accent);
    const body = `<defs><clipPath id="cel-window">${rect2(110, 640, 860, 760, "white")}</clipPath></defs>${rect2(110, 640, 860, 760, c.background, 0, c.muted, 2)}<g clip-path="url(#cel-window)"><g transform="translate(540 1080) scale(${fmt3(s.zoom)}) translate(-540 -1080)">${scene}</g></g>` + txt("Poz " + (s.index + 1) + " \xB7 A\u011F\u0131z " + s.mouth, 90, 1510, 900, 40, c.ink, 2);
    return page2(ID48, p, s.seconds, body, { layout: "triptych" });
  }

  // renderers/template-registry/modules/7d6ed6f291f1-glass-section-orbit.mjs
  var d6ed6f291f1_glass_section_orbit_exports = {};
  __export(d6ed6f291f1_glass_section_orbit_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE49,
    ID: () => ID49,
    METADATA: () => METADATA41,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA49,
    SOURCE_ID: () => SOURCE_ID49,
    capRay: () => capRay,
    render: () => render49,
    sample: () => sample49,
    validateSpec: () => validateSpec49
  });
  var ID49 = "glass-section-orbit";
  var SOURCE_ID49 = "source-lemo-style-glass-product";
  var DEFAULT_PALETTE49 = DEFAULT;
  var METADATA41 = metadata("Saydam kabuk kesiti", "shell_section", "technical-cutaway", "bounded shell orbit / clipped wall section / one Snell interface at a marked cap normal", "technical heading / large cutaway / measured ray notes");
  var PARAMETER_SCHEMA49 = { shell_geometry: { enum: ["cylinder", "capsule"] }, outer_radius: [100, 190], height: [320, 520], wall_thickness: [8, 28], light_angles: [-70, 70], section_depth: [0.2, 0.8], orbit_degrees: [10, 65], ior: [1.1, 1.6] };
  function numericLabels3(p) {
    return txt("Duvar " + p.wall_thickness + " birim", 90, 1430, 900, 35, p.palette.ink, 1) + txt("K\u0131r\u0131lma indisi " + p.ior, 90, 1490, 900, 35, p.palette.ink, 1);
  }
  function validateSpec49(spec) {
    const p = base3(spec, ID49, ["shell_geometry", "outer_radius", "height", "wall_thickness", "light_angles", "section_depth"], ["orbit_degrees", "ior"]), r = spec.parameters;
    p.shell_geometry = choice3(r.shell_geometry, "shell_geometry", ["cylinder", "capsule"]);
    for (const [k, a, b, d] of [["outer_radius", 100, 190], ["height", 320, 520], ["wall_thickness", 8, 28], ["section_depth", 0.2, 0.8], ["orbit_degrees", 10, 65, 32], ["ior", 1.1, 1.6, 1.4]]) p[k] = number3(Object.hasOwn(r, k) ? r[k] : d, k, a, b);
    p.light_angles = pair(r.light_angles, "light_angles", -70, 70);
    if (Math.abs(p.light_angles[1] - p.light_angles[0]) < 5) fail3("light sweep must span five degrees");
    if (p.wall_thickness >= p.outer_radius * 0.3) fail3("wall must retain hollow center");
    numericLabels3(p);
    return result(ID49, p);
  }
  function capRay({ cx, top, outer, inner, incident, ior }) {
    const refracted = Math.asin(Math.sin(incident) / ior), dx = Math.sin(refracted), dy = Math.cos(refracted), entry = { x: cx, y: top - outer.ry };
    const A3 = (dx / inner.rx) ** 2 + (dy / inner.ry) ** 2, B = -2 * outer.ry * dy / inner.ry ** 2, C2 = (outer.ry / inner.ry) ** 2 - 1, discriminant = B * B - 4 * A3 * C2;
    if (discriminant <= 0) fail3("cap ray does not intersect inner boundary");
    const distance2 = (-B - Math.sqrt(discriminant)) / (2 * A3);
    if (!(distance2 > 0 && Number.isFinite(distance2))) fail3("invalid cap wall segment");
    return {
      entry,
      inside: { x: entry.x + dx * distance2, y: entry.y + dy * distance2 },
      start: { x: entry.x - Math.sin(incident) * 145, y: entry.y - Math.cos(incident) * 145 },
      inward_normal: { x: 0, y: 1 },
      inside_distance: distance2,
      surface: "outer-cap-ellipse",
      termination: "first-inner-cap-intersection",
      refracted
    };
  }
  function sample49(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec49(spec), seconds), orbit = lerp3(-p.orbit_degrees / 2, p.orbit_degrees / 2, u), incident = lerp3(...p.light_angles, u) * Math.PI / 180, flatten = 0.24 + 0.16 * Math.abs(Math.sin(orbit * Math.PI / 180)), outer = { rx: p.outer_radius, ry: p.outer_radius * flatten }, inner = { rx: p.outer_radius - p.wall_thickness, ry: (p.outer_radius - p.wall_thickness) * flatten }, cx = 420, top = 760, bottom = top + p.height, cutX = cx - p.outer_radius + 2 * p.outer_radius * p.section_depth, ray = capRay({ cx, top, outer, inner, incident, ior: p.ior });
    return { seconds: t, progress: u, hold, orbit, incident, refracted: ray.refracted, outer, inner, wallThickness: p.wall_thickness, top, bottom, cx, cutX, sectionWidth: cx + p.outer_radius - cutX, ray };
  }
  var ellipse = (x, y, rx, ry, fill, stroke, sw = 3, opacity = 1) => `<ellipse cx="${fmt3(x)}" cy="${fmt3(y)}" rx="${fmt3(rx)}" ry="${fmt3(ry)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(sw)}" fill-opacity="${fmt3(opacity)}"/>`;
  function render49(spec, seconds) {
    const n = validateSpec49(spec), p = n.parameters, s = sample49(n, seconds), c = p.palette, rx = s.outer.rx, ry = s.outer.ry, curve = p.shell_geometry === "capsule" ? rx : 12;
    let shell2 = rect2(s.cx - rx, s.top, rx * 2, p.height, c.accent, curve, c.ink, 3).replace('fill="' + c.accent + '"', 'fill="' + c.accent + '" fill-opacity="0.14"') + ellipse(s.cx, s.top, rx, ry, c.background, c.ink, 3, 0.8) + ellipse(s.cx, s.bottom, rx, ry, "none", c.ink);
    let cut = rect2(s.cx - s.inner.rx, s.top + p.wall_thickness, s.inner.rx * 2, p.height - 2 * p.wall_thickness, c.background, curve, c.accent, 3) + ellipse(s.cx, s.top, s.inner.rx, s.inner.ry, c.background, c.accent, 3) + line3(s.cutX, s.top - ry, s.cutX, s.bottom + ry, c.accent, 5);
    const body = `<defs><clipPath id="shell-section">${rect2(s.cutX, s.top - ry - 5, s.sectionWidth + 5, p.height + 2 * ry + 10, "white")}</clipPath></defs>${shell2}<g clip-path="url(#shell-section)">${cut}</g><line data-ray-normal="true" x1="${fmt3(s.ray.entry.x)}" y1="${fmt3(s.ray.entry.y - 40)}" x2="${fmt3(s.ray.entry.x)}" y2="${fmt3(s.ray.entry.y + 40)}" stroke="${c.muted}" stroke-width="2" stroke-dasharray="5 5"/>` + line3(s.ray.start.x, s.ray.start.y, s.ray.entry.x, s.ray.entry.y, c.muted, 5) + line3(s.ray.entry.x, s.ray.entry.y, s.ray.inside.x, s.ray.inside.y, c.accent, 7) + circle(s.ray.entry.x, s.ray.entry.y, 8, c.ink) + numericLabels3(p) + txt("Tek kapak aray\xFCz\xFC; \u0131\u015F\u0131n i\xE7 s\u0131n\u0131rda durur. Malzeme sim\xFClasyonu de\u011Fil.", 90, 550, 900, 32, c.muted, 2);
    return page2(ID49, p, s.seconds, body, { layout: "technical" });
  }

  // renderers/template-registry/modules/31cfd3ebc00b-toon-dialogue-blocking.mjs
  var cfd3ebc00b_toon_dialogue_blocking_exports = {};
  __export(cfd3ebc00b_toon_dialogue_blocking_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE50,
    ID: () => ID50,
    METADATA: () => METADATA42,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA50,
    SOURCE_ID: () => SOURCE_ID50,
    render: () => render50,
    sample: () => sample50,
    validateSpec: () => validateSpec50
  });
  var ID50 = "toon-dialogue-blocking";
  var SOURCE_ID50 = "source-lemo-style-scifi-toon";
  var DEFAULT_PALETTE50 = DARK;
  var METADATA42 = metadata("\u0130ki \xF6zg\xFCn karakterle diyalog", "dialogue", "two-shot-stage", "caller speaker turns / target-aware gaze / deliberate shot and pose cuts", "dialogue line / two-character stage / speaker and shot legend");
  var PARAMETER_SCHEMA50 = { speaker_turns: { minItems: 2, maxItems: 4, speaker: ["a", "b"], expression: ["curious", "calm", "amused"], lineMax: 95 }, gaze_targets: { enum: ["partner", "prop", "viewer"] }, pose_cues: { enum: ["rest", "point", "open"] }, camera_slots: { enum: ["wide", "a-close", "b-close"] } };
  function validateSpec50(spec) {
    const p = base3(spec, ID50, ["speaker_turns", "gaze_targets", "pose_cues", "camera_slots"], [], DEFAULT_PALETTE50), r = spec.parameters;
    p.speaker_turns = list2(r.speaker_turns, "speaker_turns", 2, 4, (v) => {
      keys3(v, ["speaker", "line", "expression"]);
      return { speaker: choice3(v.speaker, "speaker", ["a", "b"]), line: label3(v.line, "turn line", 95, 880, 3), expression: choice3(v.expression, "expression", ["curious", "calm", "amused"]) };
    });
    for (const [k, options] of [["gaze_targets", ["partner", "prop", "viewer"]], ["pose_cues", ["rest", "point", "open"]], ["camera_slots", ["wide", "a-close", "b-close"]]]) p[k] = list2(r[k], k, p.speaker_turns.length, p.speaker_turns.length, (v) => choice3(v, k, options));
    return result(ID50, p);
  }
  function character(id, speaker, gaze, pose2, expression) {
    const x = id === "a" ? 320 : 760, target7 = gaze === "partner" ? { x: id === "a" ? 760 : 320, y: 950 } : gaze === "prop" ? { x: 540, y: 1230 } : { x, y: 950 }, vector = { x: target7.x - x, y: target7.y - 950 }, length = Math.hypot(vector.x, vector.y), eyes = length ? { x: vector.x / length * 5, y: vector.y / length * 5 } : { x: 0, y: 0 }, angles = pose2 === "point" ? [75, 0, 0, 0] : pose2 === "open" ? [112, 55, 0, 0] : [5, 5, 0, 0];
    return { id, x, y: 1010, speaking: id === speaker, gaze, eyes, bones: rig(...angles), expression: id === speaker ? expression : "calm", pose: id === speaker ? pose2 : "rest" };
  }
  function sample50(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec50(spec), seconds), index = Math.min(p.speaker_turns.length - 1, Math.floor(u * p.speaker_turns.length)), turn = p.speaker_turns[index], slot2 = p.camera_slots[index], camera = { scale: slot2 === "wide" ? 1 : 1.45, focusX: slot2 === "a-close" ? 320 : slot2 === "b-close" ? 760 : 540 };
    return { seconds: t, progress: u, hold, index, speaker: turn.speaker, camera, characters: ["a", "b"].map((id) => character(id, turn.speaker, id === turn.speaker ? p.gaze_targets[index] : "partner", id === turn.speaker ? p.pose_cues[index] : "rest", turn.expression)), prop: { x: 540, y: 1230 } };
  }
  function drawActor(a, c) {
    const b = a.pose === "rest" ? rig(5, 5, 0, 0) : a.bones;
    let g = rect2(-35, 0, 70, 95, c.accent, 20, c.ink, 4) + line3(-17, 90, -28, 170, c.ink, 18) + line3(17, 90, 28, 170, c.ink, 18) + line3(b.armStart.x, b.armStart.y, b.armMid.x, b.armMid.y, c.ink, 14) + line3(b.armMid.x, b.armMid.y, b.hand.x, b.hand.y, c.ink, 12);
    g += a.id === "a" ? circle(0, -58, 56, c.background, c.ink, 4) : polygon2([{ x: -52, y: -82 }, { x: -26, y: -115 }, { x: 31, y: -105 }, { x: 55, y: -60 }, { x: 25, y: -12 }, { x: -32, y: -15 }], c.background, c.ink, 4);
    for (const x of [-18, 18]) g += circle(x, -65, 10, c.ink) + circle(x + a.eyes.x, -65 + a.eyes.y, 4, c.background);
    g += a.speaking ? rect2(-13, -38, a.expression === "amused" ? 32 : 24, a.expression === "curious" ? 23 : 14, c.ink, 6) : line3(-11, -31, 11, -31, c.ink, 4);
    return `<g transform="translate(${a.x} ${a.y})">${g}</g>`;
  }
  function render50(spec, seconds) {
    const n = validateSpec50(spec), p = n.parameters, s = sample50(n, seconds), c = p.palette;
    const scene = line3(120, 1320, 960, 1320, c.muted, 3) + rect2(s.prop.x - 35, s.prop.y - 35, 70, 70, c.muted, 10, c.ink, 4) + s.characters.map((a) => drawActor(a, c)).join(""), body = txt(p.speaker_turns[s.index].line, 90, 555, 900, 40, c.ink, 3) + `<defs><clipPath id="dialogue-stage">${rect2(110, 780, 860, 640, "white")}</clipPath></defs>${rect2(110, 780, 860, 640, c.background, 0, c.muted, 3)}<g clip-path="url(#dialogue-stage)"><g transform="translate(540 1100) scale(${fmt3(s.camera.scale)}) translate(${fmt3(-s.camera.focusX)} -1100)">${scene}</g></g>` + txt("Konu\u015Fan " + s.speaker.toUpperCase() + " \xB7 " + p.camera_slots[s.index], 90, 1530, 900, 38, c.muted, 2);
    return page2(ID50, p, s.seconds, body, { layout: "triptych" });
  }

  // renderers/template-registry/modules/3037afd5f557-jointed-shadow-performance.mjs
  var afd5f557_jointed_shadow_performance_exports = {};
  __export(afd5f557_jointed_shadow_performance_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE51,
    ID: () => ID51,
    METADATA: () => METADATA43,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA51,
    SOURCE_ID: () => SOURCE_ID51,
    projectShadow: () => projectShadow,
    render: () => render51,
    sample: () => sample51,
    validateSpec: () => validateSpec51
  });
  var ID51 = "jointed-shadow-performance";
  var SOURCE_ID51 = "source-lemo-style-shadow-puppet";
  var DEFAULT_PALETTE51 = DEFAULT;
  var METADATA43 = metadata("Mafsall\u0131 g\xF6lge g\xF6sterisi", "jointed_shadow", "puppet-and-screen", "joint-angle key poses \u2192 fixed-length rig \u2192 geometric point-light projection", "stage title / small puppet and enlarged shadow / distance formula");
  var PARAMETER_SCHEMA51 = { joint_cues: { minItems: 2, maxItems: 4, shoulder: [-80, 80], elbow: [0, 130], hip: [-35, 35], knee: [0, 100], labelMax: 65 }, light_distance: [400, 900], screen_distance: [1200, 1800] };
  function validateSpec51(spec) {
    const p = base3(spec, ID51, ["joint_cues", "light_distance", "screen_distance"], []), r = spec.parameters;
    p.light_distance = number3(r.light_distance, "light_distance", 400, 900);
    p.screen_distance = number3(r.screen_distance, "screen_distance", 1200, 1800);
    if (p.screen_distance <= p.light_distance + 400) fail3("screen must be at least 400 units behind puppet");
    p.joint_cues = list2(r.joint_cues, "joint_cues", 2, 4, (v) => {
      keys3(v, ["shoulder", "elbow", "hip", "knee", "label"]);
      return { shoulder: number3(v.shoulder, "shoulder", -80, 80), elbow: number3(v.elbow, "elbow", 0, 130), hip: number3(v.hip, "hip", -35, 35), knee: number3(v.knee, "knee", 0, 100), label: label3(v.label) };
    });
    return result(ID51, p);
  }
  function projectShadow(point4, light, distanceToPuppet, distanceToScreen) {
    const m = distanceToScreen / distanceToPuppet;
    return { x: light.x + (point4.x - light.x) * m, y: light.y + (point4.y - light.y) * m };
  }
  function sample51(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec51(spec), seconds), position = u * (p.joint_cues.length - 1), index = Math.min(p.joint_cues.length - 2, Math.floor(position)), q = clamp3(position - index), a = p.joint_cues[index], b = p.joint_cues[index + 1], angles = Object.fromEntries(["shoulder", "elbow", "hip", "knee"].map((k) => [k, lerp3(a[k], b[k], q)])), bones = rig(angles.shoulder, angles.elbow, angles.hip, angles.knee), light = { x: -20, y: -30 }, magnification = p.screen_distance / p.light_distance, shadow = Object.fromEntries(Object.entries(bones).map(([k, v]) => [k, projectShadow(v, light, p.light_distance, p.screen_distance)])), head = projectShadow({ x: 0, y: -48 }, light, p.light_distance, p.screen_distance);
    return { seconds: t, progress: u, hold, index: q === 1 ? index + 1 : index, angles, bones, light, magnification, shadow, head, shadowHeadRadius: 36 * magnification };
  }
  function drawRig(b, color2, joints) {
    let out = line3(b.neck.x, b.neck.y, b.pelvis.x, b.pelvis.y, color2, 24) + line3(b.armStart.x, b.armStart.y, b.armMid.x, b.armMid.y, color2, 13) + line3(b.armMid.x, b.armMid.y, b.hand.x, b.hand.y, color2, 12) + line3(b.legStart.x, b.legStart.y, b.legMid.x, b.legMid.y, color2, 16) + line3(b.legMid.x, b.legMid.y, b.foot.x, b.foot.y, color2, 14);
    if (joints) for (const v of [b.armStart, b.armMid, b.legStart, b.legMid]) out += circle(v.x, v.y, 5, joints, color2, 2);
    return out;
  }
  function render51(spec, seconds) {
    const n = validateSpec51(spec), p = n.parameters, s = sample51(n, seconds), c = p.palette;
    let body = rect2(500, 650, 500, 800, c.background, 0, c.muted, 2) + line3(145, 1450, 990, 1450, c.muted, 3);
    body += `<g transform="translate(260 1060) scale(.85)">${drawRig(s.bones, c.accent, c.background)}${circle(0, -48, 36, c.accent, c.ink, 3)}${line3(s.bones.hand.x, s.bones.hand.y, s.bones.hand.x + 18, 420, c.muted, 3)}</g>`;
    body += `<g transform="translate(725 900) scale(.5)">${drawRig(s.shadow, c.ink)}${circle(s.head.x, s.head.y, s.shadowHeadRadius, c.ink)}</g>` + circle(130, 920, 22, c.accent) + line3(155, 920, 230, 1050, c.accent, 3) + txt("\xD6l\xE7ek = ekran / \u0131\u015F\u0131k", 90, 540, 900, 42, c.ink, 2) + txt("B\xFCy\xFCtme " + fmt3(s.magnification) + "\xD7 \xB7 " + p.joint_cues[s.index].label, 90, 1540, 900, 38, c.ink, 2);
    return page2(ID51, p, s.seconds, body, { layout: "technical" });
  }

  // renderers/template-registry/modules/3a3c669409e2-projection-surface-register.mjs
  var a3c669409e2_projection_surface_register_exports = {};
  __export(a3c669409e2_projection_surface_register_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE52,
    ID: () => ID52,
    METADATA: () => METADATA44,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA52,
    SOURCE_ID: () => SOURCE_ID52,
    faces: () => faces,
    planeIntersection: () => planeIntersection,
    render: () => render52,
    sample: () => sample52,
    validateSpec: () => validateSpec52
  });
  var ID52 = "projection-surface-register";
  var SOURCE_ID52 = "source-lemo-style-white-model";
  var DEFAULT_PALETTE52 = DEFAULT;
  var METADATA44 = metadata("Y\xFCzeye kay\u0131tl\u0131 desen", "surface_projection", "registered-model-plate", "fixed world-space pattern planes / camera orbit / continuous seam registration", "technical title / three-face model / registration schematic");
  var PARAMETER_SCHEMA52 = { model_geometry: { enum: ["box", "pedestal"] }, width: [260, 400], depth: [160, 300], height: [280, 480], projection_pattern: { enum: ["bands", "crossgrid"] }, band_count: [3, 8], camera_orbit: [-35, 35], projector_pose: { yaw: [-45, 45], offset: [-60, 60] } };
  function validateSpec52(spec) {
    const p = base3(spec, ID52, ["model_geometry", "width", "depth", "height", "projection_pattern", "band_count", "camera_orbit", "projector_pose"], []), r = spec.parameters;
    p.model_geometry = choice3(r.model_geometry, "model_geometry", ["box", "pedestal"]);
    for (const [k, a, b] of [["width", 260, 400], ["depth", 160, 300], ["height", 280, 480], ["band_count", 3, 8]]) p[k] = number3(r[k], k, a, b, k === "band_count");
    p.projection_pattern = choice3(r.projection_pattern, "projection_pattern", ["bands", "crossgrid"]);
    p.camera_orbit = pair(r.camera_orbit, "camera_orbit", -35, 35);
    if (Math.abs(p.camera_orbit[1] - p.camera_orbit[0]) < 5) throw new RangeError("camera orbit must span five degrees");
    keys3(r.projector_pose, ["yaw", "offset"]);
    p.projector_pose = { yaw: number3(r.projector_pose.yaw, "projector yaw", -45, 45), offset: number3(r.projector_pose.offset, "projector offset", -60, 60) };
    return result(ID52, p);
  }
  function faces(w, d, h, y = 0) {
    const v = (x, dy, z) => ({ x, y: y + dy, z });
    return [{ name: "front", vertices: [v(-w / 2, 0, d / 2), v(w / 2, 0, d / 2), v(w / 2, h, d / 2), v(-w / 2, h, d / 2)] }, { name: "side", vertices: [v(w / 2, 0, d / 2), v(w / 2, 0, -d / 2), v(w / 2, h, -d / 2), v(w / 2, h, d / 2)] }, { name: "top", vertices: [v(-w / 2, h, d / 2), v(w / 2, h, d / 2), v(w / 2, h, -d / 2), v(-w / 2, h, -d / 2)] }];
  }
  function planeIntersection(vertices, value, threshold) {
    const hits = [];
    for (let i = 0; i < vertices.length; i++) {
      const a = vertices[i], b = vertices[(i + 1) % vertices.length], av = value(a) - threshold, bv = value(b) - threshold;
      if (Math.abs(av) < 1e-9) hits.push({ ...a });
      if (av * bv < 0) {
        const q = av / (av - bv);
        hits.push({ x: lerp3(a.x, b.x, q), y: lerp3(a.y, b.y, q), z: lerp3(a.z, b.z, q) });
      }
    }
    const unique = hits.filter((v, i) => hits.findIndex((w) => Math.hypot(v.x - w.x, v.y - w.y, v.z - w.z) < 1e-8) === i);
    return unique.length >= 2 ? [unique[0], unique.at(-1)] : null;
  }
  function sample52(spec, seconds) {
    const { p, t, u, hold } = context(validateSpec52(spec), seconds), angle = lerp3(...p.camera_orbit, u), a = p.projector_pose.yaw * Math.PI / 180, scalar = (v) => v.x * Math.cos(a) + v.z * Math.sin(a), shape = p.model_geometry === "box" ? faces(p.width, p.depth, p.height) : [...faces(p.width, p.depth, 95).map((f) => ({ ...f, name: f.name + "-base" })), ...faces(p.width * 0.62, p.depth * 0.62, p.height - 95, 95).map((f) => ({ ...f, name: f.name + "-upper" }))], lines = [];
    for (let i = 1; i < p.band_count; i++) {
      const threshold = -p.width / 2 + i * p.width / p.band_count + p.projector_pose.offset;
      for (const f of shape) {
        const world = planeIntersection(f.vertices, scalar, threshold);
        if (world) lines.push({ face: f.name, axis: "projector", index: i, world, screen: world.map((v) => project2(v, angle)) });
      }
      if (p.projection_pattern === "crossgrid") for (const f of shape) {
        const world = planeIntersection(f.vertices, (v) => v.y, p.height * i / p.band_count);
        if (world) lines.push({ face: f.name, axis: "height", index: i, world, screen: world.map((v) => project2(v, angle)) });
      }
    }
    return { seconds: t, progress: u, hold, angle, faces: shape.map((f) => ({ ...f, screen: f.vertices.map((v) => project2(v, angle)) })), lines, seam: project2({ x: p.width / 2, y: p.height / 2, z: p.depth / 2 }, angle) };
  }
  function render52(spec, seconds) {
    const n = validateSpec52(spec), p = n.parameters, s = sample52(n, seconds), c = p.palette;
    let body = "";
    for (const f of s.faces) {
      body += polygon2(f.screen, c.background, c.ink, 4);
      for (const v of s.lines.filter((v2) => v2.face === f.name)) body += line3(v.screen[0].x, v.screen[0].y, v.screen[1].x, v.screen[1].y, c.accent, 5);
    }
    body += line3(s.seam.x, s.seam.y, 715, 1260, c.muted, 2) + txt("Ortak kenarda tek koordinat", 715, 1290, 275, 30, c.muted, 2) + txt("Desen modelde sabit; kamera y\xF6r\xFCngede ilerler.", 90, 1470, 900, 40, c.ink, 3) + txt("Y\xFCzey say\u0131s\u0131 " + s.faces.length + " \xB7 Kesit \xE7izgisi " + s.lines.length, 90, 555, 900, 36, c.muted, 2);
    return page2(ID52, p, s.seconds, body, { layout: "technical" });
  }

  // renderers/template-registry/modules/660a0c81c9b3-pointcloud-sweep-measure.mjs
  var a0c81c9b3_pointcloud_sweep_measure_exports = {};
  __export(a0c81c9b3_pointcloud_sweep_measure_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE53,
    ID: () => ID53,
    METADATA: () => METADATA45,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA53,
    SOURCE_ID: () => SOURCE_ID53,
    render: () => render53,
    sample: () => sample53,
    validateSpec: () => validateSpec53
  });

  // renderers/template-registry/modules/45ccdb518726-common.mjs
  var HOLD_SECONDS = 0.8;
  var radians = (degrees) => degrees * Math.PI / 180;
  function array(value, name, min, max) {
    if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype || value.length < min || value.length > max) fail2(`${name}: ${min}\u2013${max} dense items required`);
    const expected = ["length", ...Array.from({ length: value.length }, (_, i) => String(i))];
    if (Reflect.ownKeys(value).some((k) => typeof k !== "string" || !expected.includes(k)) || expected.some((k) => !Object.hasOwn(value, k))) fail2(`${name}: dense data only`);
    for (let i = 0; i < value.length; i++) if (!Object.hasOwn(Object.getOwnPropertyDescriptor(value, String(i)), "value")) fail2(`${name}: accessors refused`);
    return value;
  }
  function preflightCueInput(spec) {
    if (!spec || typeof spec !== "object" || Array.isArray(spec)) fail2("spec: plain data required");
    const parameters2 = Object.getOwnPropertyDescriptor(spec, "parameters");
    if (!parameters2 || !parameters2.enumerable || !Object.hasOwn(parameters2, "value")) fail2("parameters: enumerable data required");
    const raw = parameters2.value;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) fail2("parameters: plain data required");
    const cues = Object.getOwnPropertyDescriptor(raw, "cues");
    if (!cues || !cues.enumerable || !Object.hasOwn(cues, "value")) fail2("cues: enumerable data required");
    validateCueArray2(cues.value);
  }
  function base4(spec, id, required, optional, colors2) {
    preflightCueInput(spec);
    const p = validateBase2(spec, id, required, optional, colors2);
    fitText2(p.title, { width: 900, maximum: 58, minimum: 40, maxLines: 3 });
    return p;
  }
  var normalized = (id, p) => ({ id, version: VERSION2, parameters: p });
  function clock2(seconds, duration) {
    const time2 = sampleTime2(seconds, duration);
    return { seconds: time2, u: clamp2(time2 / (duration - HOLD_SECONDS)) };
  }
  function project3(point4, { yaw = 25, elevation = 28, scale = 70, cx = 540, cy = 1070 } = {}) {
    const a = radians(yaw), e = radians(elevation), x = point4.x * Math.cos(a) - point4.y * Math.sin(a), y = point4.x * Math.sin(a) + point4.y * Math.cos(a);
    return { x: cx + scale * x, y: cy + scale * (y * Math.sin(e) - point4.z * Math.cos(e)) };
  }
  function length3(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
  }
  function bounds2(points) {
    return { minX: Math.min(...points.map((p) => p.x)), maxX: Math.max(...points.map((p) => p.x)), minY: Math.min(...points.map((p) => p.y)), maxY: Math.max(...points.map((p) => p.y)) };
  }
  function path4(points, close = true) {
    return points.map((p, i) => `${i ? "L" : "M"}${fmt2(p.x)} ${fmt2(p.y)}`).join("") + (close ? "Z" : "");
  }
  function rotate2(point4, angle, cx = 0, cy = 0) {
    const a = radians(angle);
    return { x: cx + point4.x * Math.cos(a) - point4.y * Math.sin(a), y: cy + point4.x * Math.sin(a) + point4.y * Math.cos(a) };
  }
  function svg(id, p, seconds, body) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" role="img" aria-label="${esc2(p.title)}" data-renderer="${id}" data-seconds="${fmt2(seconds)}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="Schibsted, sans-serif">${body}</g></svg>`;
  }
  function caption(p, seconds) {
    const cue = activeCue2(p.cues, seconds);
    return cue ? svgText2(cue.text, { x: 90, y: 1710, width: 900, maximum: 42, minimum: 30, maxLines: 3, fill: p.palette.ink }) : "";
  }
  function line4(a, b, color2, width = 2, extra = "") {
    return `<path d="M${fmt2(a.x)} ${fmt2(a.y)}L${fmt2(b.x)} ${fmt2(b.y)}" fill="none" stroke="${color2}" stroke-width="${fmt2(width)}" ${extra}/>`;
  }
  var commonMetadata = (name, kind, layout, motion, hierarchy) => Object.freeze({ name, kind, layout_id: layout, motion_grammar: motion, typographic_hierarchy: hierarchy, original_implementation: true, native_verified: false, independent_accepted: false, scope: "Original bounded analytic vectors; no source code, assets or photoreal/physical simulation parity." });

  // renderers/template-registry/modules/660a0c81c9b3-pointcloud-sweep-measure.mjs
  var ID53 = "pointcloud-sweep-measure";
  var SOURCE_ID53 = "source-lemo-style-lidar-survey";
  var DEFAULT_PALETTE53 = Object.freeze({ background: "#EFF3F7", ink: "#1F3043", muted: "#52647A", accent: "#254F6D" });
  var PARAMETER_SCHEMA53 = Object.freeze({ columns: { minimum: 6, maximum: 14, type: "integer" }, rows: { minimum: 4, maximum: 10, type: "integer" }, span_x: { minimum: 4, maximum: 9 }, span_y: { minimum: 3, maximum: 6 }, ridge_height: { minimum: 0.4, maximum: 3 }, yaw_degrees: { minimum: -35, maximum: 35 }, measurement_pair: { type: "array", minItems: 2, maxItems: 2 }, survey_label: { type: "string", maxLength: 45 } });
  var METADATA45 = commonMetadata("Nokta bulutunda tarama ve \xF6l\xE7\xFCm", "survey", "survey-axis-report", "Clipped scanning plane \u2192 monotone point reveal \u2192 registered 3D measurement", ["58px left title", "64px measured distance", "34px survey label", "30\u201342px cue"]);
  function validateSpec53(spec) {
    const p = base4(spec, ID53, ["columns", "rows", "span_x", "span_y", "ridge_height", "yaw_degrees", "measurement_pair", "survey_label"], [], DEFAULT_PALETTE53), r = spec.parameters;
    p.columns = number2(r.columns, "columns", 6, 14, true);
    p.rows = number2(r.rows, "rows", 4, 10, true);
    p.span_x = number2(r.span_x, "span_x", 4, 9);
    p.span_y = number2(r.span_y, "span_y", 3, 6);
    p.ridge_height = number2(r.ridge_height, "ridge_height", 0.4, 3);
    p.yaw_degrees = number2(r.yaw_degrees, "yaw_degrees", -35, 35);
    array(r.measurement_pair, "measurement_pair", 2, 2);
    p.measurement_pair = [number2(r.measurement_pair[0], "first index", 0, p.columns * p.rows - 1, true), number2(r.measurement_pair[1], "second index", 0, p.columns * p.rows - 1, true)];
    if (p.measurement_pair[0] === p.measurement_pair[1]) fail2("measurement_pair: distinct points required");
    p.survey_label = text2(r.survey_label, "survey_label", 45);
    fitText2(p.survey_label, { width: 680, maximum: 36, minimum: 30, maxLines: 2 });
    return normalized(ID53, p);
  }
  function state42(p, seconds) {
    const c = clock2(seconds, p.duration), scan = -p.span_x / 2 + p.span_x * smooth2(c.u / 0.76), points = [];
    for (let row = 0; row < p.rows; row++) for (let column = 0; column < p.columns; column++) {
      const x = -p.span_x / 2 + column * p.span_x / (p.columns - 1), y = -p.span_y / 2 + row * p.span_y / (p.rows - 1), z = p.ridge_height * (0.18 + 0.82 * (1 - (2 * x / p.span_x) ** 2)) * (0.85 + 0.15 * Math.cos(Math.PI * y / p.span_y)), world = { x, y, z };
      points.push({ index: points.length, world, screen: project3(world, { yaw: p.yaw_degrees, scale: 66, cy: 1120 }), visible: x <= scan + 1e-9 });
    }
    const a = points[p.measurement_pair[0]], b = points[p.measurement_pair[1]], measurement = { a: a.screen, b: b.screen, distance: length3(a.world, b.world), opacity: smooth2((c.u - 0.76) / 0.24) };
    const plane = [{ x: scan, y: -p.span_y / 2, z: 0 }, { x: scan, y: p.span_y / 2, z: 0 }, { x: scan, y: p.span_y / 2, z: p.ridge_height + 0.4 }, { x: scan, y: -p.span_y / 2, z: p.ridge_height + 0.4 }].map((q) => project3(q, { yaw: p.yaw_degrees, scale: 66, cy: 1120 }));
    return { ...c, points, scan, plane, measurement, visible_count: points.filter((q) => q.visible).length, bounds: bounds2([...points.map((q) => q.screen), ...plane]) };
  }
  function sample53(spec, seconds) {
    return state42(validateSpec53(spec).parameters, seconds);
  }
  function render53(spec, seconds) {
    const p = validateSpec53(spec).parameters, s = state42(p, seconds), c = p.palette;
    const dots = s.points.map((q) => `<circle cx="${fmt2(q.screen.x)}" cy="${fmt2(q.screen.y)}" r="${q.visible ? 4.8 : 2}" fill="${q.visible ? c.accent : c.muted}" opacity="${q.visible ? 1 : 0.18}"/>`).join("");
    const axes = [{ x: -p.span_x / 2, y: -p.span_y / 2, z: 0 }, { x: p.span_x / 2, y: -p.span_y / 2, z: 0 }, { x: p.span_x / 2, y: p.span_y / 2, z: 0 }].map((q) => project3(q, { yaw: p.yaw_degrees, scale: 66, cy: 1120 }));
    return svg(ID53, p, s.seconds, `${svgText2(p.title, { y: 165, maximum: 58, minimum: 40, maxLines: 3, fill: c.ink })}${svgText2(p.survey_label, { y: 520, width: 680, maximum: 36, minimum: 30, maxLines: 2, fill: c.muted })}<path d="${path4(axes, false)}" fill="none" stroke="${c.muted}" stroke-width="2"/><path d="${path4(s.plane)}" fill="${c.accent}" fill-opacity="0.08" stroke="${c.accent}" stroke-width="2"/>${dots}<g opacity="${fmt2(s.measurement.opacity)}">${line4(s.measurement.a, s.measurement.b, c.ink, 4)}<circle cx="${fmt2(s.measurement.a.x)}" cy="${fmt2(s.measurement.a.y)}" r="10" fill="none" stroke="${c.ink}" stroke-width="3"/><circle cx="${fmt2(s.measurement.b.x)}" cy="${fmt2(s.measurement.b.y)}" r="10" fill="none" stroke="${c.ink}" stroke-width="3"/></g>${svgText2(`${s.measurement.distance.toFixed(2)} birim`, { x: 90, y: 1495, width: 750, maximum: 64, minimum: 48, maxLines: 1, fill: c.ink })}${svgText2(`${s.visible_count} / ${s.points.length} nokta`, { x: 90, y: 1580, width: 750, maximum: 34, minimum: 30, maxLines: 1, fill: c.muted })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/ddc290dca210-facet-terrain-growth.mjs
  var ddc290dca210_facet_terrain_growth_exports = {};
  __export(ddc290dca210_facet_terrain_growth_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE54,
    ID: () => ID54,
    METADATA: () => METADATA46,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA54,
    SOURCE_ID: () => SOURCE_ID54,
    clipWater: () => clipWater,
    render: () => render54,
    sample: () => sample54,
    validateSpec: () => validateSpec54
  });

  // renderers/template-registry/modules/dcc333ed3b6d-camera-geometry.mjs
  var rad = (v) => v * Math.PI / 180;
  var EPS = 1e-8;
  function cameraCoordinates(p, yaw, elevation = 28) {
    const a = rad(yaw), e = rad(elevation), side = p.x * Math.cos(a) - p.y * Math.sin(a), along2 = p.x * Math.sin(a) + p.y * Math.cos(a);
    return { x: side, y: along2 * Math.sin(e) - p.z * Math.cos(e), depth: along2 * Math.cos(e) + p.z * Math.sin(e) };
  }
  function cameraTowardViewer(yaw, elevation = 28) {
    const a = rad(yaw), e = rad(elevation);
    return { x: Math.sin(a) * Math.cos(e), y: Math.cos(a) * Math.cos(e), z: Math.sin(e) };
  }
  var BOX_FACES = [
    { key: "x-negative", indices: [0, 4, 7, 3], normal: { x: -1, y: 0, z: 0 }, shade: 30 },
    { key: "x-positive", indices: [1, 2, 6, 5], normal: { x: 1, y: 0, z: 0 }, shade: 30 },
    { key: "y-negative", indices: [0, 1, 5, 4], normal: { x: 0, y: -1, z: 0 }, shade: 0 },
    { key: "y-positive", indices: [3, 7, 6, 2], normal: { x: 0, y: 1, z: 0 }, shade: 0 },
    { key: "top", indices: [4, 5, 6, 7], normal: { x: 0, y: 0, z: 1 }, shade: 0 },
    { key: "bottom", indices: [0, 3, 2, 1], normal: { x: 0, y: 0, z: -1 }, shade: 0 }
  ];
  function visibleBoxFaces(vertices, yaw, elevation = 28) {
    const v = cameraTowardViewer(yaw, elevation);
    return BOX_FACES.filter((f) => f.normal.x * v.x + f.normal.y * v.y + f.normal.z * v.z > EPS).map((f) => ({
      ...f,
      indices: [...f.indices],
      normal: { ...f.normal },
      depth: f.indices.reduce((s, k) => s + cameraCoordinates(vertices[k], yaw, elevation).depth, 0) / 4
    })).sort((a, b) => a.depth - b.depth || a.key.localeCompare(b.key));
  }
  var cross2 = (a, b, p) => (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
  var polygonArea = (points) => points.reduce((s, a, i) => {
    const b = points[(i + 1) % points.length];
    return s + a.x * b.y - b.x * a.y;
  }, 0) / 2;
  function overlapPolygon(first, second) {
    const sign = Math.sign(polygonArea(second));
    if (!sign) return [];
    let output = first.map((p) => ({ ...p }));
    for (let i = 0; i < second.length && output.length; i++) {
      const a = second[i], b = second[(i + 1) % second.length], input = output;
      output = [];
      for (let j = 0; j < input.length; j++) {
        const p = input[j], q = input[(j + 1) % input.length], dp = sign * cross2(a, b, p), dq = sign * cross2(a, b, q), pin = dp >= -EPS, qin = dq >= -EPS;
        if (pin) output.push(p);
        if (pin !== qin) {
          const t = dp / (dp - dq);
          output.push({ x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t });
        }
      }
    }
    return output;
  }
  function facetDepthAt(facet, point4, yaw, elevation = 28) {
    const p = facet.screen;
    for (let i = 1; i < p.length - 1; i++) {
      const a = p[0], b = p[i], c = p[i + 1], area2 = cross2(a, b, c);
      if (Math.abs(area2) < EPS) continue;
      const u = cross2(point4, b, c) / area2, v = cross2(a, point4, c) / area2, w = 1 - u - v;
      return u * cameraCoordinates(facet.land[0], yaw, elevation).depth + v * cameraCoordinates(facet.land[i], yaw, elevation).depth + w * cameraCoordinates(facet.land[i + 1], yaw, elevation).depth;
    }
    return null;
  }
  function orderTerrainFacets(facets, yaw, elevation = 28) {
    const visible = facets.filter((f) => f.land.length >= 3), edges = visible.map(() => /* @__PURE__ */ new Set()), incoming = visible.map(() => 0);
    const depth = (f) => f.land.reduce((s, p) => s + cameraCoordinates(p, yaw, elevation).depth, 0) / f.land.length;
    for (let i = 0; i < visible.length; i++) for (let j = i + 1; j < visible.length; j++) {
      const a = visible[i], b = visible[j], overlap2 = overlapPolygon(a.screen, b.screen);
      if (overlap2.length < 3 || Math.abs(polygonArea(overlap2)) < 1e-5) continue;
      const deltas = overlap2.map((p) => {
        const x = facetDepthAt(a, p, yaw, elevation), y = facetDepthAt(b, p, yaw, elevation);
        return x === null || y === null ? 0 : x - y;
      });
      const positive = deltas.some((d) => d > EPS), negative = deltas.some((d) => d < -EPS);
      if (positive && negative) throw RangeError("TERRAIN_DEPTH_CROSSING: intersecting opaque facets need explicit splitting");
      const far = positive ? j : negative ? i : null, near = positive ? i : j;
      if (far !== null && !edges[far].has(near)) {
        edges[far].add(near);
        incoming[near]++;
      }
    }
    const ready = visible.map((f, i) => i).filter((i) => incoming[i] === 0), result2 = [], compare = (i, j) => depth(visible[i]) - depth(visible[j]) || visible[i].index - visible[j].index;
    while (ready.length) {
      ready.sort(compare);
      const i = ready.shift();
      result2.push(visible[i]);
      for (const j of edges[i]) if (--incoming[j] === 0) ready.push(j);
    }
    if (result2.length !== visible.length) throw RangeError("TERRAIN_DEPTH_CYCLE: unresolved opaque ordering");
    return result2;
  }

  // renderers/template-registry/modules/ddc290dca210-facet-terrain-growth.mjs
  var ID54 = "facet-terrain-growth";
  var SOURCE_ID54 = "source-lemo-style-lowpoly-island";
  var DEFAULT_PALETTE54 = Object.freeze({ background: "#F1F5EE", ink: "#203835", muted: "#51625B", accent: "#7D3E31" });
  var PARAMETER_SCHEMA54 = Object.freeze({ grid_size: { type: "integer", minimum: 4, maximum: 8 }, peak_height: { minimum: 1, maximum: 3.5 }, water_level: { minimum: 0, maximum: 1.2 }, ridge_bias: { minimum: -0.4, maximum: 0.4 }, yaw_degrees: { minimum: -35, maximum: 35 }, site_label: { type: "string", maxLength: 45 } });
  var METADATA46 = commonMetadata("Su d\xFCzleminden y\xFCkselen facet arazi", "terrain", "terrain-atlas-bottom-title", "Shared-vertex height-field rise with exact water-plane clipping", ["40px upper metric rail", "58px bottom headline", "34px site descriptor", "30\u201342px cue"]);
  function validateSpec54(spec) {
    const p = base4(spec, ID54, ["grid_size", "peak_height", "water_level", "ridge_bias", "yaw_degrees", "site_label"], [], DEFAULT_PALETTE54), r = spec.parameters;
    p.grid_size = number2(r.grid_size, "grid_size", 4, 8, true);
    p.peak_height = number2(r.peak_height, "peak_height", 1, 3.5);
    p.water_level = number2(r.water_level, "water_level", 0, 1.2);
    p.ridge_bias = number2(r.ridge_bias, "ridge_bias", -0.4, 0.4);
    p.yaw_degrees = number2(r.yaw_degrees, "yaw_degrees", -35, 35);
    p.site_label = text2(r.site_label, "site_label", 45);
    fitText2(p.site_label, { width: 800, maximum: 36, minimum: 30, maxLines: 2 });
    return normalized(ID54, p);
  }
  function clipWater(points, water) {
    const result2 = [];
    for (let i = 0; i < points.length; i++) {
      const a = points[i], b = points[(i + 1) % points.length], ain = a.z >= water, bin = b.z >= water;
      if (ain) result2.push({ ...a });
      if (ain !== bin) {
        const f = (water - a.z) / (b.z - a.z);
        result2.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, z: water });
      }
    }
    return result2;
  }
  function state43(p, seconds) {
    const c = clock2(seconds, p.duration), growth = smooth2(c.u / 0.88), n = p.grid_size, vertices = [], facets = [];
    for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
      const x = -3 + 6 * i / n, y = -3 + 6 * j / n, r2 = ((x - p.ridge_bias) / 3) ** 2 + (y / 3) ** 2, height = p.peak_height * Math.max(0, 1 - r2) * (0.8 + 0.2 * Math.cos(y));
      vertices.push({ x, y, z: height * growth, target_z: height });
    }
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const a = j * (n + 1) + i, b = a + 1, d = a + n + 1, e = d + 1;
      for (const indices of [[a, b, e], [a, e, d]]) {
        const world = indices.map((k) => vertices[k]), land = clipWater(world, p.water_level);
        facets.push({ indices, world, land, screen: land.map((q) => project3(q, { yaw: p.yaw_degrees, scale: 85, cy: 1060 })), average_z: world.reduce((sum, q) => sum + q.z, 0) / 3 });
      }
    }
    const water = [{ x: -3.6, y: -3.6, z: p.water_level }, { x: 3.6, y: -3.6, z: p.water_level }, { x: 3.6, y: 3.6, z: p.water_level }, { x: -3.6, y: 3.6, z: p.water_level }].map((q) => project3(q, { yaw: p.yaw_degrees, scale: 85, cy: 1060 }));
    return { ...c, growth, vertices, facets, water, max_height: Math.max(...vertices.map((q) => q.z)), bounds: bounds2([...vertices.map((q) => project3(q, { yaw: p.yaw_degrees, scale: 85, cy: 1060 })), ...water]) };
  }
  function sample54(spec, seconds) {
    return state43(validateSpec54(spec).parameters, seconds);
  }
  function render54(spec, seconds) {
    const p = validateSpec54(spec).parameters, s = state43(p, seconds), c = p.palette;
    const facets = orderTerrainFacets(s.facets.map((f, index) => ({ ...f, index })), p.yaw_degrees).map((f) => `<path data-terrain-facet="${f.index}" d="${path4(f.screen)}" fill="${f.index % 3 ? c.accent : c.ink}" fill-opacity="${fmt2(0.28 + 0.55 * f.average_z / p.peak_height)}" stroke="${c.ink}" stroke-width="1.2" stroke-opacity="0.65"/>`).join("");
    return svg(ID54, p, s.seconds, `${svgText2(p.site_label, { x: 90, y: 155, width: 850, maximum: 36, minimum: 30, maxLines: 2, fill: c.muted })}${svgText2(`SU ${p.water_level.toFixed(1)}`, { x: 90, y: 335, width: 390, maximum: 40, minimum: 32, maxLines: 1, fill: c.ink })}${svgText2(`TEPE ${s.max_height.toFixed(1)}`, { x: 580, y: 335, width: 390, maximum: 40, minimum: 32, maxLines: 1, fill: c.ink })}<path d="${path4(s.water)}" fill="${c.muted}" fill-opacity="0.15" stroke="${c.muted}" stroke-width="2"/>${facets}${svgText2(p.title, { x: 90, y: 1450, width: 900, maximum: 58, minimum: 40, maxLines: 3, fill: c.ink })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/d86824fe5c34-cell-focus-section.mjs
  var d86824fe5c34_cell_focus_section_exports = {};
  __export(d86824fe5c34_cell_focus_section_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE55,
    ID: () => ID55,
    METADATA: () => METADATA47,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA55,
    SOURCE_ID: () => SOURCE_ID55,
    render: () => render55,
    sample: () => sample55,
    validateSpec: () => validateSpec55
  });
  var ID55 = "cell-focus-section";
  var SOURCE_ID55 = "source-lemo-style-microscope";
  var DEFAULT_PALETTE55 = Object.freeze({ background: "#F3F3E9", ink: "#263E31", muted: "#526450", accent: "#8A3E4D" });
  var PARAMETER_SCHEMA55 = Object.freeze({ cell_count: { type: "integer", minimum: 3, maximum: 7 }, cell_radius: { minimum: 48, maximum: 72 }, optical_radius: { minimum: 0.7, maximum: 1.2 }, focus_depth: { minimum: -0.65, maximum: 0.65 }, focus_band: { minimum: 0.2, maximum: 0.6 }, transport_fraction: { minimum: 0.2, maximum: 0.8 }, sample_label: { type: "string", maxLength: 45 } });
  var METADATA47 = commonMetadata("Fokal d\xFCzlemde \xF6zg\xFCn h\xFCcre kesiti", "optical-section", "circular-optical-field", "Analytic sphere section \u2192 focus weighting \u2192 bounded radial transport", ["58px centered title", "36px sample label", "44px focus/area measures", "30\u201342px cue"]);
  function validateSpec55(spec) {
    const p = base4(spec, ID55, ["cell_count", "cell_radius", "optical_radius", "focus_depth", "focus_band", "transport_fraction", "sample_label"], [], DEFAULT_PALETTE55), r = spec.parameters;
    p.cell_count = number2(r.cell_count, "cell_count", 3, 7, true);
    p.cell_radius = number2(r.cell_radius, "cell_radius", 48, 72);
    p.optical_radius = number2(r.optical_radius, "optical_radius", 0.7, 1.2);
    p.focus_depth = number2(r.focus_depth, "focus_depth", -0.65, 0.65);
    p.focus_band = number2(r.focus_band, "focus_band", 0.2, 0.6);
    p.transport_fraction = number2(r.transport_fraction, "transport_fraction", 0.2, 0.8);
    p.sample_label = text2(r.sample_label, "sample_label", 45);
    fitText2(p.sample_label, { width: 800, maximum: 36, minimum: 30, maxLines: 2 });
    return normalized(ID55, p);
  }
  function state44(p, seconds) {
    const c = clock2(seconds, p.duration), focus = lerp2(-1.5, p.focus_depth, smooth2(c.u / 0.65)), transport = smooth2((c.u - 0.4) / 0.6), cells = [];
    for (let i = 0; i < p.cell_count; i++) {
      const angle = 2 * Math.PI * i / p.cell_count - 0.6, cx = 540 + 185 * Math.cos(angle), cy = 1010 + 185 * Math.sin(angle), z = -0.6 + 1.2 * i / (p.cell_count - 1), delta = focus - z, section = Math.sqrt(Math.max(0, p.optical_radius ** 2 - delta ** 2)), sharpness = Math.exp(-((delta / p.focus_band) ** 2)), radius = p.cell_radius * section / p.optical_radius, carrierRadius = p.cell_radius * (0.92 - p.transport_fraction * transport);
      cells.push({ index: i, cx, cy, z, delta, section_radius: section, section_area: Math.PI * section ** 2, radius, membrane_radius: p.cell_radius, sharpness, carrier: { x: cx + carrierRadius * Math.cos(angle + 0.7), y: cy + carrierRadius * Math.sin(angle + 0.7) }, carrier_radius: carrierRadius });
    }
    return { ...c, focus, transport, cells, section_area: cells.reduce((sum, q) => sum + q.section_area, 0) };
  }
  function sample55(spec, seconds) {
    return state44(validateSpec55(spec).parameters, seconds);
  }
  function render55(spec, seconds) {
    const p = validateSpec55(spec).parameters, s = state44(p, seconds), c = p.palette;
    const cells = s.cells.map((q) => `<circle cx="${fmt2(q.cx)}" cy="${fmt2(q.cy)}" r="${fmt2(q.membrane_radius)}" fill="none" stroke="${c.muted}" stroke-width="2" stroke-dasharray="5 7"/><circle cx="${fmt2(q.cx)}" cy="${fmt2(q.cy)}" r="${fmt2(q.radius)}" fill="${c.accent}" fill-opacity="${fmt2(0.15 + 0.55 * q.sharpness)}" stroke="${c.ink}" stroke-width="3"/><circle cx="${fmt2(q.cx)}" cy="${fmt2(q.cy)}" r="${fmt2(q.radius * 0.28)}" fill="${c.ink}" opacity="${fmt2(0.3 + 0.7 * q.sharpness)}"/><circle cx="${fmt2(q.carrier.x)}" cy="${fmt2(q.carrier.y)}" r="7" fill="${c.ink}"/>`).join("");
    return svg(ID55, p, s.seconds, `${svgText2(p.title, { x: 540, y: 165, width: 900, maximum: 58, minimum: 40, maxLines: 3, anchor: "middle", fill: c.ink })}${svgText2(p.sample_label, { x: 540, y: 500, width: 800, maximum: 36, minimum: 30, maxLines: 2, anchor: "middle", fill: c.muted })}<defs><clipPath id="g04-optical-field"><circle cx="540" cy="1010" r="332"/></clipPath></defs><circle cx="540" cy="1010" r="342" fill="none" stroke="${c.ink}" stroke-width="5"/><g clip-path="url(#g04-optical-field)">${cells}<path d="M210 ${fmt2(1010 + s.focus * 135)}H870" fill="none" stroke="${c.accent}" stroke-width="3"/></g>${svgText2(`Odak ${s.focus.toFixed(2)}`, { x: 90, y: 1475, width: 440, maximum: 44, minimum: 34, maxLines: 1, fill: c.ink })}${svgText2(`Alan ${s.section_area.toFixed(2)}`, { x: 580, y: 1475, width: 410, maximum: 44, minimum: 34, maxLines: 1, fill: c.ink })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/03ab609394d1-rigid-body-lightstage.mjs
  var ab609394d1_rigid_body_lightstage_exports = {};
  __export(ab609394d1_rigid_body_lightstage_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE56,
    ID: () => ID56,
    METADATA: () => METADATA48,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA56,
    SOURCE_ID: () => SOURCE_ID56,
    bounceHeight: () => bounceHeight,
    flightDuration: () => flightDuration,
    hull: () => hull,
    render: () => render56,
    sample: () => sample56,
    validateSpec: () => validateSpec56
  });
  var ID56 = "rigid-body-lightstage";
  var SOURCE_ID56 = "source-mg-style-04-3d-render";
  var DEFAULT_PALETTE56 = Object.freeze({ background: "#EEECE7", ink: "#313C43", muted: "#57656D", accent: "#8B422A" });
  var PARAMETER_SCHEMA56 = Object.freeze({ bodies: { minItems: 2, maxItems: 3, item: { label: { maxLength: 32 }, width: { minimum: 0.6, maximum: 1.3 }, height: { minimum: 0.6, maximum: 1.5 }, depth: { minimum: 0.6, maximum: 1.3 }, drop_height: { minimum: 0.8, maximum: 2.4 } } }, restitution: { minimum: 0.2, maximum: 0.5 }, light_angle: { minimum: -40, maximum: 40 }, yaw_degrees: { minimum: -30, maximum: 30 } });
  var METADATA48 = commonMetadata("Rijit kutular\u0131n analitik \u0131\u015F\u0131k sahnesi", "solid-contact", "lightstage-with-body-ledger", "Three diminishing ballistic rebounds \u2192 plane contact; directional-ray shadows follow the same solid vertices", ["58px upper-left title", "34px light direction", "30px body ledger", "30\u201342px cue"]);
  function validateSpec56(spec) {
    const p = base4(spec, ID56, ["bodies", "restitution", "light_angle", "yaw_degrees"], [], DEFAULT_PALETTE56), r = spec.parameters;
    p.bodies = array(r.bodies, "bodies", 2, 3).map((b, i) => {
      keys2(b, ["label", "width", "height", "depth", "drop_height"]);
      const label5 = text2(b.label, "body label", 32);
      fitText2(label5, { width: 820, maximum: 32, minimum: 30, maxLines: 1 });
      return { label: label5, width: number2(b.width, "width", 0.6, 1.3), height: number2(b.height, "height", 0.6, 1.5), depth: number2(b.depth, "depth", 0.6, 1.3), drop_height: number2(b.drop_height, "drop_height", 0.8, 2.4) };
    });
    p.restitution = number2(r.restitution, "restitution", 0.2, 0.5);
    p.light_angle = number2(r.light_angle, "light_angle", -40, 40);
    p.yaw_degrees = number2(r.yaw_degrees, "yaw_degrees", -30, 30);
    return normalized(ID56, p);
  }
  function flightDuration(height, restitution) {
    const fall = Math.sqrt(2 * height / 9.8);
    return fall + 2 * fall * (restitution + restitution ** 2 + restitution ** 3);
  }
  function bounceHeight(height, restitution, time2) {
    const g = 9.8, fall = Math.sqrt(2 * height / g);
    if (time2 <= fall) return Math.max(0, height - 0.5 * g * time2 * time2);
    let remaining = time2 - fall, velocity = Math.sqrt(2 * g * height) * restitution;
    for (let i = 0; i < 3; i++) {
      const duration = 2 * velocity / g;
      if (remaining <= duration) return Math.max(0, velocity * remaining - 0.5 * g * remaining ** 2);
      remaining -= duration;
      velocity *= restitution;
    }
    return 0;
  }
  function hull(points) {
    const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y), cross3 = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x), lo = [], hi = [];
    for (const p of sorted) {
      while (lo.length > 1 && cross3(lo.at(-2), lo.at(-1), p) <= 0) lo.pop();
      lo.push(p);
    }
    for (const p of [...sorted].reverse()) {
      while (hi.length > 1 && cross3(hi.at(-2), hi.at(-1), p) <= 0) hi.pop();
      hi.push(p);
    }
    lo.pop();
    hi.pop();
    return [...lo, ...hi];
  }
  function state45(p, seconds) {
    const c = clock2(seconds, p.duration), maxT = Math.max(...p.bodies.map((b) => flightDuration(b.drop_height, p.restitution))), physical_time = maxT * Math.min(1, c.u / 0.87), light_angle = lerp2(-35, p.light_angle, smooth2(c.u)), dx = 0.4 * Math.cos(radians(light_angle)), dy = 0.4 * Math.sin(radians(light_angle));
    const bodies = p.bodies.map((b, i) => {
      const z = bounceHeight(b.drop_height, p.restitution, physical_time), x = (i - (p.bodies.length - 1) / 2) * 2.35, y = i % 2 * 0.55 - 0.25, vertices = [];
      for (const level of [z, z + b.height]) for (const q of [[-b.width / 2, -b.depth / 2], [b.width / 2, -b.depth / 2], [b.width / 2, b.depth / 2], [-b.width / 2, b.depth / 2]]) vertices.push({ x: x + q[0], y: y + q[1], z: level });
      const shadow = vertices.map((q) => ({ x: q.x + q.z * dx, y: q.y + q.z * dy, z: 0 })), screen = vertices.map((q) => project3(q, { yaw: p.yaw_degrees, scale: 90, cy: 1180 })), shadow_screen = hull(shadow.map((q) => project3(q, { yaw: p.yaw_degrees, scale: 90, cy: 1180 })));
      return { index: i, bottom: z, vertices, screen, shadow, shadow_screen, contact: z <= 1e-10, bounds: bounds2([...screen, ...shadow_screen]) };
    });
    return { ...c, physical_time, light_angle, light_ray: { x: dx, y: dy, z: -1 }, bodies, bounds: bounds2(bodies.flatMap((b) => [...b.screen, ...b.shadow_screen])) };
  }
  function sample56(spec, seconds) {
    return state45(validateSpec56(spec).parameters, seconds);
  }
  function render56(spec, seconds) {
    const p = validateSpec56(spec).parameters, s = state45(p, seconds), c = p.palette;
    const shadows = s.bodies.map((b) => `<path d="${path4(b.shadow_screen)}" fill="${c.muted}" fill-opacity="0.2"/>`).join("");
    const bodies = s.bodies.map((b) => visibleBoxFaces(b.vertices, p.yaw_degrees).map((face) => `<path data-solid-face="${face.key}" d="${path4(face.indices.map((k) => b.screen[k]))}" fill="${face.key === "top" ? c.background : c.accent}" fill-opacity="${fmt2(face.key === "top" ? 1 : 0.65 + 0.25 * Math.cos(radians(s.light_angle + face.shade)))}" stroke="${c.ink}" stroke-width="3"/>`).join("")).join("");
    const labels = p.bodies.map((b, i) => svgText2(`${i + 1}. ${b.label}`, { x: 90, y: 1460 + i * 57, width: 880, maximum: 32, minimum: 30, maxLines: 1, fill: c.ink })).join("");
    return svg(ID56, p, s.seconds, `${svgText2(p.title, { y: 165, maximum: 58, minimum: 40, maxLines: 3, fill: c.ink })}${svgText2(`I\u015F\u0131k y\xF6n\xFC ${s.light_angle.toFixed(0)}\xB0`, { x: 90, y: 525, width: 850, maximum: 34, minimum: 30, maxLines: 1, fill: c.muted })}<path d="M110 1325H970M140 1350H940" stroke="${c.muted}" stroke-width="2"/>${shadows}${bodies}${labels}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/1d17763cd66d-lighttable-register.mjs
  var d17763cd66d_lighttable_register_exports = {};
  __export(d17763cd66d_lighttable_register_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE57,
    ID: () => ID57,
    METADATA: () => METADATA49,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA57,
    SOURCE_ID: () => SOURCE_ID57,
    render: () => render57,
    sample: () => sample57,
    validateSpec: () => validateSpec57
  });
  var ID57 = "lighttable-register";
  var SOURCE_ID57 = "source-lemo-style-archive-lighttable";
  var DEFAULT_PALETTE57 = Object.freeze({ background: "#F3EFE4", ink: "#34372D", muted: "#62654E", accent: "#8A3F2D" });
  var PARAMETER_SCHEMA57 = Object.freeze({ plates: { minItems: 2, maxItems: 4, item: { label: { maxLength: 35 }, offset_x: { minimum: -80, maximum: 80 }, offset_y: { minimum: -80, maximum: 80 }, angle: { minimum: -12, maximum: 12 }, mark_fraction: { minimum: 0.2, maximum: 0.8 } } }, inspection_fraction: { minimum: 0.2, maximum: 0.8 }, aperture_height: { minimum: 36, maximum: 90 } });
  var METADATA49 = commonMetadata("\xD6zg\xFCn belge katmanlar\u0131nda \u0131\u015F\u0131k masas\u0131 kayd\u0131", "document-registration", "two-column-archive-ledger", "Rigid page translation/rotation \u2192 exact common registration \u2192 clipped inspection band", ["58px archive headline", "30px numbered plate ledger", "52px registration error", "30\u201342px cue"]);
  function validateSpec57(spec) {
    const p = base4(spec, ID57, ["plates", "inspection_fraction", "aperture_height"], [], DEFAULT_PALETTE57), r = spec.parameters;
    p.plates = array(r.plates, "plates", 2, 4).map((q, i) => {
      keys2(q, ["label", "offset_x", "offset_y", "angle", "mark_fraction"]);
      const label5 = text2(q.label, "plate label", 35);
      fitText2(`${i + 1}. ${label5}`, { width: 330, maximum: 32, minimum: 30, maxLines: 2 });
      return { label: label5, offset_x: number2(q.offset_x, "offset_x", -80, 80), offset_y: number2(q.offset_y, "offset_y", -80, 80), angle: number2(q.angle, "angle", -12, 12), mark_fraction: number2(q.mark_fraction, "mark_fraction", 0.2, 0.8) };
    });
    p.inspection_fraction = number2(r.inspection_fraction, "inspection_fraction", 0.2, 0.8);
    p.aperture_height = number2(r.aperture_height, "aperture_height", 36, 90);
    return normalized(ID57, p);
  }
  function state46(p, seconds) {
    const c = clock2(seconds, p.duration), registration = smooth2(c.u / 0.55), inspection = smooth2((c.u - 0.55) / 0.45), aperture_y = 830 + 420 * lerp2(0.1, p.inspection_fraction, inspection), local = [{ x: -130, y: -210 }, { x: 130, y: -210 }, { x: 130, y: 210 }, { x: -130, y: 210 }];
    const plates = p.plates.map((q, i) => {
      const offset_x = q.offset_x * (1 - registration), offset_y = q.offset_y * (1 - registration), angle = q.angle * (1 - registration), corners2 = local.map((v) => rotate2(v, angle, 690 + offset_x, 1040 + offset_y)), mark_y = 830 + 420 * q.mark_fraction;
      return { index: i, offset_x, offset_y, angle, corners: corners2, mark_y, lit: Math.abs(mark_y - aperture_y) <= p.aperture_height / 2, registration_error: Math.hypot(offset_x, offset_y), bounds: bounds2(corners2) };
    });
    return { ...c, registration, inspection, aperture_y, plates, registration_error: Math.max(...plates.map((q) => q.registration_error)) };
  }
  function sample57(spec, seconds) {
    return state46(validateSpec57(spec).parameters, seconds);
  }
  function render57(spec, seconds) {
    const p = validateSpec57(spec).parameters, s = state46(p, seconds), c = p.palette;
    const ledger = p.plates.map((q, i) => svgText2(`${i + 1}. ${q.label}`, { x: 90, y: 650 + i * 150, width: 330, maximum: 32, minimum: 30, maxLines: 2, fill: c.ink })).join("");
    const pages = s.plates.map((q) => `<g transform="translate(${fmt2(690 + q.offset_x)} ${fmt2(1040 + q.offset_y)}) rotate(${fmt2(q.angle)})"><rect x="-130" y="-210" width="260" height="420" fill="${c.background}" fill-opacity="0.18" stroke="${c.ink}" stroke-width="2"/><path d="M-103 -166H92M-103 -130H65M-103 -98H105M-103 -66H40" stroke="${c.muted}" stroke-width="${q.index + 1}" fill="none"/><path d="M-104 ${fmt2(-210 + 420 * p.plates[q.index].mark_fraction)}H104" stroke="${c.accent}" stroke-width="4"/></g>`).join("");
    const marks = [{ x: 560, y: 830 }, { x: 820, y: 830 }, { x: 820, y: 1250 }, { x: 560, y: 1250 }].map((q) => `<path d="M${q.x - 14} ${q.y}h28M${q.x} ${q.y - 14}v28" stroke="${c.accent}" stroke-width="3"/>`).join("");
    return svg(ID57, p, s.seconds, `${svgText2(p.title, { y: 165, maximum: 58, minimum: 40, maxLines: 3, fill: c.ink })}${ledger}<defs><clipPath id="g04-light-aperture"><rect x="560" y="830" width="260" height="420"/></clipPath></defs>${pages}${marks}<g clip-path="url(#g04-light-aperture)"><rect x="560" y="${fmt2(s.aperture_y - p.aperture_height / 2)}" width="260" height="${p.aperture_height}" fill="${c.accent}" fill-opacity="0.16"/><path d="M560 ${fmt2(s.aperture_y)}H820" stroke="${c.accent}" stroke-width="3"/></g>${svgText2(`Kay\u0131t sapmas\u0131 ${s.registration_error.toFixed(1)}`, { x: 90, y: 1490, width: 900, maximum: 52, minimum: 38, maxLines: 2, fill: c.ink })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/0787ab85d27f-score-reveal-wheel.mjs
  var ab85d27f_score_reveal_wheel_exports = {};
  __export(ab85d27f_score_reveal_wheel_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE58,
    ID: () => ID58,
    METADATA: () => METADATA50,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA58,
    SOURCE_ID: () => SOURCE_ID58,
    render: () => render58,
    sample: () => sample58,
    validateSpec: () => validateSpec58
  });
  var ID58 = "score-reveal-wheel";
  var SOURCE_ID58 = "source-lemo-style-game-show";
  var DEFAULT_PALETTE58 = Object.freeze({ background: "#F8F1E8", ink: "#322C3A", muted: "#665767", accent: "#964032" });
  var PARAMETER_SCHEMA58 = Object.freeze({ segments: { minItems: 3, maxItems: 6, item: { label: { maxLength: 35 }, points: { type: "integer", minimum: 0, maximum: 250 } } }, selected_index: { type: "integer", minimum: 0, maximum: 5 }, turns: { type: "integer", minimum: 2, maximum: 5 }, base_score: { type: "integer", minimum: 0, maximum: 500 } });
  var METADATA50 = commonMetadata("Se\xE7ili sekt\xF6rde duran mekanik cevap \xE7ark\u0131", "wheel-score", "center-wheel-score-stage", "Monotone cubic braking \u2192 exact selected-sector center \u2192 hinged answer reveal and additive score", ["58px centered question", "64px wheel indices", "42px selected answer", "80px score", "30\u201342px cue"]);
  function validateSpec58(spec) {
    const p = base4(spec, ID58, ["segments", "selected_index", "turns", "base_score"], [], DEFAULT_PALETTE58), r = spec.parameters;
    p.segments = array(r.segments, "segments", 3, 6).map((q) => {
      keys2(q, ["label", "points"]);
      const label5 = text2(q.label, "segment label", 35);
      fitText2(label5, { width: 800, maximum: 42, minimum: 34, maxLines: 2 });
      return { label: label5, points: number2(q.points, "points", 0, 250, true) };
    });
    p.selected_index = number2(r.selected_index, "selected_index", 0, p.segments.length - 1, true);
    p.turns = number2(r.turns, "turns", 2, 5, true);
    p.base_score = number2(r.base_score, "base_score", 0, 500, true);
    return normalized(ID58, p);
  }
  var wrap = (a) => (a % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
  function state47(p, seconds) {
    const c = clock2(seconds, p.duration), n = p.segments.length, step = 2 * Math.PI / n, target7 = 2 * Math.PI * p.turns - (p.selected_index + 0.5) * step, a = Math.min(1, c.u / 0.62), rotation = target7 * (1 - (1 - a) ** 3), answer_open = smooth2((c.u - 0.62) / 0.18), score_progress = smooth2((c.u - 0.8) / 0.2), score = p.base_score + Math.floor(p.segments[p.selected_index].points * score_progress + 1e-9), pointer_index = Math.min(n - 1, Math.floor(wrap(-rotation) / step)), segments = p.segments.map((q, i) => ({ index: i, start: -Math.PI / 2 + i * step + rotation, end: -Math.PI / 2 + (i + 1) * step + rotation, center: -Math.PI / 2 + (i + 0.5) * step + rotation }));
    return { ...c, rotation, target_rotation: target7, pointer_index, segments, answer_open, answer_width: 800 * Math.max(0.025, Math.sin(answer_open * Math.PI / 2)), score, score_target: p.base_score + p.segments[p.selected_index].points };
  }
  function sample58(spec, seconds) {
    return state47(validateSpec58(spec).parameters, seconds);
  }
  function render58(spec, seconds) {
    const p = validateSpec58(spec).parameters, s = state47(p, seconds), c = p.palette, cx = 540, cy = 970, r = 282;
    const wheel = s.segments.map((q) => {
      const ax = cx + r * Math.cos(q.start), ay = cy + r * Math.sin(q.start), bx = cx + r * Math.cos(q.end), by = cy + r * Math.sin(q.end), tx2 = cx + 190 * Math.cos(q.center), ty = cy + 190 * Math.sin(q.center);
      return `<path d="M${cx} ${cy}L${fmt2(ax)} ${fmt2(ay)}A${r} ${r} 0 0 1 ${fmt2(bx)} ${fmt2(by)}Z" fill="${q.index % 2 ? c.background : c.accent}" fill-opacity="${q.index % 2 ? 1 : 0.18}" stroke="${c.ink}" stroke-width="3"/>${svgText2(String(q.index + 1), { x: tx2, y: ty + 22, width: 100, maximum: 64, minimum: 64, maxLines: 1, anchor: "middle", fill: c.ink })}`;
    }).join("");
    return svg(ID58, p, s.seconds, `${svgText2(p.title, { x: 540, y: 165, width: 900, maximum: 58, minimum: 40, maxLines: 3, anchor: "middle", fill: c.ink })}${wheel}<path d="M540 667l-24 -42h48Z" fill="${c.ink}"/><circle cx="540" cy="970" r="24" fill="${c.ink}"/><rect x="${fmt2(540 - s.answer_width / 2)}" y="1320" width="${fmt2(s.answer_width)}" height="155" rx="4" fill="${c.background}" stroke="${c.accent}" stroke-width="4"/><g opacity="${fmt2(s.answer_open)}">${svgText2(p.segments[p.selected_index].label, { x: 540, y: 1375, width: 740, maximum: 42, minimum: 34, maxLines: 2, anchor: "middle", fill: c.ink })}</g>${svgText2("TOPLAM PUAN", { x: 90, y: 1570, width: 580, maximum: 34, minimum: 30, maxLines: 1, fill: c.muted })}${svgText2(String(s.score), { x: 990, y: 1570, width: 300, maximum: 80, minimum: 64, maxLines: 1, anchor: "end", fill: c.ink })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/6f1884452a41-hologram-slice-volume.mjs
  var f1884452a41_hologram_slice_volume_exports = {};
  __export(f1884452a41_hologram_slice_volume_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE59,
    ID: () => ID59,
    METADATA: () => METADATA51,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA59,
    SOURCE_ID: () => SOURCE_ID59,
    ellipseSlice: () => ellipseSlice,
    render: () => render59,
    sample: () => sample59,
    validateSpec: () => validateSpec59
  });
  var ID59 = "hologram-slice-volume";
  var SOURCE_ID59 = "source-lemo-style-hologram-hud";
  var DEFAULT_PALETTE59 = Object.freeze({ background: "#EFF1F4", ink: "#273749", muted: "#536376", accent: "#764441" });
  var PARAMETER_SCHEMA59 = Object.freeze({ radii_x: { minimum: 1, maximum: 3 }, radii_y: { minimum: 0.8, maximum: 2.5 }, radii_z: { minimum: 1, maximum: 2.5 }, slice_count: { type: "integer", minimum: 6, maximum: 16 }, section_fraction: { minimum: 0.2, maximum: 0.8 }, yaw_degrees: { minimum: -35, maximum: 35 }, volume_label: { type: "string", maxLength: 45 } });
  var METADATA51 = commonMetadata("Dilimin alan\u0131ndan hacmin kurulmas\u0131na", "analytic-volume", "asymmetric-volume-drawing", "Ellipsoid slices accumulate \u2192 cross-section plane locates selected fraction \u2192 final analytic area/volume hold", ["58px left headline", "34px volume descriptor", "48px area rail", "44px volume result", "30\u201342px cue"]);
  function validateSpec59(spec) {
    const p = base4(spec, ID59, ["radii_x", "radii_y", "radii_z", "slice_count", "section_fraction", "yaw_degrees", "volume_label"], [], DEFAULT_PALETTE59), r = spec.parameters;
    p.radii_x = number2(r.radii_x, "radii_x", 1, 3);
    p.radii_y = number2(r.radii_y, "radii_y", 0.8, 2.5);
    p.radii_z = number2(r.radii_z, "radii_z", 1, 2.5);
    p.slice_count = number2(r.slice_count, "slice_count", 6, 16, true);
    p.section_fraction = number2(r.section_fraction, "section_fraction", 0.2, 0.8);
    p.yaw_degrees = number2(r.yaw_degrees, "yaw_degrees", -35, 35);
    p.volume_label = text2(r.volume_label, "volume_label", 45);
    fitText2(p.volume_label, { width: 540, maximum: 34, minimum: 30, maxLines: 2 });
    return normalized(ID59, p);
  }
  function ellipseSlice(rx, ry, rz, z) {
    const k = Math.sqrt(Math.max(0, 1 - (z / rz) ** 2));
    return { z, rx: rx * k, ry: ry * k, area: Math.PI * rx * ry * k * k };
  }
  function ellipsePoints(slice, p) {
    return Array.from({ length: 32 }, (_, i) => {
      const a = 2 * Math.PI * i / 32;
      return project3({ x: slice.rx * Math.cos(a), y: slice.ry * Math.sin(a), z: slice.z }, { yaw: p.yaw_degrees, scale: 100, cx: 520, cy: 1120 });
    });
  }
  function state48(p, seconds) {
    const c = clock2(seconds, p.duration), built = 1 + Math.floor((p.slice_count - 1) * smooth2(c.u / 0.58) + 1e-9), section_fraction = lerp2(0, p.section_fraction, smooth2((c.u - 0.35) / 0.65)), section_z = -p.radii_z + 2 * p.radii_z * section_fraction, slices = Array.from({ length: p.slice_count }, (_, i) => {
      const slice = ellipseSlice(p.radii_x, p.radii_y, p.radii_z, -p.radii_z + 2 * p.radii_z * i / (p.slice_count - 1));
      return { ...slice, index: i, visible: i < built, screen: ellipsePoints(slice, p) };
    }), section = ellipseSlice(p.radii_x, p.radii_y, p.radii_z, section_z);
    section.screen = ellipsePoints(section, p);
    let discrete_volume = 0;
    for (let i = 0; i < slices.length - 1; i++) discrete_volume += (slices[i].area + slices[i + 1].area) / 2 * (slices[i + 1].z - slices[i].z);
    return { ...c, built, slices, section, section_fraction, discrete_volume, analytic_volume: 4 * Math.PI * p.radii_x * p.radii_y * p.radii_z / 3, bounds: bounds2([...slices.flatMap((q) => q.screen), ...section.screen]) };
  }
  function sample59(spec, seconds) {
    return state48(validateSpec59(spec).parameters, seconds);
  }
  function render59(spec, seconds) {
    const p = validateSpec59(spec).parameters, s = state48(p, seconds), c = p.palette;
    const rings = s.slices.filter((q) => q.visible).map((q) => `<path d="${path4(q.screen)}" fill="none" stroke="${c.muted}" stroke-width="2"/>`).join("");
    const rails = [0, 8, 16, 24].map((index) => `<path d="${path4(s.slices.filter((q) => q.visible).map((q) => q.screen[index]), false)}" fill="none" stroke="${c.ink}" stroke-width="2"/>`).join("");
    return svg(ID59, p, s.seconds, `${svgText2(p.title, { y: 165, maximum: 58, minimum: 40, maxLines: 3, fill: c.ink })}${svgText2(p.volume_label, { x: 90, y: 540, width: 540, maximum: 34, minimum: 30, maxLines: 2, fill: c.muted })}${svgText2(`Alan ${s.section.area.toFixed(2)}`, { x: 670, y: 540, width: 320, maximum: 48, minimum: 34, maxLines: 2, fill: c.ink })}${rings}${rails}<path d="${path4(s.section.screen)}" fill="${c.accent}" fill-opacity="0.18" stroke="${c.accent}" stroke-width="4"/>${svgText2(`Hacim ${s.analytic_volume.toFixed(2)}`, { x: 90, y: 1480, width: 900, maximum: 44, minimum: 34, maxLines: 1, fill: c.ink })}${svgText2(`${s.built} / ${p.slice_count} kesit`, { x: 90, y: 1560, width: 900, maximum: 34, minimum: 30, maxLines: 1, fill: c.muted })}${caption(p, s.seconds)}`);
  }

  // renderers/template-registry/modules/7c074e219fc9-footage-caption-cuts.mjs
  var c074e219fc9_footage_caption_cuts_exports = {};
  __export(c074e219fc9_footage_caption_cuts_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE61,
    ID: () => ID60,
    METADATA: () => METADATA52,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA60,
    SOURCE_ID: () => SOURCE_ID60,
    render: () => render60,
    sample: () => sample60,
    validateSpec: () => validateSpec60
  });

  // renderers/template-registry/modules/cfba831b446a-media-core.mjs
  var DEFAULT_PALETTE60 = deepFreeze({ background: "#101B24", ink: "#F4F3E9", muted: "#BBCBD3", accent: "#8CD8EF" });
  var obj = (properties) => ({ type: "object", additionalProperties: false, required: Object.keys(properties), properties });
  var num = (minimum, maximum, integer = false) => ({ type: integer ? "integer" : "number", minimum, maximum });
  var str = (maxLength = 160) => ({ type: "string", minLength: 1, maxLength });
  var arr2 = (items, minItems = 1, maxItems = 12) => ({ type: "array", items, minItems, maxItems });
  var boxSchema = obj({ x: num(0, 1), y: num(0, 1), w: num(0.02, 1), h: num(0.02, 1) });
  var pointSchema = obj({ x: num(0, 1), y: num(0, 1) });
  var pathSchema = arr2(obj({ at: num(0, 1), x: num(0, 1), y: num(0, 1), w: num(0.02, 1), h: num(0.02, 1) }), 2, 8);
  var remapSchema = arr2(obj({ at: num(0, 1), time: num(0, 3600) }), 2, 8);
  var pauseSchema = arr2(obj({ start: num(0, 44), end: num(0.1, 45) }), 0, 6);
  var refsSchema = arr2(str(36), 1, 6);
  var hexSchema = { type: "string", pattern: "^#[0-9a-fA-F]{6}$" };
  var gridSchema = obj({ width: num(1, 8, true), height: num(1, 8, true), pixels: arr2(hexSchema, 1, 64) });
  var safePathSchema = { type: "string", maxLength: 180, pattern: "^[A-Za-z0-9][A-Za-z0-9._/-]*$" };
  var rightsSchema = obj({ owner: str(120), license: str(160), proof: safePathSchema, verification: { enum: ["proxy_original", "pending"] } });
  var mediaSchema = arr2(obj({ id: str(36), kind: { enum: ["video", "image", "screen", "depth"] }, local_path: safePathSchema, sha256: { type: "string", pattern: "^[0-9a-f]{64}$" }, material_class: { enum: ["original_rgb_proxy", "caller_local_media"] }, width: num(1, 8192, true), height: num(1, 8192, true), duration: num(1, 3600), rights: rightsSchema, proxy: gridSchema }), 1, 6);
  function schema2(fields) {
    const result2 = obj({ title: str(), duration: num(3, 45), narration: str(1500), cues: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(95) }), 1, 24), media: mediaSchema, ...fields, ...{ palette: { ...obj({ background: hexSchema, ink: hexSchema, muted: hexSchema, accent: hexSchema }), optional: true } } });
    result2.required = result2.required.filter((k) => k !== "palette");
    delete result2.properties.palette.optional;
    return deepFreeze(result2);
  }
  function list3(v, name, min = 1, max = 12) {
    if (!Array.isArray(v) || v.length < min || v.length > max || Object.keys(v).length !== v.length || Reflect.ownKeys(v).length !== v.length + 1) fail2(`${name}: dense bounded array required`);
    for (let i = 0; i < v.length; i++) {
      const d = Object.getOwnPropertyDescriptor(v, String(i));
      if (!d || !Object.hasOwn(d, "value")) fail2(`${name}: data entries required`);
    }
    return v;
  }
  function token(v, name = "asset") {
    const s = text2(v, name, 36);
    if (!/^[a-z][a-z0-9_-]{0,35}$/u.test(s)) fail2(`${name}: local token required`);
    return s;
  }
  function localPath(v, name = "local_path") {
    const s = text2(v, name, 180);
    if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/u.test(s) || s.split("/").some((x) => !x || x === "." || x === "..") || s.startsWith("/") || s.includes("://")) fail2(`${name}: safe relative local path required`);
    return s;
  }
  function grid(v, name = "grid", max = 8) {
    keys2(v, ["width", "height", "pixels"], [], name);
    const width = number2(v.width, `${name}.width`, 1, max, true), height = number2(v.height, `${name}.height`, 1, max, true);
    const pixels = list3(v.pixels, `${name}.pixels`, width * height, width * height).map((c) => {
      if (typeof c !== "string" || !/^#[0-9a-fA-F]{6}$/u.test(c)) fail2(`${name}: RGB hex required`);
      return c.toUpperCase();
    });
    return { width, height, pixels };
  }
  function preflightCueInput2(spec) {
    if (!spec || typeof spec !== "object" || Array.isArray(spec)) fail2("spec: plain data required");
    const parameters2 = Object.getOwnPropertyDescriptor(spec, "parameters");
    if (!parameters2 || !parameters2.enumerable || !Object.hasOwn(parameters2, "value")) fail2("parameters: enumerable data required");
    const raw = parameters2.value;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) fail2("parameters: plain data required");
    const cues = Object.getOwnPropertyDescriptor(raw, "cues");
    if (!cues || !cues.enumerable || !Object.hasOwn(cues, "value")) fail2("cues: enumerable data required");
    validateCueArray2(cues.value);
  }
  function base5(spec, id, fields, defaults = DEFAULT_PALETTE60) {
    preflightCueInput2(spec);
    const p = validateBase2(spec, id, ["media", ...fields], [], defaults);
    if (p.cues[0].start !== 0 || p.cues.at(-1).end !== p.duration || p.cues.some((q, i) => q.end - q.start < 0.6 || i && q.start !== p.cues[i - 1].end) || p.cues.at(-1).start > p.duration - 0.8) fail2("narration cues must cover duration and reserve the final readable hold");
    const media = list3(spec.parameters.media, "media", 1, 6).map((m, i) => {
      keys2(m, ["id", "kind", "local_path", "sha256", "material_class", "width", "height", "duration", "rights", "proxy"], [], `media ${i}`);
      keys2(m.rights, ["owner", "license", "proof", "verification"], [], "rights");
      const id2 = token(m.id);
      if (typeof m.sha256 !== "string" || !/^([0-9a-f]{64})$/u.test(m.sha256)) fail2("media sha256 required");
      return { id: id2, kind: choice2(m.kind, "kind", ["video", "image", "screen", "depth"]), local_path: localPath(m.local_path), sha256: m.sha256, material_class: choice2(m.material_class, "material_class", ["original_rgb_proxy", "caller_local_media"]), width: number2(m.width, "media width", 1, 8192, true), height: number2(m.height, "media height", 1, 8192, true), duration: number2(m.duration, "media duration", 1, 3600), rights: { owner: text2(m.rights.owner, "owner", 120), license: text2(m.rights.license, "license", 160), proof: localPath(m.rights.proof, "rights proof"), verification: choice2(m.rights.verification, "rights verification", ["proxy_original", "pending"]) }, proxy: grid(m.proxy) };
    });
    if (new Set(media.map((m) => m.id)).size !== media.length) fail2("unique media IDs required");
    for (const m of media) if (m.material_class === "original_rgb_proxy" !== (m.rights.verification === "proxy_original")) fail2("proxy rights cannot verify caller media");
    return { ...p, media };
  }
  function asset(p, id) {
    const a = p.media.find((m) => m.id === id);
    if (!a) fail2(`unknown media handle ${id}`);
    return a;
  }
  function ref(v, p, name = "media reference") {
    const id = token(v, name);
    asset(p, id);
    return id;
  }
  function refs(v, p, name = "clip order", min = 1, max = 6) {
    return list3(v, name, min, max).map((x) => ref(x, p, name));
  }
  function box(v, name = "crop") {
    keys2(v, ["x", "y", "w", "h"], [], name);
    const b = { x: number2(v.x, `${name}.x`, 0, 1), y: number2(v.y, `${name}.y`, 0, 1), w: number2(v.w, `${name}.w`, 0.02, 1), h: number2(v.h, `${name}.h`, 0.02, 1) };
    if (b.x + b.w > 1 + 1e-9 || b.y + b.h > 1 + 1e-9) fail2(`${name}: outside source`);
    return b;
  }
  function point3(v, name = "point") {
    keys2(v, ["x", "y"], [], name);
    return { x: number2(v.x, `${name}.x`, 0, 1), y: number2(v.y, `${name}.y`, 0, 1) };
  }
  var FULL = deepFreeze({ x: 0, y: 0, w: 1, h: 1 });
  function cropPath(v, name = "crop_path") {
    const out = list3(v, name, 2, 8).map((k) => {
      keys2(k, ["at", "x", "y", "w", "h"], [], name);
      const { at: at2, ...b } = k;
      return { at: number2(at2, "path time", 0, 1), ...box(b, name) };
    });
    ordered2(out.map((x) => x.at), name, 0, 1);
    return out;
  }
  function ordered2(v, name, start, end) {
    if (v[0] !== start || v.at(-1) !== end || v.some((x, i) => i && x <= v[i - 1])) fail2(`${name}: ordered endpoints ${start},${end} required`);
    return v;
  }
  function cuts(v, count, duration, name = "cuts") {
    const out = list3(v, name, count + 1, count + 1).map((x) => number2(x, name, 0, duration));
    ordered2(out, name, 0, duration);
    if (out.some((x, i) => i && x - out[i - 1] < 0.8 - 1e-8)) fail2(`${name}: each shot at least .8s`);
    return out;
  }
  function remap(v, maxTime, name = "time_remap") {
    const a = list3(v, name, 2, 8).map((k) => {
      keys2(k, ["at", "time"], [], name);
      return { at: number2(k.at, "remap at", 0, 1), time: number2(k.time, "remap time", 0, maxTime) };
    });
    ordered2(a.map((x) => x.at), name, 0, 1);
    if (a.some((k, i) => i && k.time < a[i - 1].time)) fail2("source time must be monotone");
    return a;
  }
  function pauses(v, duration, name = "pauses") {
    let end = 0;
    return list3(v, name, 0, 6).map((q) => {
      keys2(q, ["start", "end"], [], name);
      const a = number2(q.start, "pause start", 0, duration - 0.8), b = number2(q.end, "pause end", 0, duration - 0.8);
      if (a < end || b - a < 0.2 || b - a > duration / 2) fail2("ordered bounded pause required");
      end = b;
      return { start: a, end: b };
    });
  }
  function cueArray(v, duration, name, min = 1, max = 8) {
    let end = 0;
    return list3(v, name, min, max).map((q) => {
      keys2(q, ["start", "end", "text"], [], name);
      const a = number2(q.start, `${name}.start`, 0, duration), b = number2(q.end, `${name}.end`, 0, duration);
      if (a < end || b - a < 0.6 || a > duration - 1.1) fail2(`${name}: readable cues before final hold required`);
      end = b;
      const value = text2(q.text, `${name}.text`, 120);
      fitText2(value, { width: 880, maximum: 48, minimum: 30, maxLines: 4 });
      return { start: a, end: b, text: value };
    });
  }
  function track(v, name = "track") {
    const a = list3(v, name, 2, 12).map((k) => {
      keys2(k, ["at", "x", "y"], [], name);
      return { at: number2(k.at, "track at", 0, 1), ...point3({ x: k.x, y: k.y }) };
    });
    ordered2(a.map((x) => x.at), name, 0, 1);
    return a;
  }
  function interpolate(keys4, u, properties) {
    u = clamp2(u);
    let i = keys4.findIndex((k) => k.at >= u);
    if (i <= 0) return Object.fromEntries(properties.map((k) => [k, keys4[0][k]]));
    if (i < 0) i = keys4.length - 1;
    const a = keys4[i - 1], b = keys4[i], q = smooth2((u - a.at) / (b.at - a.at));
    return Object.fromEntries(properties.map((k) => [k, lerp2(a[k], b[k], q)]));
  }
  var cropAt = (keys4, u) => interpolate(keys4, u, ["x", "y", "w", "h"]);
  var pointAt = (keys4, u) => interpolate(keys4, u, ["x", "y"]);
  function sourceAt(keys4, u) {
    u = clamp2(u);
    let i = keys4.findIndex((k) => k.at >= u);
    if (i <= 0) return keys4[0].time;
    if (i < 0) i = keys4.length - 1;
    const a = keys4[i - 1], b = keys4[i];
    return lerp2(a.time, b.time, clamp2((u - a.at) / (b.at - a.at)));
  }
  function clock3(p, seconds) {
    const end = p.duration - 0.8, t = Math.min(sampleTime2(seconds, p.duration), end);
    return { t, u: t / end, end };
  }
  function pauseClock(t, windows) {
    return t - windows.reduce((n, q) => n + Math.max(0, Math.min(t, q.end) - q.start), 0);
  }
  function cutIndex(cutCues, t) {
    let i = 0;
    while (i < cutCues.length - 2 && t >= cutCues[i + 1]) i++;
    return i;
  }
  var rect3 = (x, y, w, h) => ({ x, y, w, h });
  function layer(p, id, sourceTime, crop, target7, extra = {}) {
    const a = asset(p, id);
    const time2 = number2(sourceTime, "source time", 0, a.duration);
    box(crop);
    for (const k of ["x", "y", "w", "h"]) number2(target7[k], `target ${k}`, 0, k === "x" || k === "w" ? 1080 : 1920);
    return { asset_id: id, local_path: a.local_path, sha256: a.sha256, source_time: time2, crop: { ...crop }, target: { ...target7 }, opacity: 1, transform: { dx: 0, dy: 0, scale: 1, rotation: 0 }, ...extra };
  }
  function projected(b, target7, pt2) {
    return { x: target7.x + (pt2.x - b.x) / b.w * target7.w, y: target7.y + (pt2.y - b.y) / b.h * target7.h };
  }
  function translateCropToPoint(crop, sourcePoint, targetPoint2) {
    const b = { ...crop, x: sourcePoint.x - targetPoint2.x * crop.w, y: sourcePoint.y - targetPoint2.y * crop.h };
    return box(b, "continuity alignment");
  }
  function metadata2(name, layout_id, motion_grammar, typographic_hierarchy) {
    return deepFreeze({ name, kind: "caller-local-media-pipeline", layout_id, motion_grammar, typographic_hierarchy, original_implementation: true, implementation_strategy: "original_implementation_not_source_code_port", native_verified: false, ui_verified: false, independent_accepted: false, real_media_verified: false, proxy_only_evidence: true });
  }
  function svg2(id, p, body) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc2(p.title)}" data-renderer="${esc2(id)}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="sans-serif">${body}</g></svg>`;
  }
  var tx = (value, x, y, width = 900, size = 52, color2 = "#F4F3E9", lines = 4) => svgText2(value, { x, y, width, maximum: size, minimum: Math.min(30, size), maxLines: lines, fill: color2 });
  var panel = (b, color2, opacity = 1) => `<rect x="${fmt2(b.x)}" y="${fmt2(b.y)}" width="${fmt2(b.w)}" height="${fmt2(b.h)}" fill="${esc2(color2)}" opacity="${fmt2(opacity)}"/>`;
  function cueText(p, t) {
    return p.cues.find((c) => t >= c.start && t < c.end)?.text ?? "";
  }
  function subtitle(p, t, y = 1660, x = 80, width = 920, size = 42) {
    const s = cueText(p, t);
    return s ? panel(rect3(x - 16, y - 48, width + 32, 210), p.palette.background) + tx(s, x, y, width, size, p.palette.ink, 3) : "";
  }
  function proxyMark(p, y = 1870) {
    return tx("TEKN\u0130K RGB KARE \xB7 GER\xC7EK MEDYA KABUL\xDC BEKL\u0130YOR", 64, y, 952, 24, p.palette.muted, 2);
  }
  function validateFrames(frames) {
    if (frames === void 0) return [];
    return list3(frames, "local frames", 1, 36).map((f) => {
      keys2(f, ["asset_id", "source_time", "frame"], [], "local frame");
      return { asset_id: token(f.asset_id), source_time: number2(f.source_time, "frame time", 0, 3600), frame: grid(f.frame, "local RGB frame", 64) };
    });
  }
  function drawLayer(p, l, key, frames) {
    const decoded = validateFrames(frames);
    for (const f of decoded) {
      const a = asset(p, f.asset_id);
      if (f.source_time > a.duration) fail2("caller frame beyond source duration");
    }
    const supplied = decoded.find((f) => f.asset_id === l.asset_id && Math.abs(f.source_time - l.source_time) <= 1 / 60);
    if (frames !== void 0 && !supplied) fail2("caller frame missing for exact frame request");
    const g = supplied?.frame ?? asset(p, l.asset_id).proxy, b = l.crop, t = l.target;
    const clip = `clip-${key}`;
    const polygon3 = l.mask?.map((pt2) => `${fmt2(pt2.x)},${fmt2(pt2.y)}`).join(" ");
    const mask = l.mask !== void 0 ? polygon3 ? `<polygon points="${polygon3}"/>` : "" : panel(t, "#FFFFFF");
    const tr = l.transform;
    const cx = t.x + t.w / 2, cy = t.y + t.h / 2;
    let cells = "";
    for (let j = 0; j < g.height; j++) for (let i = 0; i < g.width; i++) {
      const x = i / g.width, y = j / g.height, w = 1 / g.width, h = 1 / g.height;
      if (x + w <= b.x || x >= b.x + b.w || y + h <= b.y || y >= b.y + b.h) continue;
      cells += panel(rect3(t.x + (x - b.x) / b.w * t.w, t.y + (y - b.y) / b.h * t.h, w / b.w * t.w + 0.05, h / b.h * t.h + 0.05), g.pixels[j * g.width + i]);
    }
    const blur = l.blur ?? 0;
    const fid = `blur-${key}`;
    return `<defs><clipPath id="${clip}">${mask}</clipPath><clipPath id="${clip}-bounds">${panel(t, "#FFFFFF")}</clipPath>${blur ? `<filter id="${fid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${fmt2(blur)}"/></filter>` : ""}</defs><g clip-path="url(#${clip}-bounds)"><g clip-path="url(#${clip})" opacity="${fmt2(l.opacity)}"><g transform="translate(${fmt2(tr.dx)} ${fmt2(tr.dy)}) translate(${fmt2(cx)} ${fmt2(cy)}) rotate(${fmt2(tr.rotation)}) scale(${fmt2(tr.scale)}) translate(${fmt2(-cx)} ${fmt2(-cy)})"${blur ? ` filter="url(#${fid})"` : ""}>${cells}</g></g></g>`;
  }
  function drawLayers(p, layers, prefix, frames) {
    return layers.map((l, i) => drawLayer(p, l, `${prefix}-${i}`, frames)).join("");
  }
  function assertTextLayout(p, width = 900, size = 62, lines = 4) {
    fitText2(p.title, { width, maximum: size, minimum: 38, maxLines: lines });
    return p;
  }

  // renderers/template-registry/modules/7c074e219fc9-footage-caption-cuts.mjs
  var ID60 = "footage-caption-cuts";
  var SOURCE_ID60 = "source-lemo-style-caption-news";
  var DEFAULT_PALETTE61 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA60 = schema2({ clip_order: refsSchema, cut_cues: arr2(num(0, 45), 3, 7), caption_cues: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(120) }), 1, 8), subject_safe_boxes: arr2(obj({ clip: str(36), box: boxSchema }), 1, 6) });
  var METADATA52 = metadata2("Caption News \xB7 \xF6zg\xFCn edit", "subject-safe-caption-window", "timecoded hard cuts; caption chooses the unoccupied subject-safe band", ["news slug 30", "headline 60", "protected caption 42"]);
  var viewport = rect3(60, 410, 960, 1110);
  var overlap = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  function captionBox(subject) {
    const a = rect3(80, 435, 920, 222), b = rect3(80, 1270, 920, 222);
    if (overlap(a, subject) === 0) return a;
    if (overlap(b, subject) === 0) return b;
    fail2("subject occupies both caption safety bands");
  }
  function validateParameters19(spec) {
    const p = base5(spec, ID60, ["clip_order", "cut_cues", "caption_cues", "subject_safe_boxes"]);
    p.clip_order = refs(spec.parameters.clip_order, p, "clip_order", 2, 5);
    p.cut_cues = cuts(spec.parameters.cut_cues, p.clip_order.length, p.duration);
    p.caption_cues = cueArray(spec.parameters.caption_cues, p.duration, "caption_cues");
    for (const q of p.caption_cues) fitText2(q.text, { width: 880, maximum: 42, minimum: 30, maxLines: 3 });
    p.subject_safe_boxes = list3(spec.parameters.subject_safe_boxes, "safe boxes", p.clip_order.length, p.clip_order.length).map((v) => {
      keys2(v, ["clip", "box"]);
      const clip = ref(v.clip, p), box3 = box(v.box, "subject box");
      const subject = rect3(viewport.x + box3.x * viewport.w, viewport.y + box3.y * viewport.h, box3.w * viewport.w, box3.h * viewport.h);
      captionBox(subject);
      return { clip, box: box3 };
    });
    if (new Set(p.subject_safe_boxes.map((x) => x.clip)).size !== p.clip_order.length || p.clip_order.some((id) => !p.subject_safe_boxes.some((x) => x.clip === id))) fail2("one safety box per ordered clip");
    for (const id of p.clip_order) if (asset(p, id).duration < p.duration) fail2("source duration too short");
    return assertTextLayout(p, 950, 55, 4);
  }
  function sample60(spec, seconds) {
    const p = validateParameters19(spec), { t, u } = clock3(p, seconds), i = cutIndex(p.cut_cues, t), id = p.clip_order[i], b = p.subject_safe_boxes.find((x) => x.clip === id).box, subject = rect3(viewport.x + b.x * viewport.w, viewport.y + b.y * viewport.h, b.w * viewport.w, b.h * viewport.h);
    const caption3 = p.caption_cues.find((q) => t >= q.start && t < q.end);
    return { time: t, progress: u, shot_index: i, layers: [layer(p, id, t - p.cut_cues[i], FULL, viewport)], subject, caption_box: captionBox(subject), caption: caption3?.text ?? "", caption_subject_overlap: overlap(captionBox(subject), subject) };
  }
  function render60(spec, seconds, frames) {
    const p = validateParameters19(spec), s = sample60(spec, seconds), c = p.palette;
    return svg2(ID60, p, tx("SAHA NOTU / " + String(s.shot_index + 1).padStart(2, "0"), 64, 100, 950, 30, c.accent, 1) + tx(p.title, 64, 190, 950, 55, c.ink, 4) + drawLayers(p, s.layers, "caption", frames) + (s.caption ? panel(s.caption_box, c.background, 0.98) + tx(s.caption, s.caption_box.x + 20, s.caption_box.y + 58, s.caption_box.w - 40, 42, c.ink, 3) : "") + `<rect x="60" y="1536" width="${fmt2(960 * s.progress)}" height="8" fill="${c.accent}"/>` + subtitle(p, s.time, 1650) + proxyMark(p));
  }
  function validateSpec60(spec) {
    return deepFreeze({ id: ID60, version: "1.0.0", parameters: validateParameters19(spec) });
  }

  // renderers/template-registry/modules/1bd00339694d-timelapse-mosaic.mjs
  var bd00339694d_timelapse_mosaic_exports = {};
  __export(bd00339694d_timelapse_mosaic_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE62,
    ID: () => ID61,
    METADATA: () => METADATA53,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA61,
    SOURCE_ID: () => SOURCE_ID61,
    render: () => render61,
    sample: () => sample61,
    validateSpec: () => validateSpec61
  });
  var ID61 = "timelapse-mosaic";
  var SOURCE_ID61 = "source-lemo-style-city-symphony";
  var DEFAULT_PALETTE62 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA61 = schema2({ clip_order: refsSchema, time_remap: remapSchema, mosaic_columns: num(2, 5, true), reveal_cues: arr2(num(0, 0.72), 2, 5) });
  var METADATA53 = metadata2("Zaman Mozai\u011Fi \xB7 \xF6zg\xFCn edit", "registered-time-ribbons", "staggered vertical shutters; monotone source remapping preserves spatial registration", ["compact title 54", "row index 32", "caption 42"]);
  function validateParameters20(spec) {
    const p = base5(spec, ID61, ["clip_order", "time_remap", "mosaic_columns", "reveal_cues"]), r = spec.parameters;
    p.clip_order = refs(r.clip_order, p, "clip_order", 2, 3);
    p.time_remap = remap(r.time_remap, Math.min(...p.clip_order.map((id) => asset(p, id).duration)) - 0.5);
    p.mosaic_columns = number2(r.mosaic_columns, "mosaic_columns", 2, 5, true);
    p.reveal_cues = list3(r.reveal_cues, "reveal_cues", p.mosaic_columns, p.mosaic_columns).map((x) => number2(x, "reveal cue", 0, 0.72));
    if (p.reveal_cues.some((x, i) => i && x <= p.reveal_cues[i - 1])) fail2("ordered shutter reveals required");
    return assertTextLayout(p, 950, 56, 4);
  }
  function sample61(spec, seconds) {
    const p = validateParameters20(spec), { t, u } = clock3(p, seconds), source = sourceAt(p.time_remap, u), n = p.mosaic_columns, rows = p.clip_order.length, h = 1080 / rows, layers = [];
    for (let row = 0; row < rows; row++) for (let col = 0; col < n; col++) {
      const target7 = rect3(60 + 960 * col / n, 450 + row * h, 960 / n, h - 12), reveal = smooth2((u - p.reveal_cues[col]) / 0.2);
      layers.push(layer(p, p.clip_order[row], source + row * 0.15, { x: col / n, y: 0, w: 1 / n, h: 1 }, target7, { mask: [{ x: target7.x, y: target7.y }, { x: target7.x + target7.w * reveal, y: target7.y }, { x: target7.x + target7.w * reveal, y: target7.y + target7.h }, { x: target7.x, y: target7.y + target7.h }], reveal, row, column: col }));
    }
    return { time: t, progress: u, source_time: source, layers, registered_columns: Array.from({ length: n }, (_, i) => ({ x: i / n, w: 1 / n })), reveals: p.reveal_cues.map((q) => smooth2((u - q) / 0.2)) };
  }
  function render61(spec, seconds, frames) {
    const p = validateParameters20(spec), s = sample61(spec, seconds), c = p.palette;
    return svg2(ID61, p, tx("ZAMAN / MEK\xC2N", 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 198, 950, 56, c.ink, 4) + drawLayers(p, s.layers, "mosaic", frames) + p.clip_order.map((id, i) => tx(`KAYIT ${String(i + 1).padStart(2, "0")}`, 74, 490 + i * 1080 / p.clip_order.length, 500, 28, c.ink, 1)).join("") + subtitle(p, s.time, 1660) + proxyMark(p));
  }
  function validateSpec61(spec) {
    return deepFreeze({ id: ID61, version: "1.0.0", parameters: validateParameters20(spec) });
  }

  // renderers/template-registry/modules/8b15403a9e6f-footage-diagonal-montage.mjs
  var b15403a9e6f_footage_diagonal_montage_exports = {};
  __export(b15403a9e6f_footage_diagonal_montage_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE63,
    ID: () => ID62,
    METADATA: () => METADATA54,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA62,
    SOURCE_ID: () => SOURCE_ID62,
    render: () => render62,
    sample: () => sample62,
    validateSpec: () => validateSpec62
  });
  var ID62 = "footage-diagonal-montage";
  var SOURCE_ID62 = "source-lemo-style-kino-montage";
  var DEFAULT_PALETTE63 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA62 = schema2({ clip_order: refsSchema, diagonal_angles: arr2(num(15, 70), 2, 5), headline_cues: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(120) }), 1, 8), cut_beats: arr2(num(0, 45), 3, 6) });
  var METADATA54 = metadata2("Diyagonal Montaj \xB7 \xF6zg\xFCn edit", "complementary-diagonal-shutters", "complementary clipping planes exchange two shots on supplied beats", ["angled kicker 32", "headline 62", "beat caption 42"]);
  var target = rect3(60, 430, 960, 1100);
  var corners = [{ x: 60, y: 430 }, { x: 1020, y: 430 }, { x: 1020, y: 1530 }, { x: 60, y: 1530 }];
  function validateParameters21(spec) {
    const p = base5(spec, ID62, ["clip_order", "diagonal_angles", "headline_cues", "cut_beats"]), r = spec.parameters;
    p.clip_order = refs(r.clip_order, p, "clip_order", 2, 5);
    p.cut_beats = cuts(r.cut_beats, p.clip_order.length, p.duration, "cut_beats");
    if (p.duration - p.cut_beats.at(-2) < 1.5) fail2("last diagonal shot needs 1.5s for wipe and final hold");
    p.diagonal_angles = list3(r.diagonal_angles, "angles", p.clip_order.length, p.clip_order.length).map((x) => number2(x, "angle", 15, 70));
    p.headline_cues = cueArray(r.headline_cues, p.duration, "headline_cues");
    for (const q of p.headline_cues) fitText2(q.text, { width: 920, maximum: 38, minimum: 30, maxLines: 2 });
    if (p.clip_order.some((id) => asset(p, id).duration < p.duration)) fail2("source too short");
    return assertTextLayout(p, 950, 62, 3);
  }
  function sample62(spec, seconds) {
    const p = validateParameters21(spec), { t, u } = clock3(p, seconds), i = cutIndex(p.cut_beats, t), q = smooth2((t - p.cut_beats[i]) / 0.65), a = p.diagonal_angles[i] * Math.PI / 180, nx = Math.cos(a), ny = Math.sin(a), values = corners.map((pt2) => nx * pt2.x + ny * pt2.y), limit = lerp2(Math.min(...values) - 1, Math.max(...values) + 1, q), incoming = clipHalfPlane(corners, nx, ny, limit, true), outgoing = clipHalfPlane(corners, nx, ny, limit, false), previous = Math.max(0, i - 1);
    return { time: t, progress: u, shot_index: i, wipe: q, incoming, outgoing, partition_area: area(incoming) + area(outgoing), layers: [layer(p, p.clip_order[previous], Math.max(0, t - p.cut_beats[previous]), FULL, target, { mask: outgoing }), layer(p, p.clip_order[i], t - p.cut_beats[i], FULL, target, { mask: incoming })], headline: p.headline_cues.find((x) => t >= x.start && t < x.end)?.text ?? "" };
  }
  function render62(spec, seconds, frames) {
    const p = validateParameters21(spec), s = sample62(spec, seconds), c = p.palette;
    return svg2(ID62, p, `<path d="M60 100L480 60L480 126L60 166Z" fill="${c.accent}"/>` + tx("KESME / AKS", 84, 119, 340, 30, c.background, 1) + tx(p.title, 60, 240, 950, 62, c.ink, 3) + drawLayers(p, s.layers, "diagonal", frames) + (s.headline ? panel(rect3(60, 1432, 960, 98), c.background, 0.96) + tx(s.headline, 80, 1488, 920, 38, c.ink, 2) : "") + subtitle(p, s.time, 1660) + proxyMark(p));
  }
  function validateSpec62(spec) {
    return deepFreeze({ id: ID62, version: "1.0.0", parameters: validateParameters21(spec) });
  }

  // renderers/template-registry/modules/46976cc2886d-broadcast-footage-rundown.mjs
  var cc2886d_broadcast_footage_rundown_exports = {};
  __export(cc2886d_broadcast_footage_rundown_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE64,
    ID: () => ID63,
    METADATA: () => METADATA55,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA63,
    SOURCE_ID: () => SOURCE_ID63,
    render: () => render63,
    sample: () => sample63,
    validateSpec: () => validateSpec63
  });
  var ID63 = "broadcast-footage-rundown";
  var SOURCE_ID63 = "source-lemo-style-news-package";
  var DEFAULT_PALETTE64 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA63 = schema2({ rundown: arr2(obj({ clip: str(36), start: num(0, 45), end: num(0, 45), role: { enum: ["presenter", "field", "detail"] }, topic: str(42) }), 3, 6), clip_paths: refsSchema, lower_thirds: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(120) }), 1, 8), return_cues: arr2(num(0.1, 45), 1, 5) });
  var METADATA55 = metadata2("Yay\u0131n Ak\u0131\u015F\u0131 \xB7 \xF6zg\xFCn edit", "rundown-rail-return-presenter", "rundown handoffs; two-part lower third; explicit presenter return", ["program rail 28", "topic headline 56", "name strap 38"]);
  function validateParameters22(spec) {
    const p = base5(spec, ID63, ["rundown", "clip_paths", "lower_thirds", "return_cues"]), r = spec.parameters;
    p.clip_paths = refs(r.clip_paths, p, "clip_paths", 2, 6);
    let end = 0;
    p.rundown = list3(r.rundown, "rundown", 3, 6).map((v) => {
      keys2(v, ["clip", "start", "end", "role", "topic"]);
      const q = { clip: ref(v.clip, p), start: number2(v.start, "slot start", 0, p.duration), end: number2(v.end, "slot end", 0, p.duration), role: choice2(v.role, "role", ["presenter", "field", "detail"]), topic: text2(v.topic, "topic", 42) };
      if (q.start !== end || q.end - q.start < 1.2 || !p.clip_paths.includes(q.clip)) fail2("contiguous rundown slots of at least 1.2s");
      end = q.end;
      fitText2(q.topic, { width: 156, maximum: 28, minimum: 28, maxLines: 4 });
      fitText2(q.topic, { width: 690, maximum: 34, minimum: 30, maxLines: 1 });
      return q;
    });
    if (end !== p.duration || p.rundown[0].role !== "presenter" || p.rundown.at(-1).role !== "presenter") fail2("rundown must return to presenter and cover duration");
    if (p.rundown.at(-1).end - p.rundown.at(-1).start < 1.4) fail2("final presenter slot needs 1.4s for strap completion and hold");
    p.return_cues = list3(r.return_cues, "return cues", 1, 5).map((x) => number2(x, "return cue", 0.1, p.duration));
    const returns = p.rundown.filter((s, i) => i && s.role === "presenter").map((s) => s.start);
    if (JSON.stringify(p.return_cues) !== JSON.stringify(returns)) fail2("return cues must match presenter slots");
    p.lower_thirds = cueArray(r.lower_thirds, p.duration, "lower_thirds");
    for (const q of p.lower_thirds) fitText2(q.text, { width: 700, maximum: 38, minimum: 30, maxLines: 3 });
    if (p.clip_paths.some((id) => asset(p, id).duration < p.duration)) fail2("short source");
    return assertTextLayout(p, 740, 54, 4);
  }
  function sample63(spec, seconds) {
    const p = validateParameters22(spec), { t, u } = clock3(p, seconds), i = p.rundown.findIndex((q) => t >= q.start && t < q.end), slot2 = p.rundown[Math.max(0, i)], strap = p.lower_thirds.find((q) => t >= q.start && t < q.end);
    return { time: t, progress: u, slot_index: Math.max(0, i), role: slot2.role, topic: slot2.topic, strap: strap?.text ?? "", strap_width: 740 * smooth2((t - slot2.start) / 0.45), strap_rule: 740 * smooth2((t - slot2.start - 0.18) / 0.4), rail: p.rundown.map((q) => clamp2((t - q.start) / (q.end - q.start))), layers: [layer(p, slot2.clip, t - slot2.start, FULL, rect3(280, 510, 740, 860))] };
  }
  function render63(spec, seconds, frames) {
    const p = validateParameters22(spec), s = sample63(spec, seconds), c = p.palette;
    let rail = "";
    const railGap = 970 / (p.rundown.length - 1);
    p.rundown.forEach((q, i) => {
      rail += panel(rect3(60, 470 + i * railGap, 166, 5), c.muted) + panel(rect3(60, 470 + i * railGap, 166 * s.rail[i], 5), c.accent) + tx(`${i + 1}. ${q.topic}`, 60, 525 + i * railGap, 156, 28, i === s.slot_index ? c.ink : c.muted, 4);
    });
    return svg2(ID63, p, tx("YAYIN AKI\u015EI", 60, 110, 900, 30, c.accent, 1) + tx(p.title, 280, 204, 740, 54, c.ink, 4) + rail + panel(rect3(280, 424, 740, 70), c.accent) + tx(s.topic, 300, 470, 690, 34, c.background, 1) + drawLayers(p, s.layers, "broadcast", frames) + panel(rect3(280, 1386, s.strap_width, 160), c.background) + panel(rect3(280, 1386, s.strap_rule, 8), c.accent) + (s.strap ? tx(s.strap, 300, 1455, 700, 38, c.ink, 3) : "") + subtitle(p, s.time, 1660) + proxyMark(p));
  }
  function validateSpec63(spec) {
    return deepFreeze({ id: ID63, version: "1.0.0", parameters: validateParameters22(spec) });
  }

  // renderers/template-registry/modules/023676142033-archive-footage-gate.mjs
  var archive_footage_gate_exports = {};
  __export(archive_footage_gate_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE65,
    ID: () => ID64,
    METADATA: () => METADATA56,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA64,
    SOURCE_ID: () => SOURCE_ID64,
    render: () => render64,
    sample: () => sample64,
    validateSpec: () => validateSpec64
  });
  var ID64 = "archive-footage-gate";
  var SOURCE_ID64 = "source-lemo-style-newsreel";
  var DEFAULT_PALETTE65 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA64 = schema2({ clip_order: refsSchema, intertitle_cues: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(120) }), 1, 8), gate_weave: num(0, 8), grain_seed: num(1, 1e4, true) });
  var METADATA56 = metadata2("Ar\u015Fiv Kap\u0131s\u0131 \xB7 \xF6zg\xFCn edit", "perforated-archive-gate", "deterministic bounded gate weave; original arithmetic grain; timed intertitle gate", ["archive date 30", "serif title 58", "intertitle 46"]);
  function validateParameters23(spec) {
    const p = base5(spec, ID64, ["clip_order", "intertitle_cues", "gate_weave", "grain_seed"]), r = spec.parameters;
    p.clip_order = refs(r.clip_order, p, "clip_order", 2, 4);
    p.intertitle_cues = cueArray(r.intertitle_cues, p.duration, "intertitle_cues");
    for (const q of p.intertitle_cues) fitText2(q.text, { width: 664, maximum: 46, minimum: 30, maxLines: 4 });
    p.gate_weave = number2(r.gate_weave, "gate_weave", 0, 8);
    p.grain_seed = number2(r.grain_seed, "grain_seed", 1, 1e4, true);
    if (p.clip_order.some((id) => asset(p, id).duration < p.duration)) fail2("short archive source");
    return assertTextLayout(p, 930, 51, 4);
  }
  function sample64(spec, seconds) {
    const p = validateParameters23(spec), { t, u } = clock3(p, seconds), i = Math.min(p.clip_order.length - 1, Math.floor(u * p.clip_order.length)), envelope = Math.sin(Math.PI * u), dx = p.gate_weave * envelope * Math.sin(13 * u), dy = p.gate_weave * envelope * Math.cos(17 * u), card = p.intertitle_cues.find((q) => t >= q.start && t < q.end);
    const grain = Array.from({ length: 24 }, (_, j) => ({ x: 140 + (p.grain_seed * 17 + j * 113 + Math.floor(t * 12) * 31) % 800, y: 450 + (p.grain_seed * 29 + j * 191) % 870, radius: 1 + j % 3 }));
    return { time: t, progress: u, gate: { dx: u === 1 ? 0 : dx, dy: u === 1 ? 0 : dy }, grain, card: card?.text ?? "", card_opacity: card ? smooth2((t - card.start) / 0.18) : 0, layers: [layer(p, p.clip_order[i], t, FULL, rect3(120, 430, 840, 920), { transform: { dx: u === 1 ? 0 : dx, dy: u === 1 ? 0 : dy, scale: 1.025, rotation: 0 } })] };
  }
  function render64(spec, seconds, frames) {
    const p = validateParameters23(spec), s = sample64(spec, seconds), c = p.palette;
    let holes = "";
    for (let i = 0; i < 10; i++) holes += panel(rect3(72, 440 + i * 92, 26, 44), c.muted) + panel(rect3(982, 440 + i * 92, 26, 44), c.muted);
    return svg2(ID64, p, tx("AR\u015E\u0130V / \xD6L\xC7\xDCM KAYDI", 72, 108, 930, 30, c.accent, 1) + `<g font-family="serif">${tx(p.title, 72, 210, 930, 51, c.ink, 4)}</g>` + panel(rect3(104, 414, 872, 952), c.muted) + drawLayers(p, s.layers, "archive", frames) + holes + s.grain.map((q) => `<circle cx="${fmt2(q.x)}" cy="${fmt2(q.y)}" r="${q.radius}" fill="${c.ink}" opacity="0.16"/>`).join("") + (s.card ? `<g opacity="${fmt2(s.card_opacity)}">${panel(rect3(160, 660, 760, 460), c.background)}${tx(s.card, 208, 816, 664, 46, c.ink, 4)}</g>` : "") + subtitle(p, s.time, 1540) + proxyMark(p));
  }
  function validateSpec64(spec) {
    return deepFreeze({ id: ID64, version: "1.0.0", parameters: validateParameters23(spec) });
  }

  // renderers/template-registry/modules/b7bdec0914d1-silent-footage-intertitles.mjs
  var b7bdec0914d1_silent_footage_intertitles_exports = {};
  __export(b7bdec0914d1_silent_footage_intertitles_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE66,
    ID: () => ID65,
    METADATA: () => METADATA57,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA65,
    SOURCE_ID: () => SOURCE_ID65,
    render: () => render65,
    sample: () => sample65,
    validateSpec: () => validateSpec65
  });
  var ID65 = "silent-footage-intertitles";
  var SOURCE_ID65 = "source-lemo-style-silent-film";
  var DEFAULT_PALETTE66 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA65 = schema2({ clip_order: refsSchema, intertitles: arr2(obj({ start: num(0, 45), end: num(0, 45), text: str(120) }), 1, 8), retime_segments: remapSchema, hold_frames: pauseSchema });
  var METADATA57 = metadata2("Sessiz Ara Yaz\u0131 \xB7 \xF6zg\xFCn edit", "alternating-action-intertitle", "continuous piecewise retiming; held source clocks; ornamented intertitle alternation", ["chapter 30", "title 54", "centered intertitle 48"]);
  function validateParameters24(spec) {
    const p = base5(spec, ID65, ["clip_order", "intertitles", "retime_segments", "hold_frames"]), r = spec.parameters;
    p.clip_order = refs(r.clip_order, p, "clip_order", 2, 4);
    p.intertitles = cueArray(r.intertitles, p.duration, "intertitles");
    for (const q of p.intertitles) fitText2(q.text, { width: 720, maximum: 48, minimum: 30, maxLines: 6 });
    p.retime_segments = remap(r.retime_segments, Math.min(...p.clip_order.map((id) => asset(p, id).duration)), "retime_segments");
    p.hold_frames = pauses(r.hold_frames, p.duration, "hold_frames");
    if (p.hold_frames.reduce((n, q) => n + q.end - q.start, 0) > p.duration / 2) fail2("holds consume too much action time");
    return assertTextLayout(p, 888, 54, 4);
  }
  function sample65(spec, seconds) {
    const p = validateParameters24(spec), { t, u, end } = clock3(p, seconds), holdDuration = p.hold_frames.reduce((n, q) => n + q.end - q.start, 0), v = clamp2(pauseClock(t, p.hold_frames) / (end - holdDuration)), i = Math.min(p.clip_order.length - 1, Math.floor(v * p.clip_order.length)), source = sourceAt(p.retime_segments, v), card = p.intertitles.find((q) => t >= q.start && t < q.end), iris = card ? smooth2((t - card.start) / 0.25) : 0;
    return { time: t, progress: u, retime_progress: v, source_time: source, held: p.hold_frames.some((q) => t >= q.start && t <= q.end), intertitle: card?.text ?? "", iris, layer_opacity: card ? 1 - iris : 1, layers: [layer(p, p.clip_order[i], source, FULL, rect3(96, 480, 888, 1e3), { opacity: card ? 1 - iris : 1 })] };
  }
  function render65(spec, seconds, frames) {
    const p = validateParameters24(spec), s = sample65(spec, seconds), c = p.palette;
    const card = s.intertitle ? `<g opacity="${fmt2(s.iris)}">${panel(rect3(96, 480, 888, 1e3), c.background)}<rect x="130" y="518" width="820" height="924" fill="none" stroke="${c.muted}" stroke-width="3"/><path d="M220 700H860M220 1260H860M440 680L540 655L640 680" fill="none" stroke="${c.accent}" stroke-width="4"/>${tx(s.intertitle, 180, 890, 720, 48, c.ink, 6)}</g>` : "";
    return svg2(ID65, p, tx("EYLEM / ARA YAZI", 96, 110, 888, 30, c.accent, 1) + tx(p.title, 96, 210, 888, 54, c.ink, 4) + drawLayers(p, s.layers, "silent", frames) + card + subtitle(p, s.time, 1650) + proxyMark(p));
  }
  function validateSpec65(spec) {
    return deepFreeze({ id: ID65, version: "1.0.0", parameters: validateParameters24(spec) });
  }

  // renderers/template-registry/modules/830974c26e42-liminal-footage-inspection.mjs
  var c26e42_liminal_footage_inspection_exports = {};
  __export(c26e42_liminal_footage_inspection_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE67,
    ID: () => ID66,
    METADATA: () => METADATA58,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA66,
    SOURCE_ID: () => SOURCE_ID66,
    render: () => render66,
    sample: () => sample66,
    validateSpec: () => validateSpec66
  });
  var ID66 = "liminal-footage-inspection";
  var SOURCE_ID66 = "source-lemo-style-backrooms";
  var DEFAULT_PALETTE67 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA66 = schema2({ clip_in_out: obj({ clip: str(36), in: num(0, 3600), out: num(0.1, 3600) }), crop_path: pathSchema, drift_amount: num(0, 0.025), inspection_cues: arr2(obj({ start: num(0, 45), end: num(0.1, 45), text: str(80), point: pointSchema }), 1, 8) });
  var METADATA58 = metadata2("Kesintisiz \u0130nceleme \xB7 \xF6zg\xFCn edit", "continuous-passage-inspection-rail", "single trim; bounded source crop path and damped inspection drift", ["timecode 28", "inspection title 56", "margin note 34"]);
  function validateParameters25(spec) {
    const p = base5(spec, ID66, ["clip_in_out", "crop_path", "drift_amount", "inspection_cues"]), r = spec.parameters;
    keys2(r.clip_in_out, ["clip", "in", "out"]);
    const clip = ref(r.clip_in_out.clip, p);
    p.clip_in_out = { clip, in: number2(r.clip_in_out.in, "clip in", 0, asset(p, clip).duration), out: number2(r.clip_in_out.out, "clip out", 0, asset(p, clip).duration) };
    if (p.clip_in_out.out - p.clip_in_out.in < 1) fail2("inspection trim at least 1s");
    p.crop_path = cropPath(r.crop_path);
    p.drift_amount = number2(r.drift_amount, "drift_amount", 0, 0.025);
    if (p.crop_path.some((b) => b.x < p.drift_amount || b.y < p.drift_amount || b.x + b.w > 1 - p.drift_amount || b.y + b.h > 1 - p.drift_amount)) fail2("crop path must reserve drift margin");
    let prev = 0;
    p.inspection_cues = list3(r.inspection_cues, "inspection cues", 1, 8).map((q) => {
      keys2(q, ["start", "end", "text", "point"]);
      const a = number2(q.start, "inspection start", 0, p.duration), b = number2(q.end, "inspection end", 0, p.duration);
      if (a < prev || b - a < 0.6 || a > p.duration - 1.1) fail2("ordered inspection cues");
      prev = b;
      const label5 = text2(q.text, "inspection label", 80);
      fitText2(label5, { width: 750, maximum: 34, minimum: 30, maxLines: 2 });
      return { start: a, end: b, text: label5, point: point3(q.point) };
    });
    return assertTextLayout(p, 950, 55, 4);
  }
  function sample66(spec, seconds) {
    const p = validateParameters25(spec), { t, u } = clock3(p, seconds), b = cropAt(p.crop_path, u), drift = p.drift_amount * Math.sin(Math.PI * u), crop = { ...b, x: b.x + (u === 1 ? 0 : drift * Math.sin(7 * u)), y: b.y + (u === 1 ? 0 : drift * Math.cos(9 * u)) }, a = p.clip_in_out, source = lerp2(a.in, a.out, u), note = p.inspection_cues.find((q) => t >= q.start && t < q.end), target7 = rect3(60, 420, 830, 1110), pt2 = note ? projected(crop, target7, note.point) : { x: 475, y: 975 };
    return { time: t, progress: u, source_time: source, drift: u === 1 ? 0 : drift, exposure_ev: -0.18 * smooth2(u), inspection: note?.text ?? "", anchor: { x: Math.max(76, Math.min(874, pt2.x)), y: Math.max(436, Math.min(1514, pt2.y)) }, layers: [layer(p, a.clip, source, crop, target7, { exposure_ev: -0.18 * smooth2(u) })] };
  }
  function render66(spec, seconds, frames) {
    const p = validateParameters25(spec), s = sample66(spec, seconds), c = p.palette;
    const a = s.anchor;
    return svg2(ID66, p, tx("KES\u0130NT\u0130S\u0130Z KAYIT", 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 198, 950, 55, c.ink, 4) + drawLayers(p, s.layers, "inspection", frames) + panel(rect3(60, 420, 830, 1110), "#000000", -s.exposure_ev * 0.3) + `<path d="M${fmt2(a.x - 24)} ${fmt2(a.y)}H${fmt2(a.x + 24)}M${fmt2(a.x)} ${fmt2(a.y - 24)}V${fmt2(a.y + 24)}" stroke="${c.accent}" stroke-width="4"/>` + tx("\u0130Z", 922, 465, 90, 26, c.accent, 1) + panel(rect3(932, 625, 5, 800), c.muted) + panel(rect3(922, 625 + 800 * s.progress, 25, 8), c.accent) + (s.inspection ? panel(rect3(80, 1400, 790, 110), c.background, 0.97) + tx(s.inspection, 100, 1460, 750, 34, c.ink, 2) : "") + subtitle(p, s.time, 1660) + proxyMark(p));
  }
  function validateSpec66(spec) {
    return deepFreeze({ id: ID66, version: "1.0.0", parameters: validateParameters25(spec) });
  }

  // renderers/template-registry/modules/59b5267aabb9-screen-focus-follow.mjs
  var b5267aabb9_screen_focus_follow_exports = {};
  __export(b5267aabb9_screen_focus_follow_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE68,
    ID: () => ID67,
    METADATA: () => METADATA59,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA67,
    SOURCE_ID: () => SOURCE_ID67,
    render: () => render67,
    sample: () => sample67,
    validateSpec: () => validateSpec67
  });
  var ID67 = "screen-focus-follow";
  var SOURCE_ID67 = "source-lemo-style-living-screencast";
  var DEFAULT_PALETTE68 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA67 = schema2({ screen_clip: obj({ clip: str(36), in: num(0, 3600), out: num(1, 3600) }), event_cues: arr2(obj({ at: num(0, 45), focus: num(0, 4, true), pointer: pointSchema, label: str(80) }), 2, 8), focus_rectangles: arr2(boxSchema, 2, 5), zoom_bounds: arr2(num(1, 4), 2, 2) });
  var METADATA59 = metadata2("Ekran Oda\u011F\u0131 \xB7 \xF6zg\xFCn edit", "screen-window-step-card", "event-indexed crop and cursor interpolation; bounded focus zoom", ["step counter 30", "title 58", "focus instruction 38"]);
  function focusCrop(b, bounds3) {
    const z = Math.max(bounds3[0], Math.min(bounds3[1], Math.min(1 / b.w, 1 / b.h))), w = 1 / z, h = 1 / z;
    return { x: Math.max(0, Math.min(1 - w, b.x + b.w / 2 - w / 2)), y: Math.max(0, Math.min(1 - h, b.y + b.h / 2 - h / 2)), w, h };
  }
  function validateParameters26(spec) {
    const p = base5(spec, ID67, ["screen_clip", "event_cues", "focus_rectangles", "zoom_bounds"]), r = spec.parameters;
    keys2(r.screen_clip, ["clip", "in", "out"]);
    const id = ref(r.screen_clip.clip, p);
    p.screen_clip = { clip: id, in: number2(r.screen_clip.in, "screen in", 0, asset(p, id).duration), out: number2(r.screen_clip.out, "screen out", 1, asset(p, id).duration) };
    if (p.screen_clip.out <= p.screen_clip.in) fail2("positive screen trim");
    p.focus_rectangles = list3(r.focus_rectangles, "focus rectangles", 2, 5).map((b) => box(b));
    p.zoom_bounds = list3(r.zoom_bounds, "zoom bounds", 2, 2).map((z) => number2(z, "zoom", 1, 4));
    if (p.zoom_bounds[0] > p.zoom_bounds[1]) fail2("ordered zoom bounds");
    let at2 = -1;
    p.event_cues = list3(r.event_cues, "event cues", 2, 8).map((q) => {
      keys2(q, ["at", "focus", "pointer", "label"]);
      const v = { at: number2(q.at, "event at", 0, p.duration - 0.8), focus: number2(q.focus, "focus index", 0, p.focus_rectangles.length - 1, true), pointer: point3(q.pointer), label: text2(q.label, "event label", 80) };
      fitText2(v.label, { width: 890, maximum: 38, minimum: 30, maxLines: 3 });
      if (v.at <= at2) fail2("ordered event times");
      at2 = v.at;
      const b = focusCrop(p.focus_rectangles[v.focus], p.zoom_bounds);
      if (v.pointer.x < b.x || v.pointer.x > b.x + b.w || v.pointer.y < b.y || v.pointer.y > b.y + b.h) fail2("event pointer outside bounded focus crop");
      return v;
    });
    if (p.event_cues[0].at !== 0) fail2("initial screen event at zero required");
    return assertTextLayout(p, 950, 54, 4);
  }
  function sample67(spec, seconds) {
    const p = validateParameters26(spec), { t, u } = clock3(p, seconds);
    let i = 0;
    while (i < p.event_cues.length - 1 && t >= p.event_cues[i + 1].at) i++;
    const a = p.event_cues[i], b = p.event_cues[Math.min(i + 1, p.event_cues.length - 1)], q = a === b ? 1 : smooth2((t - a.at) / (b.at - a.at)), ca = focusCrop(p.focus_rectangles[a.focus], p.zoom_bounds), cb = focusCrop(p.focus_rectangles[b.focus], p.zoom_bounds), crop = Object.fromEntries(["x", "y", "w", "h"].map((k) => [k, lerp2(ca[k], cb[k], q)])), pt2 = { x: lerp2(a.pointer.x, b.pointer.x, q), y: lerp2(a.pointer.y, b.pointer.y, q) }, target7 = rect3(60, 480, 960, 900), source = lerp2(p.screen_clip.in, p.screen_clip.out, u);
    return { time: t, progress: u, event_index: i, label: a.label, zoom: 1 / crop.w, pointer: projected(crop, target7, pt2), layers: [layer(p, p.screen_clip.clip, source, crop, target7)] };
  }
  function render67(spec, seconds, frames) {
    const p = validateParameters26(spec), s = sample67(spec, seconds), c = p.palette;
    return svg2(ID67, p, tx(`ADIM ${s.event_index + 1} / ${p.event_cues.length}`, 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 198, 950, 54, c.ink, 4) + panel(rect3(60, 414, 960, 66), c.muted) + tx("YEREL EKRAN \xB7 ODAK TAK\u0130B\u0130", 84, 458, 890, 28, c.background, 1) + drawLayers(p, s.layers, "screen", frames) + `<path d="M${fmt2(s.pointer.x)} ${fmt2(s.pointer.y)}l12 38 10-17 18-4Z" fill="${c.ink}" stroke="${c.background}" stroke-width="4"/>` + panel(rect3(60, 1420, 960, 160), c.background) + panel(rect3(60, 1420, 8, 160), c.accent) + tx(s.label, 92, 1490, 890, 38, c.ink, 3) + subtitle(p, s.time, 1690) + proxyMark(p));
  }
  function validateSpec67(spec) {
    return deepFreeze({ id: ID67, version: "1.0.0", parameters: validateParameters26(spec) });
  }

  // renderers/template-registry/modules/15a80c4f2fc4-georeferenced-footage-track.mjs
  var a80c4f2fc4_georeferenced_footage_track_exports = {};
  __export(a80c4f2fc4_georeferenced_footage_track_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE69,
    ID: () => ID68,
    METADATA: () => METADATA60,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA68,
    SOURCE_ID: () => SOURCE_ID68,
    render: () => render68,
    sample: () => sample68,
    validateSpec: () => validateSpec68
  });
  var ID68 = "georeferenced-footage-track";
  var SOURCE_ID68 = "source-lemo-style-satellite-briefing";
  var DEFAULT_PALETTE69 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA68 = schema2({ imagery_path: str(36), coordinate_system: obj({ type: { enum: ["local_metres"] }, width_metres: num(1, 1e6), height_metres: num(1, 1e6), origin_easting: num(-1e7, 1e7), origin_northing: num(-1e7, 1e7) }), route_coordinates: arr2(obj({ east: num(0, 1e6), north: num(0, 1e6), label: str(48) }), 2, 8), scale_bounds: obj({ min_zoom: num(1, 4), max_zoom: num(1, 4), scale_bar_metres: num(0.1, 1e5) }) });
  var METADATA60 = metadata2("Koordinat Brifingi \xB7 \xF6zg\xFCn edit", "map-viewport-scale-ledger", "distance-parameterized route; bounded map crop; metre-correct scale bar", ["coordinate kicker 30", "map headline 54", "scale ledger 32"]);
  var target2 = rect3(60, 420, 960, 1050);
  function validateParameters27(spec) {
    const p = base5(spec, ID68, ["imagery_path", "coordinate_system", "route_coordinates", "scale_bounds"]), r = spec.parameters;
    p.imagery_path = ref(r.imagery_path, p);
    keys2(r.coordinate_system, ["type", "width_metres", "height_metres", "origin_easting", "origin_northing"]);
    const m = r.coordinate_system;
    p.coordinate_system = { type: choice2(m.type, "coordinate system", ["local_metres"]), width_metres: number2(m.width_metres, "map width", 1, 1e6), height_metres: number2(m.height_metres, "map height", 1, 1e6), origin_easting: number2(m.origin_easting, "origin easting", -1e7, 1e7), origin_northing: number2(m.origin_northing, "origin northing", -1e7, 1e7) };
    p.route_coordinates = list3(r.route_coordinates, "route", 2, 8).map((v) => {
      keys2(v, ["east", "north", "label"]);
      return { east: number2(v.east, "east", 0, m.width_metres), north: number2(v.north, "north", 0, m.height_metres), label: text2(v.label, "route label", 48) };
    });
    if (p.route_coordinates.some((q, i) => i && Math.hypot(q.east - p.route_coordinates[i - 1].east, q.north - p.route_coordinates[i - 1].north) < 0.01)) fail2("nonzero route legs required");
    keys2(r.scale_bounds, ["min_zoom", "max_zoom", "scale_bar_metres"]);
    p.scale_bounds = { min_zoom: number2(r.scale_bounds.min_zoom, "minimum zoom", 1, 4), max_zoom: number2(r.scale_bounds.max_zoom, "maximum zoom", 1, 4), scale_bar_metres: number2(r.scale_bounds.scale_bar_metres, "scale bar", 0.1, 1e5) };
    if (p.scale_bounds.min_zoom > p.scale_bounds.max_zoom || p.scale_bounds.scale_bar_metres * p.scale_bounds.max_zoom / m.width_metres > 0.6) fail2("scale bar or zoom outside viewport");
    for (const q of p.route_coordinates) fitText2("Konum: " + q.label, { width: 920, maximum: 30, minimum: 30, maxLines: 2 });
    return assertTextLayout(p, 950, 54, 4);
  }
  function sample68(spec, seconds) {
    const p = validateParameters27(spec), { t, u } = clock3(p, seconds), m = p.coordinate_system, r = p.route_coordinates, lengths = r.slice(1).map((q2, i) => Math.hypot(q2.east - r[i].east, q2.north - r[i].north)), total = lengths.reduce((a, b) => a + b, 0);
    let remaining = u * total, leg = 0;
    while (leg < lengths.length - 1 && remaining > lengths[leg]) {
      remaining -= lengths[leg];
      leg++;
    }
    const q = remaining / lengths[leg], pos = { east: lerp2(r[leg].east, r[leg + 1].east, q), north: lerp2(r[leg].north, r[leg + 1].north, q) }, zoom = lerp2(p.scale_bounds.min_zoom, p.scale_bounds.max_zoom, smooth2(u)), w = 1 / zoom, crop = { x: Math.max(0, Math.min(1 - w, pos.east / m.width_metres - w / 2)), y: Math.max(0, Math.min(1 - w, pos.north / m.height_metres - w / 2)), w, h: w }, project5 = (v) => projected(crop, target2, { x: v.east / m.width_metres, y: v.north / m.height_metres }), route2 = [...r.slice(0, leg + 1), pos].map(project5), scale = target2.w * p.scale_bounds.scale_bar_metres / (m.width_metres * crop.w);
    return { time: t, progress: u, route_distance: u * total, total_distance: total, position: pos, location_label: r[Math.min(r.length - 1, leg + (q >= 0.5 ? 1 : 0))].label, world_coordinates: { easting: m.origin_easting + pos.east, northing: m.origin_northing + pos.north }, camera_zoom: zoom, route: route2, marker: project5(pos), scale_bar_pixels: scale, scale_bar_metres: p.scale_bounds.scale_bar_metres, layers: [layer(p, p.imagery_path, Math.min(t, asset(p, p.imagery_path).duration), crop, target2)] };
  }
  function render68(spec, seconds, frames) {
    const p = validateParameters27(spec), s = sample68(spec, seconds), c = p.palette;
    return svg2(ID68, p, tx("YEREL METRE KOORD\u0130NATLARI", 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 198, 950, 54, c.ink, 4) + drawLayers(p, s.layers, "geo", frames) + `<defs><clipPath id="route-viewport">${panel(target2, "#FFFFFF")}</clipPath></defs><g clip-path="url(#route-viewport)"><path d="${path(s.route, false)}" fill="none" stroke="${c.accent}" stroke-width="10"/><circle cx="${fmt2(s.marker.x)}" cy="${fmt2(s.marker.y)}" r="16" fill="${c.ink}" stroke="${c.background}" stroke-width="5"/></g><path d="M80 1530H${fmt2(80 + s.scale_bar_pixels)}M80 1516V1544M${fmt2(80 + s.scale_bar_pixels)} 1516V1544" stroke="${c.ink}" stroke-width="4"/>` + panel(rect3(60, 1325, 960, 145), c.background, 0.96) + tx("Konum: " + s.location_label, 80, 1368, 920, 30, c.ink, 2) + tx(`E ${s.world_coordinates.easting.toFixed(1)} / N ${s.world_coordinates.northing.toFixed(1)}`, 80, 1450, 920, 28, c.muted, 1) + tx(`${s.scale_bar_metres} m \xB7 ${s.route_distance.toFixed(1)} m izlenen rota`, 80, 1590, 920, 32, c.ink, 2) + subtitle(p, s.time, 1710) + proxyMark(p));
  }
  function validateSpec68(spec) {
    return deepFreeze({ id: ID68, version: "1.0.0", parameters: validateParameters27(spec) });
  }

  // renderers/template-registry/modules/06f5237f5517-footage-tactical-overlay.mjs
  var f5237f5517_footage_tactical_overlay_exports = {};
  __export(f5237f5517_footage_tactical_overlay_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE70,
    ID: () => ID69,
    METADATA: () => METADATA61,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA69,
    SOURCE_ID: () => SOURCE_ID69,
    render: () => render69,
    sample: () => sample69,
    validateSpec: () => validateSpec69
  });

  // renderers/template-registry/modules/triage-cue-progress.mjs
  function cueInk(seconds, start, stop, activeEnd) {
    const span = Math.min(0.45, (stop - start) * 0.45, activeEnd - start);
    if (!(span > 0)) throw new RangeError("positive validated cue interval required");
    if (seconds <= start) return 0;
    if (seconds >= start + span) return 1;
    const u = (seconds - start) / span;
    return u * u * (3 - 2 * u);
  }

  // renderers/template-registry/modules/06f5237f5517-footage-tactical-overlay.mjs
  var ID69 = "footage-tactical-overlay";
  var SOURCE_ID69 = "source-lemo-style-telestrator";
  var DEFAULT_PALETTE70 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA69 = schema2({ clip_path: obj({ clip: str(36), in: num(0, 3600), out: num(1, 3600) }), subject_tracks: arr2(obj({ id: str(36), points: arr2(obj({ at: num(0, 1), x: num(0, 1), y: num(0, 1) }), 2, 12) }), 2, 6), pause_cues: pauseSchema, annotation_paths: arr2(obj({ from: str(36), to: str(36), bend: num(-0.35, 0.35), start: num(0, 45), end: num(0.1, 45), text: str(60) }), 1, 6) });
  var METADATA61 = metadata2("Hareket Analizi \xB7 \xF6zg\xFCn edit", "tracked-action-freeze-arrows", "paused source clock; source-space tracks; drawn anchored tactical curves", ["analysis slug 30", "title 58", "source-clock band 30"]);
  var target3 = rect3(60, 450, 960, 920);
  function validateParameters28(spec) {
    const p = base5(spec, ID69, ["clip_path", "subject_tracks", "pause_cues", "annotation_paths"]), r = spec.parameters;
    keys2(r.clip_path, ["clip", "in", "out"]);
    const id = ref(r.clip_path.clip, p);
    p.clip_path = { clip: id, in: number2(r.clip_path.in, "clip in", 0, asset(p, id).duration), out: number2(r.clip_path.out, "clip out", 1, asset(p, id).duration) };
    if (p.clip_path.out <= p.clip_path.in) fail2("positive tactical trim required");
    p.subject_tracks = list3(r.subject_tracks, "subject tracks", 2, 6).map((v) => {
      keys2(v, ["id", "points"]);
      return { id: token(v.id, "track ID"), points: track(v.points) };
    });
    if (new Set(p.subject_tracks.map((v) => v.id)).size !== p.subject_tracks.length) fail2("unique track IDs");
    p.pause_cues = pauses(r.pause_cues, p.duration, "pause_cues");
    if (p.pause_cues.reduce((n, q) => n + q.end - q.start, 0) > p.duration / 2) fail2("excess pause time");
    p.annotation_paths = list3(r.annotation_paths, "annotations", 1, 6).map((v) => {
      keys2(v, ["from", "to", "bend", "start", "end", "text"]);
      if (!p.subject_tracks.some((q2) => q2.id === v.from) || !p.subject_tracks.some((q2) => q2.id === v.to) || v.from === v.to) fail2("annotation endpoints need distinct known tracks");
      const q = { from: token(v.from), to: token(v.to), bend: number2(v.bend, "arrow bend", -0.35, 0.35), start: number2(v.start, "annotation start", 0, p.duration), end: number2(v.end, "annotation end", 0, p.duration), text: text2(v.text, "annotation text", 60) };
      if (q.end - q.start < 0.6 || q.start > p.duration - 1.1) fail2("annotation readable interval");
      fitText2(q.text, { width: 440, maximum: 28, minimum: 28, maxLines: 2 });
      return q;
    });
    return assertTextLayout(p, 950, 58, 4);
  }
  function sample69(spec, seconds) {
    const p = validateParameters28(spec), { t, u, end } = clock3(p, seconds), held = p.pause_cues.reduce((n, q) => n + q.end - q.start, 0), v = clamp2(pauseClock(t, p.pause_cues) / (end - held)), source = lerp2(p.clip_path.in, p.clip_path.out, v), tracks = p.subject_tracks.map((q) => ({ id: q.id, ...projected(FULL, target3, pointAt(q.points, v)) })), arrows = p.annotation_paths.filter((q) => t >= q.start && t < q.end).map((q) => {
      const a = tracks.find((x) => x.id === q.from), b = tracks.find((x) => x.id === q.to), dx = b.x - a.x, dy = b.y - a.y;
      return { from: q.from, to: q.to, start: { x: a.x, y: a.y }, end: { x: b.x, y: b.y }, control: { x: (a.x + b.x) / 2 - dy * q.bend, y: (a.y + b.y) / 2 + dx * q.bend }, head: [{ x: b.x, y: b.y }, { x: b.x - 16 * dx / Math.max(1, Math.hypot(dx, dy)) + 9 * dy / Math.max(1, Math.hypot(dx, dy)), y: b.y - 16 * dy / Math.max(1, Math.hypot(dx, dy)) - 9 * dx / Math.max(1, Math.hypot(dx, dy)) }, { x: b.x - 16 * dx / Math.max(1, Math.hypot(dx, dy)) - 9 * dy / Math.max(1, Math.hypot(dx, dy)), y: b.y - 16 * dy / Math.max(1, Math.hypot(dx, dy)) + 9 * dx / Math.max(1, Math.hypot(dx, dy)) }], ink: cueInk(t, q.start, q.end, end), text: q.text };
    });
    return { time: t, progress: u, source_time: source, source_progress: v, tracks, arrows, paused: p.pause_cues.some((q) => t >= q.start && t <= q.end), layers: [layer(p, p.clip_path.clip, source, FULL, target3)] };
  }
  function render69(spec, seconds, frames) {
    const p = validateParameters28(spec), s = sample69(spec, seconds), c = p.palette;
    const annotations = s.arrows.map((a) => `<path d="M${fmt2(a.start.x)} ${fmt2(a.start.y)}Q${fmt2(a.control.x)} ${fmt2(a.control.y)} ${fmt2(a.end.x)} ${fmt2(a.end.y)}" fill="none" stroke="${c.accent}" stroke-width="9" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt2(1 - a.ink)}"/><path d="${path(a.head)}" fill="${c.accent}" opacity="${fmt2(a.ink)}"/>`).join("") + s.tracks.map((q) => `<circle cx="${fmt2(q.x)}" cy="${fmt2(q.y)}" r="27" fill="none" stroke="${c.ink}" stroke-width="6"/>`).join("");
    return svg2(ID69, p, tx("AKS\u0130YON / TAK\u0130P", 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 198, 950, 58, c.ink, 4) + drawLayers(p, s.layers, "tactic", frames) + annotations + s.arrows.map((a, i) => tx(a.text, 80 + i % 2 * 470, 1400 + Math.floor(i / 2) * 64, 440, 28, c.ink, 2)).join("") + panel(rect3(60, 1580, 960, 48), c.background) + tx(`KAYNAK ${s.source_time.toFixed(2)} sn \xB7 ${s.paused ? "KARE TUTULUYOR" : "\u0130ZLEN\u0130YOR"}`, 80, 1618, 920, 30, c.ink, 1) + subtitle(p, s.time, 1710) + proxyMark(p));
  }
  function validateSpec69(spec) {
    return deepFreeze({ id: ID69, version: "1.0.0", parameters: validateParameters28(spec) });
  }

  // renderers/template-registry/modules/6e9e2f0828b6-footage-focus-band.mjs
  var e9e2f0828b6_footage_focus_band_exports = {};
  __export(e9e2f0828b6_footage_focus_band_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE71,
    ID: () => ID70,
    METADATA: () => METADATA62,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA70,
    SOURCE_ID: () => SOURCE_ID70,
    render: () => render70,
    sample: () => sample70,
    validateSpec: () => validateSpec70
  });
  var ID70 = "footage-focus-band";
  var SOURCE_ID70 = "source-lemo-style-tilt-shift";
  var DEFAULT_PALETTE71 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA70 = schema2({ clip_path: obj({ clip: str(36), in: num(0, 3600), out: num(1, 3600) }), focus_band: obj({ start_center: num(0.1, 0.9), end_center: num(0.1, 0.9), width: num(0.12, 0.45), blur_radius: num(2, 18) }), time_remap: remapSchema, crop_path: pathSchema });
  var METADATA62 = metadata2("Netlik Band\u0131 \xB7 \xF6zg\xFCn edit", "three-way-focus-mask", "monotone time remap; crop path; moving sharp band between two blur masks", ["focus label 30", "title 56", "band metric 32"]);
  var target4 = rect3(80, 430, 900, 1080);
  function validateParameters29(spec) {
    const p = base5(spec, ID70, ["clip_path", "focus_band", "time_remap", "crop_path"]), r = spec.parameters;
    keys2(r.clip_path, ["clip", "in", "out"]);
    const id = ref(r.clip_path.clip, p);
    p.clip_path = { clip: id, in: number2(r.clip_path.in, "clip in", 0, asset(p, id).duration), out: number2(r.clip_path.out, "clip out", 1, asset(p, id).duration) };
    if (p.clip_path.out <= p.clip_path.in) fail2("positive trim");
    keys2(r.focus_band, ["start_center", "end_center", "width", "blur_radius"]);
    p.focus_band = { start_center: number2(r.focus_band.start_center, "start center", 0.1, 0.9), end_center: number2(r.focus_band.end_center, "end center", 0.1, 0.9), width: number2(r.focus_band.width, "band width", 0.12, 0.45), blur_radius: number2(r.focus_band.blur_radius, "blur radius", 2, 18) };
    const b = p.focus_band;
    if ([b.start_center, b.end_center].some((v) => v - b.width / 2 < 0 || v + b.width / 2 > 1)) fail2("focus band outside viewport");
    p.time_remap = remap(r.time_remap, p.clip_path.out);
    if (p.time_remap[0].time < p.clip_path.in) fail2("remap precedes trim");
    p.crop_path = cropPath(r.crop_path);
    return assertTextLayout(p, 900, 56, 4);
  }
  function sample70(spec, seconds) {
    const p = validateParameters29(spec), { t, u } = clock3(p, seconds), b = p.focus_band, center = lerp2(b.start_center, b.end_center, smooth2(u)), top = center - b.width / 2, bottom = center + b.width / 2, crop = cropAt(p.crop_path, u), time2 = sourceAt(p.time_remap, u), zones = [{ y: 0, h: top, blur: b.blur_radius }, { y: top, h: b.width, blur: 0 }, { y: bottom, h: 1 - bottom, blur: b.blur_radius }], layers = zones.map((z) => layer(p, p.clip_path.clip, time2, crop, target4, { blur: z.blur, mask: [{ x: target4.x, y: target4.y + z.y * target4.h }, { x: target4.x + target4.w, y: target4.y + z.y * target4.h }, { x: target4.x + target4.w, y: target4.y + (z.y + z.h) * target4.h }, { x: target4.x, y: target4.y + (z.y + z.h) * target4.h }] }));
    return { time: t, progress: u, source_time: time2, focus_center: center, focus_top: top, focus_bottom: bottom, zones, partition_height: zones.reduce((n, z) => n + z.h, 0), layers };
  }
  function render70(spec, seconds, frames) {
    const p = validateParameters29(spec), s = sample70(spec, seconds), c = p.palette;
    return svg2(ID70, p, tx("NET ALAN / ZAMAN", 80, 106, 900, 30, c.accent, 1) + tx(p.title, 80, 198, 900, 56, c.ink, 4) + drawLayers(p, s.layers, "focus", frames) + panel(rect3(996, 430, 10, 1080), c.muted) + panel(rect3(989, 430 + s.focus_top * 1080, 24, (s.focus_bottom - s.focus_top) * 1080), c.accent) + tx(`Net bant: %${Math.round((s.focus_bottom - s.focus_top) * 100)} \xB7 Kaynak ${s.source_time.toFixed(2)} sn`, 80, 1590, 920, 32, c.ink, 2) + subtitle(p, s.time, 1710) + proxyMark(p));
  }
  function validateSpec70(spec) {
    return deepFreeze({ id: ID70, version: "1.0.0", parameters: validateParameters29(spec) });
  }

  // renderers/template-registry/modules/11b847c80eb3-media-evidence-compare.mjs
  var b847c80eb3_media_evidence_compare_exports = {};
  __export(b847c80eb3_media_evidence_compare_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE72,
    ID: () => ID71,
    METADATA: () => METADATA63,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA71,
    SOURCE_ID: () => SOURCE_ID71,
    render: () => render71,
    sample: () => sample71,
    validateSpec: () => validateSpec71
  });
  var ID71 = "media-evidence-compare";
  var SOURCE_ID71 = "source-lemo-style-visual-investigation";
  var DEFAULT_PALETTE72 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA71 = schema2({ media_paths: arr2(str(36), 2, 2), sync_offsets: arr2(num(0, 6), 2, 2), comparison_regions: arr2(boxSchema, 2, 2), evidence_links: arr2(obj({ id: str(36), a: pointSchema, b: pointSchema, text: str(85), start: num(0, 45), end: num(0.1, 45) }), 1, 5) });
  var METADATA63 = metadata2("G\xF6r\xFCnt\xFC Kan\u0131t\u0131 \xB7 \xF6zg\xFCn edit", "synchronized-ab-evidence-bridge", "paired clocks with offsets; crop-match zoom; source-region evidence links", ["case number 30", "headline 56", "A/B plates 32", "evidence statement 32"]);
  var targets = [rect3(60, 430, 960, 450), rect3(60, 990, 960, 450)];
  function validateParameters30(spec) {
    const p = base5(spec, ID71, ["media_paths", "sync_offsets", "comparison_regions", "evidence_links"]), r = spec.parameters;
    p.media_paths = refs(r.media_paths, p, "media_paths", 2, 2);
    p.sync_offsets = list3(r.sync_offsets, "sync offsets", 2, 2).map((x) => number2(x, "sync offset", 0, 6));
    if (p.media_paths.some((id, i) => asset(p, id).duration < p.duration + p.sync_offsets[i])) fail2("synchronized source too short");
    p.comparison_regions = list3(r.comparison_regions, "comparison regions", 2, 2).map((x) => box(x));
    p.evidence_links = list3(r.evidence_links, "evidence links", 1, 5).map((q) => {
      keys2(q, ["id", "a", "b", "text", "start", "end"]);
      const v = { id: token(q.id), a: point3(q.a), b: point3(q.b), text: text2(q.text, "evidence statement", 85), start: number2(q.start, "link start", 0, p.duration), end: number2(q.end, "link end", 0, p.duration) };
      if (v.end - v.start < 0.6 || v.start > p.duration - 1.1) fail2("evidence readable interval");
      fitText2(`${v.id}: ${v.text}`, { width: 920, maximum: 32, minimum: 30, maxLines: 3 });
      for (const [pt2, b] of [[v.a, p.comparison_regions[0]], [v.b, p.comparison_regions[1]]]) if (pt2.x < b.x || pt2.x > b.x + b.w || pt2.y < b.y || pt2.y > b.y + b.h) fail2("evidence point outside comparison region");
      return v;
    });
    return assertTextLayout(p, 950, 50, 4);
  }
  function sample71(spec, seconds) {
    const p = validateParameters30(spec), { t, u, end } = clock3(p, seconds), q = smooth2(Math.min(1, u / 0.72)), crops = p.comparison_regions.map((b) => Object.fromEntries(["x", "y", "w", "h"].map((k) => [k, lerp2(FULL[k], b[k], q)]))), times = p.sync_offsets.map((x) => x + t), links = p.evidence_links.filter((q2) => t >= q2.start && t < q2.end).map((q2) => ({ id: q2.id, text: q2.text, a: projected(crops[0], targets[0], q2.a), b: projected(crops[1], targets[1], q2.b), ink: cueInk(t, q2.start, q2.end, end) }));
    return { time: t, progress: u, source_times: times, sync_delta: times[1] - times[0], links, layers: p.media_paths.map((id, i) => layer(p, id, times[i], crops[i], targets[i])) };
  }
  function render71(spec, seconds, frames) {
    const p = validateParameters30(spec), s = sample71(spec, seconds), c = p.palette;
    const link = s.links[0];
    return svg2(ID71, p, tx("KANIT / KAYNAK E\u015ELE\u015ET\u0130RME", 60, 106, 950, 30, c.accent, 1) + tx(p.title, 60, 180, 950, 50, c.ink, 4) + drawLayers(p, s.layers, "evidence", frames) + panel(rect3(60, 382, 960, 48), c.background) + tx(`A \xB7 ${s.source_times[0].toFixed(2)} sn`, 80, 416, 900, 28, c.ink, 1) + tx(`B \xB7 ${s.source_times[1].toFixed(2)} sn`, 80, 976, 900, 28, c.ink, 1) + s.links.map((q) => `<path d="M${fmt2(q.a.x)} ${fmt2(q.a.y)}L${fmt2(q.b.x)} ${fmt2(q.b.y)}" stroke="${c.accent}" stroke-width="5" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt2(1 - q.ink)}"/><circle cx="${fmt2(q.a.x)}" cy="${fmt2(q.a.y)}" r="15" fill="none" stroke="${c.ink}" stroke-width="4"/><circle cx="${fmt2(q.b.x)}" cy="${fmt2(q.b.y)}" r="15" fill="none" stroke="${c.ink}" stroke-width="4"/>`).join("") + (link ? tx(`${link.id}: ${link.text}`, 80, 1520, 920, 32, c.ink, 3) : "") + subtitle(p, s.time, 1710) + proxyMark(p));
  }
  function validateSpec71(spec) {
    return deepFreeze({ id: ID71, version: "1.0.0", parameters: validateParameters30(spec) });
  }

  // renderers/template-registry/modules/13bf72e86fe8-vector-puppet-cause.mjs
  var bf72e86fe8_vector_puppet_cause_exports = {};
  __export(bf72e86fe8_vector_puppet_cause_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE73,
    ID: () => ID72,
    METADATA: () => METADATA64,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA72,
    SOURCE_ID: () => SOURCE_ID72,
    render: () => render72,
    sample: () => sample72,
    validateSpec: () => validateSpec72
  });

  // renderers/template-registry/modules/41ce440d7bb8-common.mjs
  var LIGHT = deepFreeze2({ background: "#F4F1E8", ink: "#1B2530", muted: "#56606B", accent: "#77512E" });
  var COOL = deepFreeze2({ background: "#EFF3F5", ink: "#182B39", muted: "#4F6575", accent: "#245E83" });
  var ROSE = deepFreeze2({ background: "#F9EFEA", ink: "#342A35", muted: "#6E5663", accent: "#92502E" });
  var DARK2 = deepFreeze2({ background: "#111A18", ink: "#D5F6DF", muted: "#9FBEAB", accent: "#ADF1C2" });
  var N2 = (min, max, integer = false) => ({ type: "number", minimum: min, maximum: max, integer });
  var T = (maxLength = 64) => ({ type: "string", minLength: 1, maxLength });
  var E2 = (...values) => ({ type: "string", enum: values });
  var A2 = (items, minItems, maxItems = minItems) => ({ type: "array", items, minItems, maxItems });
  var O2 = (properties) => ({ type: "object", properties, required: Object.keys(properties), additionalProperties: false });
  var P2 = (x0 = 180, x1 = 900, y0 = 600, y1 = 1400) => O2({ x: N2(x0, x1), y: N2(y0, y1) });
  var HEX = { type: "string", format: "hex", maxLength: 7 };
  var COMMON = { title: T(160), duration: N2(3, 45), narration: T(1500), cues: A2(O2({ start: N2(0, 45), end: N2(0, 45), text: T(95) }), 1, 24), palette: O2({ background: HEX, ink: HEX, muted: HEX, accent: HEX }) };
  function schema3(fields) {
    return deepFreeze2({ ...O2({ ...COMMON, ...fields }), required: ["title", "duration", "narration", "cues", ...Object.keys(fields)], frame_rate: 30, output: { width: 1080, height: 1920 }, final_hold_seconds: 0.8 });
  }
  function field(value, rule, name) {
    if (rule.enum) return choice3(value, name, rule.enum);
    if (rule.type === "number") return number3(value, name, rule.minimum, rule.maximum, rule.integer);
    if (rule.type === "string") {
      if (rule.format === "hex") {
        if (typeof value !== "string" || !/^#[0-9A-Fa-f]{6}$/u.test(value)) fail3(`${name}: six-digit hex required`);
        return value.toUpperCase();
      }
      if (rule.format === "ascii-ramp") {
        if (typeof value !== "string" || value.length < 4 || value.length > 12 || !/^[\x21-\x7E]+$/u.test(value) || new Set(value).size !== value.length) fail3(`${name}: 4\u201312 unique printable ASCII characters required`);
        return value;
      }
      return text3(value, name, rule.maxLength);
    }
    if (rule.type === "array") {
      if (!Array.isArray(value) || value.length < rule.minItems || value.length > rule.maxItems || Object.getPrototypeOf(value) !== Array.prototype) fail3(`${name}: bounded plain array required`);
      const own = Reflect.ownKeys(value);
      if (own.length !== value.length + 1 || own.some((k) => k !== "length" && (typeof k !== "string" || !/^\d+$/u.test(k) || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, k), "value")))) fail3(`${name}: dense data-only array required`);
      return Array.from(value, (v, i) => field(v, rule.items, `${name}[${i}]`));
    }
    keys3(value, rule.required, [], name);
    return Object.fromEntries(Object.entries(rule.properties).map(([k, r]) => [k, field(value[k], r, `${name}.${k}`)]));
  }
  function parameters(spec, id, fields, defaults) {
    keys3(spec, ["id", "version", "parameters"], [], "spec");
    keys3(spec.parameters, ["title", "duration", "narration", "cues", ...Object.keys(fields)], ["palette"], "parameters");
    field(spec.parameters.cues, COMMON.cues, "cues");
    const p = validateBase3(spec, id, Object.keys(fields), [], defaults);
    for (const [k, r] of Object.entries(fields)) p[k] = field(spec.parameters[k], r, k);
    return p;
  }
  function metadata3(name, layout, motion, hierarchy) {
    return deepFreeze2({ name, kind: "original_svg_state", layout_id: layout, motion_grammar: motion, typographic_hierarchy: hierarchy, original_implementation: true, implementation_strategy: "original_implementation_not_source_code_port", native_verified: false, ui_verified: false, independent_accepted: false, broad_classifier_axis_parity: false });
  }
  var unit = (p, t) => Math.min(sampleTime3(t, p.duration), p.duration - 0.8) / (p.duration - 0.8);
  var at = (u, a, b) => smooth3((u - a) / (b - a));
  var mixPoint = (a, b, q) => ({ x: lerp3(a.x, b.x, q), y: lerp3(a.y, b.y, q) });
  function bezier(a, b, c, u) {
    return { x: (1 - u) ** 2 * a.x + 2 * (1 - u) * u * b.x + u * u * c.x, y: (1 - u) ** 2 * a.y + 2 * (1 - u) * u * b.y + u * u * c.y };
  }
  function listPath(points, closed = false) {
    return points.map((p, i) => `${i ? "L" : "M"}${fmt3(p.x)} ${fmt3(p.y)}`).join("") + (closed ? "Z" : "");
  }
  var dot = (p, r, fill, extra = "") => `<circle cx="${fmt3(p.x)}" cy="${fmt3(p.y)}" r="${fmt3(r)}" fill="${fill}" ${extra}/>`;
  var segment = (a, b, stroke, width = 3, extra = "") => `<path d="${listPath([a, b])}" fill="none" stroke="${stroke}" stroke-width="${fmt3(width)}" ${extra}/>`;
  var box2 = (x, y, w, h, fill, extra = "") => `<rect x="${fmt3(x)}" y="${fmt3(y)}" width="${fmt3(w)}" height="${fmt3(h)}" fill="${fill}" ${extra}/>`;
  var path5 = (points, fill, stroke = "none", width = 1, extra = "") => `<path d="${listPath(points, true)}" fill="${fill}" stroke="${stroke}" stroke-width="${fmt3(width)}" ${extra}/>`;
  function label4(s, x, y, c, size = 25, extra = "") {
    return `<text x="${fmt3(x)}" y="${fmt3(y)}" fill="${c}" font-size="${size}" ${extra}>${esc3(s)}</text>`;
  }
  function caption2(p, t, options = {}) {
    const c = activeCue3(p.cues, Math.min(sampleTime3(t, p.duration), p.duration - 1e-8));
    return c ? `<g data-caption="true">${svgText3(c.text, { x: 90, y: 1680, width: 900, maximum: 42, minimum: 30, maxLines: 3, fill: p.palette.ink, ...options })}</g>` : "";
  }
  function svg3(id, p, t, body, font = "sans-serif") {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920" role="img" aria-label="${esc3(p.title)}" data-family="${id}" data-seconds="${fmt3(sampleTime3(t, p.duration))}"><rect width="1080" height="1920" fill="${p.palette.background}"/><g font-family="${font}">${body}</g></svg>`;
  }
  var headline = (p, options = {}) => svgText3(p.title, { x: 90, y: 210, width: 900, maximum: 60, minimum: 38, maxLines: 4, fill: p.palette.ink, ...options });
  function ensure(condition, message) {
    if (!condition) fail3(message);
  }
  function signedArea2(points) {
    return points.reduce((a, p, i) => {
      const q = points[(i + 1) % points.length];
      return a + p.x * q.y - q.x * p.y;
    }, 0) / 2;
  }
  var distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  function hash(seed, index) {
    let x = (seed ^ Math.imul(index + 1, 2654435761)) >>> 0;
    x = Math.imul(x ^ x >>> 16, 2246822507) >>> 0;
    x = Math.imul(x ^ x >>> 13, 3266489909) >>> 0;
    return ((x ^ x >>> 16) >>> 0) / 4294967296;
  }

  // renderers/template-registry/modules/13bf72e86fe8-vector-puppet-cause.mjs
  var ID72 = "vector-puppet-cause";
  var SOURCE_ID72 = "src-athemeroy-style-flat-vector-cartoon";
  var DEFAULT_PALETTE73 = LIGHT;
  var F = { joint_limits: A2(N2(15, 170), 2), prop_targets: P2(600, 750, 1e3, 1140), contact_cues: A2(N2(0.08, 0.36), 2), reaction_delay: N2(0, 0.8) };
  var PARAMETER_SCHEMA72 = schema3(F);
  var METADATA64 = metadata3("Vekt\xF6r kuklada kuvvet", "puppet-proscenium", "approach \u2192 palm contact \u2192 prop translation \u2192 delayed reaction \u2192 held rest", ["large left headline", "contact annotation", "stage dialogue"]);
  function validatedParameters(spec) {
    const p = parameters(spec, ID72, F, DEFAULT_PALETTE73);
    ensure(p.joint_limits[0] < p.joint_limits[1], "joint_limits: increasing limits required");
    ensure(p.joint_limits[0] <= 45 && p.joint_limits[1] >= 85, "joint_limits: the complete original arm arc requires 45\u201385 degrees");
    ensure(p.contact_cues[1] - p.contact_cues[0] >= 0.06, "contact_cues: separated approach window required");
    return p;
  }
  function arm(shoulder, wrist) {
    const d = distance(shoulder, wrist), mid = mixPoint(shoulder, wrist, 0.5), h = Math.sqrt(1e4 - d * d / 4);
    const elbow = { x: mid.x - (wrist.y - shoulder.y) / d * h, y: mid.y + (wrist.x - shoulder.x) / d * h };
    return { shoulder, elbow, wrist, lengths: [distance(shoulder, elbow), distance(elbow, wrist)], elbow_angle: Math.acos((2e4 - d * d) / 2e4) * 180 / Math.PI };
  }
  function sample72(spec, seconds) {
    const p = validatedParameters(spec), u = unit(p, seconds), contact = p.contact_cues[1], pushStart = contact + p.reaction_delay / (p.duration - 0.8), q = at(u, pushStart, 0.87), prop = mixPoint({ x: 510, y: 1050 }, p.prop_targets, q), root = { x: prop.x - 220, y: prop.y + 100 }, shoulder = { x: prop.x - 180, y: prop.y - 30 }, touch = { x: prop.x - 60, y: prop.y - 20 }, home = { x: prop.x - 120, y: prop.y + 50 }, wrist = mixPoint(home, touch, at(u, p.contact_cues[0], contact)), rig2 = arm(shoulder, wrist);
    return { prop, root, arm: rig2, contact: u >= contact, contact_gap: distance(wrist, touch), push: q, reaction: at(u, pushStart + 0.06, 0.95), force_arrow: lerp3(0, 95, q) };
  }
  function render72(spec, seconds) {
    const p = validatedParameters(spec), s = sample72(spec, seconds), c = p.palette;
    const figure = (root, head, lean = 0) => path5([{ x: root.x - 38, y: root.y }, { x: root.x + 48, y: root.y }, { x: root.x + 28 + lean, y: root.y - 155 }, { x: root.x - 20 + lean, y: root.y - 155 }], c.accent) + path5([{ x: head.x, y: head.y - 42 }, { x: head.x + 42, y: head.y }, { x: head.x, y: head.y + 42 }, { x: head.x - 42, y: head.y }], c.background, c.ink, 4) + segment({ x: root.x - 20, y: root.y }, { x: root.x - 50, y: 1320 }, c.ink, 19) + segment({ x: root.x + 25, y: root.y }, { x: root.x + 65, y: 1320 }, c.ink, 19);
    let b = headline(p) + label4("01 / KUVVET\u0130N G\xD6R\xDCN\xDCR NEDEN\u0130", 90, 490, c.muted, 25) + segment({ x: 100, y: 1320 }, { x: 980, y: 1320 }, c.ink, 5);
    b += figure(s.root, { x: s.root.x + 15, y: s.root.y - 215 }) + box2(s.prop.x - 60, s.prop.y - 70, 120, 140, c.background, `stroke="${c.ink}" stroke-width="5" rx="14"`) + dot({ x: s.prop.x - 30, y: s.prop.y + 87 }, 15, c.ink) + dot({ x: s.prop.x + 30, y: s.prop.y + 87 }, 15, c.ink);
    b += segment(s.arm.shoulder, s.arm.elbow, c.ink, 18, 'stroke-linecap="round"') + segment(s.arm.elbow, s.arm.wrist, c.ink, 18, 'stroke-linecap="round"') + [s.arm.shoulder, s.arm.elbow, s.arm.wrist].map((v) => dot(v, 12, c.background, `stroke="${c.ink}" stroke-width="4"`)).join("");
    b += figure({ x: 865, y: 1200 }, { x: 865 + 30 * s.reaction, y: 985 - 22 * s.reaction }, -25 * s.reaction) + segment({ x: s.prop.x + 62, y: s.prop.y }, { x: 810, y: 1140 - 28 * s.reaction }, c.accent, 4, 'stroke-dasharray="8 8"');
    b += label4(s.contact ? "TEMAS KAPANDI" : "EL YAKLA\u015EIYOR", 155, 730, c.ink, 30) + label4(`${Math.round(s.arm.elbow_angle)}\xB0 \xB7 iki sabit kol`, 155, 780, c.muted, 24) + `<path d="M${fmt3(s.prop.x - 45)} ${fmt3(s.prop.y - 135)}h${fmt3(s.force_arrow)}l-12 -9m12 9l-12 9" fill="none" stroke="${c.accent}" stroke-width="5"/>` + label4("Etki, temas\u0131n ard\u0131ndan aktar\u0131l\u0131r.", 90, 1500, c.muted, 30) + caption2(p, seconds);
    return svg3(ID72, p, seconds, b);
  }
  function validateSpec72(spec) {
    return { id: ID72, version: "1.0.0", parameters: validatedParameters(spec) };
  }

  // renderers/template-registry/modules/eb10ca0d6fa9-field-orbit-ensemble.mjs
  var eb10ca0d6fa9_field_orbit_ensemble_exports = {};
  __export(eb10ca0d6fa9_field_orbit_ensemble_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE74,
    ID: () => ID73,
    METADATA: () => METADATA65,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA73,
    SOURCE_ID: () => SOURCE_ID73,
    render: () => render73,
    sample: () => sample73,
    validateSpec: () => validateSpec73
  });
  var ID73 = "field-orbit-ensemble";
  var SOURCE_ID73 = "src-athemeroy-style-generative-abstract";
  var DEFAULT_PALETTE74 = COOL;
  var F2 = { field_seed: N2(1, 65535, true), attractors: A2(O2({ x: N2(350, 730), y: N2(790, 1160), strength: N2(0.5, 2) }), 2, 3), particle_count: N2(24, 72, true), band_width: N2(18, 58) };
  var PARAMETER_SCHEMA73 = schema3(F2);
  var METADATA65 = metadata3("\xC7ekim alan\u0131 toplulu\u011Fu", "field-atlas-rail", "seeded field capture \u2192 coherent rotating bands \u2192 attractor handoff \u2192 zero-velocity rest", ["left numbered rail", "bounded title", "field band counter"]);
  function validatedParameters2(spec) {
    return parameters(spec, ID73, F2, DEFAULT_PALETTE74);
  }
  function sample73(spec, seconds) {
    const p = validatedParameters2(spec), u = unit(p, seconds), capture = at(u, 0, 0.42), handoff = at(u, 0.42, 0.88), settle = at(u, 0.72, 1), nodes = Array.from({ length: p.particle_count }, (_, i) => {
      const band = i % p.attractors.length, a = p.attractors[band], next = p.attractors[(band + 1) % p.attractors.length], center = { x: lerp3(a.x, next.x, handoff), y: lerp3(a.y, next.y, handoff) }, radius = 80 + p.band_width * (1 + Math.floor(i / p.attractors.length) % 3), angle = Math.floor(i / p.attractors.length) / Math.ceil(p.particle_count / p.attractors.length) * Math.PI * 2 + (1 - settle) * a.strength * 3.5 * u + hash(p.field_seed, i) * 0.12 * (1 - capture), r = lerp3(radius + 90 * (hash(p.field_seed, i + 100) - 0.5), radius, capture), x = center.x + Math.cos(angle) * r, y = center.y + Math.sin(angle) * r * 0.62;
      return { id: i, band, center, radius, r, angle, x, y, field_vector: { x: -Math.sin(angle) * a.strength * (1 - settle), y: Math.cos(angle) * a.strength * 0.62 * (1 - settle) } };
    });
    return { nodes, capture, handoff, settled: settle === 1, bands: p.attractors.length };
  }
  function render73(spec, seconds) {
    const p = validatedParameters2(spec), s = sample73(spec, seconds), c = p.palette;
    let b = segment({ x: 98, y: 120 }, { x: 98, y: 1540 }, c.muted, 2) + label4("02", 125, 170, c.accent, 48) + headline(p, { x: 160, y: 265, width: 820, maximum: 55 }) + label4("ALAN / Y\xD6R\xDCNGE / TOPLULUK", 160, 535, c.muted, 24);
    for (let k = 0; k < s.bands; k++) {
      const nodes = s.nodes.filter((n) => n.band === k);
      b += path5(nodes, c.accent, "none", 1, `opacity="${0.07 + k * 0.025}"`) + `<ellipse cx="${fmt3(nodes[0].center.x)}" cy="${fmt3(nodes[0].center.y)}" rx="${fmt3(80 + p.band_width * 2)}" ry="${fmt3((80 + p.band_width * 2) * 0.62)}" fill="none" stroke="${c.muted}" stroke-width="2" stroke-dasharray="4 12"/>`;
      b += nodes.map((n) => dot(n, 4 + 2 * (n.id % 3), c.accent) + segment(n, { x: n.x + n.field_vector.x * 25, y: n.y + n.field_vector.y * 25 }, c.ink, 2)).join("");
    }
    b += label4(String(s.bands).padStart(2, "0"), 160, 1480, c.ink, 94) + label4("tutarl\u0131 bant", 320, 1470, c.muted, 31) + caption2(p, seconds, { x: 160, width: 820 });
    return svg3(ID73, p, seconds, b);
  }
  function validateSpec73(spec) {
    return { id: ID73, version: "1.0.0", parameters: validatedParameters2(spec) };
  }

  // renderers/template-registry/modules/121aed4c0c3a-construction-stroke-stack.mjs
  var aed4c0c3a_construction_stroke_stack_exports = {};
  __export(aed4c0c3a_construction_stroke_stack_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE75,
    ID: () => ID74,
    METADATA: () => METADATA66,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA74,
    SOURCE_ID: () => SOURCE_ID74,
    render: () => render74,
    sample: () => sample74,
    validateSpec: () => validateSpec74
  });
  var ID74 = "construction-stroke-stack";
  var SOURCE_ID74 = "src-athemeroy-style-hand-drawn-sketch";
  var DEFAULT_PALETTE75 = LIGHT;
  var F3 = { construction_lines: A2(O2({ a: P2(230, 850, 720, 1280), b: P2(230, 850, 720, 1280) }), 3, 6), correction_regions: A2(O2({ x: N2(270, 810), y: N2(760, 1240), radius: N2(35, 95) }), 1, 3), stroke_variants: N2(1, 3, true), convergence_time: N2(0.52, 0.88) };
  var PARAMETER_SCHEMA74 = schema3(F3);
  var METADATA66 = metadata3("Yap\u0131 \xE7izgisinden son bi\xE7ime", "construction-notebook", "visible construction \u2192 exploratory strokes \u2192 explicit corrections \u2192 endpoint convergence", ["serif proposition", "margin line numbers", "retained correction notes"]);
  function validatedParameters3(spec) {
    return parameters(spec, ID74, F3, DEFAULT_PALETTE75);
  }
  function sample74(spec, seconds) {
    const p = validatedParameters3(spec), u = unit(p, seconds), q = at(u, 0.15, p.convergence_time), strokes = p.construction_lines.flatMap((l, i) => Array.from({ length: p.stroke_variants }, (_, j) => {
      const d = (j + 1) * 9 * (i % 2 ? -1 : 1), oa = { x: l.a.x + d, y: l.a.y - d * 0.8 }, ob = { x: l.b.x - d * 0.7, y: l.b.y + d };
      return { line: i, variant: j, a: mixPoint(oa, l.a, q), b: mixPoint(ob, l.b, q), reveal: at(u, 0.02 + i * 0.035 + j * 0.02, 0.38 + i * 0.03) };
    }));
    return { strokes, construction: p.construction_lines, corrections: p.correction_regions, convergence: q, remaining_error: 1 - q };
  }
  function render74(spec, seconds) {
    const p = validatedParameters3(spec), s = sample74(spec, seconds), c = p.palette;
    let b = headline(p, { x: 125, y: 210, width: 850, maximum: 56 }) + label4("ARA \xC7\u0130ZG\u0130LER KAYBOLMAZ", 125, 510, c.muted, 24);
    for (let x = 180; x <= 900; x += 60) b += segment({ x, y: 650 }, { x, y: 1430 }, c.muted, 1, 'opacity="0.13"');
    for (let y = 650; y <= 1430; y += 60) b += segment({ x: 180, y }, { x: 900, y }, c.muted, 1, 'opacity="0.13"');
    s.construction.forEach((l, i) => {
      b += segment(l.a, l.b, c.muted, 2, 'stroke-dasharray="9 11" opacity="0.5"') + label4(String(i + 1).padStart(2, "0"), 108, 730 + i * 95, c.muted, 24);
    });
    s.strokes.forEach((l) => b += segment(l.a, mixPoint(l.a, l.b, l.reveal), c.ink, 2 + l.variant * 0.8, 'stroke-linecap="round"'));
    s.corrections.forEach((v, i) => {
      b += `<ellipse cx="${fmt3(v.x)}" cy="${fmt3(v.y)}" rx="${fmt3(v.radius)}" ry="${fmt3(v.radius * 0.55)}" fill="none" stroke="${c.accent}" stroke-width="3" stroke-dasharray="4 6"/>` + segment({ x: v.x - 16, y: v.y - 16 }, { x: v.x + 16, y: v.y + 16 }, c.accent, 3) + segment({ x: v.x - 16, y: v.y + 16 }, { x: v.x + 16, y: v.y - 16 }, c.accent, 3) + label4(`${i + 1}. d\xFCzeltme`, v.x - 40, v.y + v.radius * 0.55 + 36, c.accent, 23);
    });
    b += label4(`Sapma: ${(s.remaining_error * 100).toFixed(0)} / 100`, 125, 1515, c.ink, 31) + caption2(p, seconds, { x: 125, width: 850 });
    return svg3(ID74, p, seconds, b, "serif");
  }
  function validateSpec74(spec) {
    return { id: ID74, version: "1.0.0", parameters: validatedParameters3(spec) };
  }

  // renderers/template-registry/modules/b5002cf70549-geometric-proof-transform.mjs
  var b5002cf70549_geometric_proof_transform_exports = {};
  __export(b5002cf70549_geometric_proof_transform_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE76,
    ID: () => ID75,
    METADATA: () => METADATA67,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA75,
    SOURCE_ID: () => SOURCE_ID75,
    render: () => render75,
    sample: () => sample75,
    validateSpec: () => validateSpec75
  });
  var ID75 = "geometric-proof-transform";
  var SOURCE_ID75 = "src-athemeroy-style-math-diagram";
  var DEFAULT_PALETTE76 = COOL;
  var F4 = { points: A2(P2(330, 750, 790, 1190), 3), constraints: A2(E2("lengths", "area"), 1, 2), transformation: O2({ rotation: N2(-130, 130), translate_x: N2(-80, 80), translate_y: N2(-80, 80) }), measurement_labels: A2(T(18), 3) };
  var PARAMETER_SCHEMA75 = schema3(F4);
  var METADATA67 = metadata3("Geometrik de\u011Fi\u015Fmezin kan\u0131t\u0131", "rigid-proof-board", "rigid triangle transform \u2192 following measurements \u2192 exact invariant table", ["proposition title", "triangle edge labels", "numeric proof ledger"]);
  function validatedParameters4(spec) {
    const p = parameters(spec, ID75, F4, DEFAULT_PALETTE76);
    ensure(Math.abs(signedArea2(p.points)) >= 9e3, "points: a nondegenerate triangle of area \u22659000 is required");
    const center = { x: p.points.reduce((a, v) => a + v.x, 0) / 3, y: p.points.reduce((a, v) => a + v.y, 0) / 3 };
    ensure(center.x >= 410 && center.x <= 670 && center.y >= 940 && center.y <= 1080 && p.points.every((v) => distance(v, center) <= 240), "points: triangle and transformed proof disc must fit the safe stage");
    ensure(new Set(p.constraints).size === p.constraints.length, "constraints: unique entries required");
    return p;
  }
  function sample75(spec, seconds) {
    const p = validatedParameters4(spec), q = at(unit(p, seconds), 0.1, 0.9), center = { x: p.points.reduce((a, v) => a + v.x, 0) / 3, y: p.points.reduce((a, v) => a + v.y, 0) / 3 }, r = p.transformation.rotation * q * Math.PI / 180, points = p.points.map((v) => ({ x: center.x + (v.x - center.x) * Math.cos(r) - (v.y - center.y) * Math.sin(r) + p.transformation.translate_x * q, y: center.y + (v.x - center.x) * Math.sin(r) + (v.y - center.y) * Math.cos(r) + p.transformation.translate_y * q })), lengths = points.map((v, i) => distance(v, points[(i + 1) % 3]));
    return { points, source_points: p.points, center, rotation: p.transformation.rotation * q, translation: { x: p.transformation.translate_x * q, y: p.transformation.translate_y * q }, lengths, area: signedArea2(points), progress: q };
  }
  function render75(spec, seconds) {
    const p = validatedParameters4(spec), s = sample75(spec, seconds), c = p.palette;
    let b = label4("\xD6NERME 04", 90, 125, c.accent, 24) + headline(p, { y: 230, maximum: 58 }) + label4("D\xF6n\xFC\u015F\xFCm de\u011Fi\u015Fir. \xD6l\xE7\xFC korunur.", 90, 530, c.muted, 29) + path5(s.source_points, "none", c.muted, 2, 'stroke-dasharray="8 12"') + path5(s.points, c.accent, c.ink, 4, 'fill-opacity="0.12"');
    s.points.forEach((v, i) => {
      const end = s.points[(i + 1) % 3], m = mixPoint(v, end, 0.5);
      b += dot(v, 9, c.ink) + label4(String.fromCharCode(65 + i), v.x - 20, v.y - 20, c.ink, 32) + label4(p.measurement_labels[i], m.x - 35, m.y + 36, c.ink, 24);
    });
    b += segment({ x: 90, y: 1375 }, { x: 990, y: 1375 }, c.ink, 2);
    s.lengths.forEach((len, i) => b += label4(`${p.measurement_labels[i]} = ${len.toFixed(2)}`, 90 + i * 300, 1450, c.ink, 27));
    if (p.constraints.includes("area")) b += label4(`Alan = ${Math.abs(s.area).toFixed(2)}`, 90, 1520, c.muted, 28);
    if (p.constraints.includes("lengths")) b += label4("\u0394 kenar uzunlu\u011Fu = 0", 600, 1520, c.muted, 28);
    b += caption2(p, seconds);
    return svg3(ID75, p, seconds, b);
  }
  function validateSpec75(spec) {
    return { id: ID75, version: "1.0.0", parameters: validatedParameters4(spec) };
  }

  // renderers/template-registry/modules/05aa663c6498-ui-state-transition-lab.mjs
  var aa663c6498_ui_state_transition_lab_exports = {};
  __export(aa663c6498_ui_state_transition_lab_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE77,
    ID: () => ID76,
    METADATA: () => METADATA68,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA76,
    SOURCE_ID: () => SOURCE_ID76,
    render: () => render76,
    sample: () => sample76,
    validateSpec: () => validateSpec76
  });
  var ID76 = "ui-state-transition-lab";
  var SOURCE_ID76 = "src-athemeroy-style-motion-graphics-ui";
  var DEFAULT_PALETTE77 = COOL;
  var F5 = { state_graph: O2({ nodes: A2(O2({ key: T(16), label: T(32) }), 3, 4), edges: A2(O2({ from: T(16), to: T(16) }), 2, 3) }), component_bounds: A2(O2({ x: N2(28, 600), y: N2(90, 650), width: N2(100, 660), height: N2(65, 190) }), 2, 4), event_cues: A2(O2({ at: N2(0.16, 0.72), label: T(24) }), 2, 3), progress_values: A2(N2(0, 1), 3, 4) };
  var PARAMETER_SCHEMA76 = schema3(F5);
  var METADATA68 = metadata3("Aray\xFCz durum laboratuvar\u0131", "interface-state-panel", "event-gated graph \u2192 target component layout \u2192 monotone loading \u2192 completed rest", ["large state heading", "original component cards", "event and progress rail"]);
  function validatedParameters5(spec) {
    const p = parameters(spec, ID76, F5, DEFAULT_PALETTE77), nodes = p.state_graph.nodes;
    ensure(new Set(nodes.map((n) => n.key)).size === nodes.length, "state_graph: unique node keys required");
    ensure(p.state_graph.edges.length === nodes.length - 1 && p.event_cues.length === nodes.length - 1 && p.progress_values.length === nodes.length, "state_graph: one edge/event per transition and one progress value per state required");
    p.state_graph.edges.forEach((e, i) => ensure(e.from === nodes[i].key && e.to === nodes[i + 1].key, "state_graph: consecutive reachable edges required"));
    p.event_cues.forEach((e, i) => {
      ensure(i === 0 || e.at - p.event_cues[i - 1].at >= 0.12, "event_cues: increasing spaced events required");
      fitText3(e.label, { width: 225, maximum: 26, minimum: 23, maxLines: 2 });
    });
    ensure(p.progress_values[0] === 0 && p.progress_values.at(-1) === 1 && p.progress_values.every((n, i, a) => i === 0 || n >= a[i - 1]), "progress_values: monotone sequence from 0 to 1 required");
    p.component_bounds.forEach((b, i) => {
      ensure(b.x + b.width <= 720 && b.y + b.height <= 740, "component_bounds: panel overflow");
      p.component_bounds.slice(0, i).forEach((a) => ensure(b.x >= a.x + a.width + 12 || a.x >= b.x + b.width + 12 || b.y >= a.y + a.height + 12 || a.y >= b.y + b.height + 12, "component_bounds: separated components required"));
    });
    return p;
  }
  function sample76(spec, seconds) {
    const p = validatedParameters5(spec), u = unit(p, seconds), eventIndex = p.event_cues.filter((e) => u >= e.at).length, layout = at(u, 0.03, p.event_cues[0].at), events = [0, ...p.event_cues.map((e) => e.at)], next = Math.min(eventIndex + 1, events.length - 1), q = eventIndex === events.length - 1 ? 1 : at(u, events[eventIndex], events[next]), loading = lerp3(p.progress_values[eventIndex], p.progress_values[next], q), components = p.component_bounds.map((b, i) => ({ x: lerp3(360 - b.width / 2, b.x, layout), y: lerp3(140 + i * 86, b.y, layout), width: lerp3(150, b.width, layout), height: lerp3(65, b.height, layout) }));
    return { event_index: eventIndex, key: p.state_graph.nodes[eventIndex].key, loading, components, layout, tab_x: 150 + eventIndex * (780 / p.state_graph.nodes.length), reachable_keys: p.state_graph.nodes.slice(0, eventIndex + 1).map((n) => n.key) };
  }
  function render76(spec, seconds) {
    const p = validatedParameters5(spec), s = sample76(spec, seconds), c = p.palette;
    let b = label4("DURUM / 05", 90, 130, c.accent, 25) + headline(p, { y: 225, maximum: 56 }) + svgText3(p.state_graph.nodes[s.event_index].label, { x: 150, y: 550, width: 780, maximum: 48, minimum: 34, maxLines: 2, fill: c.ink }) + box2(150, 610, 780, 790, c.background, `rx="28" stroke="${c.ink}" stroke-width="4"`);
    const w = 780 / p.state_graph.nodes.length;
    p.state_graph.nodes.forEach((n, i) => b += label4(String(i + 1).padStart(2, "0"), 180 + i * w, 663, c.muted, 24));
    b += box2(s.tab_x + 22, 687, w - 44, 7, c.accent);
    s.components.forEach((r, i) => {
      b += box2(150 + r.x, 610 + r.y, r.width, r.height, c.accent, `rx="12" fill-opacity="0.1" stroke="${c.muted}" stroke-width="2"`) + label4(`Alan ${i + 1}`, 166 + r.x, 645 + r.y, c.ink, 23) + segment({ x: 168 + r.x, y: 660 + r.y }, { x: 150 + r.x + Math.max(35, r.width * 0.65), y: 660 + r.y }, c.muted, 4);
    });
    b += box2(185, 1325, 710, 16, c.muted, 'rx="8" fill-opacity="0.2"') + box2(185, 1325, 710 * s.loading, 16, c.accent, 'rx="8"') + label4(`${Math.round(100 * s.loading)}%`, 800, 1380, c.ink, 29);
    p.event_cues.forEach((e, i) => {
      const x = 170 + i * 300;
      b += dot({ x, y: 1490 }, 10, i < s.event_index ? c.accent : c.muted) + svgText3(e.label, { x: x - 30, y: 1540, width: 225, maximum: 26, minimum: 23, maxLines: 2, fill: c.ink });
    });
    b += caption2(p, seconds);
    return svg3(ID76, p, seconds, b);
  }
  function validateSpec76(spec) {
    return { id: ID76, version: "1.0.0", parameters: validatedParameters5(spec) };
  }

  // renderers/template-registry/modules/be1e443de10e-pixel-cellular-ecosystem.mjs
  var be1e443de10e_pixel_cellular_ecosystem_exports = {};
  __export(be1e443de10e_pixel_cellular_ecosystem_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE78,
    ID: () => ID77,
    METADATA: () => METADATA69,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA77,
    SOURCE_ID: () => SOURCE_ID77,
    evolve: () => evolve,
    render: () => render77,
    sample: () => sample77,
    validateSpec: () => validateSpec77
  });
  var ID77 = "pixel-cellular-ecosystem";
  var SOURCE_ID77 = "src-athemeroy-style-pixel-art";
  var DEFAULT_PALETTE78 = COOL;
  var F6 = { initial_cells: A2(O2({ x: N2(0, 23, true), y: N2(0, 23, true), state: N2(1, 2, true) }), 1, 24), transition_rules: O2({ birth_neighbors: N2(1, 4, true), mature_after: N2(1, 4, true), decay_after: N2(3, 8, true) }), grid_size: O2({ columns: N2(12, 24, true), rows: N2(12, 24, true) }), tick_cadence: N2(0.25, 0.8) };
  var PARAMETER_SCHEMA77 = schema3(F6);
  var METADATA69 = metadata3("Piksel h\xFCcre ekosistemi", "integer-cell-laboratory", "local toroidal neighbor rule \u2192 growth \u2192 mature/decay \u2192 frozen tick", ["broad integer grid", "population ledger", "monospace rule key"]);
  function validatedParameters6(spec) {
    const p = parameters(spec, ID77, F6, DEFAULT_PALETTE78), { columns, rows } = p.grid_size;
    ensure(p.initial_cells.every((v) => v.x < columns && v.y < rows), "initial_cells: coordinates must fit grid");
    ensure(new Set(p.initial_cells.map((v) => v.x + v.y * columns)).size === p.initial_cells.length, "initial_cells: duplicate coordinate");
    ensure(p.transition_rules.decay_after > p.transition_rules.mature_after, "transition_rules: decay must follow maturity");
    return p;
  }
  function evolve(grid2, columns, rows, rules) {
    return grid2.map((cell, i) => {
      const x = i % columns, y = Math.floor(i / columns), neighbors = [[(x + 1) % columns, y], [(x + columns - 1) % columns, y], [x, (y + 1) % rows], [x, (y + rows - 1) % rows]].reduce((a, [xx, yy]) => a + (grid2[xx + yy * columns].state === 1 ? 1 : 0), 0);
      if (cell.state === 0) return { state: neighbors >= rules.birth_neighbors ? 1 : 0, age: 0 };
      const age = cell.age + 1;
      if (cell.state === 1) return age >= rules.mature_after ? { state: 2, age: 0 } : { state: 1, age };
      return age >= rules.decay_after ? { state: 0, age: 0 } : { state: 2, age };
    });
  }
  function sample77(spec, seconds) {
    const p = validatedParameters6(spec), { columns, rows } = p.grid_size, tick = Math.floor((unit(p, seconds) * (p.duration - 0.8) + 1e-8) / p.tick_cadence);
    let grid2 = Array.from({ length: columns * rows }, () => ({ state: 0, age: 0 }));
    p.initial_cells.forEach((v) => grid2[v.x + v.y * columns] = { state: v.state, age: 0 });
    for (let i = 0; i < tick; i++) grid2 = evolve(grid2, columns, rows, p.transition_rules);
    const counts = [0, 0, 0];
    grid2.forEach((v) => counts[v.state]++);
    return { tick, grid: grid2, counts, columns, rows };
  }
  function render77(spec, seconds) {
    const p = validatedParameters6(spec), s = sample77(spec, seconds), c = p.palette, cell = Math.floor(840 / Math.max(s.columns, s.rows)), left = (1080 - s.columns * cell) / 2, top = 620;
    let b = label4("H\xDCCRESEL NOT DEFTER\u0130", 90, 135, c.accent, 24) + headline(p, { y: 230, maximum: 56 }) + label4(`T\u0130K ${String(s.tick).padStart(3, "0")}`, 90, 550, c.ink, 38) + label4(`${s.columns} \xD7 ${s.rows}`, 750, 550, c.muted, 30);
    s.grid.forEach((v, i) => {
      b += box2(left + i % s.columns * cell, top + Math.floor(i / s.columns) * cell, cell - 2, cell - 2, v.state === 0 ? c.muted : v.state === 1 ? c.accent : c.ink, `opacity="${v.state === 0 ? 0.12 : 1}"`);
      if (v.state === 2) b += box2(left + i % s.columns * cell + cell * 0.32, top + Math.floor(i / s.columns) * cell + cell * 0.32, cell * 0.25, cell * 0.25, c.background);
    });
    b += label4(`${s.counts[1]} b\xFCy\xFCyen`, 90, 1530, c.accent, 32) + label4(`${s.counts[2]} olgun`, 420, 1530, c.ink, 32) + label4(`\u2265${p.transition_rules.birth_neighbors} kom\u015Fu`, 710, 1530, c.muted, 28) + caption2(p, seconds);
    return svg3(ID77, p, seconds, b, "monospace");
  }
  function validateSpec77(spec) {
    return { id: ID77, version: "1.0.0", parameters: validatedParameters6(spec) };
  }

  // renderers/template-registry/modules/7ae25f27401c-ascii-wave-buffer.mjs
  var ae25f27401c_ascii_wave_buffer_exports = {};
  __export(ae25f27401c_ascii_wave_buffer_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE79,
    ID: () => ID78,
    METADATA: () => METADATA70,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA78,
    SOURCE_ID: () => SOURCE_ID78,
    density: () => density,
    render: () => render78,
    sample: () => sample78,
    validateSpec: () => validateSpec78
  });
  var ID78 = "ascii-wave-buffer";
  var SOURCE_ID78 = "src-athemeroy-style-retro-terminal-ascii";
  var DEFAULT_PALETTE79 = DARK2;
  var F7 = { density_field: O2({ frequency_x: N2(0.5, 4), frequency_y: N2(0.5, 3), phase_speed: N2(0.3, 2) }), character_ramp: { type: "string", format: "ascii-ramp", maxLength: 12 }, update_regions: A2(O2({ x: N2(0, 27, true), y: N2(0, 17, true), width: N2(5, 32, true), height: N2(3, 20, true) }), 1, 3), tear_cadence: N2(0.2, 0.8) };
  var PARAMETER_SCHEMA78 = schema3(F7);
  var METADATA70 = metadata3("ASCII dalga tamponu", "cursor-addressed-terminal", "region row write \u2192 wave density \u2192 deterministic raster tear \u2192 stopped buffer", ["monospace title", "fixed character buffer", "write address and region key"]);
  function validatedParameters7(spec) {
    const p = parameters(spec, ID78, F7, DEFAULT_PALETTE79);
    ensure(p.update_regions.every((r) => r.x + r.width <= 32 && r.y + r.height <= 20), "update_regions: buffer overflow");
    return p;
  }
  function density(x, y, t, f) {
    return Math.max(0, Math.min(1, 0.5 + 0.27 * Math.sin(x / 32 * Math.PI * 2 * f.frequency_x + t * f.phase_speed) + 0.22 * Math.cos(y / 20 * Math.PI * 2 * f.frequency_y - t * f.phase_speed * 0.7)));
  }
  function sample78(spec, seconds) {
    const p = validatedParameters7(spec), tick = Math.floor((unit(p, seconds) * (p.duration - 0.8) + 1e-8) / p.tear_cadence), buffer2 = Array(640).fill(p.character_ramp[0]);
    let cursor = { x: p.update_regions[0].x, y: p.update_regions[0].y }, last_write = { region: 0, row: cursor.y, tear: 0 };
    for (let k = 0; k <= tick; k++) {
      const ri = k % p.update_regions.length, r = p.update_regions[ri], row = r.y + Math.floor(k / p.update_regions.length) % r.height, time2 = k * p.tear_cadence;
      for (let x = r.x; x < r.x + r.width; x++) buffer2[row * 32 + x] = p.character_ramp[Math.min(p.character_ramp.length - 1, Math.floor(density(x, row, time2, p.density_field) * p.character_ramp.length))];
      const tear = k > 0 && k % 3 === 0 ? k % 2 ? 2 : -2 : 0;
      if (tear) {
        const old = buffer2.slice(row * 32, (row + 1) * 32);
        for (let x = 0; x < 32; x++) buffer2[row * 32 + x] = old[(x - tear + 32) % 32];
      }
      cursor = { x: r.x + (k + 1) % r.width, y: row };
      last_write = { region: ri, row, tear };
    }
    return { tick, buffer: buffer2, rows: Array.from({ length: 20 }, (_, y) => buffer2.slice(y * 32, (y + 1) * 32).join("")), cursor, last_write, columns: 32, height: 20 };
  }
  function render78(spec,seconds){const p=validatedParameters7(spec),s=sample78(spec,seconds),c=p.palette;let b=label4('BUFFER://YEREL-07',90,130,c.accent,25)+headline(p,{y:230,maximum:52})+segment({x:90,y:520},{x:990,y:520},c.muted,2)+label4(`WRITE ${String(s.cursor.y).padStart(2,'0')}:${String(s.cursor.x).padStart(2,'0')}`,90,580,c.ink,29)+label4(`TICK ${String(s.tick).padStart(3,'0')}`,760,580,c.muted,27)+box2(108,630,864,710,c.background,`stroke="${c.muted}" stroke-width="2"`);
   // Assign every character its buffer-cell origin. Letter spacing alone adds
   // proportional glyph advances and lets wide ramps escape the fixed panel.
   const columns=Array.from({length:s.columns},(_,x)=>124+x*26).join(' ');
   s.rows.forEach((row,y)=>{b+=`<text data-motion-role="buffer-row" x="${columns}" y="${670+y*32}" fill="${c.accent}" font-size="26" xml:space="preserve">${esc3(row)}</text>`;});b+=box2(122+s.cursor.x*26,645+s.cursor.y*32,25,30,'none',`stroke="${c.ink}" stroke-width="2"`);p.update_regions.forEach((r,i)=>b+=label4(`R${i+1} [${r.x},${r.y}] ${r.width}×${r.height}`,100,1410+i*48,c.muted,25));b+=label4(`SATIR KAYMASI ${s.last_write.tear}`,620,1540,c.ink,26)+caption2(p,seconds);return svg3(ID78,p,seconds,b,'monospace');}
  function validateSpec78(spec) {
    return { id: ID78, version: "1.0.0", parameters: validatedParameters7(spec) };
  }

  // renderers/template-registry/modules/22f17bc3c0c8-orbital-shadow-machine.mjs
  var f17bc3c0c8_orbital_shadow_machine_exports = {};
  __export(f17bc3c0c8_orbital_shadow_machine_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE80,
    ID: () => ID79,
    METADATA: () => METADATA71,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA79,
    SOURCE_ID: () => SOURCE_ID79,
    castShadow: () => castShadow,
    project: () => project4,
    render: () => render79,
    sample: () => sample79,
    validateSpec: () => validateSpec79
  });
  var ID79 = "orbital-shadow-machine";
  var SOURCE_ID79 = "src-athemeroy-style-3d-render";
  var DEFAULT_PALETTE80 = COOL;
  var F8 = { link_lengths: A2(N2(90, 170), 2, 3), joint_angles: A2(N2(-60, 60), 2, 3), light_pose: O2({ x: N2(-420, 420), y: N2(-450, -200), z: N2(600, 1e3) }), camera_path: A2(N2(-0.55, 0.55), 2) };
  var PARAMETER_SCHEMA79 = schema3(F8);
  var METADATA71 = metadata3("Y\xF6r\xFCnge ve g\xF6lge makinesi", "projected-solid-cutaway", "fixed-length spatial links \u2192 camera yaw \u2192 point-light floor intersection \u2192 depth sorted solids", ["engineering index", "projected solid mechanism", "length and light ledger"]);
  function validatedParameters8(spec) {
    const p = parameters(spec, ID79, F8, DEFAULT_PALETTE80);
    ensure(p.link_lengths.length === p.joint_angles.length, "joint_angles: one angle per link required");
    ensure(p.link_lengths.reduce((a, v) => a + v, 0) <= 420, "link_lengths: total reach must be \u2264420");
    return p;
  }
  function project4(v, yaw) {
    return { x: 540 + v.x * Math.cos(yaw) - v.y * Math.sin(yaw), y: 1150 + (v.x * Math.sin(yaw) + v.y * Math.cos(yaw)) * 0.45 - v.z };
  }
  function castShadow(v, l) {
    const lambda = l.z / (l.z - v.z);
    return { x: l.x + (v.x - l.x) * lambda, y: l.y + (v.y - l.y) * lambda, z: 0, lambda };
  }
  function sample79(spec, seconds) {
    const p = validatedParameters8(spec), q = at(unit(p, seconds), 0.08, 0.91), yaw = lerp3(p.camera_path[0], p.camera_path[1], q), joints = [{ x: -190, y: 0, z: 100 }];
    let bearing = 0;
    for (let i = 0; i < p.link_lengths.length; i++) {
      bearing += lerp3(i % 2 ? 35 : -30, p.joint_angles[i], q) * Math.PI / 180;
      const elevation = (i % 2 ? -12 : 22) * Math.PI / 180, prev = joints.at(-1), L2 = p.link_lengths[i];
      joints.push({ x: prev.x + L2 * Math.cos(bearing) * Math.cos(elevation), y: prev.y + L2 * Math.sin(bearing) * Math.cos(elevation), z: prev.z + L2 * Math.sin(elevation) });
    }
    const links = p.link_lengths.map((L2, i) => ({ index: i, a: joints[i], b: joints[i + 1], a2: project4(joints[i], yaw), b2: project4(joints[i + 1], yaw), length: L2, depth: ((joints[i].x + joints[i + 1].x) * Math.sin(yaw) + (joints[i].y + joints[i + 1].y) * Math.cos(yaw)) / 2 })), shadows = joints.map((v) => castShadow(v, p.light_pose));
    return { joints, links, shadows, shadow_points: shadows.map((v) => project4(v, yaw)), draw_order: links.toSorted((a, b) => a.depth - b.depth || a.index - b.index).map((v) => v.index), yaw, progress: q, joint_angles: p.joint_angles.map((v, i) => lerp3(i % 2 ? 35 : -30, v, q)) };
  }
  function render79(spec, seconds) {
    const p = validatedParameters8(spec), s = sample79(spec, seconds), c = p.palette;
    let b = label4("08 / MEKAN\u0130K KES\u0130T", 90, 125, c.accent, 24) + headline(p, { x: 155, y: 235, width: 835, maximum: 55 }) + path5([{ x: 110, y: 1170 }, { x: 580, y: 920 }, { x: 1e3, y: 1200 }, { x: 530, y: 1460 }], c.accent, c.muted, 2, 'fill-opacity="0.06"');
    for (let i = 0; i < s.shadow_points.length - 1; i++) b += segment(s.shadow_points[i], s.shadow_points[i + 1], c.ink, 26, 'opacity="0.17" stroke-linecap="round"');
    const lamp = project4(p.light_pose, s.yaw);
    b += dot({ x: 175, y: 630 }, 13, c.accent) + label4("TEK NOKTA I\u015EI\u011EI", 205, 640, c.muted, 24);
    s.draw_order.forEach((i) => {
      const l = s.links[i], dx = l.b2.x - l.a2.x, dy = l.b2.y - l.a2.y, d = Math.hypot(dx, dy), nx = -dy / d * 15, ny = dx / d * 15, poly2 = [{ x: l.a2.x + nx, y: l.a2.y + ny }, { x: l.b2.x + nx, y: l.b2.y + ny }, { x: l.b2.x - nx, y: l.b2.y - ny }, { x: l.a2.x - nx, y: l.a2.y - ny }];
      b += path5(poly2.map((v) => ({ x: v.x + 8, y: v.y + 12 })), c.ink) + path5(poly2, c.accent, c.ink, 3) + dot(l.a2, 24, c.background, `stroke="${c.ink}" stroke-width="5"`) + dot(l.b2, 24, c.background, `stroke="${c.ink}" stroke-width="5"`);
    });
    b += segment(s.links.at(-1).b2, s.shadow_points.at(-1), c.muted, 2, 'stroke-dasharray="5 8" opacity="0.6"') + label4("Z = 0 / G\xD6LGE D\xDCZLEM\u0130", 145, 1515, c.muted, 27);
    p.link_lengths.forEach((L2, i) => b += label4(`L${i + 1} ${L2}`, 90 + i * 285, 1590, c.ink, 27));
    b += caption2(p, seconds, { y: 1710, maximum: 39 });
    return svg3(ID79, p, seconds, b);
  }
  function validateSpec79(spec) {
    return { id: ID79, version: "1.0.0", parameters: validatedParameters8(spec) };
  }

  // renderers/template-registry/modules/95591e3235b5-original-anime-action-arc.mjs
  var e3235b5_original_anime_action_arc_exports = {};
  __export(e3235b5_original_anime_action_arc_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE81,
    ID: () => ID80,
    METADATA: () => METADATA72,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA80,
    SOURCE_ID: () => SOURCE_ID80,
    render: () => render80,
    sample: () => sample80,
    validateSpec: () => validateSpec80
  });
  var ID80 = "original-anime-action-arc";
  var SOURCE_ID80 = "src-athemeroy-style-anime";
  var DEFAULT_PALETTE81 = ROSE;
  var F9 = { pose_sequence: A2(E2("coil", "reach", "brace"), 3), impact_cues: A2(N2(0.7, 0.84), 1, 2), arc_path: A2(P2(280, 800, 750, 1280), 3), speedline_density: N2(8, 28, true) };
  var PARAMETER_SCHEMA80 = schema3(F9);
  var METADATA72 = metadata3("\xD6zg\xFCn habercinin hareket yay\u0131", "angular-courier-action-panel", "held anticipation \u2192 quadratic travel \u2192 stepped poses \u2192 bounded impact pulse \u2192 landing hold", ["quiet headline", "diagonal original character panel", "action and distance strip"]);
  function validatedParameters9(spec) {
    const p = parameters(spec, ID80, F9, DEFAULT_PALETTE81);
    ensure(new Set(p.pose_sequence).size === 3, "pose_sequence: one of each original pose required");
    ensure(Math.hypot(p.arc_path[2].x - p.arc_path[0].x, p.arc_path[2].y - p.arc_path[0].y) >= 200, "arc_path: distinct departure and landing required");
    ensure(p.impact_cues.every((v, i, a) => i === 0 || v - a[i - 1] >= 0.06), "impact_cues: distinct ordered impacts required");
    return p;
  }
  function sample80(spec, seconds) {
    const p = validatedParameters9(spec), u = unit(p, seconds), travel = at(u, 0.2, 0.7), position = bezier(...p.arc_path, travel), pose2 = u < 0.2 ? p.pose_sequence[0] : u < 0.7 ? p.pose_sequence[1] : p.pose_sequence[2], impact = p.impact_cues.reduce((m, c) => Math.max(m, Math.max(0, 1 - Math.abs(u - c) / 0.025)), 0), speed = u > 0.2 && u < 0.7 ? Math.sin(Math.PI * travel) : 0;
    return { position, travel, pose: pose2, impact, speed, stage: u < 0.2 ? "anticipation" : u < 0.7 ? "flight" : "landed", mask_center: position };
  }
  var POSES3 = { coil: { elbow: [-55, 30], hand: [-5, -5], knee: [-45, 85], foot: [5, 100] }, reach: { elbow: [30, -15], hand: [78, -65], knee: [-25, 70], foot: [-75, 78] }, brace: { elbow: [50, 25], hand: [58, 65], knee: [20, 95], foot: [65, 110] } };
  function render80(spec, seconds) {
    const p = validatedParameters9(spec), s = sample80(spec, seconds), c = p.palette, v = s.position, pose2 = POSES3[s.pose], pt2 = (a) => ({ x: v.x + a[0], y: v.y + a[1] });
    let b = headline(p, { y: 205, maximum: 58 }) + label4("\xD6ZG\xDCN HABERC\u0130 / HAREKET \xC7ALI\u015EMASI", 90, 510, c.muted, 24) + path5([{ x: 130, y: 665 }, { x: 950, y: 605 }, { x: 975, y: 1440 }, { x: 110, y: 1490 }], c.background, c.ink, 4) + `<defs><mask id="action-exclusion"><rect x="100" y="600" width="880" height="900" fill="#FFFFFF"/><circle cx="${fmt3(v.x)}" cy="${fmt3(v.y)}" r="125" fill="#000000"/></mask></defs><g mask="url(#action-exclusion)">`;
    for (let i = 0; i < p.speedline_density; i++) {
      const y = 690 + i * (660 / p.speedline_density), start = 170 + i % 3 * 30, end = 170 + s.speed * (630 - i % 4 * 45);
      b += segment({ x: start, y }, { x: end, y: y - 75 * s.speed }, c.accent, 1 + i % 3, `opacity="${fmt3(s.speed * 0.65)}"`);
    }
    b += "</g>";
    b += `<path d="M${fmt3(p.arc_path[0].x)} ${fmt3(p.arc_path[0].y)}Q${fmt3(p.arc_path[1].x)} ${fmt3(p.arc_path[1].y)} ${fmt3(p.arc_path[2].x)} ${fmt3(p.arc_path[2].y)}" fill="none" stroke="${c.muted}" stroke-width="2" stroke-dasharray="5 12" opacity="0.35"/>`;
    b += path5([pt2([-25, -25]), pt2([35, -20]), pt2([53, 45]), pt2([-36, 47])], c.accent, c.ink, 4) + path5([pt2([-36, -52]), pt2([-12, -92]), pt2([39, -71]), pt2([48, -35]), pt2([5, -23])], c.background, c.ink, 4) + path5([pt2([-28, -54]), pt2([-8, -82]), pt2([25, -71]), pt2([31, -46])], c.ink) + segment(pt2([10, -41]), pt2([25, -44]), c.ink, 3) + path5([pt2([-30, -15]), pt2([-65 - 65 * s.speed, -3]), pt2([-58 - 60 * s.speed, 20]), pt2([-12, 4])], c.accent, c.ink, 3);
    b += segment(pt2([12, 5]), pt2(pose2.elbow), c.ink, 15, 'stroke-linecap="round"') + segment(pt2(pose2.elbow), pt2(pose2.hand), c.ink, 13, 'stroke-linecap="round"') + segment(pt2([-5, 40]), pt2(pose2.knee), c.ink, 17, 'stroke-linecap="round"') + segment(pt2(pose2.knee), pt2(pose2.foot), c.ink, 16, 'stroke-linecap="round"') + dot(pt2(pose2.hand), 8, c.background, `stroke="${c.ink}" stroke-width="3"`);
    if (s.impact > 0) {
      for (let i = 0; i < 6; i++) {
        const a = i * Math.PI / 3;
        b += segment({ x: v.x + Math.cos(a) * 95, y: v.y + 110 + Math.sin(a) * 30 }, { x: v.x + Math.cos(a) * (95 + 65 * s.impact), y: v.y + 110 + Math.sin(a) * (30 + 35 * s.impact) }, c.accent, 5);
      }
    }
    b += label4(s.stage === "anticipation" ? "HAZIRLIK" : s.stage === "flight" ? "HAREKET" : "VARI\u015E", 90, 1585, c.ink, 37) + label4(`Yay: ${Math.round(s.travel * 100)}%`, 700, 1585, c.muted, 28) + caption2(p, seconds);
    return svg3(ID80, p, seconds, b);
  }
  function validateSpec80(spec) {
    return { id: ID80, version: "1.0.0", parameters: validatedParameters9(spec) };
  }

  // renderers/template-registry/modules/3cb1c2447d23-sand-rake-reformation.mjs
  var cb1c2447d23_sand_rake_reformation_exports = {};
  __export(cb1c2447d23_sand_rake_reformation_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE82,
    ID: () => ID81,
    METADATA: () => METADATA73,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA81,
    SOURCE_ID: () => SOURCE_ID81,
    render: () => render81,
    sample: () => sample81,
    symbolPoint: () => symbolPoint,
    validateSpec: () => validateSpec81
  });
  var ID81 = "sand-rake-reformation";
  var SOURCE_ID81 = "src-athemeroy-style-painterly-ink-sand";
  var DEFAULT_PALETTE82 = LIGHT;
  var F10 = { rake_path: A2(P2(260, 820, 760, 1260), 3, 5), grain_seed: N2(1, 65535, true), ridge_height: N2(8, 28), symbol_sequence: A2(E2("circle", "arch", "chevron"), 2, 3) };
  var PARAMETER_SCHEMA81 = schema3(F10);
  var METADATA73 = metadata3("Kumun izden bi\xE7ime d\xF6n\xFC\u015F\xFCm\xFC", "raked-material-tray", "tool path \u2192 bounded normal ridges \u2192 mass-preserving symbol reformations \u2192 exact held figure", ["centered serif title", "material count", "tray and symbol ledger"]);
  function validatedParameters10(spec) {
    const p = parameters(spec, ID81, F10, DEFAULT_PALETTE82);
    ensure(p.rake_path.every((v, i, a) => i === 0 || distance(v, a[i - 1]) >= 90), "rake_path: separated consecutive control points required");
    ensure(p.symbol_sequence.every((v, i, a) => i === 0 || v !== a[i - 1]), "symbol_sequence: consecutive symbols must differ");
    return p;
  }
  function symbolPoint(kind, i, total = 144) {
    const u = i / total, a = u * Math.PI * 2;
    if (kind === "circle") return { x: 540 + Math.cos(a) * 235, y: 1030 + Math.sin(a) * 235 };
    if (kind === "arch") {
      const angle = Math.PI + u * Math.PI;
      return { x: 540 + Math.cos(angle) * 260, y: 1160 + Math.sin(angle) * 270 };
    }
    return u < 0.5 ? mixPoint({ x: 285, y: 1170 }, { x: 540, y: 835 }, u * 2) : mixPoint({ x: 540, y: 835 }, { x: 795, y: 1170 }, (u - 0.5) * 2);
  }
  function toolAt(points, u) {
    const z = Math.min(u, 1) * (points.length - 1), i = Math.min(points.length - 2, Math.floor(z));
    return mixPoint(points[i], points[i + 1], z - i);
  }
  function rake(base6, points, sweep, height) {
    let best = { dist: 1e9, dx: 0, dy: 0 };
    for (let i = 0; i < points.length - 1; i++) {
      const limit = Math.max(0, Math.min(1, sweep * (points.length - 1) - i));
      if (limit === 0) continue;
      const a = points[i], b = mixPoint(a, points[i + 1], limit), vx = b.x - a.x, vy = b.y - a.y, len = Math.hypot(vx, vy), t = Math.max(0, Math.min(1, ((base6.x - a.x) * vx + (base6.y - a.y) * vy) / (len * len))), near = { x: a.x + t * vx, y: a.y + t * vy }, dist = distance(base6, near);
      if (dist < best.dist) best = { dist, dx: -vy / len, dy: vx / len };
    }
    const amount = best.dist < 85 ? height * (1 - best.dist / 85) : 0;
    return { x: base6.x + best.dx * amount, y: base6.y + best.dy * amount, displacement: amount };
  }
  function sample81(spec, seconds) {
    const p = validatedParameters10(spec), u = unit(p, seconds), sweep = at(u, 0.04, 0.43), reform = Math.max(0, Math.min(1, (u - 0.45) / 0.49)), z = reform * p.symbol_sequence.length, stage = Math.min(p.symbol_sequence.length - 1, Math.floor(z)), q = at(z - stage, 0, 1), grains = Array.from({ length: 144 }, (_, i) => {
      const base6 = { x: 260 + i % 12 * 50 + (hash(p.grain_seed, i) - 0.5) * 13, y: 760 + Math.floor(i / 12) * 45 + (hash(p.grain_seed, i + 144) - 0.5) * 13 }, raked = rake(base6, p.rake_path, sweep, p.ridge_height), previous = stage === 0 ? raked : symbolPoint(p.symbol_sequence[stage - 1], i), target7 = symbolPoint(p.symbol_sequence[stage], i), point4 = mixPoint(previous, target7, q);
      return { id: i, base: base6, raked, target: target7, ...point4 };
    }), tool = toolAt(p.rake_path, sweep);
    return { grains, tool, tool_parked: u >= 0.45, sweep, reform, symbol_index: stage, symbol: p.symbol_sequence[stage], blend: q };
  }
  function render81(spec, seconds) {
    const p = validatedParameters10(spec), s = sample81(spec, seconds), c = p.palette;
    let b = headline(p, { x: 540, y: 220, width: 880, maximum: 58, anchor: "middle" }) + label4("144", 130, 550, c.ink, 94) + label4("ayn\u0131 kum tanesi", 350, 535, c.muted, 30) + box2(155, 635, 770, 775, c.accent, `rx="70" fill-opacity="0.065" stroke="${c.muted}" stroke-width="3"`);
    for (let j = -2; j <= 2; j++) b += `<path d="${listPath(p.rake_path.map((v) => ({ x: v.x + j * p.ridge_height * 0.45, y: v.y + j * p.ridge_height * 0.25 })))}" fill="none" stroke="${c.accent}" stroke-width="2" opacity="${fmt3(s.sweep * (1 - s.reform) * 0.28)}"/>`;
    s.grains.forEach((g) => {
      b += dot(g, 2.8 + hash(p.grain_seed, g.id + 400) * 1.5, c.accent) + segment({ x: g.x - 3, y: g.y + 5 }, { x: g.x + 4, y: g.y + 5 }, c.muted, 1, 'opacity="0.35"');
    });
    const tool = s.tool_parked ? { x: 200, y: 1320 } : s.tool;
    b += segment({ x: tool.x - 50, y: tool.y - 60 }, { x: tool.x + 50, y: tool.y - 60 }, c.ink, 9) + segment({ x: tool.x, y: tool.y - 60 }, { x: tool.x, y: tool.y - 145 }, c.ink, 8);
    for (let j = -2; j <= 2; j++) b += segment({ x: tool.x + j * 20, y: tool.y - 60 }, { x: tool.x + j * 20, y: tool.y - 20 }, c.ink, 5);
    b += label4(s.reform > 0 ? `B\u0130\xC7\u0130M ${s.symbol_index + 1} / ${s.symbol.toUpperCase()}` : "TIRMIK / \u0130Z / SIRT", 145, 1520, c.ink, 30) + caption2(p, seconds);
    return svg3(ID81, p, seconds, b, "serif");
  }
  function validateSpec81(spec) {
    return { id: ID81, version: "1.0.0", parameters: validatedParameters10(spec) };
  }

  // renderers/template-registry/modules/bf5ceb0dc5c1-torn-edge-layer-transfer.mjs
  var bf5ceb0dc5c1_torn_edge_layer_transfer_exports = {};
  __export(bf5ceb0dc5c1_torn_edge_layer_transfer_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE83,
    ID: () => ID82,
    METADATA: () => METADATA74,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA82,
    SOURCE_ID: () => SOURCE_ID82,
    render: () => render82,
    sample: () => sample82,
    tornPolygon: () => tornPolygon,
    validateSpec: () => validateSpec82
  });
  var ID82 = "torn-edge-layer-transfer";
  var SOURCE_ID82 = "src-athemeroy-style-paper-cutout-collage";
  var DEFAULT_PALETTE83 = LIGHT;
  var F11 = { tear_paths: A2(A2(N2(-18, 18), 5, 8), 2, 4), layer_order: A2(N2(0, 3, true), 2, 4), pattern_palette: A2(HEX, 2, 4), transfer_paths: A2(O2({ from: P2(260, 820, 790, 1270), to: P2(260, 820, 790, 1270), lift: N2(50, 130) }), 2, 4) };
  var PARAMETER_SCHEMA82 = schema3(F11);
  var METADATA74 = metadata3("Y\u0131rt\u0131k kenarl\u0131 katman aktar\u0131m\u0131", "torn-print-collage", "authored edge separation \u2192 independent lifted arcs \u2192 depth transfer \u2192 rigid settled stack", ["off-axis headline", "original clipped prints", "depth and transfer rail"]);
  function validatedParameters11(spec) {
    const p = parameters(spec, ID82, F11, DEFAULT_PALETTE83), n = p.tear_paths.length;
    ensure(p.layer_order.length === n && p.pattern_palette.length === n && p.transfer_paths.length === n, "layers: tears, order, palette and transfer counts must agree");
    ensure(new Set(p.layer_order).size === n && p.layer_order.every((v) => v < n), "layer_order: complete index permutation required");
    ensure(p.pattern_palette.every((col) => contrastRatio3(p.palette.ink, col) >= 4.5), "pattern_palette: ink contrast must be \u22654.5");
    return p;
  }
  function tornPolygon(offsets) {
    const n = offsets.length;
    return [{ x: -105, y: -115 }, { x: 105, y: -115 }, ...offsets.map((v, i) => ({ x: 105 + v, y: -115 + (i + 1) * 230 / (n + 1) })), { x: 105, y: 115 }, { x: -105, y: 115 }, ...offsets.toReversed().map((v, i) => ({ x: -105 + v, y: 115 - (i + 1) * 230 / (n + 1) }))];
  }
  function sample82(spec, seconds) {
    const p = validatedParameters11(spec), u = unit(p, seconds), layers = p.transfer_paths.map((v, i) => {
      const q = at(u, 0.06 + i * 0.055, 0.8 + i * 0.04), local = tornPolygon(p.tear_paths[i]), center = bezier(v.from, { x: (v.from.x + v.to.x) / 2, y: Math.min(v.from.y, v.to.y) - v.lift }, v.to, q), rotation = (1 - q) * (i % 2 ? 9 : -8), r = rotation * Math.PI / 180, points = local.map((a) => ({ x: center.x + a.x * Math.cos(r) - a.y * Math.sin(r), y: center.y + a.x * Math.sin(r) + a.y * Math.cos(r) })), rank = p.layer_order.indexOf(i);
      return { id: i, center, rotation, points, local, area: Math.abs(signedArea2(points)), depth: rank + Math.sin(Math.PI * q) * 4, q };
    });
    return { layers, draw_order: layers.toSorted((a, b) => a.depth - b.depth || a.id - b.id).map((v) => v.id), settled: layers.every((l) => l.q === 1) };
  }
  function render82(spec, seconds) {
    const p = validatedParameters11(spec), s = sample82(spec, seconds), c = p.palette;
    let b = label4("11 / KATMANIN YEN\u0130 YER\u0130", 90, 135, c.accent, 24) + headline(p, { x: 135, y: 235, width: 815, maximum: 59 }) + segment({ x: 90, y: 625 }, { x: 985, y: 580 }, c.muted, 2);
    s.draw_order.forEach((id) => {
      const l = s.layers[id], clip = `paper-${id}`, shade = l.points.map((v) => ({ x: v.x + 10, y: v.y + 12 }));
      b += path5(shade, c.ink, "none", 1, 'opacity="0.13"') + `<defs><clipPath id="${clip}"><path d="${listPath(l.points, true)}"/></clipPath></defs>` + path5(l.points, p.pattern_palette[id], c.ink, 2) + `<g clip-path="url(#${clip})"><g transform="translate(${fmt3(l.center.x)} ${fmt3(l.center.y)}) rotate(${fmt3(l.rotation)})">`;
      for (let k = -6; k <= 6; k++) {
        const x = k * 35;
        b += segment({ x: x - 150, y: -160 }, { x: x + 170, y: 160 }, c.accent, 2, 'opacity="0.35"');
      }
      b += `</g></g>` + label4(`${id + 1}`, l.center.x - 16, l.center.y + 12, c.ink, 44, 'font-family="serif"');
    });
    b += label4(`S\u0131ra: ${p.layer_order.map((i) => i + 1).join(" \u2192 ")}`, 110, 1515, c.ink, 31) + label4(s.settled ? "YEN\u0130 B\xDCT\xDCN / D\u0130NLENME" : "AYRILMA / TA\u015EIMA", 110, 1570, c.muted, 25) + caption2(p, seconds);
    return svg3(ID82, p, seconds, b);
  }
  function validateSpec82(spec) {
    return { id: ID82, version: "1.0.0", parameters: validatedParameters11(spec) };
  }

  // renderers/template-registry/modules/08bab8372e98-licensed-shot-continuity.mjs
  var bab8372e98_licensed_shot_continuity_exports = {};
  __export(bab8372e98_licensed_shot_continuity_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE84,
    ID: () => ID83,
    METADATA: () => METADATA75,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA83,
    SOURCE_ID: () => SOURCE_ID83,
    render: () => render83,
    sample: () => sample83,
    validateSpec: () => validateSpec83
  });
  var ID83 = "licensed-shot-continuity";
  var SOURCE_ID83 = "src-athemeroy-style-live-action";
  var DEFAULT_PALETTE84 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA83 = schema2({ clip_paths: refsSchema, action_cues: arr2(obj({ clip: str(36), in: num(0, 3600), out: num(0.1, 3600), action_time: num(0, 3600) }), 2, 5), continuity_pairs: arr2(obj({ from: str(36), to: str(36), from_point: pointSchema, to_point: pointSchema, target: pointSchema }), 1, 4), crop_paths: arr2(obj({ clip: str(36), path: pathSchema }), 2, 5) });
  var METADATA75 = metadata2("Aksiyon S\xFCreklili\u011Fi \xB7 \xF6zg\xFCn edit", "action-match-cut-ledger", "trim-duration cuts; source point interpolation; exact screen-space endpoint alignment", ["continuity kicker 30", "headline 56", "cut ledger 30"]);
  var target5 = rect3(80, 440, 920, 1050);
  function aligned(p, i, u) {
    const path6 = p.crop_paths.find((q) => q.clip === p.clip_paths[i]).path, raw = cropAt(path6, u), before = p.continuity_pairs[i - 1], after = p.continuity_pairs[i], a = before?.to_point ?? after.from_point, b = after?.from_point ?? before.to_point, ta = before?.target ?? after.target, tb = after?.target ?? before.target;
    return { crop: translateCropToPoint(raw, { x: lerp2(a.x, b.x, smooth2(u)), y: lerp2(a.y, b.y, smooth2(u)) }, { x: lerp2(ta.x, tb.x, smooth2(u)), y: lerp2(ta.y, tb.y, smooth2(u)) }) };
  }
  function validateParameters31(spec) {
    const p = base5(spec, ID83, ["clip_paths", "action_cues", "continuity_pairs", "crop_paths"]), r = spec.parameters;
    p.clip_paths = refs(r.clip_paths, p, "clip_paths", 2, 5);
    if (new Set(p.clip_paths).size !== p.clip_paths.length) fail2("unique continuity shots required");
    p.action_cues = list3(r.action_cues, "action cues", p.clip_paths.length, p.clip_paths.length).map((q, i) => {
      keys2(q, ["clip", "in", "out", "action_time"]);
      if (q.clip !== p.clip_paths[i]) fail2("action cue order must match shot order");
      const id = ref(q.clip, p), v = { clip: id, in: number2(q.in, "trim in", 0, asset(p, id).duration), out: number2(q.out, "trim out", 0, asset(p, id).duration), action_time: number2(q.action_time, "action time", 0, asset(p, id).duration) };
      if (v.out - v.in < 1.2 || v.action_time !== v.out) fail2("action match must mark outgoing trim boundary");
      return v;
    });
    if (Math.abs(p.action_cues.reduce((n, q) => n + q.out - q.in, 0) - p.duration) > 1e-7) fail2("trim durations must equal composition duration");
    p.continuity_pairs = list3(r.continuity_pairs, "continuity pairs", p.clip_paths.length - 1, p.clip_paths.length - 1).map((q, i) => {
      keys2(q, ["from", "to", "from_point", "to_point", "target"]);
      if (q.from !== p.clip_paths[i] || q.to !== p.clip_paths[i + 1]) fail2("adjacent continuity pair required");
      return { from: q.from, to: q.to, from_point: point3(q.from_point), to_point: point3(q.to_point), target: point3(q.target) };
    });
    p.crop_paths = list3(r.crop_paths, "crop_paths", p.clip_paths.length, p.clip_paths.length).map((q, i) => {
      keys2(q, ["clip", "path"]);
      if (q.clip !== p.clip_paths[i]) fail2("crop path order");
      return { clip: q.clip, path: cropPath(q.path) };
    });
    for (let i = 0; i < p.clip_paths.length; i++) for (let k = 0; k <= 16; k++) aligned(p, i, k / 16);
    return assertTextLayout(p, 920, 56, 4);
  }
  function sample83(spec, seconds) {
    const p = validateParameters31(spec), { t, u, end } = clock3(p, seconds), editTime = p.duration * u;
    let elapsed = 0, i = 0;
    while (i < p.action_cues.length - 1 && editTime >= elapsed + p.action_cues[i].out - p.action_cues[i].in) {
      elapsed += p.action_cues[i].out - p.action_cues[i].in;
      i++;
    }
    const a = p.action_cues[i], local = Math.min(a.out - a.in, editTime - elapsed), v = local / (a.out - a.in), crop = aligned(p, i, v).crop, matches = p.continuity_pairs.map((q, j) => {
      const out = projected(aligned(p, j, 1).crop, target5, q.from_point), inc = projected(aligned(p, j + 1, 0).crop, target5, q.to_point);
      return { from: q.from, to: q.to, outgoing: out, incoming: inc, error_pixels: Math.hypot(out.x - inc.x, out.y - inc.y) };
    });
    return { time: t, progress: u, shot_index: i, edit_time: editTime, playback_rate: p.duration / end, source_time: Math.min(a.out, a.in + local), shot_progress: v, matches, layers: [layer(p, a.clip, Math.min(a.out, a.in + local), crop, target5)] };
  }
  function render83(spec, seconds, frames) {
    const p = validateParameters31(spec), s = sample83(spec, seconds), c = p.palette;
    let elapsed = 0;
    const ledger = p.action_cues.map((q, i) => {
      const x = 80 + 920 * elapsed / p.duration, w = 920 * (q.out - q.in) / p.duration;
      elapsed += q.out - q.in;
      return panel(rect3(x, 1550, w - 8, 16), i === s.shot_index ? c.accent : c.muted) + tx(`P${i + 1}`, x, 1618, w - 8, 28, c.ink, 1);
    }).join("");
    return svg2(ID83, p, tx("AKS\u0130YON E\u015ELE\u015EMES\u0130", 80, 106, 920, 30, c.accent, 1) + tx(p.title, 80, 198, 920, 56, c.ink, 4) + drawLayers(p, s.layers, "continuity", frames) + ledger + panel(rect3(80, 1518, 920 * s.progress, 7), c.accent) + subtitle(p, s.time, 1710) + proxyMark(p));
  }
  function validateSpec83(spec) {
    return deepFreeze({ id: ID83, version: "1.0.0", parameters: validateParameters31(spec) });
  }

  // renderers/template-registry/modules/0d4d416c6c9e-licensed-photo-depth.mjs
  var d4d416c6c9e_licensed_photo_depth_exports = {};
  __export(d4d416c6c9e_licensed_photo_depth_exports, {
    DEFAULT_PALETTE: () => DEFAULT_PALETTE85,
    ID: () => ID84,
    METADATA: () => METADATA76,
    PARAMETER_SCHEMA: () => PARAMETER_SCHEMA84,
    SOURCE_ID: () => SOURCE_ID84,
    render: () => render84,
    sample: () => sample84,
    validateSpec: () => validateSpec84
  });
  var ID84 = "licensed-photo-depth";
  var SOURCE_ID84 = "src-athemeroy-style-photoreal";
  var DEFAULT_PALETTE85 = DEFAULT_PALETTE60;
  var PARAMETER_SCHEMA84 = schema2({ image_paths: arr2(str(36), 1, 2), depth_paths: arr2(str(36), 1, 2), region_masks: arr2(obj({ image: str(36), depth: str(36), depth_value: num(0, 1), polygon: arr2(pointSchema, 3, 8), label: str(60), light_gain: num(0.85, 1.15) }), 2, 5), parallax_bounds: obj({ x_pixels: num(0, 30), y_pixels: num(0, 30), camera_x: num(-1, 1), camera_y: num(-1, 1) }) });
  var METADATA76 = metadata2("Maskeli Foto\u011Fraf Derinli\u011Fi \xB7 \xF6zg\xFCn edit", "depth-ordered-photo-layers", "caller-supplied masks and depth scalars; bounded parallax; masked relighting envelope", ["depth kicker 30", "headline 56", "region ledger 30"]);
  var target6 = rect3(80, 430, 920, 1040);
  function maskPolygon(value) {
    const polygon3 = list3(value, "mask polygon", 3, 8).map((x) => point3(x)), epsilon = 1e-10;
    const turn = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
    const onSegment = (a, b, p) => Math.abs(turn(a, b, p)) <= epsilon && p.x >= Math.min(a.x, b.x) - epsilon && p.x <= Math.max(a.x, b.x) + epsilon && p.y >= Math.min(a.y, b.y) - epsilon && p.y <= Math.max(a.y, b.y) + epsilon;
    const intersects = (a, b, c, d) => {
      const abC = turn(a, b, c), abD = turn(a, b, d), cdA = turn(c, d, a), cdB = turn(c, d, b);
      if (onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b)) return true;
      return (abC > epsilon && abD < -epsilon || abC < -epsilon && abD > epsilon) && (cdA > epsilon && cdB < -epsilon || cdA < -epsilon && cdB > epsilon);
    };
    for (let i = 0; i < polygon3.length; i++) for (let j = i + 1; j < polygon3.length; j++) {
      if (Math.hypot(polygon3[i].x - polygon3[j].x, polygon3[i].y - polygon3[j].y) <= epsilon)
        fail2("mask vertices must be distinct");
      if ((i + 1) % polygon3.length === j || (j + 1) % polygon3.length === i) continue;
      if (intersects(polygon3[i], polygon3[(i + 1) % polygon3.length], polygon3[j], polygon3[(j + 1) % polygon3.length]))
        fail2("nonintersecting mask edges required");
    }
    let sign = 0;
    for (let i = 0; i < polygon3.length; i++) {
      const a = polygon3[i], b = polygon3[(i + 1) % polygon3.length], c = polygon3[(i + 2) % polygon3.length], cross3 = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
      if (Math.abs(cross3) < epsilon) continue;
      if (sign && Math.sign(cross3) !== sign) fail2("convex nonintersecting mask required");
      sign = Math.sign(cross3);
    }
    if (!sign || area(polygon3) < 3e-3) fail2("mask area too small");
    return polygon3;
  }
  function validateParameters32(spec) {
    const p = base5(spec, ID84, ["image_paths", "depth_paths", "region_masks", "parallax_bounds"]), r = spec.parameters;
    p.image_paths = refs(r.image_paths, p, "image_paths", 1, 2);
    p.depth_paths = refs(r.depth_paths, p, "depth_paths", 1, 2);
    if (p.image_paths.some((id) => asset(p, id).kind !== "image") || p.depth_paths.some((id) => asset(p, id).kind !== "depth")) fail2("image and depth handles need matching kinds");
    p.region_masks = list3(r.region_masks, "region masks", 2, 5).map((q) => {
      keys2(q, ["image", "depth", "depth_value", "polygon", "label", "light_gain"]);
      if (!p.image_paths.includes(q.image) || !p.depth_paths.includes(q.depth)) fail2("mask source handles");
      const poly2 = maskPolygon(q.polygon);
      return { image: q.image, depth: q.depth, depth_value: number2(q.depth_value, "region depth", 0, 1), polygon: poly2, label: text2(q.label, "region label", 60), light_gain: number2(q.light_gain, "light gain", 0.85, 1.15) };
    });
    keys2(r.parallax_bounds, ["x_pixels", "y_pixels", "camera_x", "camera_y"]);
    p.parallax_bounds = { x_pixels: number2(r.parallax_bounds.x_pixels, "x parallax", 0, 30), y_pixels: number2(r.parallax_bounds.y_pixels, "y parallax", 0, 30), camera_x: number2(r.parallax_bounds.camera_x, "camera x", -1, 1), camera_y: number2(r.parallax_bounds.camera_y, "camera y", -1, 1) };
    for (const q of p.region_masks) fitText2(`${p.region_masks.indexOf(q) + 1}. ${q.label}`, { width: 440, maximum: 30, minimum: 30, maxLines: 2 });
    return assertTextLayout(p, 920, 56, 4);
  }
  function sample84(spec, seconds) {
    const p = validateParameters32(spec), { t, u } = clock3(p, seconds), b = p.parallax_bounds, q = smooth2(u), regions = [...p.region_masks].sort((a, b2) => b2.depth_value - a.depth_value).map((r) => {
      const dx = b.x_pixels * b.camera_x * (1 - r.depth_value) * q, dy = b.y_pixels * b.camera_y * (1 - r.depth_value) * q, mask = r.polygon.map((pt2) => ({ x: target6.x + pt2.x * target6.w + dx, y: target6.y + pt2.y * target6.h + dy }));
      return { ...r, dx, dy, mask, light_opacity: Math.abs(r.light_gain - 1) * q };
    }), layers = [layer(p, p.image_paths[0], 0, FULL, target6, { transform: { dx: 0, dy: 0, scale: 1, rotation: 0 } }), ...regions.map((r) => layer(p, r.image, 0, FULL, target6, { mask: r.mask, depth_asset_id: r.depth, depth_value: r.depth_value, light_gain: lerp2(1, r.light_gain, q), transform: { dx: r.dx, dy: r.dy, scale: 1, rotation: 0 } }))];
    return { time: t, progress: u, regions, layers };
  }
  function render84(spec, seconds, frames) {
    const p = validateParameters32(spec), s = sample84(spec, seconds), c = p.palette;
    const lighting = s.regions.map((r) => `<polygon points="${r.mask.map((pt2) => `${fmt2(pt2.x)},${fmt2(pt2.y)}`).join(" ")}" fill="${r.light_gain >= 1 ? "#FFFFFF" : "#000000"}" opacity="${fmt2(r.light_opacity)}"/>`).join("");
    return svg2(ID84, p, tx("B\xD6LGE / DER\u0130NL\u0130K KATMANI", 80, 106, 920, 30, c.accent, 1) + tx(p.title, 80, 198, 920, 56, c.ink, 4) + drawLayers(p, s.layers, "photo", frames) + lighting + s.regions.map((r, i) => tx(`${i + 1}. ${r.label}`, 80 + i % 2 * 470, 1515 + Math.floor(i / 2) * 76, 440, 30, c.ink, 2)).join("") + subtitle(p, s.time, 1755, 80, 920, 36) + proxyMark(p, 1890));
  }
  function validateSpec84(spec) {
    return deepFreeze({ id: ID84, version: "1.0.0", parameters: validateParameters32(spec) });
  }

  // renderers/template-registry/registry.mjs
  var definitions = [{ "family_id": "contour-trace", "source_id": "source-mg-style-02-line-art", "batch_id": "B01", "sample_export": "sampleFrame", "render_export": "renderFrame", "requires_caller_media": false }, { "family_id": "shape-morph", "source_id": "source-mg-style-08-morph", "batch_id": "B01", "sample_export": "sampleFrame", "render_export": "renderFrame", "requires_caller_media": false }, { "family_id": "scan-hud", "source_id": "source-mg-style-22-hud", "batch_id": "B01", "sample_export": "sampleFrame", "render_export": "renderFrame", "requires_caller_media": false }, { "family_id": "vector-mass-transfer", "source_id": "source-mg-style-01-flat-vector", "batch_id": "B02", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "cel-contour-boil", "source_id": "source-mg-style-05-cel-boil", "batch_id": "B02", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "cutout-pin-assembly", "source_id": "source-mg-style-06-collage", "batch_id": "B02", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "caption-impact-rig", "source_id": "source-mg-style-18-hanazi", "batch_id": "B02", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "sticker-peel-callout", "source_id": "source-mg-style-19-paperclip", "batch_id": "B02", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "iso-room-route", "source_id": "source-mg-style-03-isometric", "batch_id": "B03", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "perspective-neon-run", "source_id": "source-mg-style-10-synthwave", "batch_id": "B03", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "aurora-refraction-panels", "source_id": "source-mg-style-12-aurora-glass", "batch_id": "B03", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "deco-radial-reveal", "source_id": "source-lemo-style-art-deco", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "terminal-raster", "source_id": "source-lemo-style-ascii-crt", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "split-counter-flip", "source_id": "source-lemo-style-countdown", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "spotlight-product-reveal", "source_id": "source-lemo-style-dark-keynote", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "iris-silhouette-chase", "source_id": "source-lemo-style-spy-titles", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "baseline-type-reflow", "source_id": "source-lemo-style-swiss-motion", "batch_id": "B04", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "dimension-construction", "source_id": "source-lemo-style-blueprint", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "board-pin-routing", "source_id": "source-lemo-style-briefing-board", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "bead-transfer-counts", "source_id": "source-lemo-style-data-physical", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "scale-morph-charts", "source_id": "source-lemo-style-dataviz", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "iso-transport-network", "source_id": "source-lemo-style-iso-infographic", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "constrained-part-section", "source_id": "source-lemo-style-teardown", "batch_id": "B05", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "engraved-hatch-growth", "source_id": "source-lemo-style-engraving", "batch_id": "B06", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "single-path-identity", "source_id": "source-lemo-style-one-line", "batch_id": "B06", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "pictogram-limb-transition", "source_id": "source-lemo-style-pictogram-motion", "batch_id": "B06", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "perspective-pen-wash", "source_id": "source-lemo-style-urban-sketch", "batch_id": "B06", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "stroke-erase-explanation", "source_id": "source-lemo-style-whiteboard", "batch_id": "B06", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "crayon-stroke-fill", "source_id": "source-lemo-style-crayon-book", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "halftone-evidence-lens", "source_id": "source-lemo-style-halftone-dossier", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "paint-ridge-deposition", "source_id": "source-lemo-style-impasto", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "ink-diffusion-front", "source_id": "source-lemo-style-ink-wash", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "ink-drum-misregister", "source_id": "source-lemo-style-risograph", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "pigment-pool-drying", "source_id": "source-lemo-style-watercolor", "batch_id": "B07", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "paper-lightbox-parallax", "source_id": "source-lemo-style-paper-lantern", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "page-hinge-popups", "source_id": "source-lemo-style-paper-popup", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "negative-space-cut", "source_id": "source-lemo-style-papercut-red", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "screenprint-layer-pull", "source_id": "source-lemo-style-silkscreen-poster", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "lead-cell-lightpass", "source_id": "source-lemo-style-stained-glass", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "woodblock-wave-layers", "source_id": "source-lemo-style-ukiyoe", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "carved-groove-print", "source_id": "source-lemo-style-woodcut", "batch_id": "B08", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "stud-lock-assembly", "source_id": "source-lemo-style-brick-toy", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "pixel-depth-diorama", "source_id": "source-lemo-style-hd-2d", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "microgame-state-loop", "source_id": "source-lemo-style-microgame", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "limited-pose-acting", "source_id": "source-lemo-style-midcentury-toon", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "tile-quest-state", "source_id": "source-lemo-style-pixel-rpg", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "rubber-limb-cycle", "source_id": "source-lemo-style-rubber-hose", "batch_id": "B09", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "cel-pose-camera", "source_id": "source-lemo-style-cel-anime-80s", "batch_id": "B10", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "glass-section-orbit", "source_id": "source-lemo-style-glass-product", "batch_id": "B10", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "toon-dialogue-blocking", "source_id": "source-lemo-style-scifi-toon", "batch_id": "B10", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "jointed-shadow-performance", "source_id": "source-lemo-style-shadow-puppet", "batch_id": "B10", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "projection-surface-register", "source_id": "source-lemo-style-white-model", "batch_id": "B10", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "pointcloud-sweep-measure", "source_id": "source-lemo-style-lidar-survey", "batch_id": "B11", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "facet-terrain-growth", "source_id": "source-lemo-style-lowpoly-island", "batch_id": "B11", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "cell-focus-section", "source_id": "source-lemo-style-microscope", "batch_id": "B11", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "rigid-body-lightstage", "source_id": "source-mg-style-04-3d-render", "batch_id": "B11", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "lighttable-register", "source_id": "source-lemo-style-archive-lighttable", "batch_id": "B12", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "score-reveal-wheel", "source_id": "source-lemo-style-game-show", "batch_id": "B12", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "hologram-slice-volume", "source_id": "source-lemo-style-hologram-hud", "batch_id": "B12", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "footage-caption-cuts", "source_id": "source-lemo-style-caption-news", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "timelapse-mosaic", "source_id": "source-lemo-style-city-symphony", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "footage-diagonal-montage", "source_id": "source-lemo-style-kino-montage", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "broadcast-footage-rundown", "source_id": "source-lemo-style-news-package", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "archive-footage-gate", "source_id": "source-lemo-style-newsreel", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "silent-footage-intertitles", "source_id": "source-lemo-style-silent-film", "batch_id": "B13", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "liminal-footage-inspection", "source_id": "source-lemo-style-backrooms", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "screen-focus-follow", "source_id": "source-lemo-style-living-screencast", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "georeferenced-footage-track", "source_id": "source-lemo-style-satellite-briefing", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "footage-tactical-overlay", "source_id": "source-lemo-style-telestrator", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "footage-focus-band", "source_id": "source-lemo-style-tilt-shift", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "media-evidence-compare", "source_id": "source-lemo-style-visual-investigation", "batch_id": "B14", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "vector-puppet-cause", "source_id": "src-athemeroy-style-flat-vector-cartoon", "batch_id": "B15", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "field-orbit-ensemble", "source_id": "src-athemeroy-style-generative-abstract", "batch_id": "B15", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "construction-stroke-stack", "source_id": "src-athemeroy-style-hand-drawn-sketch", "batch_id": "B15", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "geometric-proof-transform", "source_id": "src-athemeroy-style-math-diagram", "batch_id": "B15", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "ui-state-transition-lab", "source_id": "src-athemeroy-style-motion-graphics-ui", "batch_id": "B16", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "pixel-cellular-ecosystem", "source_id": "src-athemeroy-style-pixel-art", "batch_id": "B16", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "ascii-wave-buffer", "source_id": "src-athemeroy-style-retro-terminal-ascii", "batch_id": "B16", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "orbital-shadow-machine", "source_id": "src-athemeroy-style-3d-render", "batch_id": "B17", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "original-anime-action-arc", "source_id": "src-athemeroy-style-anime", "batch_id": "B17", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "sand-rake-reformation", "source_id": "src-athemeroy-style-painterly-ink-sand", "batch_id": "B17", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "torn-edge-layer-transfer", "source_id": "src-athemeroy-style-paper-cutout-collage", "batch_id": "B17", "sample_export": "sample", "render_export": "render", "requires_caller_media": false }, { "family_id": "licensed-shot-continuity", "source_id": "src-athemeroy-style-live-action", "batch_id": "B18", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }, { "family_id": "licensed-photo-depth", "source_id": "src-athemeroy-style-photoreal", "batch_id": "B18", "sample_export": "sample", "render_export": "render", "requires_caller_media": true }];
  var modules = [ffc6796ae06a_contour_trace_exports, bcf766fc13eb_shape_morph_exports, d1ce3e8bcfd_scan_hud_exports, fb574edcf4_vector_mass_transfer_exports, b1d2640cfb89_cel_contour_boil_exports, f4dcd3ea2_cutout_pin_assembly_exports, e3d757d8a6a6_caption_impact_rig_exports, f5239a9fb835_sticker_peel_callout_exports, ff5ac61f8ea_iso_room_route_exports, ba5d_perspective_neon_run_exports, b205d5e0ed2f_aurora_refraction_panels_exports, e55f7e8780df_deco_radial_reveal_exports, eef0c64a3_terminal_raster_exports, a33d8_split_counter_flip_exports, c346a4b44e9b_spotlight_product_reveal_exports, d36dce2821fa_iris_silhouette_chase_exports, bc1bbb0f9f88_baseline_type_reflow_exports, f3a7cd528c4a_dimension_construction_exports, b5e308b_board_pin_routing_exports, d03e84a019_bead_transfer_counts_exports, dc1665fa7e_scale_morph_charts_exports, b37cccf12fab_iso_transport_network_exports, accaca81a3_constrained_part_section_exports, f2c18f83429e_engraved_hatch_growth_exports, c7b47b37de1_single_path_identity_exports, d7125cd46e_pictogram_limb_transition_exports, c39820654d_perspective_pen_wash_exports, a3cd84f26709_stroke_erase_explanation_exports, f297372a_crayon_stroke_fill_exports, d8086956379e_halftone_evidence_lens_exports, e440b89_paint_ridge_deposition_exports, afde3da0ca7_ink_diffusion_front_exports, feb6c9fcea1_ink_drum_misregister_exports, f694a6ac3510_pigment_pool_drying_exports, db6c476432e_paper_lightbox_parallax_exports, c59afdf2fe07_page_hinge_popups_exports, ca2481eb30_negative_space_cut_exports, c58325ff8c_screenprint_layer_pull_exports, c29def5_lead_cell_lightpass_exports, e3c09b_woodblock_wave_layers_exports, f1f65e5b2121_carved_groove_print_exports, b47c644108ee_stud_lock_assembly_exports, bb7abca301_pixel_depth_diorama_exports, bec6fd07b754_microgame_state_loop_exports, c6cd87e211a_limited_pose_acting_exports, ef2e8afd0528_tile_quest_state_exports, dcbc8bd22a1_rubber_limb_cycle_exports, c770ac3b9d21_cel_pose_camera_exports, d6ed6f291f1_glass_section_orbit_exports, cfd3ebc00b_toon_dialogue_blocking_exports, afd5f557_jointed_shadow_performance_exports, a3c669409e2_projection_surface_register_exports, a0c81c9b3_pointcloud_sweep_measure_exports, ddc290dca210_facet_terrain_growth_exports, d86824fe5c34_cell_focus_section_exports, ab609394d1_rigid_body_lightstage_exports, d17763cd66d_lighttable_register_exports, ab85d27f_score_reveal_wheel_exports, f1884452a41_hologram_slice_volume_exports, c074e219fc9_footage_caption_cuts_exports, bd00339694d_timelapse_mosaic_exports, b15403a9e6f_footage_diagonal_montage_exports, cc2886d_broadcast_footage_rundown_exports, archive_footage_gate_exports, b7bdec0914d1_silent_footage_intertitles_exports, c26e42_liminal_footage_inspection_exports, b5267aabb9_screen_focus_follow_exports, a80c4f2fc4_georeferenced_footage_track_exports, f5237f5517_footage_tactical_overlay_exports, e9e2f0828b6_footage_focus_band_exports, b847c80eb3_media_evidence_compare_exports, bf72e86fe8_vector_puppet_cause_exports, eb10ca0d6fa9_field_orbit_ensemble_exports, aed4c0c3a_construction_stroke_stack_exports, b5002cf70549_geometric_proof_transform_exports, aa663c6498_ui_state_transition_lab_exports, be1e443de10e_pixel_cellular_ecosystem_exports, ae25f27401c_ascii_wave_buffer_exports, f17bc3c0c8_orbital_shadow_machine_exports, e3235b5_original_anime_action_arc_exports, cb1c2447d23_sand_rake_reformation_exports, bf5ceb0dc5c1_torn_edge_layer_transfer_exports, bab8372e98_licensed_shot_continuity_exports, d4d416c6c9e_licensed_photo_depth_exports];
  var ENTRIES = Object.freeze(definitions.map((e, i) => {
    const module = modules[i];
    if (module.ID !== e.family_id || module.SOURCE_ID !== e.source_id) throw Error("INTEGRATED_REGISTRY_IDENTITY");
    return Object.freeze({ ...e, module });
  }));
  var byId = new Map(ENTRIES.map((e) => [e.family_id, e]));
  function compileStaged(spec) {
    const d = spec && typeof spec === "object" && !Array.isArray(spec) ? Object.getOwnPropertyDescriptor(spec, "id") : null;
    const e = d && Object.hasOwn(d, "value") ? byId.get(d.value) : null;
    if (!e) throw Error("REVISION_INPUT: exact family required; no fallback");
    const normalized2 = deepFreeze(e.module.validateSpec(spec));
    return Object.freeze({ spec: normalized2, sourceId: e.source_id, rendererId: e.family_id, sample: (s) => e.module[e.sample_export](normalized2, s), render: (s, frames = void 0) => frames === void 0 ? e.module[e.render_export](normalized2, s) : e.module[e.render_export](normalized2, s, frames), readiness: Object.freeze({ native_verified: false, dashboard_ready: false, independent_accepted: false }) });
  }

  // renderers/svg-tree.mjs
  var tags = /* @__PURE__ */ new Set(["svg", "g", "path", "circle", "defs", "mask", "rect", "text", "clipPath", "ellipse", "tspan", "line", "polygon", "filter", "feGaussianBlur", "polyline", "feColorMatrix", "feComposite"]);
  var names = /* @__PURE__ */ new Set(["xmlns", "viewBox", "width", "height", "x", "y", "dx", "dy", "xml:space", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "id", "transform", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset", "fill-rule", "clip-rule", "fill-opacity", "stroke-opacity", "opacity", "pathLength", "text-anchor", "font-size", "font-family", "font-weight", "letter-spacing", "dominant-baseline", "filter", "mask", "clip-path", "maskUnits", "maskContentUnits", "filterUnits", "color-interpolation-filters", "in", "in2", "result", "stdDeviation", "type", "mode", "values", "operator", "role"]);
  var number4 = String.raw`[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?`;
  var numbers = new RegExp(`^(?:${number4})(?:[ ,]+${number4})*$`);
  var fail4 = () => {
    throw Error("TEMPLATE_SVG_INVALID");
  };
  function decode(value) {
    if (value.length > 8192 || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(value)) fail4();
    return value.replace(/&([^;\s]{1,15});|&/g, (whole, entity) => {
      const known = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };
      if (Object.hasOwn(known, entity)) return known[entity];
      if (!entity || !/^#(?:\d{1,7}|x[0-9a-fA-F]{1,6})$/u.test(entity)) fail4();
      const n = entity[1] === "x" ? parseInt(entity.slice(2), 16) : Number(entity.slice(1));
      if (!Number.isInteger(n) || n < 32 || n > 1114111 || n >= 55296 && n <= 57343) fail4();
      return String.fromCodePoint(n);
    });
  }
  function numeric(value) {
    if (!numbers.test(value) || value.match(new RegExp(number4, "g")).some((v) => !Number.isFinite(Number(v)) || Math.abs(Number(v)) > 1e9)) fail4();
  }
  function svgAttribute(name, value) {
    if (!names.has(name) && !/^data-[a-z0-9-]{1,50}$/u.test(name) && !/^aria-[a-z-]{1,40}$/u.test(name) || typeof value !== "string" || value.length > 8192 || /[<>\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(value)) fail4();
    if (name === "xmlns") {
      if (value !== "http://www.w3.org/2000/svg") fail4();
    } else if (["fill", "stroke"].includes(name)) {
      if (!/^(?:#[a-fA-F0-9]{3,8}|none|transparent|currentColor|white|url\(#[a-zA-Z0-9_-]+\))$/u.test(value)) fail4();
    } else if (["filter", "mask", "clip-path"].includes(name)) {
      if (!/^(?:none|url\(#[a-zA-Z0-9_-]+\))$/u.test(value)) fail4();
    } else if (name === "transform") {
      if (!/^(?:(?:translate|rotate|scale|matrix|skewX|skewY)\([-+., eE0-9]+\)\s*)+$/u.test(value)) fail4();
      for (const part of value.matchAll(/\(([^)]+)\)/g)) numeric(part[1]);
    } else if (name === "d") {
      if (!/^[MmZzLlHhVvCcSsQqTtAa0-9eE+.,\s-]*$/u.test(value)) fail4();
    } else if (name === "points" || name === "viewBox" || name === "values") {
      numeric(value);
    } else if (name === "xml:space") {
      if (!["preserve", "default"].includes(value)) fail4();
    } else if (name === "id") {
      if (!/^[a-zA-Z][a-zA-Z0-9_-]{0,100}$/u.test(value)) fail4();
    } else if (["x", "y", "dx", "dy", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "stroke-width", "stroke-dashoffset", "pathLength", "font-size", "letter-spacing", "opacity", "fill-opacity", "stroke-opacity", "stdDeviation"].includes(name)) {
      numeric(value.endsWith("%") ? value.slice(0, -1) : value);
    } else if (name === "stroke-dasharray" && value !== "none") numeric(value);
    else if (name === "font-family" && !/^[a-zA-Z ,'-]{1,100}$/u.test(value)) fail4();
    else if (/(?:javascript|https?|data):|expression\s*\(|@import/iu.test(value)) fail4();
    return value;
  }
  function parseSvg(value) {
    if (typeof value !== "string" || value.length > 1e6 || /<!|<\?/u.test(value)) fail4();
    let i = 0, count = 0, root = null;
    const stack = [];
    function add(node) {
      if (++count > 4096 || stack.length > 64) fail4();
      if (stack.length) stack.at(-1).children.push(node);
      else if (!root && node.tag === "svg") root = node;
      else fail4();
    }
    while (i < value.length) {
      if (value[i] !== "<") {
        const end = value.indexOf("<", i), next = end < 0 ? value.length : end, raw2 = value.slice(i, next);
        i = next;
        if (raw2.trim()) {
          if (!stack.length) fail4();
          add({ tag: "#text", text: decode(raw2), attrs: {}, children: [] });
        }
        continue;
      }
      const slice = value.slice(i), close = /^<\/([A-Za-z][A-Za-z0-9]*)\s*>/u.exec(slice);
      if (close) {
        if (!stack.length || stack.at(-1).tag !== close[1]) fail4();
        stack.pop();
        i += close[0].length;
        continue;
      }
      const open = /^<([A-Za-z][A-Za-z0-9]*)(\s[^<>]*?)?\s*(\/?)>/u.exec(slice);
      if (!open || !tags.has(open[1])) fail4();
      const raw = open[2] || "", attrs = {};
      let offset = 0;
      while (offset < raw.length) {
        const attr = /^\s+([A-Za-z][A-Za-z0-9:-]*)\s*=\s*"([^"<]*)"/u.exec(raw.slice(offset));
        if (!attr) {
          if (raw.slice(offset).trim()) fail4();
          break;
        }
        if (Object.hasOwn(attrs, attr[1]) || Object.keys(attrs).length >= 64) fail4();
        attrs[attr[1]] = svgAttribute(attr[1], decode(attr[2]));
        offset += attr[0].length;
      }
      const node = { tag: open[1], attrs, children: [], text: null };
      add(node);
      if (!open[3]) stack.push(node);
      i += open[0].length;
    }
    if (stack.length || !root || root.attrs.viewBox !== "0 0 1080 1920" || root.attrs.width !== "1080" || root.attrs.height !== "1920") fail4();
    return root;
  }
  function svgDom(tree, document) {
    if (tree.tag === "#text") return document.createTextNode(tree.text);
    if (!tags.has(tree.tag)) fail4();
    const node = document.createElementNS("http://www.w3.org/2000/svg", tree.tag);
    for (const [name, value] of Object.entries(tree.attrs)) node.setAttribute(name, svgAttribute(name, value));
    for (const child of tree.children) node.appendChild(svgDom(child, document));
    return node;
  }
  return __toCommonJS(browser_entry_exports);
})();
