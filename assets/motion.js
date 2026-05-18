/* Spark Console motion — vanilla JS, no deps.
 * Three responsibilities:
 *   1. Hero numeral count-up (0 → N) + regression-band wipe
 *   2. Stagger-reveal trigger for [data-stagger] containers via IntersectionObserver
 *   3. Kanban filter chips — blur+desaturate non-matching tickets (preserves spatial memory)
 *
 * All motion respects prefers-reduced-motion. Total: well under 100 LOC.
 */
(function () {
  'use strict';

  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── 1. Hero count-up + regression-band wipe ───────────────────────────────
  function countUp(el) {
    var target = parseInt(el.getAttribute('data-countup'), 10);
    if (isNaN(target)) return;
    if (prefersReduced) { el.textContent = String(target); return; }
    var duration = 800;
    var start = null;
    function tick(ts) {
      if (start === null) start = ts;
      var progress = Math.min(1, (ts - start) / duration);
      var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      el.textContent = String(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function wipeRegressionBand() {
    var band = document.querySelector('.hero-band-wipe');
    if (!band) return;
    if (prefersReduced) { band.setAttribute('data-wiped', ''); return; }
    // Fire after the count-up settles
    setTimeout(function () { band.setAttribute('data-wiped', ''); }, 600);
  }

  // ── 2. Stagger reveal — flip data-revealed on intersection ────────────────
  function observeStagger() {
    var groups = document.querySelectorAll('[data-stagger]');
    if (!groups.length) return;
    if (prefersReduced) {
      groups.forEach(function (g) { g.setAttribute('data-revealed', ''); });
      return;
    }
    if (!('IntersectionObserver' in window)) {
      groups.forEach(function (g) { g.setAttribute('data-revealed', ''); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.setAttribute('data-revealed', '');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.05, rootMargin: '0px 0px -10% 0px' });
    groups.forEach(function (g) { io.observe(g); });
  }

  // ── 3. Kanban filter — blur+desaturate non-matching, not display:none ─────
  function bindKanbanFilters() {
    var chips = document.querySelectorAll('.filter-chip[data-source]');
    if (!chips.length) return;
    var active = new Set();
    chips.forEach(function (chip) {
      if (chip.getAttribute('data-active') === 'true') active.add(chip.getAttribute('data-source'));
      chip.addEventListener('click', function () {
        var source = chip.getAttribute('data-source');
        if (active.has(source)) active.delete(source); else active.add(source);
        chip.setAttribute('data-active', active.has(source) ? 'true' : 'false');
        applyFilter();
      });
    });
    function applyFilter() {
      var tickets = document.querySelectorAll('.ticket[data-source]');
      var anyActive = active.size > 0;
      tickets.forEach(function (t) {
        var match = !anyActive || active.has(t.getAttribute('data-source'));
        t.classList.toggle('filtered-out', !match);
      });
    }
  }

  function init() {
    document.querySelectorAll('[data-countup]').forEach(countUp);
    wipeRegressionBand();
    observeStagger();
    bindKanbanFilters();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
