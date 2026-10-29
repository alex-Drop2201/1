"""Правки поверх готовой картинки автора: вырезать надпись или букву, стереть её с фона (бумага, градиент),
поставить в другое место — с тем же шрифтом, наклоном и фактурой, потому что это пиксели оригинала.

    import sys; sys.path.insert(0, '.claude/skills/poster-refine/scripts')
    from patch import Canvas
    c = Canvas('projects/<папка>/assets/drafts/story-2.webp')
    piece = c.cut((835, 832, 982, 883))          # вырезать «ОЧ СКОРО» (x0, y0, x1, y1) и стереть с бумаги
    c.paste(piece, dx=-13, dy=-16)                # поставить на 13 px левее и 16 px выше
    cols = c.glyphs((679, 1310, 961, 1360))       # границы букв слова — для перестановки и дублирования
    c.save('projects/<папка>/export/story-2.png')

Надпись — всё, что заметно темнее (ink='dark') или светлее (ink='light') своего фона. Фон под ней восстанавливается
по соседним пикселям (нормированная свёртка) с зерном той же силы; поэтому стирать можно на однотонной бумаге,
градиенте, размытом фото — не на резкой фотографии с деталями.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

LUMA = np.array([0.299, 0.587, 0.114], np.float32)


class Piece:
    """Вырезанный кусок: RGB без смешения с фоном, альфа и место в исходнике."""

    def __init__(self, rgb, alpha, x0, y0):
        self.rgb, self.alpha, self.x0, self.y0 = rgb, alpha, x0, y0

    def crop_cols(self, c0, c1):
        """Часть куска по столбцам (локальные координаты) — например, одна буква."""
        return Piece(self.rgb[:, c0:c1], self.alpha[:, c0:c1], self.x0 + c0, self.y0)


def fit_size(text, font_path, width, tracking=0.0):
    """Кегль, при котором text этим шрифтом займёт width px (для замены слова на исправленное той же ширины букв)."""
    from PIL import ImageFont
    f = ImageFont.truetype(font_path, 100)
    w = sum(f.getlength(ch) for ch in text) + tracking * 100 * (len(text) - 1)
    # ширина по краске: без боковых отступов первой и последней буквы
    l0 = f.getbbox(text[0])[0]
    r1 = f.getlength(text[-1]) - f.getbbox(text[-1])[2]
    return 100 * width / (w - l0 - r1)


def text_piece(text, font_path, size, color=(30, 30, 30), angle=0.0, tracking=0.0, soften=0.0):
    """Новая надпись подобранным шрифтом — как кусок для paste(): angle в градусах по часовой (как наклон строки
    с dy/dx = tan(angle)), tracking — разрядка в долях кегля. Ставится paste(piece, x=…, y=…)."""
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype(font_path, size)
    k = 4  # рисовать крупнее и уменьшать — ровный край
    fk = ImageFont.truetype(font_path, size * k)
    widths = [fk.getlength(ch) for ch in text]
    w = int(sum(widths) + tracking * size * k * (len(text) - 1)) + size * k
    h = int(size * k * 1.6)
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    x = size * k // 2
    for ch, cw in zip(text, widths):
        d.text((x, size * k * 0.2), ch, font=fk, fill=255)
        x += cw + tracking * size * k
    im = im.rotate(-angle, resample=Image.BICUBIC, expand=True)
    im = im.resize((max(im.width // k, 1), max(im.height // k, 1)), Image.LANCZOS)
    if soften:
        from PIL import ImageFilter
        im = im.filter(ImageFilter.GaussianBlur(soften))  # мягкий край, как у сжатой картинки автора
    a = np.asarray(im).astype(np.float32) / 255
    ys, xs = np.nonzero(a > 0.02)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    rgb = np.ones(a.shape + (3,), np.float32) * np.array(color, np.float32)
    del font
    return Piece(rgb, a, 0, 0)


def scale_piece(piece, k):
    """Увеличить/уменьшить кусок (например, выровнять кегль одной роли)."""
    h, w = piece.alpha.shape
    size = (max(round(w * k), 1), max(round(h * k), 1))
    rgb = np.stack([np.asarray(Image.fromarray(piece.rgb[..., c].astype(np.float32), 'F').resize(size, Image.LANCZOS))
                    for c in range(3)], -1)
    a = np.asarray(Image.fromarray(piece.alpha.astype(np.float32), 'F').resize(size, Image.LANCZOS))
    return Piece(np.clip(rgb, 0, 255), np.clip(a, 0, 1), piece.x0, piece.y0)


def join(pieces, gaps):
    """Склеить куски одной высоты по горизонтали: gaps[i] — промежуток после pieces[i] (для слова без буквы)."""
    h = max(p.alpha.shape[0] for p in pieces)
    w = sum(p.alpha.shape[1] for p in pieces) + sum(gaps[:len(pieces) - 1])
    rgb = np.zeros((h, w, 3), np.float32)
    a = np.zeros((h, w), np.float32)
    x = 0
    for i, p in enumerate(pieces):
        ph, pw = p.alpha.shape
        rgb[:ph, x:x + pw] = p.rgb
        a[:ph, x:x + pw] = np.maximum(a[:ph, x:x + pw], p.alpha)
        x += pw + (gaps[i] if i < len(gaps) else 0)
    return Piece(rgb, a, pieces[0].x0, pieces[0].y0)


class Canvas:
    def __init__(self, path, ink='dark'):
        self.img = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
        self.ink = ink
        self.rng = np.random.default_rng(5)

    # --- анализ -------------------------------------------------------------------------------------------
    def _bg_estimate(self, box, pad=24, contrast=22):
        """Фон под надписью: окрестность без самой надписи, сглаженная и продолженная внутрь. contrast — насколько
        надпись темнее/светлее фона; для чёрного текста на мятой бумаге 60, чтобы не цеплять складки и следы печати."""
        x0, y0, x1, y1 = box
        X0, Y0 = max(x0 - pad, 0), max(y0 - pad, 0)
        X1, Y1 = min(x1 + pad, self.img.shape[1]), min(y1 + pad, self.img.shape[0])
        reg = self.img[Y0:Y1, X0:X1]
        lum = reg @ LUMA
        # Фон без надписи: морфологическое закрытие (для тёмной краски) убирает штрихи уже окна целиком,
        # включая середину толстых букв; открытие — для светлой краски.
        size = (35, 35)
        ref = ndi.grey_closing(lum, size=size) if self.ink == 'dark' else ndi.grey_opening(lum, size=size)
        ref = ndi.gaussian_filter(ref, 3)
        text = (lum < ref - contrast) if self.ink == 'dark' else (lum > ref + contrast)
        text = ndi.binary_dilation(text, iterations=3)
        bg = self._fill(reg, text)
        return bg, text, (X0, Y0, X1, Y1)

    @staticmethod
    def _fill(reg, hole):
        known = ~hole
        out = reg.copy()
        for sigma in (3, 7, 16, 40):
            w = ndi.gaussian_filter(known.astype(np.float32), sigma)
            acc = np.stack([ndi.gaussian_filter(out[..., c] * known, sigma) for c in range(3)], -1)
            est = acc / np.maximum(w, 1e-6)[..., None]
            take = (~known) & (w > 0.03)
            out[take] = est[take]
            known = known | take
        return out

    def _grain(self, reg, mask):
        """Сила зерна вокруг — чтобы стёртое место не было глаже соседнего."""
        lum = reg @ LUMA
        hp = lum - ndi.gaussian_filter(lum, 2)
        # Устойчивая оценка (медиана модулей): края предметов рядом не должны завышать зерно.
        s = float(1.4826 * np.median(np.abs(hp[~mask]))) if (~mask).any() else 2.0
        return min(max(s, 0.3), 12.0)

    # --- правки ---------------------------------------------------------------------------------------------
    def cut(self, box, erase=True, contrast=22, slope=0.0, height=None):
        """Вырезать надпись из прямоугольника box и (по умолчанию) стереть её с картинки.
        Наклонная строка рядом с другими (пунктир под словом): slope = dy/dx строки, height — высота полосы;
        берётся только параллелограмм от верха левого края y0, а не весь прямоугольник."""
        bg, text, (X0, Y0, X1, Y1) = self._bg_estimate(box, contrast=contrast)
        x0, y0, x1, y1 = box
        reg = self.img[Y0:Y1, X0:X1]
        lum, bgl = reg @ LUMA, bg @ LUMA
        if self.ink == 'dark':
            inkl = np.percentile(lum[text], 3) if text.any() else 0
            alpha = np.clip((bgl - lum) / np.maximum(bgl - inkl, 8), 0, 1)
        else:
            inkl = np.percentile(lum[text], 97) if text.any() else 255
            alpha = np.clip((lum - bgl) / np.maximum(inkl - bgl, 8), 0, 1)
        inside = np.zeros_like(text)
        if height is None:
            inside[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = True
        else:
            yy, xx = np.mgrid[Y0:Y1, X0:X1]
            top = y0 + slope * (xx - x0)
            inside = (xx >= x0) & (xx < x1) & (yy >= top) & (yy < top + height)
        # Мягкий край букв светлее порога — маску расширить на 2 px, иначе при стирании останется контур.
        text = ndi.binary_dilation(text, iterations=2)
        alpha = np.where(text & inside, alpha, 0)
        a3 = np.maximum(alpha, 1e-3)[..., None]
        rgb = np.clip((reg - (1 - alpha[..., None]) * bg) / a3, 0, 255)  # цвет краски без примеси фона
        sl = (slice(y0 - Y0, y1 - Y0), slice(x0 - X0, x1 - X0))
        piece = Piece(rgb[sl].copy(), alpha[sl].copy(), x0, y0)
        if erase:
            m = text & inside
            g = self._grain(reg, text)
            noise = self.rng.normal(0, g, m.shape)[..., None]
            reg[m] = np.clip(bg + noise, 0, 255)[m]
        return piece

    def paste(self, piece, dx=0, dy=0, x=None, y=None):
        """Поставить кусок: сдвиг от исходного места (dx, dy) или в точку (x, y) — левый верхний угол."""
        X = int(round(piece.x0 + dx if x is None else x))
        Y = int(round(piece.y0 + dy if y is None else y))
        h, w = piece.alpha.shape
        H, W = self.img.shape[:2]
        xs0, ys0, xs1, ys1 = max(X, 0), max(Y, 0), min(X + w, W), min(Y + h, H)
        if xs1 <= xs0 or ys1 <= ys0:
            return
        a = piece.alpha[ys0 - Y:ys1 - Y, xs0 - X:xs1 - X][..., None]
        c = piece.rgb[ys0 - Y:ys1 - Y, xs0 - X:xs1 - X]
        dst = self.img[ys0:ys1, xs0:xs1]
        self.img[ys0:ys1, xs0:xs1] = dst * (1 - a) + c * a

    @staticmethod
    def _coons(reg, x0, y0, x1, y1, band=6):
        """Заливка прямоугольника по четырём краям (Coons-патч): совпадает с фоном сверху, снизу, слева и справа,
        внутри — плавный переход. Для больших областей на градиенте, где сглаживание «из окрестности» мутнеет."""
        sm = lambda v: ndi.gaussian_filter1d(v, 4, axis=0)
        T = sm(np.median(reg[y0 - band:y0, x0:x1], 0))
        B = sm(np.median(reg[y1:y1 + band, x0:x1], 0))
        L = sm(np.median(reg[y0:y1, x0 - band:x0], 1))
        R = sm(np.median(reg[y0:y1, x1:x1 + band], 1))
        h, w = y1 - y0, x1 - x0
        u = np.linspace(0, 1, w)[None, :, None]
        v = np.linspace(0, 1, h)[:, None, None]
        c00, c10, c01, c11 = T[0], T[-1], B[0], B[-1]
        F = (1 - u) * L[:, None] + u * R[:, None] + (1 - v) * T[None] + v * B[None] \
            - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11)
        return F

    def cut_object(self, box, thr=30, pad=12, min_area=150):
        """Вырезать цветной предмет целиком (мазок с надписью, стикер, звёздочку) и стереть его: фон под ним —
        Coons-заливка по краям рамки (рамка должна лежать на чистом фоне), предмет — всё, что заметно отличается
        от этого фона по цвету (мелкие пятна меньше min_area отбрасываются)."""
        x0, y0, x1, y1 = box
        X0, Y0 = max(x0 - pad, 0), max(y0 - pad, 0)
        X1, Y1 = min(x1 + pad, self.img.shape[1]), min(y1 + pad, self.img.shape[0])
        reg = self.img[Y0:Y1, X0:X1]
        bx0, by0, bx1, by1 = x0 - X0, y0 - Y0, x1 - X0, y1 - Y0
        fillv = self._coons(reg, bx0, by0, bx1, by1)
        inner = reg[by0:by1, bx0:bx1]
        dist = np.sqrt(((ndi.gaussian_filter(inner, (1, 1, 0)) - fillv) ** 2).sum(-1))
        m = dist > thr
        lab, n = ndi.label(ndi.binary_closing(m, iterations=2))
        sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
        m = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= min_area])
        m = ndi.binary_fill_holes(m)
        m = ndi.binary_dilation(m, iterations=2)
        alpha = ndi.gaussian_filter(m.astype(np.float32), 0.8)
        piece = Piece(inner.copy(), alpha, x0, y0)
        ring = np.ones(reg.shape[:2], bool)
        ring[by0:by1, bx0:bx1] = False                      # зерно мерить только по фону вокруг рамки
        g = self._grain(reg, ~ring)
        noise = self.rng.normal(0, g, fillv.shape[:2])[..., None]
        reg[by0:by1, bx0:bx1] = np.clip(fillv + noise, 0, 255)
        return piece

    def erase_area(self, box):
        """Стереть всё в прямоугольнике — заменить Coons-заливкой по его краям (рамка на чистом фоне)."""
        self.cut_object(box, thr=1e9)

    def erase(self, box, contrast=22):
        """Только стереть надпись в box."""
        self.cut(box, erase=True, contrast=contrast)

    def glyphs(self, box, gap=1):
        """Границы букв в надписи: столбцы без краски разделяют буквы. Возвращает [(x0, x1), …] в координатах картинки."""
        piece = self.cut(box, erase=False)
        col = piece.alpha.max(0) > 0.25
        out, start = [], None
        for i, on in enumerate(col):
            if on and start is None:
                start = i
            elif not on and start is not None:
                out.append((box[0] + start, box[0] + i))
                start = None
        if start is not None:
            out.append((box[0] + start, box[0] + len(col)))
        merged = []
        for g in out:  # слить «щели» внутри буквы уже gap
            if merged and g[0] - merged[-1][1] <= gap:
                merged[-1] = (merged[-1][0], g[1])
            else:
                merged.append(g)
        return merged

    def insert_rows(self, y, n):
        """Растянуть картинку по высоте: полоса [y−n, y) повторяется ещё раз (всё ниже сдвигается на n вниз,
        низ холста срезается). Полоса — без надписей и деталей: середина карточки, фон, вертикальные края.
        Повторяется полоса, а не одна строка, — иначе зерно фона вытянется в вертикальные штрихи."""
        H = self.img.shape[0]
        band = self.img[y - n:y].copy()
        self.img = np.concatenate([self.img[:y], band, self.img[y:]], 0)[:H]

    def save(self, path):
        Image.fromarray(np.clip(self.img, 0, 255).astype(np.uint8)).save(path)
