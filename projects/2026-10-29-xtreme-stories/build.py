"""Сторис XTREME: правки поверх черновиков продакшена (скил poster-refine) — без перерисовки дизайна.

    python3 -I projects/2026-10-29-xtreme-stories/build.py      → export/story-2.png …

Каждая правка — отдельная строка с координатами из замеров черновика (1080×1920). Черновики не меняются.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../..'))
sys.path.insert(0, os.path.join(ROOT, '.claude/skills/poster-refine/scripts'))
from patch import Canvas, text_piece, fit_size, scale_piece, join  # noqa: E402

FONTS = os.path.join(ROOT, 'fonts')
DRAFTS = os.path.join(HERE, 'assets/drafts')
OUT = os.path.join(HERE, 'export')

# Наклон чека во 2-й сторис: правый край бумаги x = 1081.9 − 0.0659·y → строки наклонены на 3.8° (dy/dx = 0.066).
K2 = 0.066
ANGLE2 = 3.78


def story1():
    """«Будь светом этой ночью». Проблемы черновика и правки:
    1. Дата «31.10» начинается левее заголовка (130 px против 159), время «18:00» кончается левее его правого края
       (901 против 916). → Дата и время встали точно по краям заголовка: дата слева сверху, время справа снизу —
       диагональ автора сохранена.
    2. «Универмаг 3й-этаж» висит на 35 px ниже времени и с отступом 192 px — ни к чему не привязан. → Встал
       от левого края заголовка на одну линию со временем.
    3. «3й-этаж» → «3-й этаж» — перестановкой букв автора.
    Не тронуто: фон, заголовок, шрифт, кегли, цвет."""
    c = Canvas(os.path.join(DRAFTS, 'story-1.webp'))
    date = c.cut((126, 738, 254, 792), contrast=40)
    time = c.cut((740, 1138, 906, 1198), contrast=40)
    place = {name: c.cut(box, contrast=40) for name, box in {
        'univ': (188, 1186, 468, 1232), 'three': (479, 1186, 510, 1232), 'y': (510, 1182, 538, 1232),
        'dash': (538, 1186, 557, 1232), 'etazh': (557, 1186, 698, 1232)}.items()}
    ink = {'univ': (192, 464), 'three': (482, 508), 'y': (513, 535), 'dash': (540, 554), 'etazh': (560, 694)}
    left, right = 159, 916                      # края заголовка «Будь светом»
    c.paste(date, dx=left - 130)
    base_dy_time, base_dy_place = 7, -28        # общая нижняя линия времени и места — 1200 px
    c.paste(time, dx=right - 901, dy=base_dy_time)
    x = left                                    # «Универмаг 3-й этаж», межбуквенные и словесные отступы автора
    for name, gap in [('univ', 18), ('three', 5), ('dash', 5), ('y', 18), ('etazh', 0)]:
        a, b = ink[name]
        piece = place[name]
        c.paste(piece, x=x - (a - piece.x0), y=piece.y0 + base_dy_place)
        x += (b - a) + gap
    c.save(os.path.join(OUT, 'story-1.png'))


def story2():
    """Чек. Проблемы черновика и правки:
    1. «Цены» справа стоят каждая на своём крае (932 / 982 / 999 / 929 / 946 px) и сползают ниже своих пунктов
       (у 2-го и 3-го — на 16–23 px). → Вырезаны и переставлены: правый край — одна линия параллельно краю чека
       (отступ 40 px, как у пунктира), низ — на линии пояснения своего пункта. «Терпение…» длинное и стоит отдельной
       строкой, как у автора, — только выровнено по общему краю.
    2. Опечатки: «ИТОГОО» → «ИТОГО», «БЕСЛПАТНО» → «БЕСПЛАТНО», «Востань» → «Восстань» — набрано тем же шрифтом
       автора (Montserrat, у пояснений — Montserrat Alternates), тем же кеглем и наклоном.
    3. «(ЕЩЕ ПРИЗЫ)» прописными среди строчных пояснений → «(ещё призы)».
    Не тронуто: наклон, бумага с фактурой и следами печати, скотч, шрифты, номера, штрихкод, порядок и тексты."""
    c = Canvas(os.path.join(DRAFTS, 'story-2.webp'))
    edge = lambda y: 1081.9 - 0.0659 * y - 40  # общий правый край «цен»

    # 1. «Цены»: (рамка, низ-правый угол сейчас, куда — низ на линии пояснения: (низ пояснения, его правый x)).
    values = [
        ((831, 688, 936, 748), (932, 744), (717, 403)),     # 18:30
        ((830, 828, 986, 887), (982, 883), (840, 473)),     # ОЧ СКОРО
        ((619, 976, 1003, 1049), (999, 1045), None),        # ТЕРПЕНИЕ БРАТЬЯ И СЕСТРЫ — своя строка
        ((830, 1108, 933, 1170), (929, 1166), (1127, 394)),  # ВАЙБ
        ((777, 1219, 950, 1277), (946, 1273), (1236, 292)),  # ОДИН РИТМ
    ]
    pieces = [(c.cut(box, contrast=60), br, note) for box, br, note in values]
    for piece, (x, y), note in pieces:
        if note is None:                     # только по краю, вдоль наклона строки
            dx = edge(y) - x
            dy = K2 * dx
        else:                                # низ на линии пояснения: решить вместе с краем (край зависит от y)
            nb, nx = note
            yb = y
            for _ in range(4):
                xr = edge(yb)
                yb = nb + K2 * (xr - nx)
            dx, dy = edge(yb) - x, yb - y
        c.paste(piece, dx=dx, dy=dy)

    # 2–3. Слова с опечатками: стереть полосу слова (без соседнего пунктира) и набрать заново тем же шрифтом.
    def retype(box, top_h, old, new, font, tracking=0.0, size=None, scale=1.0, color=(24, 24, 24)):
        x0, y0, x1, y1 = box
        c.cut(box, contrast=60, slope=K2, height=top_h)
        f = os.path.join(FONTS, font)
        if size is None:
            size = fit_size(old, f, (x1 - x0) - 3, tracking) * scale  # scale — поправка на кегль по высоте букв
        piece = text_piece(new, f, round(size), color=color, angle=ANGLE2, tracking=tracking, soften=0.45)
        c.paste(piece, x=x0, y=y0)
        return size

    retype((117, 1277, 391, 1338), 46, 'ИТОГОО:', 'ИТОГО:', 'Montserrat/Montserrat-900.ttf', scale=1.07)
    retype((679, 1310, 962, 1361), 37, 'БЕСЛПАТНО', 'БЕСПЛАТНО', 'Montserrat/Montserrat-400.ttf')
    note_size = retype((200, 796, 474, 841), 32, '(Востань и воссияй)', '(Восстань и воссияй)',
                       'Montserrat-Alternates/Montserrat-Alternates-400.ttf', scale=1.1)
    retype((179, 1087, 395, 1128), 32, '(ЕЩЕ ПРИЗЫ)', '(ещё призы)',
           'Montserrat-Alternates/Montserrat-Alternates-400.ttf', size=note_size)

    c.save(os.path.join(OUT, 'story-2.png'))


def story3():
    """YOUTH CODE. Проблемы черновика и правки:
    1. «YOUTH CODE» сдвинут на 28 px влево от середины карточки. → По центру.
    2. Первое правило: строки начинаются в разных местах (225 и 138 px), пробел перед двоеточием
       («ЛЮБИМОГО :»). → Пункт-квадрат на оси точек списка, текст от левого края слов списка (173 px), двоеточие
       без пробела.
    3. Второе правило набрано мельче первого (прописные 20 px против 25) и упирается в края карточки
       (100–980 px при карточке 99–979). → Тот же кегль, что у первого правила, тот же левый край и пункт,
       строки переносятся по словам в поле карточки; цвета слов (чёрный / фиолетовый) — авторские.
    4. «ПРИЙДЕШЬ» → «ПРИДЕШЬ» — убрана лишняя буква.
    5. Чтобы второе правило не прижалось к фиолетовой подписи, карточка вытянута вниз на столько же, на сколько
       правило стало выше; подпись, зажим, задняя карточка и фон — авторские.
    Не тронуто: тексты (кроме опечатки), шрифты, цвета, список, подпись, зажим, карточки."""
    c = Canvas(os.path.join(DRAFTS, 'story-3.webp'))
    TEXT_X, BULLET_C, CARD_R = 173, 151, 979

    # --- 1. Сначала всё вырезать (и стереть), потом растягивать карточку, потом ставить — иначе растяжка
    #        повторит уже поставленный текст.
    head = c.cut((218, 514, 804, 588), contrast=60)
    r1 = [((660, 712), [(225, 240), (258, 315), (334, 518), (536, 701)]),
          ((722, 757), [(138, 162), (181, 384), (402, 567), (586, 822)])]
    r1p = [[c.cut((a - 2, y0, b + 2, y1), contrast=60) for a, b in ws] for (y0, y1), ws in r1]
    colon = c.cut((834, 722, 850, 757), contrast=60)            # «:» после пробела — придвинуть к слову
    r2 = [((970, 1008), 983, [(128, 139), (153, 238), (252, 295), (308, 489), (502, 542), (555, 680), (693, 867), (881, 899), (913, 952)]),
          ((1012, 1043), 1019, [(107, 217), (231, 291), (305, 408), (422, 554), (568, 606), (619, 662), (676, 872), (886, 973)]),
          ((1043, 1080), 1054, [(218, 321), (335, 487), (501, 582), (596, 614), (628, 710), (724, 862)])]
    words = [(c.cut((a - 2, y0, b + 2, y1), contrast=60), cap - y0) for (y0, y1), cap, ws in r2 for a, b in ws]

    # «ПРИЙДЕШЬ»: убрать четвёртую букву (Й).
    p, off = words[3]
    cols = np.nonzero(p.alpha.max(0) > 0.3)[0]
    starts = [cols[0]] + list(cols[1:][np.diff(cols) > 1])
    ends = list(cols[:-1][np.diff(cols) > 1] + 1) + [cols[-1] + 1]
    letters = [p.crop_cols(s0, e0) for s0, e0 in zip(starts, ends)]
    words[3] = (join(letters[:3] + letters[4:], [starts[1] - ends[0]] * 7), off)
    bullet2, boff = words[0]
    words = words[1:]
    # Дочистить места, откуда вынуты строки (карточка там ровно белая): следы мягкого края букв.
    for box in [(214, 510, 808, 592), (120, 655, 860, 760), (97, 962, 974, 1084)]:
        c.erase(box, contrast=12)

    # --- 2. Раскладка второго правила: кегль как у первого (прописные 25 px вместо 20), если влезает в 4 строки
    #        без одинокого слова в конце; иначе чуть меньше.
    cap_top, pitch = 983, 47

    def layout(k):
        x, line, pos = TEXT_X, 0, []
        for p, off in words:
            w = p.alpha.shape[1] * k - 4 * k
            if x + w > CARD_R - 40 and x > TEXT_X:
                line, x = line + 1, TEXT_X
            pos.append((x, line))
            x += w + round(13 * k)
        lone = sum(1 for _, l in pos if l == line) == 1
        return pos, line, lone

    for K in (1.25, 1.2, 1.15, 1.1):
        pos, last_line, lone = layout(K)
        if last_line <= 3 and not lone:
            break
    bottom = cap_top + last_line * pitch + round(20 * K)
    grow = max(0, bottom + 110 - 1207)                           # подпись — на прежнем расстоянии от правила
    if grow:
        c.insert_rows(1190, grow)

    # --- 3. Поставить.
    c.paste(head, dx=539 - 511)                                  # «YOUTH CODE» по центру карточки (99–979)
    bullet, *w1 = r1p[0]
    c.paste(bullet, x=BULLET_C - bullet.alpha.shape[1] / 2, y=bullet.y0)
    for row in (w1, r1p[1]):
        x = TEXT_X
        for p in row:
            c.paste(p, x=x - 2, y=p.y0)
            x += p.alpha.shape[1] - 4 + 18
    c.paste(colon, x=x - 18 + 3, y=colon.y0)
    bp = scale_piece(bullet2, K)
    c.paste(bp, x=BULLET_C - bp.alpha.shape[1] / 2, y=cap_top - boff * K)
    for (p, off), (x, line) in zip(words, pos):
        c.paste(scale_piece(p, K), x=x - 2 * K, y=cap_top + line * pitch - off * K)
    c.save(os.path.join(OUT, 'story-3.png'))
    return K, last_line + 1, grow


def story4():
    """Розыгрыш. Проблемы черновика и правки:
    1. «РОЗЫГРЫШ» стоит на 93–183 px — в верхних 250 px сторис его закрывают полоски и аватар. → Верхний блок
       (РОЗЫГРЫШ, мазок «OVEC» со звёздочкой, «А ВОТ И ПОДАРОЧЕК») целиком опущен на 170 px — до телефона и
       кнопок места хватает, расстояния внутри блока авторские.
    2. Текст в трёх кнопках-условиях разного кегля (прописные 22 / 17 / 16 px), в третьей — двойной пробел и поля
       3 px. → Всё одним кеглем 20 px; вторая — в две строки, третья — в три, по словам, по центру кнопок.
    Не тронуто: тексты, шрифт, мазок, телефон со скриншотом, кнопки, звёздочки, фото, фон.
    Исходник с фото людей — private/ (в репозиторий не попадает)."""
    c = Canvas(os.path.join(HERE, 'private/story-4.webp'))
    DY = 170
    title = c.cut((120, 86, 1034, 190), contrast=60)  # чёрные пиксельные буквы — по краске, без фона
    c.erase_area((112, 80, 1040, 196))               # место под ними — заливкой по краям, без следов
    stroke = c.cut_object((84, 228, 734, 442))       # мазок с OVEC и звёздочка — цветной предмет целиком
    sub = c.cut((196, 444, 884, 506), contrast=60)
    c.erase_area((190, 440, 890, 510))

    def take(frame, cap, ws):
        y0, y1 = frame
        return [(c.cut((a - 2, y0, b + 2, y1), contrast=60), cap - y0) for a, b in ws]

    p1 = take((776, 814), 782, [(477, 767), (785, 832), (850, 1003)])
    p2 = take((920, 962), 935, [(471, 587), (600, 617), (630, 793), (806, 843), (856, 872), (886, 999)])
    p3 = take((1058, 1088), 1066, [(495, 655), (668, 802), (824, 858), (871, 962)]) + \
        take((1084, 1118), 1097, [(454, 570), (582, 692), (705, 721), (733, 881), (894, 1004)])

    for box in [(452, 770, 1030, 822), (452, 916, 1030, 966), (444, 1056, 1030, 1122)]:
        c.erase(box, contrast=12)                    # дочистить мягкие края вынутых слов (кнопки белые)

    c.paste(title, dy=DY)
    c.paste(stroke, dy=DY)
    c.paste(sub, dy=DY)

    # Прописные во всех кнопках 20 px (было 22 / 17 / 16): 2-я — в две строки, 3-я — в три, по центру кнопок.
    CX, CAP, SPACE, LEAD = 741, 20, 15, 17   # зазор строк — с запасом под хвосты Д, З и краткую Й

    def set_lines(lines, k, cy):
        h = CAP * len(lines) + LEAD * (len(lines) - 1)
        top = cy - h / 2
        for i, line in enumerate(lines):
            parts = [(scale_piece(p, k), off) for p, off in line]
            w = sum(sp.alpha.shape[1] - 4 * k for sp, _ in parts) + SPACE * (len(parts) - 1)
            x = CX - w / 2
            for sp, off in parts:
                c.paste(sp, x=x - 2 * k, y=top + i * (CAP + LEAD) - off * k)
                x += sp.alpha.shape[1] - 4 * k + SPACE

    set_lines([p1], 20 / 22, (732 + 847) / 2)
    set_lines([p2[0:3], p2[3:6]], 20 / 17, (883 + 997) / 2)
    set_lines([p3[0:2], p3[2:6], p3[6:9]], 20 / 16, (1032 + 1148) / 2)
    c.save(os.path.join(HERE, 'private/story-4.png'))   # с фото людей — не в export/ (export коммитится)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    story1()
    story2()
    print('story3', story3())
    if os.path.exists(os.path.join(HERE, 'private/story-4.webp')):
        story4()
    print('ok')
