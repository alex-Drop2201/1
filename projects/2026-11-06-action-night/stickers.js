// Наклейки как в референсе: ч/б фото человека в неровном многоугольнике со светлым фоном и толстой белой обводкой.
const SNS = 'http://www.w3.org/2000/svg';
function rngS(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

function polygonPoints(x, y, w, h, seed, n = 7) {
  const r = rngS(seed), pts = [];
  const a0 = r() * Math.PI * 2;
  for (let i = 0; i < n; i++) {
    const a = a0 + (i / n) * Math.PI * 2 + (r() - 0.5) * 0.45;
    const k = 0.9 + r() * 0.12;
    pts.push([x + w / 2 + Math.cos(a) * w / 2 * k, y + h / 2 + Math.sin(a) * h / 2 * k]);
  }
  return pts;
}

// svg — общий слой; src — PNG без фона; box — где наклейка; focus — какую долю высоты фото занимает «голова и плечи».
function personSticker(svg, src, { x, y, w, h, seed = 1, imgScale = 1.05, dy = 0, stroke = 11 }) {
  const id = `st${seed}`;
  const pts = polygonPoints(x, y, w, h, seed).map((p) => p.map((v) => v.toFixed(1)).join(',')).join(' ');
  const defs = document.createElementNS(SNS, 'defs');
  defs.innerHTML = `<clipPath id="${id}c"><polygon points="${pts}"/></clipPath>
    <filter id="${id}g"><feColorMatrix type="saturate" values="0"/><feComponentTransfer>
      <feFuncR type="linear" slope="1.12" intercept="-0.04"/><feFuncG type="linear" slope="1.12" intercept="-0.04"/><feFuncB type="linear" slope="1.12" intercept="-0.04"/></feComponentTransfer></filter>
    <filter id="${id}s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000" flood-opacity=".55"/></filter>`;
  svg.appendChild(defs);
  const g = document.createElementNS(SNS, 'g');
  g.innerHTML = `<polygon points="${pts}" fill="#fff" stroke="#fff" stroke-width="${stroke * 2}" stroke-linejoin="round" filter="url(#${id}s)"/>
    <g clip-path="url(#${id}c)"><rect x="${x - 20}" y="${y - 20}" width="${w + 40}" height="${h + 40}" fill="#d9d8d5"/>
      <image href="${src}" x="${x + w / 2 - (w * imgScale) / 2}" y="${y + dy}" width="${w * imgScale}" height="${h * imgScale}"
             preserveAspectRatio="xMidYMin slice" filter="url(#${id}g)"/></g>`;
  svg.appendChild(g);
}
