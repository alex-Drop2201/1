#!/usr/bin/env node
// Рендер HTML-макета в PNG / JPG / PDF через Playwright (Chromium).
//
//   node scripts/render.cjs projects/2026-10-16-sale/post.html
//   node scripts/render.cjs <file.html> [--format story | --size 1080x1920] [--jpg] [--pdf] [--scale 2] [--out dir]
//
// Размер: флаг --size/--format, иначе <meta name="size" content="1080x1350"> в самом HTML.
// Карусель: если на странице есть элементы [data-slide], каждый сохраняется отдельным файлом.
// Результат по умолчанию кладётся в папку export/ рядом с HTML.
// Репозиторий раздаётся локальным сервером, поэтому пути вида /fonts/fonts.css и /brand/brand.css работают из любой папки.

const fs = require('fs');
const http = require('http');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');

const FORMATS = {
  post: [1080, 1350],
  square: [1080, 1080],
  story: [1080, 1920],
  youtube: [1280, 720],
  wide: [1920, 1080],
  og: [1200, 630],
  x: [1600, 900],
  a4: [2480, 3508],
  a3: [3508, 4961],
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.avif': 'image/avif',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
};

function loadPlaywright() {
  try {
    return require('playwright');
  } catch {
    const globalRoot = execSync('npm root -g').toString().trim();
    return require(path.join(globalRoot, 'playwright'));
  }
}

function parseArgs(argv) {
  const opts = { files: [], scale: 1, jpg: false, pdf: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--size') opts.size = argv[++i];
    else if (a === '--format') opts.format = argv[++i];
    else if (a === '--scale') opts.scale = Number(argv[++i]);
    else if (a === '--out') opts.out = argv[++i];
    else if (a === '--jpg') opts.jpg = true;
    else if (a === '--pdf') opts.pdf = true;
    else if (a.startsWith('--')) throw new Error(`Неизвестный флаг ${a}`);
    else opts.files.push(a);
  }
  if (!opts.files.length) {
    throw new Error('Укажите HTML-файл: node scripts/render.cjs projects/<папка>/post.html');
  }
  return opts;
}

