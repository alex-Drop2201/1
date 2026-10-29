// Пиксельные значки для набросков: рисуются квадратами по маске из строк.
const PIX = {
  heart: ['.XX.XX.', 'XXXXXXX', 'XXXXXXX', '.XXXXX.', '..XXX..', '...X...'],
  crown: ['X..X..X', 'XX.X.XX', 'XXXXXXX', 'XXXXXXX', '.......', 'XXXXXXX'],
  mask: ['XXXXXXXXX', 'X..XXX..X', 'X..XXX..X', 'XXXXXXXXX', '.XXX.XXX.'],
  star: ['...X...', '...X...', 'XXXXXXX', '.XXXXX.', '.XX.XX.', 'XX...XX'],
  check: ['......X', '.....XX', 'X...XX.', 'XX.XX..', '.XXX...', '..X....'],
};
function pix(name, x, y, cell, color, parent = document.querySelector('main')) {
  const rows = PIX[name];
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', rows[0].length * cell); svg.setAttribute('height', rows.length * cell);
  svg.style.cssText = `position:absolute;left:${x}px;top:${y}px;z-index:30;overflow:visible`;
  rows.forEach((r, j) => [...r].forEach((c, i) => {
    if (c !== 'X') return;
    const q = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    q.setAttribute('x', i * cell); q.setAttribute('y', j * cell); q.setAttribute('width', cell); q.setAttribute('height', cell);
    q.setAttribute('fill', color); svg.appendChild(q);
  }));
  parent.appendChild(svg);
  return svg;
}
function hearts(x, y, n = 3, cell = 5) { for (let i = 0; i < n; i++) pix('heart', x + i * cell * 9, y, cell, '#111'); }
window.renderReady = document.fonts.ready;
