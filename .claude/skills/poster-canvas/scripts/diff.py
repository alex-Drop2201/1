#!/usr/bin/env python3
"""Что пользователь поменял на холсте: сравнить артборд с холста с отправленной копией.

    python3 -I .claude/skills/poster-canvas/scripts/diff.py <отправленный.dc.html> <скачанный с холста.dc.html>

Сравнивает элементы с меткой data-t (текст) и все элементы по порядку (inline style, src, class): печатает
изменённые тексты, сдвиги и стили, удалённые и добавленные элементы. Их потом переносят в исходный HTML макета.
"""
import re
import sys
from html.parser import HTMLParser


class Collect(HTMLParser):
    """Элементы внутри <main>: путь, атрибуты и собственный текст (с <br> как переводом строки)."""

    VOID = {'img', 'br', 'hr', 'input', 'meta', 'link'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.items, self.inside = [], [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'main':
            self.inside = True
        if not self.inside:
            return
        if tag == 'br' and self.stack:
            self.stack[-1]['text'] += '\n'
            return
        item = {'tag': tag, 'attrs': a, 'text': '', 'path': '/'.join(s['tag'] for s in self.stack) + '/' + tag}
        self.items.append(item)
        if tag not in self.VOID:
            self.stack.append(item)

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag == 'main':
            self.inside = False
        while self.stack:
            if self.stack.pop()['tag'] == tag:
                break

    def handle_data(self, data):
        if self.inside and self.stack:
            self.stack[-1]['text'] += data


def load(path):
    c = Collect()
    c.feed(open(path, encoding='utf-8').read())
    return c.items


def norm(t):
    return re.sub(r'[ \t ]+', ' ', t).strip()


def main():
    before, after = load(sys.argv[1]), load(sys.argv[2])
    out = []
    tb = {i['attrs'].get('data-t'): i for i in before if 'data-t' in i['attrs']}
    ta = {i['attrs'].get('data-t'): i for i in after if 'data-t' in i['attrs']}
    for k, b in tb.items():
        a = ta.get(k)
        if a is None:
            out.append(f'удалён текст [{k}]: «{norm(b["text"])}»')
        elif norm(a['text']) != norm(b['text']):
            out.append(f'текст [{k}]: «{norm(b["text"])}» → «{norm(a["text"])}»')
    for k, a in ta.items():
        if k not in tb:
            out.append(f'новый текст [{k}]: «{norm(a["text"])}»')
    # Атрибуты по порядку элементов (сдвиги, размеры, цвета — правки в панели свойств).
    for i, (b, a) in enumerate(zip(before, after)):
        if b['tag'] != a['tag']:
            out.append(f'структура разошлась с элемента №{i} ({b["path"]} → {a["path"]}) — дальше сравнить вручную')
            break
        label = f'[{b["attrs"].get("data-t")}] ' if 'data-t' in b['attrs'] else ''
        label += f'{b["tag"]}.{b["attrs"].get("class", "").replace(" ", ".")}'.rstrip('.')
        for attr in sorted(set(b['attrs']) | set(a['attrs'])):
            if attr == 'data-t':
                continue
            vb, va = b['attrs'].get(attr), a['attrs'].get(attr)
            if vb != va:
                out.append(f'{label}: {attr}: {vb!r} → {va!r}')
    if len(after) != len(before):
        out.append(f'элементов было {len(before)}, стало {len(after)}')
    print('\n'.join(out) if out else 'изменений нет')


if __name__ == '__main__':
    main()
