// Общие помощники генеративных постеров: детерминированный генератор случайных чисел,
// создание SVG-элементов и сглаженные контуры. Один и тот же seed — одна и та же картинка при каждом рендере.

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

// Плавный шум по углу: сумма гармоник со случайными фазами, амплитуда около ±1.
function angularNoise(random, harmonics = 5) {
  const parts = Array.from({ length: harmonics }, (_, i) => ({
    k: i + 2,
    a: (random() * 2 - 1) / (i + 1.5),
    p: random() * Math.PI * 2,
  }));
  return (theta) => parts.reduce((sum, h) => sum + h.a * Math.sin(h.k * theta + h.p), 0);
}

const fmt = (n) => n.toFixed(2);

// Сглаженный замкнутый контур через точки (Catmull-Rom → кубические Безье).
function smoothClosed(pts) {
  const n = pts.length;
  let d = `M${fmt(pts[0][0])},${fmt(pts[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n];
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const p3 = pts[(i + 2) % n];
    d += `C${fmt(p1[0] + (p2[0] - p0[0]) / 6)},${fmt(p1[1] + (p2[1] - p0[1]) / 6)} ` +
      `${fmt(p2[0] - (p3[0] - p1[0]) / 6)},${fmt(p2[1] - (p3[1] - p1[1]) / 6)} ${fmt(p2[0])},${fmt(p2[1])}`;
  }
  return d + 'Z';
}

// Сглаженная открытая линия через точки.
function smoothOpen(pts) {
  const n = pts.length;
  let d = `M${fmt(pts[0][0])},${fmt(pts[0][1])}`;
  for (let i = 0; i < n - 1; i++) {
    const p0 = pts[Math.max(i - 1, 0)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(i + 2, n - 1)];
    d += `C${fmt(p1[0] + (p2[0] - p0[0]) / 6)},${fmt(p1[1] + (p2[1] - p0[1]) / 6)} ` +
      `${fmt(p2[0] - (p3[0] - p1[0]) / 6)},${fmt(p2[1] - (p3[1] - p1[1]) / 6)} ${fmt(p2[0])},${fmt(p2[1])}`;
  }
  return d;
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Интерполяция цвета между опорными точками [[позиция 0..1, '#rrggbb'], ...].
function colorAt(stops, t) {
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  for (let i = 0; i < stops.length - 1; i++) {
    const [p0, c0] = stops[i];
    const [p1, c1] = stops[i + 1];
    if (t <= p1 || i === stops.length - 2) {
      const k = Math.min(1, Math.max(0, (t - p0) / (p1 - p0)));
      const a = hex(c0);
      const b = hex(c1);
      return `rgb(${a.map((v, j) => Math.round(lerp(v, b[j], k))).join(',')})`;
    }
  }
  return stops[stops.length - 1][1];
}
