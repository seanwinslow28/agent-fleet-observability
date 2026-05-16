// Filter chip toggle for the kanban board. Vanilla JS, no framework.
(function () {
  'use strict';
  function init() {
    var chips = document.querySelectorAll('.filter-chip');
    var tickets = document.querySelectorAll('.ticket');
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var nowActive = chip.getAttribute('data-active') !== 'true';
        chip.setAttribute('data-active', nowActive ? 'true' : 'false');
        applyFilter();
      });
    });

    function applyFilter() {
      var enabled = {};
      chips.forEach(function (c) {
        enabled[c.getAttribute('data-source')] = c.getAttribute('data-active') === 'true';
      });
      tickets.forEach(function (t) {
        var src = t.getAttribute('data-source');
        if (enabled[src] === false) {
          t.classList.add('hidden');
        } else {
          t.classList.remove('hidden');
        }
      });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
