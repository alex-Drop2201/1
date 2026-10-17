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

async function renderFile(browser, port, file, opts) {
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

main().catch((err) => {
  console.error(`✗ ${err.message}`);
  process.exit(1);
});
