/* Spielgrafik – Seitenverhalten. Ohne Abhängigkeiten; jede Funktion prüft, ob ihre Elemente existieren.
   Ohne JavaScript bleibt alles lesbar: Karten in Katalogreihenfolge, Tabelle nach Familie, Videos mit Bedienelementen. */
(function () {
  'use strict';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var canHover = window.matchMedia('(hover: hover) and (pointer: fine)');

  document.querySelectorAll('[data-needs-js]').forEach(function (el) { el.hidden = false; });

  /* ---------- Videos in Karten: Hover/Fokus spielt ab, auf Touch-Geräten Antippen ---------- */
  var current = null;
  function stop(card) {
    var v = card.querySelector('video');
    if (v && !v.paused) v.pause();
    card.classList.remove('playing');
    if (current === card) current = null;
  }
  function play(card, explicit) {
    var v = card.querySelector('video');
    if (!v) return;
    if (reduceMotion.matches && !explicit) return;
    if (current && current !== card) stop(current);
    current = card;
    var p = v.play();
    if (p && p.catch) p.catch(function () { card.classList.remove('playing'); });
  }
  document.querySelectorAll('.card[data-video]').forEach(function (card) {
    var v = card.querySelector('video');
    var media = card.querySelector('.cimg');
    if (!v || !media) return;
    v.addEventListener('playing', function () { card.classList.add('playing'); });
    card.addEventListener('mouseenter', function () { if (canHover.matches) play(card, false); });
    card.addEventListener('mouseleave', function () { if (canHover.matches) stop(card); });
    card.addEventListener('focusin', function () { play(card, false); });
    card.addEventListener('focusout', function (ev) { if (!card.contains(ev.relatedTarget)) stop(card); });
    media.addEventListener('click', function (ev) {
      if (canHover.matches) return;          // Maus: Klick öffnet den Eintrag
      ev.preventDefault();                   // Touch: Antippen spielt ab oder hält an
      if (v.paused) play(card, true); else stop(card);
    });
  });

  /* ---------- Startseite: Filter und Sortierung ---------- */
  var cat = document.querySelector('[data-catalog]');
  if (cat) {
    var grid = cat.querySelector('.cat-grid');
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
    var heads = Array.prototype.slice.call(grid.querySelectorAll('.fam-h'));
    var tally = cat.querySelector('[data-tally]');
    var none = cat.querySelector('[data-none]');
    var select = cat.querySelector('[data-sort]');
    var state = { fam: '*', kind: '*', status: '*', sort: 'family' };
    var DESC = { text_adventure: true, ai_fit: true, effort: false };

    function rating(card, key) {
      var v = card.getAttribute('data-r-' + key);
      return v ? Number(v) : null;
    }
    function order(card) { return Number(card.dataset.order); }
    function compare(a, b) {
      var key = state.sort;
      if (key === 'name') return a.dataset.name.localeCompare(b.dataset.name, 'de') || order(a) - order(b);
      if (key in DESC) {
        var ra = rating(a, key), rb = rating(b, key);
        if (ra === null && rb !== null) return 1;     // ohne Bewertung ans Ende
        if (rb === null && ra !== null) return -1;
        if (ra !== rb) return DESC[key] ? rb - ra : ra - rb;
      }
      return order(a) - order(b);
    }
    function update() {
      var shown = 0;
      cards.forEach(function (c) {
        var on = (state.fam === '*' || c.dataset.fam === state.fam) &&
                 (state.kind === '*' || c.dataset.kind === state.kind) &&
                 (state.status === '*' || c.dataset.status === state.status);
        c.hidden = !on;
        if (on) shown++;
      });
      var sorted = cards.slice().sort(compare);
      if (state.sort === 'family') {
        heads.forEach(function (hd) {
          grid.appendChild(hd);
          var any = false;
          sorted.forEach(function (c) {
            if (c.dataset.fam !== hd.dataset.fam) return;
            grid.appendChild(c);
            if (!c.hidden) any = true;
          });
          hd.hidden = !any;
        });
      } else {
        heads.forEach(function (hd) { hd.hidden = true; });
        sorted.forEach(function (c) { grid.appendChild(c); });
      }
      if (tally) tally.textContent = shown + ' von ' + cards.length + (cards.length === 1 ? ' Eintrag' : ' Einträgen');
      if (none) none.hidden = shown > 0;
    }
    cat.querySelectorAll('[data-filter-group]').forEach(function (group) {
      group.addEventListener('click', function (ev) {
        var chip = ev.target.closest('[data-value]');
        if (!chip) return;
        state[group.dataset.filterGroup] = chip.dataset.value;
        group.querySelectorAll('[data-value]').forEach(function (c) { c.setAttribute('aria-pressed', String(c === chip)); });
        update();
      });
    });
    if (select) select.addEventListener('change', function () { state.sort = select.value; update(); });
    update();
  }

  /* ---------- Vergleich: sortierbare Tabelle ---------- */
  document.querySelectorAll('table[data-sortable]').forEach(function (table) {
    var body = table.tBodies[0];
    var ths = Array.prototype.slice.call(table.tHead.rows[0].cells);
    ths.forEach(function (th, col) {
      var button = th.querySelector('button');
      if (!button) return;
      button.addEventListener('click', function () {
        var numeric = th.dataset.type === 'num';
        var dir = th.getAttribute('aria-sort') === (numeric ? 'descending' : 'ascending')
          ? (numeric ? 'ascending' : 'descending') : (numeric ? 'descending' : 'ascending');
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var va = a.cells[col].dataset.v, vb = b.cells[col].dataset.v, r;
          if (numeric) {
            var na = va === '' ? null : Number(va), nb = vb === '' ? null : Number(vb);
            if (na === null || nb === null) return (na === null) - (nb === null) || Number(a.dataset.order) - Number(b.dataset.order);
            r = na - nb;
          } else {
            r = String(va).localeCompare(String(vb), 'de');
          }
          if (dir === 'descending') r = -r;
          return r || Number(a.dataset.order) - Number(b.dataset.order);
        });
        rows.forEach(function (row) { body.appendChild(row); });
        ths.forEach(function (other) { other.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', dir);
      });
    });
  });

  /* ---------- Eintragsseite: Demo startet ohne Ton, wenn Bewegung erwünscht ist ---------- */
  document.querySelectorAll('video[data-autoplay]').forEach(function (v) {
    if (reduceMotion.matches) return;
    var p = v.play();
    if (p && p.catch) p.catch(function () { /* Autoplay blockiert: Bedienelemente bleiben. */ });
  });
})();
