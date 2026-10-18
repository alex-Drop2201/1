#!/usr/bin/env node
// Снимок готовой раскладки макета для холста Design: стили, разметка, прозрачные слои декора, список файлов.
//
//   node .claude/skills/poster-canvas/scripts/snapshot.cjs projects/<папка>/<макет>.html tmp/canvas/<макет>
//
// Пишет в папку snapshot.json ({width, height, title, css, markup, assets, texts}) и ras-*.png / grain-*.png.
// В css и markup файлы стоят как ASSET:<путь от корня репозитория> — их заменяют на адреса загруженных файлов.
// Каждому элементу с текстом ставится data-t="<номер>", texts[номер] — исходный текст (по нему сверяются правки).

const fs = require('fs');
const path = require('path');
const { ROOT, loadPlaywright, serve, launch, openPage } = require(path.join(__dirname, '../../../../scripts/render.cjs'));

async function main() {
  const [file, outArg] = process.argv.slice(2);
  const out = path.resolve(outArg);
  fs.mkdirSync(out, { recursive: true });
  const rel = (p) => path.relative(ROOT, p).split(path.sep).join('/');

  const { chromium } = loadPlaywright();
  const server = await serve();
  const browser = await launch(chromium);
  try {
    const { page, width, height } = await openPage(browser, server.address().port, file, { scale: 1 });

    // 1. Тяжёлый декор (много узлов или шум feTurbulence) — в прозрачные картинки.
    const rasCount = await page.evaluate(() => {
      const list = [...document.querySelectorAll('main svg')].filter((s) => !s.closest('.cutbox')
        && (s.outerHTML.length > 2500 || s.querySelector('feTurbulence')));
      list.forEach((s, i) => s.setAttribute('data-ras', i));
      return list.length;
    });
    const rasPaths = [];
    for (let i = 0; i < rasCount; i++) {
      const tag = await page.addStyleTag({ content: `
        html, body, main, main::after { background: transparent !important; }
        main::after { display: none !important; }
        main * { visibility: hidden !important; }
        main svg[data-ras="${i}"], main svg[data-ras="${i}"] * { visibility: visible !important; }` });
      const p = path.join(out, `ras-${i}.png`);
      await page.screenshot({ path: p, clip: { x: 0, y: 0, width, height }, omitBackground: true });
      await tag.evaluate((n) => n.remove());
      rasPaths.push(rel(p));
    }

    // 2. Зерно (::after с SVG-шумом в data:) — плиткой PNG.
    const grains = await page.evaluate(() => ['grain', 'grain-light'].map((c) => {
      const el = document.querySelector(`main.${c}`);
      return el ? { cls: c, bg: getComputedStyle(el, '::after').backgroundImage } : null;
    }).filter(Boolean));
    const grainRules = [];
    for (const g of grains) {
      const m = /url\("(data:[^"]+)"\)/.exec(g.bg);
      if (!m) continue;
      const tile = await browser.newPage();
      await tile.setViewportSize({ width: 260, height: 260 });
      await tile.setContent(`<style>html,body{margin:0;background:transparent}</style><img src="${m[1].replace(/"/g, '&quot;')}" width="260" height="260">`);
      await tile.waitForTimeout(100);
      const p = path.join(out, `${g.cls}.png`);
      await tile.screenshot({ path: p, omitBackground: true });
      await tile.close();
      grainRules.push(`.${g.cls}::after { background-image: url(ASSET:${rel(p)}); }`);
    }

    // 3. Стили, шрифты (только загруженные), разметка с метками текста.
    const snap = await page.evaluate(() => {
      const css = [];
      const faces = [];
      const walk = (sheet) => {
        let rules;
        try { rules = sheet.cssRules; } catch { return; }
        for (const r of rules) {
          if (r instanceof CSSImportRule) { if (r.styleSheet) walk(r.styleSheet); continue; }
          if (r instanceof CSSFontFaceRule) {
            const src = /url\("?([^")]+)"?\)/.exec(r.style.getPropertyValue('src'));
            faces.push({ family: r.style.getPropertyValue('font-family').replace(/["']/g, '').trim(),
                         weight: r.style.getPropertyValue('font-weight') || '400', style: r.style.getPropertyValue('font-style') || 'normal',
                         url: src ? new URL(src[1], sheet.href || location.href).href : null, text: r.cssText });
            continue;
          }
          css.push(r.cssText.replace(/url\("data:[^"]*"\)/g, 'none'));
        }
      };
      for (const s of document.styleSheets) walk(s);
      const loaded = [...document.fonts].filter((f) => f.status === 'loaded')
        .map((f) => `${f.family.replace(/["']/g, '')}|${f.weight}|${f.style}`);
      const usedFaces = faces.filter((f) => f.url && loaded.includes(`${f.family}|${f.weight}|${f.style}`));

      const main = document.querySelector('main').cloneNode(true);
      main.querySelectorAll('script, .need, .slot > .ph').forEach((n) => n.remove());
      main.querySelectorAll('[data-ph], [data-need], [data-label], [data-src]').forEach((n) => {
        ['data-ph', 'data-need', 'data-label', 'data-src'].forEach((a) => n.removeAttribute(a));
      });
      main.querySelectorAll('svg[data-ras]').forEach((s) => {
        const img = document.createElement('img');
        img.setAttribute('src', `RAS:${s.getAttribute('data-ras')}`);
        img.setAttribute('alt', '');
        const z = s.style.zIndex || getComputedStyle(document.querySelector(`main svg[data-ras="${s.getAttribute('data-ras')}"]`)).zIndex;
        img.setAttribute('style', `position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;${z && z !== 'auto' ? ` z-index: ${z};` : ''}`);
        s.replaceWith(img);
      });
      const assets = new Set();
      main.querySelectorAll('img[src]').forEach((im) => {
        const src = im.getAttribute('src');
        if (src.startsWith('RAS:')) return;
        const u = new URL(src, location.href);
        im.setAttribute('src', `ASSET:${decodeURIComponent(u.pathname.slice(1))}`);
        assets.add(decodeURIComponent(u.pathname.slice(1)));
      });
      // Метки текста: элемент, у которого есть собственный непустой текст.
      const texts = {};
      let n = 0;
      main.querySelectorAll('*').forEach((el) => {
        if ([...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) {
          el.setAttribute('data-t', ++n);
          texts[n] = el.innerHTML;
        }
      });
      main.style.width = `${innerWidth}px`;
      main.style.height = `${innerHeight}px`;
      return { css: css.join('\n'), faces: usedFaces, markup: main.outerHTML, assets: [...assets], texts, title: document.title };
    });

    let markup = snap.markup.replace(/RAS:(\d+)/g, (_, i) => `ASSET:${rasPaths[+i]}`);
    const fontCss = snap.faces.map((f) => {
      const p = decodeURIComponent(new URL(f.url).pathname.slice(1));
      return `@font-face { font-family: '${f.family}'; font-style: ${f.style}; font-weight: ${f.weight}; font-display: block; src: url(ASSET:${p}); }`;
    });
    const css = [...fontCss, snap.css, `.canvas { width: ${width}px; height: ${height}px; }`, ...grainRules].join('\n');
    const assets = [...new Set([...snap.assets, ...rasPaths, ...grainRules.map((r) => /ASSET:([^)]+)/.exec(r)[1]),
      ...snap.faces.map((f) => decodeURIComponent(new URL(f.url).pathname.slice(1)))])];
    const result = { source: rel(path.resolve(file)), title: snap.title, width, height, css, markup, assets, texts: snap.texts };
    fs.writeFileSync(path.join(out, 'snapshot.json'), JSON.stringify(result, null, 1));
    await page.close();
    console.log(`✓ ${rel(out)}: ${width}×${height}, разметка ${(markup.length / 1024).toFixed(1)} КБ, стили ${(css.length / 1024).toFixed(1)} КБ, `
      + `${Object.keys(snap.texts).length} текстов, файлов ${assets.length}`);
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error(`✗ ${err.message}`);
  process.exit(1);
});
