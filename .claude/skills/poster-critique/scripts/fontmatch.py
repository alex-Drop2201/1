#!/usr/bin/env python3
"""Подбор кириллического шрифта под шрифт референса: кусок референса сверху, кандидаты ниже — нашим текстом,
на той же высоте знаков и в тех же цветах, плюс строка трудных для кириллицы букв.

    python3 -I .claude/skills/poster-critique/scripts/fontmatch.py \\
        --ref references/telegram/006-2025-04-24.jpg --box 0.18,0.02,0.30,0.13 \\
        --text "Бог видит" --fonts "Caveat:700" "Neucha" "Shantell Sans:700" --out tmp/critique/fonts-006.jpg

--box: x,y,w,h куска референса в пикселях или долях (0–1). --text: наш текст той же роли (одна строка).
--fg / --bg: цвет текста и фона референса (#RRGGBB), если рядом с надписью есть другие элементы и автоопределение ошибается.
Шрифт: "Семейство[:вес[:italic]]". Берётся из fonts/, иначе скачивается с Google Fonts в tmp/fonts/
(в репозиторий не попадает; понравившийся потом ставится через scripts/get_font.py).
"""
import argparse
import os
import re
import subprocess
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
LABEL_FONT = os.path.join(ROOT, 'fonts/Inter/Inter-700.ttf')
STRESS = 'Ждём тебя в воскресенье — д т ж ш щ ы я б в ф Ё 10:30'


def font_file(spec):
    """Путь к TTF по «Семейство:вес:italic»: fonts/ → tmp/fonts/ → скачать с Google Fonts."""
    parts = spec.split(':')
    family, weight = parts[0], int(parts[1]) if len(parts) > 1 else 400
    italic = len(parts) > 2 and parts[2] == 'italic'
    slug = family.replace(' ', '-')
    name = f'{slug}-{weight}{"-italic" if italic else ""}'
    for base in ('fonts', 'tmp/fonts'):
        for ext in ('ttf', 'otf'):
            p = os.path.join(ROOT, base, slug, f'{name}.{ext}')
            if os.path.exists(p):
                return p
    axis = f'ital,wght@{int(italic)},{weight}'
    url = 'https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(family) + ':' + axis
    req = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'curl/8.0'}), timeout=60).read()
    css = req(url).decode()
    src = re.search(r'url\((.*?)\)', css).group(1)
    target = os.path.join(ROOT, 'tmp/fonts', slug)
    os.makedirs(target, exist_ok=True)
    p = os.path.join(target, f'{name}.{src.rsplit(".", 1)[-1]}')
    with open(p, 'wb') as f:
        f.write(req(src))
    return p


def cyrillic(path):
    """Есть ли весь русский алфавит (А–я, Ё, ё)."""
    out = subprocess.run(['fc-query', '--format', '%{charset}', path], capture_output=True, text=True).stdout
    have = set()
    for part in out.split():
        a, _, b = part.partition('-')
        have.update(range(int(a, 16), int(b or a, 16) + 1))
    need = set(range(0x410, 0x450)) | {0x401, 0x451}
    return need <= have


def ink_box(im, bg, fg=None, thr=60):
    px = np.asarray(im.convert('RGB')).astype(int)
    # Знаки — пиксели цвета текста, если он задан, иначе всё, что заметно отличается от фона.
    a = np.abs(px - np.array(fg)).sum(-1) < 110 if fg else np.abs(px - np.array(bg)).sum(-1) > thr
    ys, xs = np.where(a)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else (0, 0, im.width, im.height)


def render(path, text, ink_h, fg, bg):
    """Строка шрифтом path, подогнанная так, чтобы высота знаков была ink_h."""
    size = 200
    for _ in range(3):
        f = ImageFont.truetype(path, size)
        l, t, r, b = f.getbbox(text)
        size = max(8, round(size * ink_h / max(1, b - t)))
    f = ImageFont.truetype(path, size)
    l, t, r, b = f.getbbox(text)
    pad = round(ink_h * 0.25)
    im = Image.new('RGB', (r - l + 2 * pad, b - t + 2 * pad), bg)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=fg)
    return im, r - l


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', required=True)
    ap.add_argument('--box', required=True)
    ap.add_argument('--text', required=True)
    ap.add_argument('--fonts', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fg')
    ap.add_argument('--bg')
    a = ap.parse_args()

    ref = Image.open(a.ref).convert('RGB')
    box = [float(v) for v in a.box.split(',')]
    if all(v <= 1 for v in box):
        box = [box[0] * ref.width, box[1] * ref.height, box[2] * ref.width, box[3] * ref.height]
    x, y, w, h = box
    crop = ref.crop((round(x), round(y), round(x + w), round(y + h)))
    px = np.asarray(crop).reshape(-1, 3).astype(int)
    border = np.concatenate([np.asarray(crop)[0], np.asarray(crop)[-1], np.asarray(crop)[:, 0], np.asarray(crop)[:, -1]])
    bg = tuple(int(v) for v in np.median(border, axis=0))
    dist = np.abs(px - np.array(bg)).sum(-1)
    fg = tuple(int(v) for v in np.median(px[dist >= np.percentile(dist, 97)], axis=0))
    hexrgb = lambda c: tuple(int(c.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    bg = hexrgb(a.bg) if a.bg else bg
    fg = hexrgb(a.fg) if a.fg else fg
    l, t, r, b = ink_box(crop, bg, fg if a.fg else None)
    ink_h, ink_w = b - t, r - l
    # Кандидаты — с высотой знаков 120 px; кусок референса показываем не меньше 220 px высотой, чтобы был виден характер.
    k = max(120 / ink_h, 220 / crop.height)
    rows = [('референс', crop.resize((round(crop.width * k), round(crop.height * k)), Image.LANCZOS), '')]

    for spec in a.fonts:
        try:
            path = font_file(spec)
        except Exception as e:
            rows.append((f'{spec}: не скачался ({e.__class__.__name__})', None, ''))
            continue
        ok = cyrillic(path)
        im, width = render(path, a.text, 120, fg, bg)
        stress, _ = render(path, STRESS, 46, fg, bg)
        note = f'ширина {width / (ink_w * k):.2f} от референса' if ok else 'НЕТ КИРИЛЛИЦЫ'
        rows.append((f'{spec}  ·  {note}', im, stress))

    W = max([r[1].width for r in rows if r[1] is not None] + [r[2].width for r in rows if r[2]] + [900]) + 40
    H = sum(60 + (r[1].height if r[1] is not None else 0) + (r[2].height if r[2] else 0) + 20 for r in rows)
    sheet = Image.new('RGB', (W, H), (236, 233, 228))
    d = ImageDraw.Draw(sheet)
    lf = ImageFont.truetype(LABEL_FONT, 26)
    yy = 10
    for label, im, stress in rows:
        d.text((20, yy + 14), label, fill=(20, 20, 20), font=lf)
        yy += 60
        if im is not None:
            sheet.paste(im, (20, yy))
            yy += im.height
        if stress:
            sheet.paste(stress, (20, yy))
            yy += stress.height
        yy += 20
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out, quality=88)
    print(f'✓ {os.path.relpath(os.path.abspath(a.out), ROOT)}: высота знаков в референсе {ink_h}px, цвет текста {fg}, фон {bg}')


if __name__ == '__main__':
    main()
