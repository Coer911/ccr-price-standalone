"""Генерация файлов импорта в Tilda для концентратов Баринофф 1 кг.

Запуск: python3 build_concentrates.py <прайс.xlsx> [наценка, напр. 1.0]
Создаёт barinoff-concentrates.yml (формат как у выгрузки Tilda) и
barinoff-concentrates.csv (CSV-импорт Tilda).
Картинки: впишите URL в PICTURES и перезапустите.
"""
import csv, re, sys, html
from pathlib import Path
import openpyxl

OUT = Path(__file__).parent
CATEGORY_ID = "367001772802"
CATEGORY = "концентраты Баринофф"
MARKUP = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

# Латинские части артикула и описания по вкусу
FLAVORS = {
    "Апельсин": ("ORANGE", "Яркий сочный апельсин с лёгкой цитрусовой горчинкой цедры."),
    "Апельсин Имбирь": ("ORANGEGINGER", "Сладкий апельсин и жгучий имбирь — согревающее цитрусовое сочетание."),
    "Банан": ("BANANA", "Насыщенный вкус спелого банана с мягкой сладостью."),
    "Грейпфрукт Бузина": ("GRAPEFRUITELDER", "Горьковатый грейпфрут и цветочная бузина — освежающий и необычный дуэт."),
    "Киви": ("KIWI", "Сочный киви с тропической сладостью и лёгкой кислинкой."),
    "Клубника": ("STRAWBERRY", "Вкус спелой летней клубники."),
    "Клюква Апельсин": ("CRANBERRYORANGE", "Кислая клюква и сладкий апельсин — яркий ягодно-цитрусовый баланс."),
    "Клюква Можжевельник": ("CRANBERRYJUNIPER", "Северная клюква с хвойными нотами можжевельника."),
    "Лесные ягоды": ("FORESTBERRIES", "Ароматный микс лесных ягод."),
    "Лимон Имбирь": ("LEMONGINGER", "Классика согревающих напитков: свежий лимон и пряный имбирь."),
    "Малина Имбирь": ("RASPBERRYGINGER", "Сладкая малина с тёплой пряностью имбиря."),
    "Манго": ("MANGO", "Сочное спелое манго — тропическое настроение в каждом напитке."),
    "Манго Маракуйя": ("MANGOPASSION", "Тропический дуэт сладкого манго и кисловатой маракуйи."),
    "Облепиха Имбирь": ("SEABUCKTHORNGINGER", "Облепиха с имбирём — яркий, согревающий и полезный вкус."),
    "Ревень": ("RHUBARB", "Свежий кисло-сладкий вкус ревеня."),
    "Черная смородина Малина": ("BLACKCURRANTRASPBERRY", "Ароматная чёрная смородина и сладкая малина."),
    "Черная смородина Мята": ("BLACKCURRANTMINT", "Чёрная смородина с освежающей мятой."),
    "Черная смородина Красная смородина": ("BLACKREDCURRANT", "Два вида смородины: насыщенная чёрная и кисловатая красная."),
    "Черника": ("BLUEBERRY", "Глубокий ягодный вкус черники."),
    "Черника Мята": ("BLUEBERRYMINT", "Черника с прохладной мятой."),
    "Юзу": ("YUZU", "Японский цитрус юзу — тонкий аромат на грани лимона, мандарина и грейпфрута."),
    "Яблоко": ("APPLE", "Свежий вкус сочного яблока."),
    "Яблоко Корица": ("APPLECINNAMON", "Печёное яблоко с корицей — уютный осенний вкус."),
    "Ягодный микс Базилик": ("BERRYBASIL", "Ягодный микс с пряной свежестью базилика."),
}
PICTURES = {}  # "Юзу": "https://static.tildacdn.com/....png"

COMMON = ("Концентрат для приготовления лимонадов, морсов, чаёв и горячих напитков. "
          "Разбавляется водой. Упаковка: пластиковая бутылка 1 кг. Срок годности: 18 мес.")


def rows(xlsx):
    ws = openpyxl.load_workbook(xlsx, data_only=True).worksheets[0]
    for r in ws.iter_rows(values_only=True):
        if isinstance(r[0], int) and str(r[1]).startswith("Концентрат"):
            m = re.match(r"Концентрат «(.+?)»\s*(Халяль)?", r[1])
            yield r[0], m.group(1), bool(m.group(2)), r[8], r[9]


def main():
    items = []
    for num, flavor, halal, barcode, price in rows(sys.argv[1]):
        code, desc = FLAVORS[flavor]
        items.append(dict(
            id=f"9100{num:08d}",
            name=f"КОНЦЕНТРАТ «{flavor.upper()}» 1 КГ" + (" (ХАЛЯЛЬ)" if halal else ""),
            sku=f"BARINOFF_{code}_1KG",
            desc=f"{desc} {COMMON}",
            picture=PICTURES.get(flavor, ""),
            price=f"{round(price * MARKUP):.2f}",
            barcode=str(barcode),
            halal=halal,
        ))

    e = lambda s: html.escape(s, quote=False)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<yml_catalog date="2026-10-07T00:00:00+03:00">', '\t<shop>',
           '\t\t<name>Культура кофе</name>', '\t\t<company>CCR</company>',
           '\t\t<url>https://cultura-coffee.ru</url>',
           '\t\t<currencies>', '\t\t\t<currency id="RUR" rate="1"/>', '\t\t</currencies>',
           '\t\t<categories>', f'\t\t\t<category id="{CATEGORY_ID}">{CATEGORY}</category>',
           '\t\t</categories>', '\t\t<offers>']
    for it in items:
        out += [f'\t\t<offer id="{it["id"]}">',
                f'\t\t\t<name>{e(it["name"])}</name>',
                '\t\t\t<vendor>Barinoff</vendor>',
                f'\t\t\t<vendorCode>{it["sku"]}</vendorCode>',
                f'\t\t\t<description>\n<![CDATA[\n{it["desc"]}\n]]>\n\t\t\t</description>']
        if it["picture"]:
            out.append(f'\t\t\t<picture>{it["picture"]}</picture>')
        out += ['\t\t\t<count>9999</count>',
                f'\t\t\t<price>{it["price"]}</price>',
                '\t\t\t<currencyId>RUR</currencyId>',
                f'\t\t\t<categoryId>{CATEGORY_ID}</categoryId>',
                '\t\t\t<weight>1.1</weight>',
                f'\t\t\t<barcode>{it["barcode"]}</barcode>',
                '\t\t\t<param name="Страна производства">Россия</param>',
                '\t\t\t<param name="ОБЬЕМ">1 кг</param>']
        if it["halal"]:
            out.append('\t\t\t<param name="Халяль">Да</param>')
        out.append('\t\t</offer>')
    out += ['\t\t</offers>', '\t</shop>', '</yml_catalog>', '']
    (OUT / "barinoff-concentrates.yml").write_text("\n".join(out), encoding="utf-8")

    with open(OUT / "barinoff-concentrates.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Tilda UID", "Brand", "SKU", "Category", "Title", "Description",
                    "Text", "Photo", "Price", "Quantity", "External ID", "Weight"])
        for it in items:
            w.writerow(["", "Barinoff", it["sku"], CATEGORY, it["name"], it["desc"],
                        it["desc"], it["picture"], it["price"], 9999, it["id"], 1100])
    print(f"{len(items)} товаров, наценка x{MARKUP}")


if __name__ == "__main__":
    main()
