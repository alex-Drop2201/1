#!/usr/bin/env python3
"""Пометки на макете: пронумерованные рамки и кружки по списку замечаний.

    python3 -I .claude/skills/poster-critique/scripts/annotate.py tmp/critique/twin-015 issues.json

issues.json — список замечаний: [{"n": 1, "sev": "crit|warn|minor", "box": [x, y, w, h], "text": "коротко"}, ...]
(координаты в пикселях макета; "box" можно заменить точкой "at": [x, y]). Пишет annotated.jpg: слева макет с пометками,
справа список замечаний тем же номером и цветом.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
FONT_B = os.path.join(ROOT, 'fonts/Inter/Inter-700.ttf')
FONT_R = os.path.join(ROOT, 'fonts/Inter/Inter-500.ttf')
COLOR = {'crit': (230, 40, 40), 'warn': (245, 150, 0), 'minor': (40, 120, 255)}
LABEL = {'crit': 'критично', 'warn': 'заметно', 'minor': 'мелочь'}


def wrap(text, font, width):
    """Перенос по словам по реальной ширине шрифта."""
    lines, cur = [], ''
    for word in text.split():
        probe = f'{cur} {word}'.strip()
        if font.getlength(probe) <= width or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def main():
    out, issues_file = sys.argv[1], sys.argv[2]
    issues = json.load(open(issues_file, encoding='utf-8'))
    im = Image.open(os.path.join(out, 'ours.png')).convert('RGB')
    W, H = im.size
    k = W / 1080
    d = ImageDraw.Draw(im)
    r = round(26 * k)
    placed = []
    for it in issues:
        col = COLOR[it.get('sev', 'warn')]
        if 'box' in it:
            x, y, w, h = it['box']
            d.rectangle((x, y, x + w, y + h), outline=col, width=round(5 * k))
            cx, cy = x + r * 0.6, y + r * 0.6
        else:
            cx, cy = it['at']
        cx, cy = min(max(cx, r), W - r), min(max(cy, r), H - r)
        # Номера не должны лечь друг на друга.
        while any(abs(cx - px) < 2.2 * r and abs(cy - py) < 2.2 * r for px, py in placed):
            cx = cx + 2.2 * r if cx + 3.2 * r < W else cx - 2.2 * r
        placed.append((cx, cy))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col, outline=(255, 255, 255), width=round(3 * k))
        d.text((cx, cy), str(it['n']), fill=(255, 255, 255), font=ImageFont.truetype(FONT_B, round(28 * k)), anchor='mm')

    # Список справа, высота как у макета.
    panel_w = round(W * 0.8)
    panel = Image.new('RGB', (panel_w, H), (246, 244, 240))
    pd = ImageDraw.Draw(panel)
    fb, fr = ImageFont.truetype(FONT_B, round(30 * k)), ImageFont.truetype(FONT_R, round(28 * k))
    y = round(40 * k)
    for it in issues:
        col = COLOR[it.get('sev', 'warn')]
        pd.ellipse((30 * k, y, 30 * k + 2 * r, y + 2 * r), fill=col)
        pd.text((30 * k + r, y + r), str(it['n']), fill=(255, 255, 255), font=fb, anchor='mm')
        pd.text((30 * k + 2 * r + 16 * k, y + 6 * k), LABEL[it.get('sev', 'warn')], fill=col, font=fb)
        y += round(48 * k)
        left = 30 * k + 2 * r + 16 * k
        for line in wrap(it['text'], fr, panel_w - left - 30 * k):
            pd.text((left, y), line, fill=(25, 25, 25), font=fr)
            y += round(36 * k)
        y += round(22 * k)
    sheet = Image.new('RGB', (W + panel_w, H), (246, 244, 240))
    sheet.paste(im, (0, 0))
    sheet.paste(panel, (W, 0))
    sheet.save(os.path.join(out, 'annotated.jpg'), quality=86)
    print(f'✓ {os.path.relpath(os.path.join(out, "annotated.jpg"), ROOT)}')


if __name__ == '__main__':
    main()
