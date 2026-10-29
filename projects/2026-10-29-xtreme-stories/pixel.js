// Пиксельный декор серии XTREME: всё рисуется квадратами одной сетки, как пиксельный шрифт сторис.
const NS = 'http://www.w3.org/2000/svg';

function layer() {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 1080 1920');
  svg.style.cssText = 'position:absolute;left:0;top:0;width:1080px;height:1920px;z-index:30;overflow:visible';
  document.querySelector('main').appendChild(svg);
  return svg;
}

function rect(svg, x, y, w, h, fill) {
  const r = document.createElementNS(NS, 'rect');
  Object.entries({ x, y, width: w, height: h, fill }).forEach(([k, v]) => r.setAttribute(k, v));
  svg.appendChild(r);
  return r;
}

// Узор из строк ('X' — квадрат) с левым верхним углом (x, y) и стороной квадрата cell.
function pattern(svg, rows, x, y, cell, fill) {
  rows.forEach((row, j) => [...row].forEach((c, i) => { if (c === 'X') rect(svg, x + i * cell, y + j * cell, cell, cell, fill); }));
}

const CHECK = ['.......X', '......XX', 'X....XX.', 'XX..XX..', '.XXXX...', '..XX....'];

// Чек-бокс: квадрат 12×12 клеток с рамкой в клетку и пиксельной тенью; галочка целиком внутри (поле в клетку).
function checkbox(svg, x, y, cell = 4, { ink = '#111', paper = '#fff', mark = '#6129fb', checked = true } = {}) {
  const n = 12;
  rect(svg, x + cell, y + cell, n * cell, n * cell, ink);              // тень на клетку вправо-вниз
  rect(svg, x, y, n * cell, n * cell, ink);
  rect(svg, x + cell, y + cell, (n - 2) * cell, (n - 2) * cell, paper);
  if (checked) pattern(svg, CHECK, x + 2 * cell, y + 3 * cell, cell, mark);
}

// Пиксельная стрелка: квадраты вдоль кубической кривой и наконечник-треугольник, направленный по касательной.
function pixelArrow(svg, p0, p1, p2, p3, { cell = 8, step = 22, fill = '#fff', edge = '#111' } = {}) {
  const at = (t) => [0, 1].map((k) => (1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * p1[k] + 3 * (1 - t) * t * t * p2[k] + t ** 3 * p3[k]);
  const pts = [];
  let last = null;
  for (let t = 0; t <= 0.93; t += 0.002) {
    const p = at(t);
    if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) >= step) { pts.push(p); last = p; }
  }
  const snap = (v) => Math.round(v / cell) * cell;
  pts.forEach(([x, y]) => rect(svg, snap(x) - cell / 2 + 2, snap(y) - cell / 2 + 2, cell, cell, edge));
  pts.forEach(([x, y]) => rect(svg, snap(x) - cell / 2, snap(y) - cell / 2, cell, cell, fill));
  // наконечник вправо (стрелка приходит к кнопке слева)
  const head = ['X....', 'XX...', 'XXX..', 'XXXX.', 'XXXXX', 'XXXX.', 'XXX..', 'XX...', 'X....'];
  const [hx, hy] = p3;
  pattern(svg, head, snap(hx) - 5 * cell + 2, snap(hy) - 4.5 * cell + 2, cell, edge);
  pattern(svg, head, snap(hx) - 5 * cell, snap(hy) - 4.5 * cell, cell, fill);
}

// Пиксельный пузырь реплики: размер по тексту (с полями), ступенчатые углы, хвост лесенкой к точке tail.
function bubble(svg, text, x, y, { size = 34, pad = [26, 34], cell = 6, tail = null, ink = '#111', paper = '#fff' } = {}) {
  const t = document.createElement('div');
  t.className = 'px-line';
  t.style.cssText = `position:absolute;left:0;top:0;font-size:${size}px;z-index:31;color:${ink}`;
  t.textContent = text;
  document.querySelector('main').appendChild(t);
  const r = t.getBoundingClientRect();                 // ширина уже с растяжением шрифта
  const w = Math.ceil((r.width + 2 * pad[1]) / cell) * cell;
  const h = Math.ceil((r.height + 2 * pad[0]) / cell) * cell;
  const c = cell;
  // рамка со ступенькой в углах: тень, чёрная подложка, белое поле
  const body = (dx, dy, fill, inset) => {
    rect(svg, x + dx + c + inset, y + dy + inset, w - 2 * c - 2 * inset, h - 2 * inset, fill);
    rect(svg, x + dx + inset, y + dy + c + inset, w - 2 * inset, h - 2 * c - 2 * inset, fill);
  };
  body(c, c, ink, 0);
  body(0, 0, ink, 0);
  body(0, 0, paper, c);
  if (tail) {                                           // хвост: лесенка из клеток от низа пузыря к tail
    const [tx, ty] = tail;
    const bx = Math.round((tx - x) / c) * c + x;
    const steps = Math.max(2, Math.round((ty - (y + h)) / c));
    for (let i = 0; i < steps; i++) {
      const sx = bx + (tx < x + w / 2 ? -i * c : i * c);
      const width = Math.max(c, (steps - i) * c);
      rect(svg, sx - c, y + h - c + i * c, width + 2 * c, c, ink);
      if (i < steps - 1) rect(svg, sx, y + h - c + i * c, width, c, paper);
    }
  }
  t.style.left = `${x + (w - r.width) / 2}px`;
  t.style.top = `${y + (h - r.height) / 2 - 2}px`;
  return { w, h };
}

// Звёздочка-блик серии (как в 4-й сторис).
function sparkle(x, y, size, color = '#fff') {
  const s = document.createElementNS(NS, 'svg');
  s.setAttribute('viewBox', '-50 -50 100 100');
  s.style.cssText = `position:absolute;left:${x - size / 2}px;top:${y - size / 2}px;width:${size}px;height:${size}px;z-index:29`;
  s.innerHTML = `<path d="M0,-48 C3,-7 7,-3 48,0 C7,3 3,7 0,48 C-3,7 -7,3 -48,0 C-7,-3 -3,-7 0,-48Z" fill="${color}"/>`;
  document.querySelector('main').appendChild(s);
}
