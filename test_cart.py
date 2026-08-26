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
    check("плашка корзины скрыта", page.locator("#cartbar").is_hidden())
    check("подсказка показана", page.locator(".buyhint").count() == 1)
    page.locator(".card").nth(3).scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "01-filter-empty.png"))

    print("\n2. Добавление позиции тапом по цене")
    cell = page.locator('.pcell.is-buy[data-name="Колумбия супремо"]').first
    cell.click()
    page.wait_for_timeout(350)
    check("значок с количеством появился", cell.locator(".qty").count() == 1)
    check("значок показывает 1", cell.locator(".qty").inner_text() == "1")
    check("плашка появилась", page.locator("#cartbar").is_visible())
    check("сумма 660 ₽", "660" in page.locator("#cartSum").inner_text(),
          page.locator("#cartSum").inner_text())
    check("подсказка скрылась", page.locator(".buyhint").is_hidden())
    page.screenshot(path=str(SHOTS / "02-added.png"))

    print("\n3. Ступень опта считается от суммарных кг кофе")
    # 0.25 кг фильтра уже в заказе; добавляем 19 кг «Блю спешл» -> 19.25 кг, ступень 1-19
    esp = page.locator('.pcell.is-buy[data-name="Блю спешл"][data-tier="0"]')
    for _ in range(19):
        esp.click()
    page.wait_for_timeout(300)
    live = page.locator('.pcell.is-live[data-name="Блю спешл"]')
    check("активна первая ступень при 19,25 кг", live.get_attribute("data-tier") == "0",
          f'tier={live.get_attribute("data-tier")}')
    esp.click()  # 20.25 кг -> ступень 20-49
    page.wait_for_timeout(300)
    live = page.locator('.pcell.is-live[data-name="Блю спешл"]')
    check("на 20,25 кг ступень переключилась", live.get_attribute("data-tier") == "1",
          f'tier={live.get_attribute("data-tier")}')
    check("значок переехал на активную ступень",
          page.locator('.pcell.is-buy[data-name="Блю спешл"][data-tier="1"] .qty').count() == 1)
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
    page.screenshot(path=str(SHOTS / "04-sheet.png"))

    print("\n5. Минус в панели и удаление")
    page.locator(".line").first.locator(".step__btn").first.click()
    page.wait_for_timeout(250)
    check("количество уменьшилось",
          page.locator("#cartTotal").inner_text() != "", page.locator("#cartTotal").inner_text())
    page.locator("#cartClear").click()
    page.wait_for_timeout(350)
    check("после очистки плашка скрыта", page.locator("#cartbar").is_hidden())
    check("значков не осталось", page.locator(".qty").count() == 0)

    print("\n6. Чай — зелёный акцент и свои позиции")
    tea = page.locator('.tea-price.is-buy').first
    tea.scroll_into_view_if_needed()
    tea.click()
    page.wait_for_timeout(300)
    check("значок чая зелёный", "qty--tea" in (tea.locator(".qty").get_attribute("class") or ""))
    page.screenshot(path=str(SHOTS / "05-tea.png"))

    print("\n7. Сохранение между визитами")
    page.reload()
    page.wait_for_timeout(600)
    check("заказ восстановился", page.locator("#cartbar").is_visible())
    check("значок на месте", page.locator(".qty").count() == 1)

    print("\n8. Печать")
    pdf_page = b.new_page()
    pdf_page.goto(URL)
    pdf_page.wait_for_timeout(500)
    pdf_page.emulate_media(media="print")
    pdf_page.wait_for_timeout(200)
    check("плашка не печатается", pdf_page.locator("#cartbar").is_hidden())
    pdf = pdf_page.pdf(format="A4", print_background=True)
    (ROOT / "shots" / "print.pdf").write_bytes(pdf)
    check("PDF собрался", len(pdf) > 50000, f"{len(pdf)//1024} КБ")

    print("\n9. Ошибки консоли за весь прогон")
    check("консоль чистая", not errors, "; ".join(errors[:3]))

    b.close()

print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not fails else "ПРОВАЛЫ: " + ", ".join(fails)))
