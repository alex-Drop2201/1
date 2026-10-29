// Набор строк по верху прописных (как в story-5-saturday.html): пиксельный шрифт растянут до ширины букв автора.
const ctx2 = document.createElement('canvas').getContext('2d');
let SX = 1.45;
function line(text, { family = "'Tiny5'", weight = 400, style = 'normal', capTop, capH, x = 0, sx = 1, align = 'left',
                      color = '#111', rotate = 0, parent = document.querySelector('main'), html = null, z = 10, upper = true }) {
  ctx2.font = `${style} ${weight} 100px ${family}`;
  const size = capH / (ctx2.measureText('Н').actualBoundingBoxAscent / 100);  // по высоте прописной
  ctx2.font = `${style} ${weight} ${size}px ${family}`;
  const m = ctx2.measureText('Н');
  const el = document.createElement('div');
  el.style.cssText = `position:absolute;white-space:nowrap;z-index:${z};color:${color};text-transform:${upper ? 'uppercase' : 'none'};font:${style} ${weight} ${size}px/1 ${family}`;
  if (html) el.innerHTML = html; else el.textContent = text;
  if (sx !== 1) { el.style.transform = `scaleX(${sx})`; el.style.transformOrigin = 'left top'; }
  parent.appendChild(el);
  const base = (size - (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent)) / 2 + m.fontBoundingBoxAscent;
  el.style.top = `${capTop - (base - m.actualBoundingBoxAscent)}px`;
  const w = el.getBoundingClientRect().width;
  el.style.left = `${align === 'center' ? x - w / 2 : align === 'right' ? x - w : x}px`;
  return { el, w };
}
const px = (text, o) => line(text, { ...o, sx: SX });
function calibrate() {
  const p = line('Ты должен прийти', { capTop: -500, capH: 25 });
  SX = 443 / p.w;                 // как «ТЫ ДОЛЖЕН ПРИЙТИ» в 3-й сторис
  p.el.remove();
}
function fontsReady() {
  return Promise.all(["40px 'Tiny5'", "italic 900 40px 'Fira Sans'", "700 40px 'Comfortaa'", "900 40px 'Montserrat'",
    "600 40px 'Oswald'", "500 40px 'Montserrat'"].map((f) => document.fonts.load(f))).then(() => document.fonts.ready).then(calibrate);
}
// Розовый скотч, как во 2-й сторис.
function tape(x, y, w, h, deg) {
  const t = document.createElement('div');
  t.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;transform:rotate(${deg}deg);z-index:20;
    background:#f28ab8;opacity:.92;box-shadow:0 3px 8px rgba(0,0,0,.12);clip-path:polygon(2% 8%,98% 0,100% 50%,97% 100%,1% 92%,3% 50%)`;
  document.querySelector('main').appendChild(t);
}
