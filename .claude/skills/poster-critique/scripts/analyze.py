#!/usr/bin/env python3
"""Анализ замеров макета: контраст текста, зоны, кегли, фото, палитра, «прищур», распределение масс.

    python3 -I .claude/skills/poster-critique/scripts/analyze.py tmp/critique/twin-015 [--ref references/telegram/015-....jpg]

Читает ours.png, bg.png, metrics.json из папки (их пишет measure.cjs) и кладёт туда же:
side.jpg, squint.jpg, zones.jpg, palette.jpg, mass.jpg и auto.md со списком найденного автоматически.
Референс по умолчанию ищется по номеру в имени файла макета (twin-015.html, ref-047.html → references/telegram/015-*.jpg).
Готовая картинка без HTML (чужой постер, присланный PNG): --image путь.png — тогда без проверок текста, только картинки.
"""
import datetime
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
FONT = os.path.join(ROOT, 'fonts/Inter/Inter-700.ttf')
SEV = {'crit': 'критично', 'warn': 'заметно', 'minor': 'мелочь'}
SEV_COLOR = {'crit': (230, 40, 40), 'warn': (245, 160, 0), 'minor': (60, 140, 255)}


def font(size):
    return ImageFont.truetype(FONT, size)


def lum(rgb):
    """Относительная яркость WCAG для массива RGB 0..255 (последняя ось — каналы)."""
    c = np.asarray(rgb, dtype=float) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def ratio(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def to_lab(rgb):
    c = np.asarray(rgb, dtype=float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def find_ref(metrics_file):
    m = re.search(r'(?:twin|ref)-(\d{3})', metrics_file)
    if not m:
        return None
    hits = glob.glob(os.path.join(ROOT, f'references/telegram/{m.group(1)}-*.jpg'))
    return hits[0] if hits else None


def grid(im, step=0.1, color=(0, 230, 230)):
    im = im.copy()
    d = ImageDraw.Draw(im)
    for k in range(1, int(1 / step)):
        x, y = im.width * k * step, im.height * k * step
        d.line([(x, 0), (x, im.height)], fill=color, width=1)
        d.line([(0, y), (im.width, y)], fill=color, width=1)
    return im


def at_height(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def row(images, labels, h=900, gap=16, pad=50):
    tiles = [at_height(im, h) for im in images]
    out = Image.new('RGB', (sum(t.width for t in tiles) + gap * (len(tiles) - 1), h + pad), (150, 146, 138))
    d = ImageDraw.Draw(out)
    x = 0
    for t, label in zip(tiles, labels):
        out.paste(t, (x, pad))
        d.text((x + 8, 10), label, fill=(20, 20, 20), font=font(26))
        x += t.width + gap
    return out


def palette(im, k=6):
    """Основные цвета и их доля: медианное сечение на уменьшенной картинке."""
    small = im.convert('RGB').resize((160, round(160 * im.height / im.width)))
    q = small.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[: k * 3]).reshape(-1, 3)
    counts = np.bincount(np.asarray(q).ravel(), minlength=k)[:k]
    order = np.argsort(-counts)
    return [(tuple(int(v) for v in pal[i]), counts[i] / counts.sum()) for i in order if counts[i]]


WD = {'пн': 0, 'понедельник': 0, 'вт': 1, 'вторник': 1, 'ср': 2, 'среда': 2, 'среду': 2, 'чт': 3, 'четверг': 3,
      'пт': 4, 'пятница': 4, 'пятницу': 4, 'сб': 5, 'суббота': 5, 'субботу': 5, 'вс': 6, 'воскресенье': 6}
WD_NAMES = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']


def date_mentions(text):
    """Пары «день недели — дата» в тексте макета. Год — из текста, иначе ближайший к сегодняшнему дню."""
    found = []
    pat = r'\b(' + '|'.join(sorted(WD, key=len, reverse=True)) + r')\b[^\d]{0,25}?(?:\d{1,2}:\d{2}[^\d]{0,10}?)?(\d{1,2})(?:-?е)?\s+([а-яё]+)(?:\s+(\d{4}))?'
    for m in re.finditer(pat, text.lower()):
        wd, d, mon, y = m.groups()
        mi = next((i for i, p in enumerate(MONTHS) if mon.startswith(p) or (p == 'мая' and mon.startswith('май'))), None)
        if mi is None:
            continue
        today = datetime.date.today()
        year = int(y) if y else today.year
        try:
            day = datetime.date(year, mi + 1, int(d))
        except ValueError:
            continue
        if not y and (today - day).days > 180:
            day = day.replace(year=year + 1)
        found.append((WD[wd], day, mon, y))
    return found


def hexc(c):
    return '#%02X%02X%02X' % c


def main():
    args = sys.argv[1:]
    out = os.path.abspath(args[0])
    ref_path = args[args.index('--ref') + 1] if '--ref' in args else None
    os.makedirs(out, exist_ok=True)
    if '--image' in args:
        src = args[args.index('--image') + 1]
        Image.open(src).convert('RGB').save(os.path.join(out, 'ours.png'))
        m = {'file': os.path.relpath(os.path.abspath(src), ROOT), 'lines': [], 'images': [], 'width': 0, 'height': 0}
    else:
        m = json.load(open(os.path.join(out, 'metrics.json'), encoding='utf-8'))
    ours = Image.open(os.path.join(out, 'ours.png')).convert('RGB')
    bg_file = os.path.join(out, 'bg.png')
    bg = Image.open(bg_file).convert('RGB') if '--image' not in args and os.path.exists(bg_file) else ours
    W, H = ours.size
    ref_path = ref_path or find_ref(m['file'])
    ref = Image.open(ref_path).convert('RGB') if ref_path else None
    A, B = np.asarray(ours).astype(int), np.asarray(bg).astype(int)
    findings = []

    def add(sev, what, fix, box=None):
        findings.append({'sev': sev, 'what': what, 'fix': fix, 'box': box})

    for e in m.get('scriptErrors', []):
        add('crit', f'ошибка JavaScript: {e}', 'исправить скрипт макета — часть элементов могла не нарисоваться')

    # Контраст: пиксели, которые меняются, когда текст спрятан, — это сам текст; под ними — его фон.
    for i, ln in enumerate(m['lines']):
        x0, y0 = max(ln['x'] - 2, 0), max(ln['y'] - 2, 0)
        x1, y1 = min(ln['x'] + ln['w'] + 2, W), min(ln['y'] + ln['h'] + 2, H)
        if x1 <= x0 or y1 <= y0:
            continue
        a, b = A[y0:y1, x0:x1], B[y0:y1, x0:x1]
        mask = np.abs(a - b).sum(-1) > 60
        # Сплошной цвет: только пиксели этого цвета — иначе в «текст» попадут соседние надписи за ним.
        solid = re.match(r'rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)', ln['color'])
        if solid and not ln['gradient'] and float(solid.group(4) or 1) > 0.5:
            near = np.abs(a - np.array([int(v) for v in solid.groups()[:3]])).sum(-1) < 90
            if (mask & near).sum() >= 25:
                mask &= near
        ln['box'] = [x0, y0, x1 - x0, y1 - y0]
        if mask.sum() < 25:
            continue
        lt = float(np.median(lum(a[mask])))
        lb = lum(b[mask])
        # Худший случай — фон, ближайший по светлоте к тексту (10 % самых неудачных пикселей).
        worst = float(np.percentile(lb, 90 if lt > np.median(lb) else 10))
        ln['contrast'] = round(ratio(lt, float(np.median(lb))), 2)
        ln['contrast_worst'] = round(ratio(lt, worst), 2)
        large = ln['fontSize'] >= 32 or (ln['fontSize'] >= 24 and int(ln['fontWeight']) >= 700)
        name = f'«{ln["text"][:30]}»'
        if ln['bleed']:
            continue  # декоративная надпись за краем — бледность задумана
        c = ln['contrast_worst']
        if c < 3:
            add('crit', f'{name}: контраст {c}:1 в худшем месте (медиана {ln["contrast"]}:1)',
                'плашка или затемнение под текстом, другой цвет текста или сдвинуть на ровный участок', ln['box'])
        elif c < 4.5:
            add('warn' if not large else 'minor', f'{name}: контраст {c}:1 в худшем месте (норма 4.5:1)',
                'усилить затемнение фото под текстом или сделать текст светлее/темнее', ln['box'])

    # Кегли.
    # Видимый кегль: с учётом растяжения трансформацией (бокс строки ≈ 1.2 кегля).
    sizes = [max(ln['fontSize'], ln['h'] / 1.2) for ln in m['lines']]
    if sizes and max(sizes) < 90 * W / 1080:
        add('warn', f'самый крупный текст {max(sizes):.0f}px — заголовок мельче 90px на 1080',
            'увеличить заголовок, если это не служебная типографика референса')
    small = sorted({ln['text'][:24] for ln in m['lines'] if ln['fontSize'] < 20 * W / 1080 and not ln['bleed']})
    if small:
        add('minor', f'очень мелкий текст (<20px): {", ".join(small[:6])}{" …" if len(small) > 6 else ""}',
            'на телефоне не прочтётся; если так в референсе — оставить как служебную строку, важное (время, адрес) крупнее')

    # Зоны: интерфейс сторис и обрезка поста 4:5 до 3:4 в сетке профиля.
    zones = []
    if (W, H) == (1080, 1920):
        zones = [('верх сторис', 0, 0, W, 250), ('низ сторис', 0, H - 340, W, 340)]
    elif abs(W / H - 0.8) < 0.01:
        side = round((W - H * 0.75) / 2)
        zones = [('обрезка 3:4 слева', 0, 0, side, H), ('обрезка 3:4 справа', W - side, 0, side, H)]
    for ln in m['lines']:
        if ln['bleed'] or 'box' not in ln:
            continue
        x, y, w, h = ln['box']
        for zname, zx, zy, zw, zh in zones:
            if x < zx + zw and x + w > zx and y < zy + zh and y + h > zy:
                add('crit' if 'сторис' in zname else 'warn', f'«{ln["text"][:30]}» в зоне «{zname}»',
                    'перенести текст из зоны' if 'сторис' in zname else 'отодвинуть от края: в сетке профиля обрежется', ln['box'])
        if min(x, y, W - x - w, H - y - h) < 0.03 * W:
            add('minor', f'«{ln["text"][:30]}» почти у края (меньше 3 % ширины)', 'добавить поле, если это не приём референса', ln['box'])

    # Висячие предлоги и одиночные слова в последней строке.
    for ln in m['lines']:
        if ln.get('hangingShort'):
            add('minor', f'«{ln["hangingShort"]}» висит в конце строки «{ln["text"][:30]}»',
                f'перенести «{ln["hangingShort"]}» на следующую строку или поставить &nbsp; после него', ln.get('box'))
        if ln.get('widow'):
            add('minor', f'одно слово в последней строке: «{ln["text"]}»', 'перебить строки или сузить блок', ln.get('box'))

    # День недели и дата: «Вт 20 окт», «Ср 21-е окт 2026», «Воскресенье · 10:00 · 1 ноября».
    text = ' '.join(ln['text'] for ln in m['lines'])
    for wd, day, mon, year in date_mentions(text):
        if wd != day.weekday():
            add('crit', f'«{WD_NAMES[wd]}» стоит рядом с датой {day:%d.%m.%Y}, а это {WD_NAMES[day.weekday()]}',
                'исправить день недели или дату')

    # Фото.
    for im in m['images']:
        if im['upscale'] > 1.5:
            add('warn', f'{im["src"]} растянуто ×{im["upscale"]} — будет мыло', 'взять фото крупнее', [im['x'], im['y'], im['w'], im['h']])
        elif im['upscale'] > 1.15:
            add('minor', f'{im["src"]} растянуто ×{im["upscale"]}', 'по возможности фото крупнее', [im['x'], im['y'], im['w'], im['h']])

    # --- Картинки для глаза ---
    if ref:
        row([grid(ref), grid(ours)], ['референс', 'наш']).save(os.path.join(out, 'side.jpg'), quality=86)
    pair = [ref, ours] if ref else [ours]
    names = ['референс', 'наш'] if ref else ['наш']
    blur = [im.filter(ImageFilter.GaussianBlur(im.width / 55)) for im in pair]
    gray = [im.convert('L').convert('RGB') for im in pair]
    row(blur + gray, [f'{n}: прищур' for n in names] + [f'{n}: светлота' for n in names], h=700).save(
        os.path.join(out, 'squint.jpg'), quality=86)

    # Сводный лист для одного взгляда: сравнение с сеткой, под ним прищур и светлота.
    top = row([grid(ref), grid(ours)] if ref else [grid(ours)], names, h=900)
    bottom = row(blur + gray, [f'{n}: прищур' for n in names] + [f'{n}: светлота' for n in names], h=520)
    sheet = Image.new('RGB', (max(top.width, bottom.width), top.height + bottom.height + 10), (150, 146, 138))
    sheet.paste(top, (0, 0))
    sheet.paste(bottom, (0, top.height + 10))
    sheet.save(os.path.join(out, 'sheet.jpg'), quality=84)

    # Зоны и боксы текста с контрастом: зелёный ≥ 4.5, оранжевый 3–4.5, красный < 3.
    z = ours.copy()
    shade = Image.new('RGBA', z.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for _, zx, zy, zw, zh in zones:
        sd.rectangle((zx, zy, zx + zw, zy + zh), fill=(255, 0, 0, 70))
    z = Image.alpha_composite(z.convert('RGBA'), shade)
    d = ImageDraw.Draw(z)
    for ln in m['lines']:
        if 'box' not in ln:
            continue
        x, y, w, h = ln['box']
        c = ln.get('contrast_worst')
        col = (140, 140, 140) if c is None or ln['bleed'] else (0, 200, 0) if c >= 4.5 else (255, 160, 0) if c >= 3 else (255, 0, 0)
        d.rectangle((x, y, x + w, y + h), outline=col, width=3)
        if c is not None and not ln['bleed']:
            d.text((x + 4, y + h + 2), f'{c}:1', fill=col, font=font(18), stroke_width=2, stroke_fill=(0, 0, 0))
    z.convert('RGB').save(os.path.join(out, 'zones.jpg'), quality=86)

    # Палитра: свои цвета и ближайшие из референса (ΔE).
    pal_o = palette(ours)
    pal_r = palette(ref) if ref else []
    sw = Image.new('RGB', (1200, 70 + 90 * max(len(pal_o), len(pal_r))), (240, 238, 234))
    d = ImageDraw.Draw(sw)
    d.text((20, 20), 'референс', fill=(0, 0, 0), font=font(24))
    d.text((620, 20), 'наш  (ΔE до ближайшего цвета референса)', fill=(0, 0, 0), font=font(24))
    lab_r = to_lab(np.array([c for c, _ in pal_r])) if pal_r else None
    pal_report = []
    for col_x, pal in [(20, pal_r), (620, pal_o)]:
        for i, (c, share) in enumerate(pal):
            y = 70 + 90 * i
            d.rectangle((col_x, y, col_x + 120, y + 70), fill=c, outline=(0, 0, 0))
            label = f'{hexc(c)}  {share * 100:.0f}%'
            if col_x == 620 and lab_r is not None:
                de = float(np.min(np.linalg.norm(lab_r - to_lab(np.array(c)), axis=-1)))
                label += f'  ΔE {de:.0f}'
                pal_report.append((hexc(c), share, de))
            d.text((col_x + 140, y + 20), label, fill=(0, 0, 0), font=font(24))
    sw.save(os.path.join(out, 'palette.jpg'), quality=90)

    # Распределение масс: средняя светлота по сетке 10×10 и разница с референсом.
    mass_note = ''
    if ref:
        def cells(im):
            return np.asarray(im.convert('L').resize((10, 10), Image.BOX)).astype(float)
        cr, co = cells(ref), cells(ours)
        diff = co - cr
        cell = 60
        mp = Image.new('RGB', (cell * 30 + 40, cell * 10 + 50), (150, 146, 138))
        d = ImageDraw.Draw(mp)
        for k, (title, arr) in enumerate([('референс', cr), ('наш', co), ('наш − референс', diff)]):
            ox = k * (cell * 10 + 20)
            d.text((ox + 4, 8), title, fill=(0, 0, 0), font=font(22))
            for r in range(10):
                for c in range(10):
                    v = arr[r, c]
                    col = (int(v),) * 3 if k < 2 else ((255, int(255 - min(255, v * 3)), int(255 - min(255, v * 3))) if v > 0
                                                       else (int(255 + max(-255, v * 3)), int(255 + max(-255, v * 3)), 255))
                    d.rectangle((ox + c * cell, 40 + r * cell, ox + (c + 1) * cell - 1, 40 + (r + 1) * cell - 1), fill=col)
        mp.save(os.path.join(out, 'mass.jpg'), quality=88)
        big = [(r, c, diff[r, c]) for r in range(10) for c in range(10) if abs(diff[r, c]) > 60]
        if len(big) >= 5:
            spots = ', '.join(f'x{c * 10}–{c * 10 + 10}% y{r * 10}–{r * 10 + 10}% ({"светлее" if v > 0 else "темнее"} на {abs(v):.0f})'
                              for r, c, v in sorted(big, key=lambda t: -abs(t[2]))[:5])
            mass_note = f'сильнее всего расходится светлота: {spots}'
            add('warn' if len(big) >= 20 else 'minor',
                f'распределение светлого и тёмного отличается от референса в {len(big)} клетках из 100', mass_note)

    # Отчёт.
    order = {'crit': 0, 'warn': 1, 'minor': 2}
    findings.sort(key=lambda f: order[f['sev']])
    lines = [f'# Автопроверка: {m["file"]}', '', f'Холст {W}×{H}' + (f', референс {os.path.relpath(ref_path, ROOT)}' if ref else ', без референса'), '']
    if findings:
        for n, f in enumerate(findings, 1):
            lines.append(f'{n}. **{SEV[f["sev"]]}** — {f["what"]}. Как исправить: {f["fix"]}.')
    else:
        lines.append('Автоматически ничего не найдено — остаётся визуальная проверка по чек-листу.')
    lines += ['', '## Текст', '', '| строка | кегль | контраст (медиана / худший) |', '|---|---|---|']
    for ln in m['lines']:
        c = f'{ln.get("contrast", "—")} / {ln.get("contrast_worst", "—")}' + (' (за краем, декор)' if ln['bleed'] else '')
        cell = ln['text'][:40].replace('|', '\\|')
        lines.append(f'| {cell} | {ln["fontSize"]:.0f}px {ln["fontFamily"]} {ln["fontWeight"]} | {c} |')
    if pal_report:
        lines += ['', '## Палитра (наш цвет → ΔE до ближайшего в референсе; >10 заметно, >20 другой цвет)', '']
        lines += [f'- {h} — {s * 100:.0f}% площади, ΔE {de:.0f}' for h, s, de in pal_report]
    open(os.path.join(out, 'auto.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    json.dump(findings, open(os.path.join(out, 'auto.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'✓ {os.path.relpath(out, ROOT)}: {len(findings)} автонаходок '
          f'({sum(f["sev"] == "crit" for f in findings)} критично, {sum(f["sev"] == "warn" for f in findings)} заметно)')


if __name__ == '__main__':
    main()
