// Пиксельный двухэтажный автобус (свой рисунок, вместо картинки из референса): сетка 140×62 клетки,
// клетка CELL px — в любом размере остаётся резким. Нос слева. Фактура — шахматные точки темнее основного красного.
function drawBus(svg, ox, oy, CELL = 6, { reflect = true } = {}) {
  const NS = 'http://www.w3.org/2000/svg';
  const W = 140, H = 62;
  const grid = Array.from({ length: H }, () => Array(W).fill(null));
  const put = (x, y, c) => { if (x >= 0 && y >= 0 && x < W && y < H) grid[y][x] = c; };
  const box = (x0, y0, x1, y1, c) => { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) put(x, y, c); };
  const RED = '#d4252a', RED_D = '#a9171d', RED_L = '#ff5148', DARK = '#17171c', GLASS = '#2a2d36', GLINT = '#5a6170',
        RIM = '#8b8f99', TYRE = '#0c0c0e', CREAM = '#f0e2c8';
  // кузов со скруглёнными углами (верх скруглён сильнее — крыша)
  box(3, 2, 136, 53, RED);
  [[3, 2, 6], [4, 2, 4], [5, 2, 2], [6, 2, 1], [7, 2, 1]].forEach(([x, y, n]) => { for (let i = 0; i < n; i++) { put(x, y + i, null); put(W - 1 - x, y + i, null); } });
  for (let i = 0; i < 3; i++) { put(3, 51 + i, null); put(136, 51 + i, null); }
  box(8, 2, 131, 2, RED_L);                                    // блик по крыше
  // окна второго этажа: 6 окон
  const upper = [[10, 30], [32, 52], [54, 74], [76, 96], [98, 118], [120, 131]];
  upper.forEach(([a, b]) => { box(a, 8, b, 19, GLASS); box(a, 8, b, 8, DARK); box(a + 2, 10, a + 4, 12, GLINT); box(a + 3, 13, a + 3, 14, GLINT); });
  put(10, 8, RED); put(131, 8, RED);
  // пояс между этажами: тёмная линия и светлая полоса
  box(4, 22, 135, 22, RED_D); box(4, 23, 135, 24, CREAM); box(4, 25, 135, 25, RED_D);
  // первый этаж: кабина водителя спереди, окна салона, открытая площадка сзади
  box(6, 29, 16, 40, GLASS); box(8, 31, 10, 33, GLINT);
  const lower = [[22, 42], [45, 65], [68, 88], [91, 111]];
  lower.forEach(([a, b]) => { box(a, 29, b, 40, GLASS); box(a, 29, b, 29, DARK); box(a + 2, 31, a + 4, 33, GLINT); });
  box(115, 28, 134, 47, DARK); box(118, 30, 131, 44, GLASS); box(124, 28, 125, 47, RIM);   // площадка с поручнем
  // нос: решётка радиатора и фары
  box(3, 42, 9, 50, DARK); for (let y = 43; y <= 49; y += 2) box(4, y, 8, y, RIM);
  box(3, 40, 4, 41, '#ffe9a8'); box(12, 44, 14, 45, '#ffe9a8');
  // юбка кузова
  box(3, 51, 136, 53, RED_D);
  // колёса (пиксельные круги) поверх юбки
  const wheel = (cx, cy, r) => {
    for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
      const d = Math.hypot(x, y);
      if (d <= r + 0.3) put(cx + x, cy + y, d > r - 2.2 ? TYRE : d > r - 4.2 ? RIM : '#3a3c44');
    }
    put(cx, cy, RIM);
  };
  const arch = (cx) => { for (let y = 46; y <= 53; y++) for (let x = cx - 9; x <= cx + 9; x++) if (Math.hypot(x - cx, y - 54) <= 9.5) put(x, y, DARK); };
  arch(30); arch(104);
  wheel(30, 54, 7); wheel(104, 54, 7);
  // фактура: шахматные точки на красном
  const hash = (x, y) => (((x * 73856093) ^ (y * 19349663)) >>> 0) % 9;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (grid[y][x] !== RED) continue;
    if (y >= 44 && (x + y) % 2 === 0) grid[y][x] = RED_D;          // низ кузова темнее — объём
    else if (hash(x, y) === 0) grid[y][x] = RED_D;                  // редкие точки — фактура
    else if (y <= 5 && hash(x, y) === 1) grid[y][x] = RED_L;        // блики у крыши
  }

  const g = document.createElementNS(NS, 'g');
  const paint = (parent, flip) => {
    for (let y = 0; y < H; y++) {
      let x = 0;
      while (x < W) {
        const c = grid[y][x];
        if (!c) { x++; continue; }
        let x1 = x; while (x1 + 1 < W && grid[y][x1 + 1] === c) x1++;
        const r = document.createElementNS(NS, 'rect');
        const yy = flip ? (H - 1 - y) : y;
        r.setAttribute('x', ox + x * CELL); r.setAttribute('y', (flip ? oy + H * CELL : oy) + yy * CELL);
        r.setAttribute('width', (x1 - x + 1) * CELL); r.setAttribute('height', CELL); r.setAttribute('fill', c);
        parent.appendChild(r);
        x = x1 + 1;
      }
    }
  };
  paint(g, false);
  svg.appendChild(g);
  if (reflect) {                                                // отражение на «полу», как в референсе
    const defs = document.createElementNS(NS, 'defs');
    defs.innerHTML = `<linearGradient id="refl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".42"/><stop offset=".3" stop-color="#fff" stop-opacity="0"/></linearGradient>
      <mask id="reflm"><rect x="${ox}" y="${oy + H * CELL}" width="${W * CELL}" height="${H * CELL}" fill="url(#refl)"/></mask>`;
    svg.appendChild(defs);
    const r = document.createElementNS(NS, 'g');
    r.setAttribute('mask', 'url(#reflm)');
    paint(r, true);
    svg.appendChild(r);
  }
  return { w: W * CELL, h: H * CELL };
}
