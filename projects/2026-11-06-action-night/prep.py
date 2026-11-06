"""Люди и стаканчики из черновиков — вырезки без фона, увеличенные нейросетью (EDSR ×2), чтобы наклейки не мылились.

    <venv с rembg, opencv-contrib, scipy>/bin/python -I projects/2026-11-06-action-night/prep.py <EDSR_x2.pb>

Выход — private/ (на фото люди, в том числе дети: репозиторий публичный).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, 'private')

# Люди на автобусе в черновике 1 (x0, y0, x1, y1) — с запасом; снизу их режет борт автобуса.
PEOPLE = {
    'p1': (226, 1018, 432, 1192),   # светлые волосы, рука у рта
    'p2': (690, 1044, 852, 1192),   # девушка справа сверху
    'p3': (318, 1192, 496, 1346),   # мальчик
    'p4': (590, 1172, 700, 1324),   # мужчина
    'p5': (716, 1176, 908, 1324),   # девушка с косой
}
CUPS = {'coffee': (96, 990, 580, 1640), 'cocoa': (580, 1020, 1010, 1580)}


def upscale(sr, rgb):
    return cv2.cvtColor(sr.upsample(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)), cv2.COLOR_BGR2RGB)


def cut(src, box, session, sr, name, erode=2):
    im = Image.open(src).convert('RGB').crop(box)
    big = upscale(sr, np.asarray(im))
    rgba = np.asarray(remove(Image.fromarray(big), session=session)).copy()
    a = rgba[..., 3]
    a = ndi.grey_erosion(a, size=(erode * 2 + 1, erode * 2 + 1))
    rgba[..., 3] = a
    Image.fromarray(rgba, 'RGBA').save(os.path.join(PRIV, f'{name}.png'))
    print(name, rgba.shape)


def main():
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(sys.argv[1])
    sr.setModel('edsr', 2)
    people = new_session('u2net_human_seg')
    for name, box in PEOPLE.items():
        cut(os.path.join(PRIV, 'draft-1-action.webp'), box, people, sr, name)
    objects = new_session('isnet-general-use')
    for name, box in CUPS.items():
        cut(os.path.join(PRIV, 'draft-3-coffee.webp'), box, objects, sr, f'cup-{name}', erode=1)


if __name__ == '__main__':
    main()
