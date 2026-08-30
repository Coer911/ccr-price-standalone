#!/usr/bin/env python3
"""
Сборка index.html из src/price-base.html.

Базовая вёрстка (src/price-base.html) руками под корзину не правится.
Скрипт:
  1) размечает покупаемые ценовые ячейки data-атрибутами;
  2) ставит у каждой позиции кнопку + (она же становится счётчиком −N+);
  3) вшивает src/cart.css, src/cart.html и src/cart.js;
  4) выгружает src/products.json — машиночитаемый список позиций.

Флаг --no-cart собирает страницу без корзины и без разметки.
Результат обязан быть байт в байт равен исходному index.html —
этим проверяется, что перенос не тронул визуал.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
BASE = SRC / "price-base.html"
OUT = ROOT / "index.html"

TEA_SLIDES = {"08", "09", "10"}
COFFEE_WEIGHT_SLIDES = {"04", "05"}          # кофе на вес — формирует ступень опта
ESPRESSO_CAPS = ("1–19 кг", "20–49 кг", "от 50 кг")

PCELL = (r'<div class="pcell(?: [^"]*)?"><div class="pcell__cap">.*?</div>'
         r'<div class="pcell__opt">.*?</div></div>')


# ── вспомогательное ───────────────────────────────────────────────────────────

def to_num(price_html: str) -> int:
    """'2 020 ₽' -> 2020"""
    digits = re.sub(r"[^0-9]", "", price_html)
    return int(digits) if digits else 0


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    out = []
    for ch in text:
        if ch in table:
            out.append(table[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-")


def cap_to_kg(cap: str) -> float:
    """Вес одной покупки в кг. Считается только для весового кофе."""
    cap = cap.strip()
    m = re.match(r"^(\d+)\s*г$", cap)
    if m:
        return int(m.group(1)) / 1000
    m = re.match(r"^(\d+)\s*кг$", cap)
    if m:
        return float(m.group(1))
    return 0.0


def section_map(html: str):
    spans = []
    marks = [(m.start(), m.group(1)) for m in re.finditer(
        r'<section class="card[^"]*">\s*(?:<span class="card__no">(\d+)</span>)?', html)]
    for i, (pos, no) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        spans.append((pos, end, no or "01"))
    return spans


def slide_of(spans, pos: int) -> str:
    for start, end, no in spans:
        if start <= pos < end:
            return no
    return "01"


def anchors(base, pattern):
    """[(начало, конец, текст)] — подписи, к которым привязываются цены."""
    return [(m.start(), m.end(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
            for m in re.finditer(pattern, base, re.S)]


def nearest(anchor_list, pos, default=None):
    best = default
    for a in anchor_list:
        if a[0] < pos:
            best = a
        else:
            break
    return best


def ctl(sku: str, accent: str, mod: str = "") -> str:
    """Кнопка + у позиции. При количестве > 0 разворачивается в −N+."""
    cls = "buyctl" + (" buyctl--tea" if accent == "tea" else "") + (f" {mod}" if mod else "")
    return (f'<div class="{cls}" data-ctl="{sku}">'
            f'<button class="buyctl__b buyctl__minus" type="button" tabindex="-1"'
            f' aria-label="Убрать одну единицу">−</button>'
            f'<span class="buyctl__n">0</span>'
            f'<button class="buyctl__b buyctl__plus" type="button"'
            f' aria-label="Добавить в заказ">+</button></div>')


def cell_attrs(sku, name, unit, price, kg, accent, extra=""):
    return (f' is-buy" role="button" tabindex="0" data-sku="{sku}" data-name="{name}"'
            f' data-unit="{unit}" data-price="{price}" data-kg="{kg:g}"'
            f' data-accent="{accent}"{extra}')


# ── сборка ────────────────────────────────────────────────────────────────────

def build_html(base: str, with_cart: bool):
    if not with_cart:
        return base, []

    spans = section_map(base)
    products = []
    seen = {}
    replacements = []            # (начало, конец, новый текст) — по base
    name_skus = {}               # (начало, конец) названия -> [sku]
    name_wrap = {}               # (начало, конец) -> (префикс, суффикс) для дрипа
    name_accent = {}             # (начало, конец) -> акцент подчёркивания

    def bind(anc, sku, accent):
        """Привязать название к позиции — по нему будет идти подчёркивание."""
        if not anc:
            return
        key = (anc[0], anc[1])
        name_skus.setdefault(key, []).append(sku)
        name_accent[key] = accent

    def uniq(b):
        seen[b] = seen.get(b, 0) + 1
        return b if seen[b] == 1 else f"{b}-{seen[b]}"

    item_names = anchors(base, r'<div class="item__name">(.*?)</div>')
    tea_names = anchors(base, r'<div class="tea-row__name">(.*?)</div>')
    drip_names = sorted(
        anchors(base, r'<span class="variant__name">(.*?)</span>')
        + anchors(base, r'<div class="box__kind">(.*?)</div>'))
    single_names = anchors(base, r'<span class="single__name">(.*?)</span>')
    box_caps = [(m.start(), m.end(), f"{m.group(1)} {m.group(2)}") for m in re.finditer(
        r'<span class="box__num">(.*?)</span><span class="box__unit">(.*?)</span>', base)]
    tea_cols = [(m.start(), m.end(), re.findall(r"<span>(.*?)</span>", m.group(1)))
                for m in re.finditer(r'<div class="tea-cat__cols">(.*?)</div>', base, re.S)]

    # ── 1. блоки цен .prices: фильтр, эспрессо, матча ─────────────────────────
    # у одного блока есть инлайновый style — учитываем произвольные атрибуты
    for cont in re.finditer(r'<div class="prices[^"]*"[^>]*>(?:\s*' + PCELL + r')+\s*</div>',
                            base, re.S):
        block = cont.group(0)
        no = slide_of(spans, cont.start())
        anc = nearest(item_names, cont.start())
        pname = anc[2] if anc else ""
        accent = "tea" if no in TEA_SLIDES else "coffee"

        cells = list(re.finditer(
            r'<div class="pcell((?: [^"]*)?)"><div class="pcell__cap">(.*?)</div>'
            r'<div class="pcell__opt">(.*?)</div></div>', block, re.S))
        caps = tuple(c.group(2).strip() for c in cells)

        # эспрессо: одна позиция, три ступени цены, один общий счётчик под блоком
        if caps == ESPRESSO_CAPS:
            sku = uniq(slug(pname))
            prices = [to_num(c.group(3)) for c in cells]
            products.append({"sku": sku, "name": pname, "unit": "кг", "price": prices[0],
                             "tiers": prices, "kg": 1.0, "group": "espresso",
                             "accent": "coffee", "slide": no})
            new = block
            for ci in range(len(cells) - 1, -1, -1):
                c = cells[ci]
                rep = ('<div class="pcell' + c.group(1)
                       + cell_attrs(sku, pname, "кг", prices[0], 1.0, "coffee",
                                    f' data-tiers="{",".join(map(str, prices))}"'
                                    f' data-tier="{ci}"')
                       + f'><div class="pcell__cap">{c.group(2)}</div>'
                       + f'<div class="pcell__opt">{c.group(3)}</div></div>')
                new = new[:c.start()] + rep + new[c.end():]
            bind(anc, sku, "coffee")
            new += ctl(sku, "coffee", "buyctl--wide")
            replacements.append((cont.start(), cont.end(), new))
            continue

        # остальное: каждая ячейка — своя позиция, кнопка + внутри ячейки
        new = block
        for ci in range(len(cells) - 1, -1, -1):
            c = cells[ci]
            cap = c.group(2).strip()
            price = to_num(c.group(3))
            if not price:
                continue
            kg = cap_to_kg(cap) if no in COFFEE_WEIGHT_SLIDES else 0.0
            sku = uniq(f"{slug(pname)}-{slug(cap)}")
            products.append({"sku": sku, "name": pname, "unit": cap, "price": price,
                             "kg": kg, "group": "coffee" if accent == "coffee" else "tea",
                             "accent": accent, "slide": no})
            bind(anc, sku, accent)
            rep = ('<div class="pcell' + c.group(1)
                   + cell_attrs(sku, pname, cap, price, kg, accent)
                   + f'><div class="pcell__cap">{c.group(2)}</div>'
                   + f'<div class="pcell__opt">{c.group(3)}</div>'
                   + ctl(sku, accent) + '</div>')
            new = new[:c.start()] + rep + new[c.end():]
        replacements.append((cont.start(), cont.end(), new))

    # ── 2. дрип в коробочках: + рядом с названием ─────────────────────────────
    for m in re.finditer(r'<span class="pp"><span class="pp__lbl">опт</span>'
                         r'<span class="pp__opt">(.*?)</span></span>', base, re.S):
        anc = nearest(drip_names, m.start())
        cap_anc = nearest(box_caps, m.start())
        nm = anc[2] if anc else ""
        cap = cap_anc[2] if cap_anc else "шт"
        price = to_num(m.group(1))
        if not price:
            continue
        sku = uniq(f"drip-{slug(nm)}-{slug(cap)}")
        products.append({"sku": sku, "name": nm, "unit": cap, "price": price, "kg": 0.0,
                         "group": "drip", "accent": "coffee", "slide": "06"})
        replacements.append((m.start(), m.end(),
            '<span class="pp' + cell_attrs(sku, nm, cap, price, 0.0, "coffee")
            + '><span class="pp__lbl">опт</span>'
            + f'<span class="pp__opt">{m.group(1)}</span></span>'))
        bind(anc, sku, "coffee")
        if anc:
            tag = base[anc[0]:anc[1]]
            if tag.startswith('<span class="variant__name"'):
                # имя и кнопку кладём в колонку, иначе строка не помещается по ширине
                name_wrap[(anc[0], anc[1])] = (
                    '<span class="variant__head">',
                    ctl(sku, "coffee", "buyctl--under") + '</span>')
            else:
                # коробка «24 шт»: название сверху, под ним подпись, кнопка после неё
                fill = re.compile(r'\s*<div class="box__fill">.*?</div>', re.S).match(base, anc[1])
                pos = fill.end() if fill else anc[1]
                replacements.append((pos, pos, ctl(sku, "coffee", "buyctl--under")))

    # ── 3. дрип штучный: + рядом с названием ──────────────────────────────────
    for m in re.finditer(r'<span class="spp"><span class="spp__lbl">опт</span>'
                         r'<span class="single__opt">(.*?)</span></span>', base, re.S):
        anc = nearest(single_names, m.start())
        nm = anc[2] if anc else ""
        price = to_num(m.group(1))
        if not price:
            continue
        sku = uniq(f"drip-sht-{slug(nm)}")
        products.append({"sku": sku, "name": nm, "unit": "шт", "price": price, "kg": 0.0,
                         "group": "drip", "accent": "coffee", "slide": "06"})
        replacements.append((m.start(), m.end(),
            '<span class="spp' + cell_attrs(sku, nm, "шт", price, 0.0, "coffee")
            + '><span class="spp__lbl">опт</span>'
            + f'<span class="single__opt">{m.group(1)}</span></span>'))
        bind(anc, sku, "coffee")
        if anc:
            name_wrap[(anc[0], anc[1])] = (
                '<span class="single__head">',
                ctl(sku, "coffee", "buyctl--under") + '</span>')

    # ── 4. чай: + под каждой ценой ────────────────────────────────────────────
    col_pos = {}
    for m in re.finditer(r'<div class="tea-price"><div class="tea-price__opt">(.*?)</div></div>',
                         base, re.S):
        anc = nearest(tea_names, m.start())
        key = anc[0] if anc else -1
        ci = col_pos.get(key, 0)
        col_pos[key] = ci + 1
        price = to_num(m.group(1))
        if not price:
            continue
        nm = anc[2] if anc else ""
        cols_anc = nearest(tea_cols, m.start())
        cols = cols_anc[2] if cols_anc else ["200 г", "500 г"]
        cap = cols[ci] if ci < len(cols) else ""
        no = slide_of(spans, m.start())
        sku = uniq(f"tea-{slug(nm)}-{slug(cap)}")
        products.append({"sku": sku, "name": nm, "unit": cap, "price": price, "kg": 0.0,
                         "group": "tea", "accent": "tea", "slide": no})
        bind(anc, sku, "tea")
        replacements.append((m.start(), m.end(),
            '<div class="tea-price' + cell_attrs(sku, nm, cap, price, 0.0, "tea")
            + f'><div class="tea-price__opt">{m.group(1)}</div>'
            + ctl(sku, "tea") + '</div>'))

    # названия получают привязку к позициям — по ней рисуется подчёркивание
    for (ns, ne), skus in name_skus.items():
        tag = base[ns:ne]
        acc = name_accent.get((ns, ne), "coffee")
        tag = re.sub(r"^(<[a-z]+)", r'\1 data-buy-name="' + " ".join(skus) + '"'
                     + f' data-buy-accent="{acc}"', tag, count=1)
        pre, post = name_wrap.get((ns, ne), ("", ""))
        replacements.append((ns, ne, pre + tag + post))

    # применяем справа налево, чтобы не сдвигать смещения
    out = base
    for start, end, new in sorted(replacements, key=lambda r: (-r[0], -r[1])):
        out = out[:start] + new + out[end:]

    return out, products


def main():
    with_cart = "--no-cart" not in sys.argv
    base = BASE.read_text(encoding="utf-8")
    html, products = build_html(base, with_cart)

    if with_cart:
        # в чае колонки ррц нет — легенда убирается
        html = re.sub(
            r'\s*<div class="price-legend">В колонке: <b>опт</b> сверху · <i>ррц</i> снизу</div>\n',
            "\n", html)
        css = (SRC / "cart.css").read_text(encoding="utf-8")
        js = (SRC / "cart.js").read_text(encoding="utf-8")
        markup = (SRC / "cart.html").read_text(encoding="utf-8")
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
        html = html.replace("</body>", f"{markup}\n<script>\n{js}\n</script>\n</body>", 1)
        (SRC / "products.json").write_text(
            json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.write_text(html, encoding="utf-8")
    print(f"index.html собран: {len(html)} символов, позиций: {len(products)}")
    if products:
        from collections import Counter
        for g, n in Counter(p["group"] for p in products).most_common():
            print(f"  {g}: {n}")


if __name__ == "__main__":
    main()
