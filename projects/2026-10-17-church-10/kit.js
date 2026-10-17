// Помощники серии: детерминированный ГСЧ, SVG-элементы, подгонка текста по ширине и «рукотворные» линии.

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(parent, tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  parent.appendChild(node);
  return node;
}

const f2 = (n) => n.toFixed(1);

function smoothOpen(pts) {
  let d = `M${f2(pts[0][0])},${f2(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(i - 1, 0)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(i + 2, pts.length - 1)];
    d += `C${f2(p1[0] + (p2[0] - p0[0]) / 6)},${f2(p1[1] + (p2[1] - p0[1]) / 6)} ` +
      `${f2(p2[0] - (p3[0] - p1[0]) / 6)},${f2(p2[1] - (p3[1] - p1[1]) / 6)} ${f2(p2[0])},${f2(p2[1])}`;
  }
  return d;
}

// Овал «от руки»: чуть больше одного оборота, радиус слегка гуляет.
function handOval(cx, cy, rx, ry, random, turns = 1.12) {
  const pts = [];
  const n = 36;
  const start = random() * Math.PI * 2;
  for (let i = 0; i <= n * turns; i++) {
    const a = start + (i / n) * Math.PI * 2;
    const k = 1 + (random() - 0.5) * 0.05 + (i / n) * 0.05;
    pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]);
  }
  return smoothOpen(pts);
}

// Стрелка «от руки»: изогнутая линия от a к b и две короткие черты наконечника.
function handArrow(a, b, bend, head = 22) {
  const mx = (a[0] + b[0]) / 2 - (b[1] - a[1]) * bend;
  const my = (a[1] + b[1]) / 2 + (b[0] - a[0]) * bend;
  const ang = Math.atan2(b[1] - my, b[0] - mx);
  const h1 = [b[0] - head * Math.cos(ang - 0.45), b[1] - head * Math.sin(ang - 0.45)];
  const h2 = [b[0] - head * Math.cos(ang + 0.45), b[1] - head * Math.sin(ang + 0.45)];
  return `M${f2(a[0])},${f2(a[1])} Q${f2(mx)},${f2(my)} ${f2(b[0])},${f2(b[1])} M${f2(h1[0])},${f2(h1[1])} L${f2(b[0])},${f2(b[1])} L${f2(h2[0])},${f2(h2[1])}`;
}

// Рваный край бумаги: прямоугольник с зазубренными сторонами.
function tornRect(x, y, w, h, random, jag = 5, step = 14) {
  const pts = [];
  const edge = (x1, y1, x2, y2, nx, ny) => {
    const len = Math.hypot(x2 - x1, y2 - y1);
    const n = Math.max(2, Math.round(len / step));
    for (let i = 0; i < n; i++) {
      const t = i / n;
      const o = (random() - 0.5) * 2 * jag;
      pts.push([x1 + (x2 - x1) * t + nx * o, y1 + (y2 - y1) * t + ny * o]);
    }
  };
  edge(x, y, x + w, y, 0, 1);
  edge(x + w, y, x + w, y + h, 1, 0);
  edge(x + w, y + h, x, y + h, 0, 1);
  edge(x, y + h, x, y, 1, 0);
  return 'M' + pts.map((p) => `${f2(p[0])},${f2(p[1])}`).join(' L') + 'Z';
}

// Фильтр «нарисовано от руки»: лёгкое дрожание контура.
function sketchFilter(defs, id, scale = 3, freq = 0.03, seed = 2) {
  const f = svgEl(defs, 'filter', { id, x: '-5%', y: '-5%', width: '110%', height: '110%' });
  svgEl(f, 'feTurbulence', { type: 'fractalNoise', baseFrequency: freq, numOctaves: 2, seed, result: 'n' });
  svgEl(f, 'feDisplacementMap', { in: 'SourceGraphic', in2: 'n', scale, xChannelSelector: 'R', yChannelSelector: 'G' });
}

// Подогнать кегль элемента так, чтобы его ширина стала равна width.
function fitWidth(el, width) {
  const size = parseFloat(getComputedStyle(el).fontSize);
  const w = el.getBoundingClientRect().width;
  el.style.fontSize = `${(size * width) / w}px`;
}

// Выполнить подгонку после загрузки шрифтов (specs — например '900 100px "Inter"'); рендер дождётся window.renderReady.
function afterFonts(specs, fn) {
  window.renderReady = Promise.all(specs.map((s) => document.fonts.load(s)))
    .then(() => document.fonts.ready)
    .then(fn);
}
