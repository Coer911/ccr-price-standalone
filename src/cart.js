/* ═══════════════════════════════════════════════════════════════════════════
   КОРЗИНА ПРАЙСА CULTURA COFFEE
   Тап по оптовой цене — позиция уходит в заказ.
   Ступень опта по эспрессо считается от суммарного веса кофе в заказе.
   Данные читаются из data-атрибутов разметки, внешних запросов нет.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var STORE_KEY = 'ccr-cart-v1';
  var FREE_DELIVERY = 6000;      // ₽, слайд «Условия заказа»
  var TIERS = [0, 20, 50];       // кг: 1–19 / 20–49 / от 50

  var state = load();
  var els = {};
  var nodes = [];                // все кликабельные ячейки
  var bySku = {};                // sku -> [ячейки]
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

  function tierIndex() {
    var kg = coffeeKg();
    if (kg >= TIERS[2]) return 2;
    if (kg >= TIERS[1]) return 1;
    return 0;
  }

  function unitPrice(sku) {
    var m = meta[sku];
    if (!m) return 0;
    if (m.tiers) return m.tiers[tierIndex()];
    return m.price;
  }

  function totals() {
    var sum = 0, count = 0;
    for (var sku in state) {
      var q = state[sku];
      if (!q || !meta[sku]) continue;
      sum += q * unitPrice(sku);
      count += 1;
    }
    return { sum: sum, count: count };
  }

  // ── изменение количества ───────────────────────────────────────────────────

  function add(sku, delta) {
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

  // ── отрисовка ──────────────────────────────────────────────────────────────

  function renderBadges() {
    var ti = tierIndex();
    var kg = coffeeKg();

    nodes.forEach(function (el) {
      var sku = el.dataset.sku;
      var q = state[sku] || 0;
      var isTiered = el.dataset.tiers != null;
      var tier = isTiered ? parseInt(el.dataset.tier, 10) : -1;

      // подсветка действующей ступени опта
      if (isTiered) {
        el.classList.toggle('is-live', kg > 0 && tier === ti);
      }

      // значок с количеством: у эспрессо — только на действующей ступени
      var show = q > 0 && (!isTiered || tier === ti);
      var badge = el.querySelector('.qty');
      if (show) {
        if (!badge) {
          badge = document.createElement('span');
          badge.className = 'qty' + (el.dataset.accent === 'tea' ? ' qty--tea' : '');
          badge.setAttribute('role', 'button');
          badge.setAttribute('aria-label', 'Убрать одну единицу');
          el.appendChild(badge);
        }
        badge.textContent = q;
      } else if (badge) {
        badge.remove();
      }
    });
  }

  function hints() {
    var list = [];
    var t = totals();
    var kg = coffeeKg();
    var ti = tierIndex();

    // ступень опта по кофе
    if (kg > 0 && ti < 2) {
      var need = TIERS[ti + 1] - kg;
      list.push({
        win: false,
        html: 'Ещё <b>' + kgFmt(need) + ' кг</b> кофе — и весь эспрессо уйдёт на ступень «' +
              (ti === 0 ? '20–49 кг' : 'от 50 кг') + '»'
      });
    } else if (kg >= TIERS[2]) {
      list.push({ win: true, html: 'В заказе <b>' + kgFmt(kg) + ' кг</b> кофе — действует лучшая цена «от 50 кг»' });
    }

    // бесплатная доставка
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

  function renderSheet() {
    var body = els.lines;
    body.innerHTML = '';

    var skus = Object.keys(state).filter(function (s) { return state[s] > 0 && meta[s]; });
    if (!skus.length) {
      body.innerHTML = '<div class="sheet__empty">Заказ пуст.<br>Коснитесь оптовой цены, чтобы добавить позицию.</div>';
    } else {
      skus.forEach(function (sku) {
        var m = meta[sku], q = state[sku], p = unitPrice(sku);

        var line = document.createElement('div');
        line.className = 'line';

        var main = document.createElement('div');
        main.className = 'line__main';
        var name = document.createElement('div');
        name.className = 'line__name';
        name.textContent = m.name;
        var metaEl = document.createElement('div');
        metaEl.className = 'line__meta';
        metaEl.innerHTML = '<span class="line__dot' + (m.accent === 'tea' ? ' line__dot--tea' : '') +
                           '"></span>' + m.unit + ' · ' + money(p);
        main.appendChild(name);
        main.appendChild(metaEl);

        var step = document.createElement('div');
        step.className = 'step';
        var minus = document.createElement('button');
        minus.className = 'step__btn';
        minus.type = 'button';
        minus.textContent = '−';
        minus.setAttribute('aria-label', 'Убрать одну единицу');
        minus.addEventListener('click', function () { add(sku, -1); });
        var val = document.createElement('span');
        val.className = 'step__val';
        val.textContent = q;
        var plus = document.createElement('button');
        plus.className = 'step__btn';
        plus.type = 'button';
        plus.textContent = '+';
        plus.setAttribute('aria-label', 'Добавить одну единицу');
        plus.addEventListener('click', function () { add(sku, 1); });
        step.appendChild(minus);
        step.appendChild(val);
        step.appendChild(plus);

        var sum = document.createElement('div');
        sum.className = 'line__sum';
        sum.textContent = money(q * p);

        line.appendChild(main);
        line.appendChild(step);
        line.appendChild(sum);
        body.appendChild(line);
      });
    }

    els.hints.innerHTML = '';
    hints().forEach(function (h) {
      var d = document.createElement('div');
      d.className = 'hint' + (h.win ? ' hint--win' : '');
      d.innerHTML = '<span class="hint__ico">' + (h.win ? '✓' : '→') + '</span><span>' + h.html + '</span>';
      els.hints.appendChild(d);
    });

    els.total.textContent = money(totals().sum);
  }

  function render() {
    var t = totals();

    renderBadges();

    if (t.count > 0) {
      els.bar.hidden = false;
      document.body.classList.add('has-cart');
      els.count.textContent = t.count;
      els.label.textContent = plural(t.count, 'позиция', 'позиции', 'позиций');
      els.sum.textContent = money(t.sum);

      var hs = hints();
      els.barHint.hidden = !hs.length;
      document.body.classList.toggle('has-hint', hs.length > 0);
      if (hs.length) els.barHint.innerHTML = hs[0].html;
    } else {
      els.bar.hidden = true;
      els.barHint.hidden = true;
      document.body.classList.remove('has-cart');
      document.body.classList.remove('has-hint');
      closeSheet();
    }

    if (els.hint) els.hint.style.display = t.count > 0 ? 'none' : '';

    if (!els.sheet.hidden) renderSheet();
  }

  // ── панель ─────────────────────────────────────────────────────────────────

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
    if (!card) return;
    var head = card.querySelector('.head');
    if (!head) return;
    var hint = document.createElement('div');
    hint.className = 'buyhint';
    hint.innerHTML = 'Коснитесь <b>оптовой цены</b> — позиция уйдёт в заказ';
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
      total: document.getElementById('cartTotal')
    };
    if (!els.bar || !els.sheet) return;

    nodes = Array.prototype.slice.call(document.querySelectorAll('.is-buy'));
    nodes.forEach(function (el) {
      var sku = el.dataset.sku;
      if (!sku) return;
      (bySku[sku] = bySku[sku] || []).push(el);
      if (!meta[sku]) {
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
      }
    });

    // чистим состояние от позиций, которых больше нет в прайсе
    for (var sku in state) if (!meta[sku]) delete state[sku];

    document.addEventListener('click', function (e) {
      var badge = e.target.closest && e.target.closest('.qty');
      if (badge) {
        e.preventDefault();
        e.stopPropagation();
        var host = badge.closest('.is-buy');
        if (host) add(host.dataset.sku, -1);
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
      if ((e.key === 'Enter' || e.key === ' ') &&
          e.target.classList && e.target.classList.contains('is-buy')) {
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
