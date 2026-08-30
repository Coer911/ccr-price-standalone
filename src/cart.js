/* ═══════════════════════════════════════════════════════════════════════════
   КОРЗИНА ПРАЙСА CULTURA COFFEE
   У каждой позиции своя кнопка +, она же счётчик −N+. Тап по цене тоже добавляет.
   Ступень опта по эспрессо считается от суммарного веса кофе в заказе.
   Внешних запросов нет, данные берутся из data-атрибутов разметки.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var STORE_KEY = 'ccr-cart-v1';
  var FREE_DELIVERY = 6000;      // ₽, слайд «Условия заказа»
  var TIERS = [0, 20, 50];       // кг: 1–19 / 20–49 / от 50

  var state = load();
  var els = {};
  var cells = [];                // ценовые ячейки
  var ctls = [];                 // кнопки-счётчики
  var meta = {};                 // sku -> данные позиции

  // ── хранилище ──────────────────────────────────────────────────────────────

  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      var obj = raw ? JSON.parse(raw) : {};
      return obj && typeof obj === 'object' ? obj : {};
    } catch (e) { return {}; }
  }

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) {}
  }

  // ── формат ─────────────────────────────────────────────────────────────────

  function money(n) {
    return Math.round(n).toLocaleString('ru-RU').replace(/ /g, ' ') + ' ₽';
  }

  function kgFmt(n) {
    return (Math.round(n * 100) / 100).toLocaleString('ru-RU').replace(/ /g, ' ');
  }

  function plural(n, one, few, many) {
    var a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b > 1 && b < 5) return few;
    if (b === 1) return one;
    return many;
  }

  // ── расчёт ─────────────────────────────────────────────────────────────────

  function coffeeKg() {
    var kg = 0;
    for (var sku in state) {
      if (!state[sku] || !meta[sku]) continue;
      kg += state[sku] * (meta[sku].kg || 0);
    }
    return kg;
  }

  function tierFor(kg) {
    if (kg >= TIERS[2]) return 2;
    if (kg >= TIERS[1]) return 1;
    return 0;
  }

  function tierIndex() { return tierFor(coffeeKg()); }

  function priceAt(sku, ti) {
    var m = meta[sku];
    if (!m) return 0;
    return m.tiers ? m.tiers[ti] : m.price;
  }

  function unitPrice(sku) { return priceAt(sku, tierIndex()); }

  function totals() {
    var ti = tierIndex();
    var sum = 0, base = 0, count = 0, units = 0;
    for (var sku in state) {
      var q = state[sku];
      if (!q || !meta[sku]) continue;
      sum += q * priceAt(sku, ti);
      base += q * priceAt(sku, 0);     // цена без объёмной скидки
      count += 1;
      units += q;
    }
    return { sum: sum, base: base, save: base - sum, count: count, units: units };
  }

  /** Сколько сэкономит текущий заказ, если объём дотянет до следующей ступени. */
  function saveIfNextTier() {
    var ti = tierIndex();
    if (ti >= 2) return 0;
    var diff = 0;
    for (var sku in state) {
      var q = state[sku];
      if (!q || !meta[sku] || !meta[sku].tiers) continue;
      diff += q * (priceAt(sku, ti) - priceAt(sku, ti + 1));
    }
    return diff;
  }

  // ── изменение количества ───────────────────────────────────────────────────

  function add(sku, delta) {
    if (!meta[sku]) return;
    var q = (state[sku] || 0) + delta;
    if (q <= 0) delete state[sku]; else state[sku] = q;
    save();
    render();
  }

  function clear() {
    state = {};
    save();
    render();
  }

  // ── отрисовка прайса ───────────────────────────────────────────────────────

  function renderCells() {
    var ti = tierIndex();
    var kg = coffeeKg();

    cells.forEach(function (el) {
      if (el.dataset.tiers == null) return;
      // подсвечиваем ступень, по которой сейчас идёт расчёт
      el.classList.toggle('is-live', kg > 0 && parseInt(el.dataset.tier, 10) === ti);
    });

    ctls.forEach(function (c) {
      var q = state[c.dataset.ctl] || 0;
      c.classList.toggle('is-on', q > 0);
      c.querySelector('.buyctl__n').textContent = q;
    });
  }

  // ── подсказки ──────────────────────────────────────────────────────────────

  function hints() {
    var list = [];
    var t = totals();
    var kg = coffeeKg();
    var ti = tierIndex();

    if (kg > 0 && ti < 2) {
      var need = TIERS[ti + 1] - kg;
      var gain = saveIfNextTier();
      list.push({
        win: false,
        html: 'До скидки осталось <b>' + kgFmt(need) + ' кг</b> кофе' +
              (gain > 0 ? ' — сэкономите <b>' + money(gain) + '</b>' : '')
      });
    } else if (kg >= TIERS[2]) {
      list.push({
        win: true,
        html: 'В заказе <b>' + kgFmt(kg) + ' кг</b> кофе — действует лучшая цена «от 50 кг»'
      });
    }

    if (t.sum > 0 && t.sum < FREE_DELIVERY) {
      list.push({
        win: false,
        html: 'До бесплатной доставки не хватает <b>' + money(FREE_DELIVERY - t.sum) + '</b>'
      });
    } else if (t.sum >= FREE_DELIVERY) {
      list.push({ win: true, html: 'Доставка бесплатно — заказ больше ' + money(FREE_DELIVERY) });
    }

    return list;
  }

  // ── панель заказа ──────────────────────────────────────────────────────────

  function lineNode(sku) {
    var m = meta[sku], q = state[sku], p = unitPrice(sku), full = priceAt(sku, 0);

    var line = document.createElement('div');
    line.className = 'line';

    var main = document.createElement('div');
    main.className = 'line__main';

    var name = document.createElement('div');
    name.className = 'line__name';
    name.textContent = m.name;

    var info = document.createElement('div');
    info.className = 'line__meta';
    info.innerHTML = '<span class="line__dot' + (m.accent === 'tea' ? ' line__dot--tea' : '') +
                     '"></span>' + m.unit + ' · ' + money(p) +
                     (p < full ? ' <s>' + money(full) + '</s>' : '');
    main.appendChild(name);
    main.appendChild(info);

    var step = document.createElement('div');
    step.className = 'step';
    ['−', null, '+'].forEach(function (label) {
      if (label === null) {
        var val = document.createElement('span');
        val.className = 'step__val';
        val.textContent = q;
        step.appendChild(val);
        return;
      }
      var b = document.createElement('button');
      b.className = 'step__btn';
      b.type = 'button';
      b.textContent = label;
      b.setAttribute('aria-label', label === '+' ? 'Добавить одну единицу' : 'Убрать одну единицу');
      b.addEventListener('click', function () { add(sku, label === '+' ? 1 : -1); });
      step.appendChild(b);
    });

    var sum = document.createElement('div');
    sum.className = 'line__sum';
    sum.textContent = money(q * p);

    line.appendChild(main);
    line.appendChild(step);
    line.appendChild(sum);
    return line;
  }

  function renderSheet() {
    var body = els.lines;
    body.innerHTML = '';

    var skus = Object.keys(state).filter(function (s) { return state[s] > 0 && meta[s]; });
    if (!skus.length) {
      body.innerHTML = '<div class="sheet__empty">Заказ пуст.<br>' +
                       'Нажмите + у нужной позиции.</div>';
    } else {
      skus.forEach(function (sku) { body.appendChild(lineNode(sku)); });
    }

    els.hints.innerHTML = '';
    hints().forEach(function (h) {
      var d = document.createElement('div');
      d.className = 'hint' + (h.win ? ' hint--win' : '');
      d.innerHTML = '<span class="hint__ico">' + (h.win ? '✓' : '→') + '</span><span>' +
                    h.html + '</span>';
      els.hints.appendChild(d);
    });

    var t = totals();
    els.cta.hidden = t.count === 0;
    els.save.hidden = t.save <= 0;
    els.saveVal.textContent = '−' + money(t.save);
    els.total.textContent = money(t.sum);
  }

  // ── общий рендер ───────────────────────────────────────────────────────────

  function render() {
    var t = totals();

    renderCells();

    els.bar.classList.toggle('is-empty', t.count === 0);
    els.count.textContent = t.count;
    els.label.textContent = plural(t.count, 'позиция', 'позиции', 'позиций');
    els.sum.textContent = money(t.sum);

    var hs = hints();
    els.barHint.hidden = !hs.length;
    document.body.classList.toggle('has-hint', hs.length > 0);
    if (hs.length) els.barHint.innerHTML = hs[0].html;

    if (els.hint) els.hint.style.display = t.count > 0 ? 'none' : '';

    if (!els.sheet.hidden) renderSheet();
  }

  function openSheet() {
    els.sheet.hidden = false;
    document.documentElement.style.overflow = 'hidden';
    renderSheet();
  }

  function closeSheet() {
    els.sheet.hidden = true;
    document.documentElement.style.overflow = '';
  }

  // ── подсказка на первом ценовом слайде ─────────────────────────────────────

  function mountHint() {
    var first = document.querySelector('.is-buy');
    if (!first) return;
    var card = first.closest('.card');
    var head = card && card.querySelector('.head');
    if (!head) return;
    var hint = document.createElement('div');
    hint.className = 'buyhint';
    hint.innerHTML = 'Нажмите <b>+</b> у позиции — она уйдёт в заказ';
    head.insertAdjacentElement('afterend', hint);
    els.hint = hint;
  }

  // ── инициализация ──────────────────────────────────────────────────────────

  function init() {
    els = {
      bar: document.getElementById('cartbar'),
      barHint: document.getElementById('cartBarHint'),
      count: document.getElementById('cartCount'),
      label: document.getElementById('cartLabel'),
      sum: document.getElementById('cartSum'),
      sheet: document.getElementById('cartSheet'),
      lines: document.getElementById('cartLines'),
      hints: document.getElementById('cartHints'),
      save: document.getElementById('cartSave'),
      cta: document.getElementById('cartCta'),
      saveVal: document.getElementById('cartSaveVal'),
      total: document.getElementById('cartTotal')
    };
    if (!els.bar || !els.sheet) return;

    cells = Array.prototype.slice.call(document.querySelectorAll('.is-buy'));
    ctls = Array.prototype.slice.call(document.querySelectorAll('.buyctl'));

    cells.forEach(function (el) {
      var sku = el.dataset.sku;
      if (!sku || meta[sku]) return;
      meta[sku] = {
        name: el.dataset.name,
        unit: el.dataset.unit,
        price: parseInt(el.dataset.price, 10) || 0,
        kg: parseFloat(el.dataset.kg) || 0,
        accent: el.dataset.accent,
        tiers: el.dataset.tiers
          ? el.dataset.tiers.split(',').map(function (x) { return parseInt(x, 10); })
          : null
      };
    });

    // выкидываем из сохранённого заказа позиции, которых больше нет в прайсе
    for (var sku in state) if (!meta[sku]) delete state[sku];

    document.addEventListener('click', function (e) {
      var btn = e.target.closest && e.target.closest('.buyctl__b');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        var ctl = btn.closest('.buyctl');
        add(ctl.dataset.ctl, btn.classList.contains('buyctl__plus') ? 1 : -1);
        return;
      }
      var cell = e.target.closest && e.target.closest('.is-buy');
      if (cell) {
        e.preventDefault();
        add(cell.dataset.sku, 1);
        cell.classList.remove('is-pop');
        void cell.offsetWidth;
        cell.classList.add('is-pop');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !els.sheet.hidden) closeSheet();
      if ((e.key === 'Enter' || e.key === ' ') && e.target.classList &&
          e.target.classList.contains('is-buy')) {
        e.preventDefault();
        add(e.target.dataset.sku, 1);
      }
    });

    document.getElementById('cartbarOpen').addEventListener('click', openSheet);
    document.getElementById('cartClose').addEventListener('click', closeSheet);
    document.getElementById('cartScrim').addEventListener('click', closeSheet);
    document.getElementById('cartClear').addEventListener('click', clear);

    mountHint();
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
