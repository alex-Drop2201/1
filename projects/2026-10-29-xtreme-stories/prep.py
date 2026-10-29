"""Подготовка исходников из черновиков сторис: чистые фоны без текста и предметов, буквы заголовка 1-й сторис,
телефон со скриншотом и вырезанный человек из 4-й.

    <venv с numpy, scipy, pillow, rembg>/bin/python -I projects/2026-10-29-xtreme-stories/prep.py

Фон восстанавливается так: всё, что не похоже на тёплый размытый фон (белое, серое, чёрное, фиолетовое, розовое,
плюс прямоугольники вокруг крупных предметов), маскируется и заполняется сглаживанием по соседним пикселям фона
на нескольких масштабах; затем фон целиком слегка размывается и получает ровное плёночное зерно.
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(HERE, 'assets/drafts')
PRIVATE = os.path.join(HERE, 'private')
OUT = os.path.join(HERE, 'assets')


def load(path):
    return np.asarray(Image.open(path).convert('RGB')).astype(np.float32)


def warm_background_mask(a):
    """True там, где пиксель похож на фон: тёплый (оттенок 10–60°), насыщенный, не тёмный."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    return (sat > 0.13) & (mx > 120) & (hue > 8) & (hue < 62)


def fill(a, hole, grain=5.0, seed=1):
    """Заполнить hole по соседнему фону (нормированная свёртка, от мелкого масштаба к крупному), сгладить и добавить зерно."""
    valid = ~hole
    out = a.copy()
    known = valid.copy()
    for sigma in (6, 16, 40, 100, 240):
        w = ndi.gaussian_filter(known.astype(np.float32), sigma)
        acc = np.stack([ndi.gaussian_filter(out[..., c] * known, sigma) for c in range(3)], -1)
        est = acc / np.maximum(w, 1e-6)[..., None]
        take = (~known) & (w > 0.02)
        out[take] = est[take]
        known = known | take
    out = np.stack([ndi.gaussian_filter(out[..., c], 3) for c in range(3)], -1)
    noise = np.random.default_rng(seed).normal(0, grain, out.shape[:2])[..., None]
    return np.clip(out + noise, 0, 255).astype(np.uint8)


def rect_mask(shape, rects):
    m = np.zeros(shape[:2], bool)
    for x0, y0, x1, y1 in rects:
        m[y0:y1, x0:x1] = True
    return m


def story1():
    a = load(os.path.join(DRAFTS, 'story-1.webp'))
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    text = ndi.binary_dilation(lum < 110, iterations=7)
    bg = fill(a, text, grain=5.5, seed=11)
    Image.fromarray(bg).save(os.path.join(OUT, 's1-bg.jpg'), quality=92)
    # Буквы: альфа из разницы с восстановленным фоном — чёрная краска, края сглажены как в оригинале.
    bg_l = bg.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    ink = 14.0
    alpha = np.clip((bg_l - lum) / np.maximum(bg_l - ink, 1), 0, 1)
    alpha[~text] = 0
    pieces = {  # x0, y0, x1, y1 — с запасом вокруг слова
        's1-title-1': (154, 830, 921, 943),
        's1-title-2': (167, 1006, 913, 1102),
        's1-date': (126, 738, 254, 792),
        's1-time': (740, 1138, 906, 1198),
        's1-place-1': (188, 1186, 468, 1232),   # «Универмаг»
        's1-place-3': (479, 1186, 510, 1232),   # «3»
        's1-place-y': (510, 1186, 538, 1232),   # «й» с краткой
        's1-place-dash': (538, 1186, 557, 1232),
        's1-place-2': (557, 1186, 698, 1232),   # «этаж»
    }
    for name, (x0, y0, x1, y1) in pieces.items():
        al = (alpha[y0:y1, x0:x1] * 255).astype(np.uint8)
        rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        rgba[..., 3] = al
        Image.fromarray(rgba, 'RGBA').save(os.path.join(OUT, f'{name}.png'))


def story_bg(src, name, seed):
    """Фон-градиент как в черновике: цвет каждой строки снят с левого и правого краёв (там всегда фон),
    между ними — плавный переход; затем сильное размытие и зерно. Предметы черновика в фон не попадают."""
    a = load(src)
    warm = warm_background_mask(a)
    h, w = warm.shape
    prof = []
    for xs in (slice(0, 14), slice(w - 14, w)):
        col = a[:, xs].copy()
        ok = warm[:, xs]
        val = np.full((h, 3), np.nan, np.float32)
        for y in range(h):
            if ok[y].sum() > 4:
                val[y] = np.median(col[y][ok[y]], axis=0)
        prof.append(val)
    left, right = prof
    left = np.where(np.isnan(left), right, left)
    right = np.where(np.isnan(right), left, right)
    for v in (left, right):  # дыры, где фона нет с обеих сторон, — по соседним строкам
        idx = np.arange(h)
        for c in range(3):
            good = ~np.isnan(v[:, c])
            v[:, c] = np.interp(idx, idx[good], v[good, c])
    left = ndi.gaussian_filter1d(left, 30, axis=0)
    right = ndi.gaussian_filter1d(right, 30, axis=0)
    t = np.linspace(0, 1, w)[None, :, None]
    t = t * t * (3 - 2 * t)
    bg = left[:, None, :] * (1 - t) + right[:, None, :] * t
    bg = np.stack([ndi.gaussian_filter(bg[..., c], 40) for c in range(3)], -1)
    noise = np.random.default_rng(seed).normal(0, 5.0, (h, w))[..., None]
    Image.fromarray(np.clip(bg + noise, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name), quality=92)


def rounded_alpha(w, h, r, k=4):
    """Маска скруглённого прямоугольника со сглаженным краем (рисуется в k раз крупнее и уменьшается)."""
    from PIL import ImageDraw
    m = Image.new('L', (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * k - 1, h * k - 1), r * k, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def story4_parts():
    from rembg import remove, new_session
    im = Image.open(os.path.join(PRIVATE, 'story-4.webp')).convert('RGB')
    phone = im.crop((27, 745, 412, 1526)).convert('RGBA')  # телефон со скриншотом, углы скруглены как у рамки
    phone.putalpha(rounded_alpha(*phone.size, 58))
    phone.save(os.path.join(PRIVATE, 's4-phone.png'))
    guy = im.crop((380, 1400, 1080, 1920))
    cut = remove(guy, session=new_session('u2net_human_seg'))
    al = np.asarray(cut)[..., 3]
    al = ndi.grey_erosion(al, size=(3, 3))  # ужать край на 1–2 px, без каймы фона
    rgba = np.asarray(cut).copy()
    rgba[..., 3] = al
    Image.fromarray(rgba, 'RGBA').save(os.path.join(PRIVATE, 's4-guy.png'))


if __name__ == '__main__':
    import sys
    if 'bg' not in sys.argv:
        story1()
    story_bg(os.path.join(DRAFTS, 'story-2.webp'), 's2-bg.jpg', 21)
    story_bg(os.path.join(DRAFTS, 'story-3.webp'), 's3-bg.jpg', 31)
    story_bg(os.path.join(PRIVATE, 'story-4.webp'), 's4-bg.jpg', 41)
    if 'bg' not in sys.argv:
        story4_parts()
    else:
        a = Image.open(os.path.join(PRIVATE, 'story-4.webp')).convert('RGB').crop((27, 745, 412, 1526)).convert('RGBA')
        a.putalpha(rounded_alpha(*a.size, 58))
        a.save(os.path.join(PRIVATE, 's4-phone.png'))
    print('ok')
