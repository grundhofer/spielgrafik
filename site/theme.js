(function () {
  'use strict';
  // Übernommen aus bildsprache/web/theme.js (dort aus Designsprache), eigener Speicherschlüssel.
  // Ab hier gilt die Seite als skriptfähig: Schalter und Filter erscheinen ohne Layoutsprung (site.css .js).
  document.documentElement.classList.add('js');
  var KEY = 'spielgrafik.theme';
  var preference = 'system';
  function normalize(value) { return ['light', 'dark'].includes(value) ? value : 'system'; }
  function readPreference() {
    try { return normalize(window.localStorage.getItem(KEY)); }
    catch (error) { return preference; }
  }
  function apply(value) {
    preference = normalize(value);
    // Steht das Attribut auf "system", folgt das CSS live der Systemeinstellung.
    document.documentElement.dataset.theme = preference;
    document.querySelectorAll('[data-theme-choice]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === preference));
    });
  }
  // Läuft im head, vor dem ersten Zeichnen.
  apply(readPreference());
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-theme-controls]').forEach(function (group) { group.hidden = false; });
    document.querySelectorAll('[data-theme-choice]').forEach(function (button) {
      button.addEventListener('click', function () {
        apply(button.dataset.themeChoice);
        try { window.localStorage.setItem(KEY, preference); } catch (error) { /* Umschalten geht trotzdem. */ }
      });
    });
    apply(preference);
  });
  // Offene Tabs und Seiten aus dem Zurück-Cache synchron halten.
  window.addEventListener('storage', function (event) {
    if (event.key !== KEY && event.key !== null) return;
    if (event.storageArea && event.storageArea !== window.localStorage) return;
    apply(event.newValue);
  });
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) apply(readPreference());
  });
})();
