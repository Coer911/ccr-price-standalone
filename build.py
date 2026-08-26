#!/usr/bin/env python3
"""
Сборка index.html из src/price-base.html.

Базовая вёрстка (src/price-base.html) не редактируется руками под корзину.
Скрипт делает три вещи:
  1) размечает покупаемые ценовые ячейки data-атрибутами;
  2) вшивает src/cart.css и src/cart.js перед </body>;
  3) выгружает src/products.json — машиночитаемый список позиций.

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

# ── вспомогательное ───────────────────────────────────────────────────────────

WS = "     "


def to_num(price_html: str) -> int:
    """'2 020 ₽' -> 2020"""
    digits = re.sub(r"[^0-9]", "", price_html)
    return int(digits) if digits else 0


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    out = []
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
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
    """[(начало, конец, номер слайда)] — чтобы знать, в каком слайде лежит ячейка."""
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


TEA_SLIDES = {"08", "09", "10"}
# слайды, где кофе продаётся на вес и формирует ступень опта
COFFEE_WEIGHT_SLIDES = {"04", "05"}
ESPRESSO_CAPS = ("1–19 кг", "20–49 кг", "от 50 кг")


def anchors(base, pattern):
    """[(позиция, текст)] — подписи, к которым привязываются ценовые ячейки."""
    return [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
            for m in re.finditer(pattern, base, re.S)]


def nearest(anchor_list, pos, default=None):
    """Ближайшая подпись слева от позиции."""
    best = default
    for apos, val in anchor_list:
        if apos < pos:
            best = val
        else:
            break
    return best


def nearest_idx(anchor_list, pos):
    """Индекс ближайшей подписи слева (для группировки ячеек по позиции)."""
    idx = -1
    for i, (apos, _) in enumerate(anchor_list):
        if apos < pos:
            idx = i
        else:
            break
    return idx


def build_html(base: str, with_cart: bool) -> tuple:
    """Возвращает (html, список позиций). Правки — точечные, вёрстка вокруг не трогается."""
    if not with_cart:
        return base, []

    spans = section_map(base)
    products = []
    seen = {}

    def uniq(b):
        seen[b] = seen.get(b, 0) + 1
        return b if seen[b] == 1 else f"{b}-{seen[b]}"

    item_names = anchors(base, r'<div class="item__name">(.*?)</div>')
    tea_names = anchors(base, r'<div class="tea-row__name">(.*?)</div>')
    var_names = sorted(
        anchors(base, r'<span class="variant__name">(.*?)</span>')
        + anchors(base, r'<div class="box__kind">(.*?)</div>'))
    single_names = anchors(base, r'<span class="single__name">(.*?)</span>')
    box_caps = [(m.start(), f"{m.group(1)} {m.group(2)}") for m in re.finditer(
        r'<span class="box__num">(.*?)</span><span class="box__unit">(.*?)</span>', base)]
    tea_cols = [(m.start(), re.findall(r"<span>(.*?)</span>", m.group(1)))
                for m in re.finditer(r'<div class="tea-cat__cols">(.*?)</div>', base, re.S)]

    replacements = []   # (начало, конец, новый текст)

    # ── 1. pcell: фильтр, эспрессо, матча ─────────────────────────────────────
    pcells = list(re.finditer(
        r'<div class="pcell((?: [^"]*)?)"><div class="pcell__cap">(.*?)</div>'
        r'<div class="pcell__opt">(.*?)</div></div>', base, re.S))

    groups = {}
    for m in pcells:
        groups.setdefault(nearest_idx(item_names, m.start()), []).append(m)

    for gi, cells in groups.items():
        pname = item_names[gi][1] if gi >= 0 else ""
        no = slide_of(spans, cells[0].start())
        caps = tuple(c.group(2).strip() for c in cells)
        accent = "tea" if no in TEA_SLIDES else "coffee"

        if caps == ESPRESSO_CAPS:
            sku = uniq(slug(pname))
            prices = [to_num(c.group(3)) for c in cells]
            products.append({"sku": sku, "name": pname, "unit": "кг",
                             "price": prices[0], "tiers": prices, "kg": 1.0,
                             "group": "espresso", "accent": "coffee", "slide": no})
            for ci, c in enumerate(cells):
                replacements.append((c.start(), c.end(),
                    f'<div class="pcell{c.group(1)} is-buy" role="button" tabindex="0"'
                    f' data-sku="{sku}" data-name="{pname}" data-unit="кг"'
                    f' data-price="{prices[0]}" data-tiers="{",".join(map(str, prices))}"'
                    f' data-tier="{ci}" data-kg="1" data-accent="coffee">'
                    f'<div class="pcell__cap">{c.group(2)}</div>'
                    f'<div class="pcell__opt">{c.group(3)}</div></div>'))
        else:
            for c in cells:
                cap = c.group(2).strip()
                price = to_num(c.group(3))
                if not price:
                    continue
                kg = cap_to_kg(cap) if no in COFFEE_WEIGHT_SLIDES else 0.0
                sku = uniq(f"{slug(pname)}-{slug(cap)}")
                products.append({"sku": sku, "name": pname, "unit": cap, "price": price,
                                 "kg": kg, "group": "coffee" if accent == "coffee" else "tea",
                                 "accent": accent, "slide": no})
                replacements.append((c.start(), c.end(),
                    f'<div class="pcell{c.group(1)} is-buy" role="button" tabindex="0"'
                    f' data-sku="{sku}" data-name="{pname}" data-unit="{cap}"'
                    f' data-price="{price}" data-kg="{kg:g}" data-accent="{accent}">'
                    f'<div class="pcell__cap">{c.group(2)}</div>'
                    f'<div class="pcell__opt">{c.group(3)}</div></div>'))

    # ── 2. дрип в коробочках ──────────────────────────────────────────────────
    for m in re.finditer(
            r'<span class="pp"><span class="pp__lbl">опт</span>'
            r'<span class="pp__opt">(.*?)</span></span>', base, re.S):
        nm = nearest(var_names, m.start(), "")
        cap = nearest(box_caps, m.start(), "шт")
        price = to_num(m.group(1))
        if not price:
            continue
        sku = uniq(f"drip-{slug(nm)}-{slug(cap)}")
        products.append({"sku": sku, "name": nm, "unit": cap, "price": price,
                         "kg": 0.0, "group": "drip", "accent": "coffee", "slide": "06"})
        replacements.append((m.start(), m.end(),
            f'<span class="pp is-buy" role="button" tabindex="0"'
            f' data-sku="{sku}" data-name="{nm}" data-unit="{cap}"'
            f' data-price="{price}" data-kg="0" data-accent="coffee">'
            f'<span class="pp__lbl">опт</span>'
            f'<span class="pp__opt">{m.group(1)}</span></span>'))

    # ── 3. дрип штучный ───────────────────────────────────────────────────────
    for m in re.finditer(
            r'<span class="spp"><span class="spp__lbl">опт</span>'
            r'<span class="single__opt">(.*?)</span></span>', base, re.S):
        nm = nearest(single_names, m.start(), "")
        price = to_num(m.group(1))
        if not price:
            continue
        sku = uniq(f"drip-sht-{slug(nm)}")
        products.append({"sku": sku, "name": nm, "unit": "шт", "price": price,
                         "kg": 0.0, "group": "drip", "accent": "coffee", "slide": "06"})
        replacements.append((m.start(), m.end(),
            f'<span class="spp is-buy" role="button" tabindex="0"'
            f' data-sku="{sku}" data-name="{nm}" data-unit="шт"'
            f' data-price="{price}" data-kg="0" data-accent="coffee">'
            f'<span class="spp__lbl">опт</span>'
            f'<span class="single__opt">{m.group(1)}</span></span>'))

    # ── 4. чай: строки списков ────────────────────────────────────────────────
    tea_cells = list(re.finditer(
        r'<div class="tea-price"><div class="tea-price__opt">(.*?)</div></div>', base, re.S))
    col_pos = {}
    for m in tea_cells:
        ri = nearest_idx(tea_names, m.start())
        ci = col_pos.get(ri, 0)
        col_pos[ri] = ci + 1
        nm = tea_names[ri][1] if ri >= 0 else ""
        cols = nearest(tea_cols, m.start(), ["200 г", "500 г"])
        cap = cols[ci] if ci < len(cols) else ""
        price = to_num(m.group(1))
        if not price:
            continue
        no = slide_of(spans, m.start())
        sku = uniq(f"tea-{slug(nm)}-{slug(cap)}")
        products.append({"sku": sku, "name": nm, "unit": cap, "price": price,
                         "kg": 0.0, "group": "tea", "accent": "tea", "slide": no})
        replacements.append((m.start(), m.end(),
            f'<div class="tea-price is-buy" role="button" tabindex="0"'
            f' data-sku="{sku}" data-name="{nm}" data-unit="{cap}"'
            f' data-price="{price}" data-kg="0" data-accent="tea">'
            f'<div class="tea-price__opt">{m.group(1)}</div></div>'))

    # применяем справа налево, чтобы не сдвигать смещения
    out = base
    for start, end, new in sorted(replacements, key=lambda r: -r[0]):
        out = out[:start] + new + out[end:]

    return out, products


def main():
    with_cart = "--no-cart" not in sys.argv
    base = BASE.read_text(encoding="utf-8")

    html, products = build_html(base, with_cart)

    if with_cart:
        # убираем легенду ррц у чая — колонок с ррц в чае нет
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
    print(f"index.html собран: {len(html)} байт, позиций: {len(products)}")
    if products:
        from collections import Counter
        for g, n in Counter(p["group"] for p in products).most_common():
            print(f"  {g}: {n}")


if __name__ == "__main__":
    main()