function parseSize(value) {
  if (!value) return null;
  if (FORMATS[value]) return FORMATS[value];
  const m = /^(\d+)x(\d+)$/.exec(value);
  if (!m) throw new Error(`Не понимаю размер "${value}". Пример: 1080x1350 или ${Object.keys(FORMATS).join(', ')}`);
  return [Number(m[1]), Number(m[2])];
}

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let file = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
      if (!file.startsWith(ROOT)) return res.writeHead(403).end();
      if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
      fs.readFile(file, (err, data) => {
        if (err) return res.writeHead(404).end();
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

async function launch(chromium) {
  try {
    return await chromium.launch();
  } catch (err) {
    // Версия playwright не совпала с установленным браузером — берём предустановленный Chromium.
    if (fs.existsSync('/opt/pw-browsers/chromium')) {
      return chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
    }
    throw err;
  }
}

// Открыть макет, выставить размер и дождаться шрифтов и window.renderReady. Нужна и рендеру, и замерам критики.
async function openPage(browser, port, file, opts) {
  const abs = path.resolve(file);
  if (!fs.existsSync(abs)) throw new Error(`Нет файла ${file}`);
  if (!abs.startsWith(ROOT)) throw new Error('HTML должен лежать внутри репозитория');
  const rel = path.relative(ROOT, abs).split(path.sep).map(encodeURIComponent).join('/');

  const page = await browser.newPage({ deviceScaleFactor: opts.scale });
  const failed = [];
  page.on('response', (r) => r.status() >= 400 && failed.push(`${r.status()} ${r.url()}`));
  page.on('requestfailed', (r) => failed.push(`ошибка ${r.url()}`));
  const scriptErrors = [];
  page.on('pageerror', (err) => scriptErrors.push(err.message));

  await page.goto(`http://127.0.0.1:${port}/${rel}`, { waitUntil: 'networkidle' });
  const metaSize = await page.$eval('meta[name="size"]', (m) => m.content).catch(() => null);
  const size = parseSize(opts.size) || parseSize(opts.format) || parseSize(metaSize);
  if (!size) throw new Error(`${file}: не задан размер (--size, --format или <meta name="size">)`);
  const [width, height] = size;
  await page.setViewportSize({ width, height });
  await page.evaluate(() => document.fonts.ready);
  // Макет может отложить рендер, пока подгоняет текст: window.renderReady = Promise.
  await page.evaluate(() => window.renderReady);
  await page.waitForTimeout(100);
  return { page, abs, width, height, failed, scriptErrors };
}

async function renderFile(browser, port, file, opts) {
  const { page, abs, width, height, failed, scriptErrors } = await openPage(browser, port, file, opts);

  const missingFonts = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === 'error').map((f) => `${f.family} ${f.weight}`),
  );

  // Текст, вылезающий за край макета (по вертикали проверяем только одиночный макет, не карусель).
  const overflow = await page.evaluate(() => {
    const W = innerWidth;
    const H = innerHeight;
    const single = !document.querySelector('[data-slide]');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const hits = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent.trim();
      if (!text) continue;
      // data-bleed — надпись намеренно уходит за край (как в референсе), её не проверяем.
      if (node.parentElement && node.parentElement.closest('[data-bleed]')) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (!r.width && !r.height) continue;
      if (r.left < -1 || r.right > W + 1 || (single && (r.top < -1 || r.bottom > H + 1))) {
        hits.push(text.slice(0, 40));
      }
    }
    return hits;
  });

  // Ошибки, которые раньше находила только критика (скил poster-critique), — ловим уже при рендере.
  const design = await page.evaluate(() => {
    const out = { faces: [], stretch: [], hanging: [], small: [], dates: [], placeholders: [] };
    const declared = {};
    for (const f of document.fonts) {
      if (f.status === 'error') continue;
      const fam = f.family.replace(/["']/g, '');
      (declared[fam] = declared[fam] || new Set()).add(`${f.weight}${f.style === 'italic' ? ' italic' : ''}`);
    }
    // Рукописные и кистевые шрифты мельче этого (px при ширине 1080) не читаются.
    const MIN_PX = { 'Comforter Brush': 100, 'Great Vibes': 56, 'Amatic SC': 28, Caveat: 24, Neucha: 24 };
    const SHORT = /^(в|во|и|к|ко|с|со|о|об|у|а|но|на|по|за|от|до|из|не|ни|для|при|без|над|под|про)$/i;
    const k1080 = innerWidth / 1080;
    const seen = new Set();
    const once = (key, list, msg) => !seen.has(key) && (seen.add(key), list.push(msg));
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement;
      const text = node.textContent.trim();
      if (!el || !text || el.closest('script, style, .need')) continue;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      const short = `«${text.slice(0, 30)}»`;
      const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      const face = `${cs.fontWeight}${cs.fontStyle === 'italic' ? ' italic' : ''}`;
      if (!declared[fam]) once(`f:${fam}`, out.faces, `${fam} не подключён — ${short}`);
      else if (!declared[fam].has(face)) {
        once(`f:${fam}:${face}`, out.faces, `${fam} ${face} нет (есть ${[...declared[fam]].join(', ')}) — ${short}`);
      }
      // Растяжение трансформациями — своими и родителей.
      let sx = 1, sy = 1;
      for (let e = el; e && e !== document.body; e = e.parentElement) {
        const t = getComputedStyle(e).transform;
        if (!t || t === 'none') continue;
        const v = t.match(/-?[\d.e]+/g).map(Number);
        sx *= Math.hypot(v[0], v[1]);
        sy *= Math.hypot(v[2], v[3]);
      }
      // Пиксельный шрифт растягивается по ширине без искажения штриха (пиксель просто становится шире).
      const pixel = /^(Tiny5|Press Start 2P|Pixelify Sans|Silkscreen|DotGothic16)$/.test(fam);
      if (sx < 0.9 || sy / sx > 1.3 || (sy / sx < 0.77 && !pixel)) {
        once(`s:${text}`, out.stretch, `${short} (${fam}): ×${sx.toFixed(2)} по ширине, ×${sy.toFixed(2)} по высоте`);
      }
      const px = (parseFloat(cs.fontSize) * Math.min(sx, sy)) / k1080;
      if (MIN_PX[fam] && px < MIN_PX[fam]) once(`m:${text}`, out.small, `${short} — ${fam} ${Math.round(px)}px (читается от ${MIN_PX[fam]}px)`);
      // Висячее короткое слово: в конце строки внутри абзаца или перед ручным переносом <br>.
      const words = [];
      const re = /\S+/g;
      for (let m = re.exec(node.textContent); m; m = re.exec(node.textContent)) {
        const range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        const r = range.getBoundingClientRect();
        if (r.width || r.height) words.push({ w: m[0], end: m.index + m[0].length, top: r.top, h: r.height });
      }
      words.forEach((w, i) => {
        const next = words[i + 1];
        const lineEnd = next ? next.top > w.top + w.h * 0.5 : node.nextSibling && node.nextSibling.nodeName === 'BR';
        if (lineEnd && SHORT.test(w.w) && node.textContent[w.end] !== ' ') {
          once(`h:${text}`, out.hanging, `«${w.w}» в конце строки ${short}`);
        }
      });
    }
    // День недели рядом с датой: «Вт 20 окт», «Ср 21-е окт 2026», «Воскресенье · 10:00 · 1 ноября».
    const WD = { пн: 0, понедельник: 0, вт: 1, вторник: 1, ср: 2, среда: 2, среду: 2, чт: 3, четверг: 3, пт: 4, пятница: 4,
                 пятницу: 4, сб: 5, суббота: 5, субботу: 5, вс: 6, воскресенье: 6 };
    const WD_NAMES = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'];
    const MONTHS = ['янв', 'фев', 'мар', 'апр', 'ма', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
    const all = document.body.innerText.toLowerCase().replace(/\s+/g, ' ');
    const names = Object.keys(WD).sort((a, b) => b.length - a.length).join('|');
    // Между днём недели и числом не должно быть другого дня недели: «…на субботу · пятница 30 октября» — берётся пятница.
    const gap = `(?:(?!(?<![а-яё])(?:${names})(?![а-яё]))[^\\d]){0,25}?`;
    const pat = new RegExp(`(?<![а-яё])(${names})(?![а-яё])${gap}(?:\\d{1,2}:\\d{2}[^\\d]{0,10}?)?(\\d{1,2})(?:-?е)?\\s+([а-яё]+)(?:\\s+(\\d{4}))?`, 'g');
    const today = new Date();
    for (const m of all.matchAll(pat)) {
      const mi = MONTHS.findIndex((p) => m[3].startsWith(p));
      if (mi < 0) continue;
      const day = new Date(m[4] ? +m[4] : today.getFullYear(), mi, +m[2]);
      if (!m[4] && today - day > 180 * 864e5) day.setFullYear(day.getFullYear() + 1);
      if (day.getDay() !== (WD[m[1]] + 1) % 7) {
        out.dates.push(`«${m[0].trim()}»: ${day.toLocaleDateString('ru-RU')} — это ${WD_NAMES[(day.getDay() + 6) % 7]}`);
      }
    }
    // Заглушки, которые нельзя публиковать: [data-placeholder] и типовые слова.
    const PH = /адрес здесь|адрес церкви|название (вашей )?церкви|ваш город|ваш район|логотип|город, улица|пастор иван/g;
    const ph = new Set([...all.matchAll(PH)].map((m) => m[0]));
    document.querySelectorAll('[data-placeholder]').forEach((e) => ph.add(e.textContent.trim().slice(0, 30)));
    out.placeholders = [...ph];
    return out;
  });

  const outDir = path.resolve(opts.out || path.join(path.dirname(abs), 'export'));
  fs.mkdirSync(outDir, { recursive: true });
  const base = path.basename(abs, path.extname(abs));
  const ext = opts.jpg ? 'jpg' : 'png';
  const shot = opts.jpg ? { type: 'jpeg', quality: 92 } : { type: 'png' };
  const written = [];

  const slides = await page.$$('[data-slide]');
  if (slides.length) {
    for (let i = 0; i < slides.length; i++) {
      const out = path.join(outDir, `${base}-${String(i + 1).padStart(2, '0')}.${ext}`);
      await slides[i].screenshot({ path: out, ...shot });
      written.push(out);
    }
  } else {
    const out = path.join(outDir, `${base}.${ext}`);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width, height }, ...shot });
    written.push(out);
  }

  if (opts.pdf) {
    const out = path.join(outDir, `${base}.pdf`);
    await page.pdf({ path: out, width: `${width}px`, height: `${height}px`, printBackground: true, pageRanges: '1' });
    written.push(out);
  }

  await page.close();
  for (const w of written) console.log(`✓ ${path.relative(ROOT, w)}  (${width * opts.scale}×${height * opts.scale})`);
  for (const f of failed) console.warn(`⚠ не загрузилось: ${f}`);
  for (const f of missingFonts) console.warn(`⚠ шрифт не загрузился: ${f}`);
  for (const t of overflow) console.warn(`⚠ текст выходит за край макета: «${t}»`);
  for (const e of scriptErrors) console.warn(`⚠ ошибка JavaScript на странице: ${e}`);
  for (const f of design.faces) console.warn(`⚠ нет начертания — браузер подставит соседнее: ${f}`);
  for (const s of design.stretch) console.warn(`⚠ шрифт искажён растяжением (допустимо до ×1.3 по высоте): ${s}`);
  for (const s of design.small) console.warn(`⚠ рукописный шрифт слишком мелкий: ${s}`);
  for (const h of design.hanging) console.warn(`⚠ висячее слово — перенести или &nbsp;: ${h}`);
  for (const d of design.dates) console.warn(`⚠ день недели не совпадает с датой: ${d}`);
  if (design.placeholders.length) console.log(`ℹ заглушки (заменить перед публикацией): ${design.placeholders.join(', ')}`);
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { chromium } = loadPlaywright();
  const server = await serve();
  const browser = await launch(chromium);
  try {
    for (const file of opts.files) await renderFile(browser, server.address().port, file, opts);
  } finally {
    await browser.close();
    server.close();
  }
}

if (require.main === module) {
  main().catch((err) => {
    console.error(`✗ ${err.message}`);
    process.exit(1);
  });
}

module.exports = { ROOT, loadPlaywright, serve, launch, openPage };
