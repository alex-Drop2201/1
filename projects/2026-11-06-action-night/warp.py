"""Заголовок с деформацией «линза», как «FUCK UP / STAND UP» в референсе: буквы к краям строки сжимаются
и становятся ниже, в середине — раздуваются; верх и низ строки выгибаются наружу.

    python3 -I projects/2026-11-06-action-night/warp.py "ACTION" assets/t-action.png [--bulge 0.55] [--widen 0.35]

Строка рисуется Unbounded Black в 4 раза крупнее нужного и деформируется обратным отображением (каждой точке
результата — точка исходника), поэтому край букв остаётся чистым; результат — белый PNG с прозрачностью,
ставится в макет в натуральную величину (1 px картинки = 1 px макета), без растяжения.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
FONT = os.path.join(ROOT, 'fonts/Unbounded/Unbounded-900.ttf')


def render(text, cap, k=4, tracking=-0.04):
    """Строка шрифтом Unbounded Black: высота прописных cap·k px, разрядка в долях кегля."""
    f100 = ImageFont.truetype(FONT, 100)
    capr = (f100.getbbox('H')[3] - f100.getbbox('H')[1]) / 100
    size = round(cap * k / capr)
    f = ImageFont.truetype(FONT, size)
    widths = [f.getlength(ch) for ch in text]
    w = int(sum(widths) + tracking * size * (len(text) - 1) + size)
    h = int(size * 1.6)
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    x = size * 0.3
    for ch, cw in zip(text, widths):
        d.text((x, size * 0.25), ch, font=f, fill=255)
        x += cw + tracking * size
    a = np.asarray(im)
    ys, xs = np.nonzero(a > 0)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32) / 255


def warp(a, bulge=0.55, widen=0.35, pad=0.6):
    """bulge — насколько середина выше краёв (0.55: края на 55 % ниже середины); widen — насколько середина шире."""
    h, w = a.shape
    H = int(h * (1 + pad))
    out_w = w
    yy, xx = np.mgrid[0:H, 0:out_w].astype(np.float32)
    u = xx / (out_w - 1) * 2 - 1                          # −1 … 1 по ширине результата
    # горизонталь: середина шире, края уже — обратное отображение u → исходное s
    s = np.sign(u) * np.abs(u) ** (1 + widen)
    src_x = (s + 1) / 2 * (w - 1)
    # вертикаль: высота строки по ширине — косинусная «линза»
    scale = (1 - bulge) + bulge * np.clip(np.cos(u * np.pi / 2), 0, 1) ** 0.9
    scale = scale / scale.max() * (1 + pad * 0.85)         # в середине строка выше исходной
    cy_out, cy_src = (H - 1) / 2, (h - 1) / 2
    src_y = cy_src + (yy - cy_out) / scale
    res = ndi.map_coordinates(a, [src_y, src_x], order=1, mode='constant', cval=0)
    ys, xs = np.nonzero(res > 0.02)
    return res[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('text')
    ap.add_argument('out')
    ap.add_argument('--cap', type=float, default=150, help='высота прописных до деформации, px макета')
    ap.add_argument('--bulge', type=float, default=0.55)
    ap.add_argument('--widen', type=float, default=0.35)
    ap.add_argument('--width', type=float, default=0, help='итоговая ширина, px макета (0 — как получится)')
    ap.add_argument('--color', default='#ffffff')
    args = ap.parse_args()
    k = 4
    a = warp(render(args.text, args.cap, k), args.bulge, args.widen)
    im = Image.fromarray((a * 255).astype(np.uint8), 'L')
    target_w = args.width or im.width / k
    im = im.resize((round(target_w), round(im.height * target_w / im.width)), Image.LANCZOS)
    rgb = Image.new('RGB', im.size, args.color)
    rgb.putalpha(im)
    rgb.save(args.out)
    print(args.out, rgb.size)


if __name__ == '__main__':
    main()
