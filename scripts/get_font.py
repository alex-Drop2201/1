#!/usr/bin/env python3
"""Скачать шрифт с Google Fonts в fonts/ и пересобрать fonts/fonts.css.

Примеры:
  python3 scripts/get_font.py "Playfair Display" 400 700 900 --italic
  python3 scripts/get_font.py Unbounded 400 700 900
  python3 scripts/get_font.py            # только пересобрать fonts.css
"""
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
# С таким User-Agent Google Fonts отдаёт полные TTF (все алфавиты, включая кириллицу).
UA = {"User-Agent": "curl/8.0"}
FILE_RE = re.compile(r"^(?P<dir>.+)-(?P<weight>\d{3})(?P<italic>-italic)?\.(?P<ext>ttf|otf|woff2?)$")
FORMATS = {"ttf": "truetype", "otf": "opentype", "woff": "woff", "woff2": "woff2"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def download(family, weights, italic):
    weights = sorted(set(int(w) for w in weights)) or [400]
    if italic:
        axis = "ital,wght@" + ";".join(f"{i},{w}" for i in (0, 1) for w in weights)
    else:
        axis = "wght@" + ";".join(str(w) for w in weights)
    url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(family) + ":" + axis
    css = fetch(url).decode()
    slug = family.replace(" ", "-")
    target = FONTS / slug
    target.mkdir(parents=True, exist_ok=True)
    for block in re.findall(r"@font-face\s*{(.*?)}", css, re.S):
        style = re.search(r"font-style:\s*(\w+)", block).group(1)
        weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
        src = re.search(r"url\((.*?)\)", block).group(1)
        ext = src.rsplit(".", 1)[-1]
        name = f"{slug}-{weight}{'-italic' if style == 'italic' else ''}.{ext}"
        (target / name).write_bytes(fetch(src))
        print("  +", target.relative_to(ROOT) / name)


def build_css():
    rules = []
    for f in sorted(FONTS.glob("*/*")):
        m = FILE_RE.match(f.name)
        if not m or m["dir"] != f.parent.name:
            continue
        family = f.parent.name.replace("-", " ")
        rules.append(
            "@font-face { "
            f"font-family: '{family}'; "
            f"font-style: {'italic' if m['italic'] else 'normal'}; "
            f"font-weight: {m['weight']}; "
            "font-display: block; "
            f"src: url('{f.parent.name}/{f.name}') format('{FORMATS[m['ext']]}'); }}"
        )
    header = "/* Сгенерировано scripts/get_font.py — не редактировать вручную. */\n"
    (FONTS / "fonts.css").write_text(header + "\n".join(rules) + "\n")
    families = sorted({f.parent.name.replace("-", " ") for f in FONTS.glob("*/*") if FILE_RE.match(f.name)})
    print(f"fonts.css: {len(rules)} начертаний, семейства: {', '.join(families)}")


def main(argv):
    italic = "--italic" in argv
    args = [a for a in argv if a != "--italic"]
    if args:
        family, weights = args[0], args[1:]
        print(f"Скачиваю {family} {' '.join(weights) or '400'}{' +italic' if italic else ''}")
        download(family, weights, italic)
    build_css()


if __name__ == "__main__":
    main(sys.argv[1:])
