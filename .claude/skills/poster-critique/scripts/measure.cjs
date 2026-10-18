#!/usr/bin/env node
// Замеры макета для критики: снимок, снимок без текста, строки текста с координатами и стилями, фото.
//
//   node .claude/skills/poster-critique/scripts/measure.cjs projects/<папка>/post.html tmp/critique/post
//
// Пишет в папку: ours.png, bg.png (тот же макет, текст спрятан) и metrics.json.

const fs = require('fs');
const path = require('path');
const { ROOT, loadPlaywright, serve, launch, openPage } = require(path.join(__dirname, '../../../../scripts/render.cjs'));

async function main() {
  const [file, outArg] = process.argv.slice(2);
  if (!file) throw new Error('Укажите HTML-файл: measure.cjs projects/<папка>/post.html [папка-вывода]');
  const out = path.resolve(outArg || path.join(ROOT, 'tmp/critique', path.basename(file, '.html')));
  fs.mkdirSync(out, { recursive: true });

  const { chromium } = loadPlaywright();
  const server = await serve();
  const browser = await launch(chromium);
  try {
    const { page, width, height, scriptErrors } = await openPage(browser, server.address().port, file, { scale: 1 });
    await page.screenshot({ path: path.join(out, 'ours.png'), clip: { x: 0, y: 0, width, height } });

    const metrics = await page.evaluate(() => {
      // Короткие слова, которые не должны висеть в конце строки.
      const SHORT = /^(в|во|и|к|ко|с|со|о|об|обо|у|а|но|на|по|за|от|до|из|не|ни|же|ли|бы|для|при|без|над|под|про|что|как)$/i;
      const lines = [];
      // Подключённые начертания: семейство → набор весов (normal/italic).
      const faces = {};
      for (const f of document.fonts) {
        if (f.status === 'error') continue;
        const fam = f.family.replace(/["']/g, '');
        (faces[fam] = faces[fam] || new Set()).add(`${f.weight}${f.style === 'italic' ? 'i' : ''}`);
      }
      // Суммарное растяжение элемента трансформациями (свои и родителей).
      const stretch = (el) => {
        let sx = 1, sy = 1;
        for (let e = el; e && e !== document.body; e = e.parentElement) {
          const t = getComputedStyle(e).transform;
          if (!t || t === 'none') continue;
          const v = t.match(/-?[\d.e]+/g).map(Number);
          sx *= Math.hypot(v[0], v[1]);
          sy *= Math.hypot(v[2], v[3]);
        }
        return [+sx.toFixed(2), +sy.toFixed(2)];
      };
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const el = node.parentElement;
        if (!el || !node.textContent.trim() || el.closest('script, style, .need')) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        // Строки: слова с одинаковым верхом бокса — одна строка.
        const words = [];
        const re = /\S+/g;
        for (let m = re.exec(node.textContent); m; m = re.exec(node.textContent)) {
          const range = document.createRange();
          range.setStart(node, m.index);
          range.setEnd(node, m.index + m[0].length);
          const r = range.getBoundingClientRect();
          if (r.width || r.height) words.push({ w: m[0], end: m.index + m[0].length, x: r.left, y: r.top, r: r.right, b: r.bottom });
        }
        const groups = [];
        for (const w of words) {
          const g = groups.find((g) => Math.abs(g.y - w.y) < (w.b - w.y) * 0.5);
          if (g) {
            g.words.push(w.w);
            g.end = w.end;
            g.x = Math.min(g.x, w.x); g.r = Math.max(g.r, w.r); g.b = Math.max(g.b, w.b);
          } else groups.push({ y: w.y, x: w.x, r: w.r, b: w.b, end: w.end, words: [w.w] });
        }
        const bleed = !!el.closest('[data-bleed]');
        const family = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
        const weightKey = `${cs.fontWeight}${cs.fontStyle === 'italic' ? 'i' : ''}`;
        const fontStatus = !faces[family] ? 'нет шрифта' : faces[family].has(weightKey) ? 'ok'
          : `нет начертания ${cs.fontWeight}${cs.fontStyle === 'italic' ? ' italic' : ''} (есть ${[...faces[family]].join(', ')})`;
        const [sx, sy] = stretch(el);
        const gradient = cs.backgroundClip === 'text' || cs.webkitBackgroundClip === 'text';
        groups.forEach((g, i) => {
          const last = g.words[g.words.length - 1];
          // Неразрывный пробел после предлога склеивает слова — тогда «висячего» нет.
          const nextChar = node.textContent[g.end];
          lines.push({
            text: g.words.join(' '),
            x: Math.round(g.x), y: Math.round(g.y), w: Math.round(g.r - g.x), h: Math.round(g.b - g.y),
            fontSize: parseFloat(cs.fontSize), fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, ''),
            fontWeight: cs.fontWeight, fontStyle: cs.fontStyle, color: cs.color, gradient, bleed, fontStatus, sx, sy,
            // Висячее слово: в конце строки внутри абзаца или перед ручным переносом <br>.
            hangingShort: SHORT.test(last) && nextChar !== '\u00a0'
              && (i < groups.length - 1 || (node.nextSibling && node.nextSibling.nodeName === 'BR')) ? last : null,
            widow: groups.length > 2 && i === groups.length - 1 && g.words.length === 1,
          });
        });
      }

      // Фото: во сколько раз растянуто относительно своего размера.
      const images = [...document.querySelectorAll('img')].filter((im) => im.complete && im.naturalWidth).map((im) => {
        const r = im.getBoundingClientRect();
        const fit = getComputedStyle(im).objectFit;
        // Размер без трансформаций (скошенная тень шире, но не растянута); object-fit: cover — по большей стороне.
        const k = fit === 'cover'
          ? Math.max(im.offsetWidth / im.naturalWidth, im.offsetHeight / im.naturalHeight)
          : im.offsetWidth / im.naturalWidth;
        return { src: im.getAttribute('src'), x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
                 natural: [im.naturalWidth, im.naturalHeight], upscale: +k.toFixed(2) };
      });

      // Метки для снимка без текста: градиентный текст держится на фоне, его фон тоже прячем.
      document.querySelectorAll('*').forEach((el) => {
        const cs = getComputedStyle(el);
        if (cs.backgroundClip === 'text' || cs.webkitBackgroundClip === 'text') el.setAttribute('data-crit-grad', '');
      });
      return { width: innerWidth, height: innerHeight, lines, images };
    });

    await page.addStyleTag({ content: `
      * { color: transparent !important; -webkit-text-fill-color: transparent !important;
          -webkit-text-stroke-color: transparent !important; text-shadow: none !important; text-decoration-color: transparent !important; }
      [data-crit-grad] { background: none !important; }
      .need { display: none !important; }` });
    await page.waitForTimeout(50);
    await page.screenshot({ path: path.join(out, 'bg.png'), clip: { x: 0, y: 0, width, height } });

    metrics.file = path.relative(ROOT, path.resolve(file));
    metrics.scriptErrors = scriptErrors;
    fs.writeFileSync(path.join(out, 'metrics.json'), JSON.stringify(metrics, null, 1));
    await page.close();
    console.log(`✓ замеры: ${path.relative(ROOT, out)} (${metrics.lines.length} строк текста, ${metrics.images.length} фото)`);
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error(`✗ ${err.message}`);
  process.exit(1);
});
