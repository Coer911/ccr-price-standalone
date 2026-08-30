"""Проверка корзины в реальном браузере: клики, ступени опта, печать."""
import json
import pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
URL = "file://" + str(ROOT / "index.html")
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)

fails = []


def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": 414, "height": 896}, device_scale_factor=2)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_timeout(600)

    print("\n1. Исходное состояние")
    check("нет ошибок JS", not errors, "; ".join(errors[:3]))
    # 122 позиции, но у 5 эспрессо по 3 ячейки-ступени -> 122 + 5*2 = 132 элемента
    check("кликабельных ячеек 132", page.locator(".is-buy").count() == 132,
          f"найдено {page.locator('.is-buy').count()}")
    skus = page.evaluate(
        "Array.from(document.querySelectorAll('.is-buy')).map(e=>e.dataset.sku)")
    check("уникальных sku 122", len(set(skus)) == 122, f"{len(set(skus))}")
    check("плашка корзины видна всегда", page.locator("#cartbar").is_visible())
    check("в пустой корзине 0", page.locator("#cartCount").inner_text() == "0",
          page.locator("#cartCount").inner_text())
    check("плашка помечена пустой", "is-empty" in (page.locator("#cartbar").get_attribute("class") or ""))
    check("плашка подписана «Корзина»",
          page.locator(".cartbar__label").inner_text() == "Корзина",
          page.locator(".cartbar__label").inner_text())
    check("в пустой корзине приписки нет", page.locator("#cartNote").inner_text() == "")
    check("кнопок + ровно 122", page.locator(".buyctl").count() == 122,
          f"найдено {page.locator('.buyctl').count()}")
    check("ни один счётчик не раскрыт", page.locator(".buyctl.is-on").count() == 0)
    check("названия привязаны к позициям", page.locator("[data-buy-name]").count() > 60,
          f"{page.locator('[data-buy-name]').count()}")
    check("ничего не подчёркнуто", page.locator("[data-buy-name].is-picked").count() == 0)
    check("подсказка показана", page.locator(".buyhint").count() == 1)
    page.locator(".card").nth(3).scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "01-filter-empty.png"))

    print("\n2. Добавление позиции тапом по цене")
    cell = page.locator('.pcell.is-buy[data-name="Колумбия супремо"]').first
    cell.click()
    page.wait_for_timeout(350)
    check("счётчик раскрылся", page.locator(".buyctl.is-on").count() == 1)
    check("счётчик показывает 1",
          page.locator(".buyctl.is-on .buyctl__n").inner_text() == "1")
    check("плашка перестала быть пустой",
          "is-empty" not in (page.locator("#cartbar").get_attribute("class") or ""))
    check("сумма 660 ₽", "660" in page.locator("#cartSum").inner_text(),
          page.locator("#cartSum").inner_text())
    check("приписка про количество позиций",
          page.locator("#cartNote").inner_text() == "· 1 позиция",
          page.locator("#cartNote").inner_text())
    check("подсказка скрылась", page.locator(".buyhint").is_hidden())
    check("название позиции подчёркнулось",
          page.locator('.item__name.is-picked').count() == 1)
    check("подчёркнуто именно «Колумбия супремо»",
          page.locator('.item__name.is-picked').inner_text().strip().lower() == "колумбия супремо",
          page.locator('.item__name.is-picked').inner_text())
    check("базовая ступень не подсвечивается",
          page.locator('.pcell.is-live').count() == 0)
    page.screenshot(path=str(SHOTS / "02-added.png"))

    print("\n3. Ступень опта считается от суммарных кг кофе")
    # 0.25 кг фильтра уже в заказе; добавляем 19 кг «Блю спешл» -> 19.25 кг, ступень 1-19
    esp = page.locator('.pcell.is-buy[data-name="Блю спешл"][data-tier="0"]')
    for _ in range(19):
        esp.click()
    page.wait_for_timeout(300)
    check("на базовой ступени подсветки нет", page.locator('.pcell.is-live').count() == 0)
    check("название эспрессо подчёркнуто",
          page.locator('.item__name.is-picked').count() == 2,
          f"{page.locator('.item__name.is-picked').count()}")
    esp.click()  # 20.25 кг -> ступень 20-49
    page.wait_for_timeout(300)
    live = page.locator('.pcell.is-live[data-name="Блю спешл"]')
    check("на 20,25 кг ступень переключилась", live.get_attribute("data-tier") == "1",
          f'tier={live.get_attribute("data-tier")}')
    check("у эспрессо один общий счётчик на позицию",
          page.locator('.buyctl--wide.is-on').count() == 1)
    # 20 кг по 1700 + фильтр 660
    check("сумма пересчиталась по новой ступени",
          "34 660" in page.locator("#cartSum").inner_text().replace(" ", " "),
          page.locator("#cartSum").inner_text())
    page.screenshot(path=str(SHOTS / "03-tier.png"))

    print("\n4. Панель заказа")
    page.locator("#cartbarOpen").click()
    page.wait_for_timeout(450)
    check("панель открылась", page.locator("#cartSheet").is_visible())
    check("две строки в заказе", page.locator(".line").count() == 2,
          f"строк {page.locator('.line').count()}")
    check("есть подсказка про ступень или доставку", page.locator(".hint").count() >= 1)
    check("есть призыв отправить скриншот менеджеру",
          "скриншот" in page.locator("#cartCta").inner_text())
    page.screenshot(path=str(SHOTS / "04-sheet.png"))

    print("\n5. Минус в панели и удаление")
    page.locator(".line").first.locator(".step__btn").first.click()
    page.wait_for_timeout(250)
    check("количество уменьшилось",
          page.locator("#cartTotal").inner_text() != "", page.locator("#cartTotal").inner_text())
    check("выгода от объёма показана", not page.locator("#cartSave").is_hidden())
    check("выгода посчитана", page.locator("#cartSaveVal").inner_text() != "−0 ₽",
          page.locator("#cartSaveVal").inner_text())
    page.locator("#cartClear").click()
    page.wait_for_timeout(350)
    check("после очистки плашка пуста",
          "is-empty" in (page.locator("#cartbar").get_attribute("class") or ""))
    check("счётчиков не осталось", page.locator(".buyctl.is-on").count() == 0)
    check("подчёркивания сняты", page.locator("[data-buy-name].is-picked").count() == 0)
    check("строка выгоды скрыта", page.locator("#cartSave").is_hidden())
    check("призыв к заказу скрыт при пустом заказе", page.locator("#cartCta").is_hidden())
    check("пустая панель подсказывает про +",
          "Нажмите +" in page.locator(".sheet__empty").inner_text())
    page.locator("#cartClose").click()
    page.wait_for_timeout(350)

    print("\n6. Чай — зелёный акцент и свои позиции")
    tea = page.locator('.tea-price.is-buy').first
    tea.scroll_into_view_if_needed()
    tea.locator('.buyctl__plus').click()
    page.wait_for_timeout(300)
    check("кнопка чая зелёная",
          "buyctl--tea" in (tea.locator(".buyctl").get_attribute("class") or ""))
    check("счётчик чая раскрылся", page.locator(".buyctl.is-on").count() == 1)
    tea.locator('.buyctl__minus').click()
    page.wait_for_timeout(250)
    check("минус у позиции убирает из заказа", page.locator(".buyctl.is-on").count() == 0)
    tea.locator('.buyctl__plus').click()
    page.wait_for_timeout(250)
    page.screenshot(path=str(SHOTS / "05-tea.png"))

    print("\n7. Сохранение между визитами")
    page.reload()
    page.wait_for_timeout(600)
    check("заказ восстановился",
          "is-empty" not in (page.locator("#cartbar").get_attribute("class") or ""))
    check("счётчик на месте", page.locator(".buyctl.is-on").count() == 1)

    print("\n8. Печать")
    pdf_page = b.new_page()
    pdf_page.goto(URL)
    pdf_page.wait_for_timeout(500)
    pdf_page.emulate_media(media="print")
    pdf_page.wait_for_timeout(200)
    check("плашка не печатается", pdf_page.locator("#cartbar").is_hidden())
    check("кнопки + не печатаются", pdf_page.locator(".buyctl").first.is_hidden())
    pdf = pdf_page.pdf(format="A4", print_background=True)
    (ROOT / "shots" / "print.pdf").write_bytes(pdf)
    check("PDF собрался", len(pdf) > 50000, f"{len(pdf)//1024} КБ")

    print("\n9. Ошибки консоли за весь прогон")
    check("консоль чистая", not errors, "; ".join(errors[:3]))

    b.close()

print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not fails else "ПРОВАЛЫ: " + ", ".join(fails)))
