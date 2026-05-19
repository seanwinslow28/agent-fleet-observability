// Kanban click-to-modal — vanilla JS, ~40 lines.
// Reads data-* attributes off the clicked ticket; populates the modal; restores
// focus to the originating ticket on close. Escape + backdrop click also close.

(function () {
  "use strict";

  function init() {
    const modal = document.getElementById("ticket-modal");
    if (!modal) return;
    const elHeadline = modal.querySelector("#ticket-modal-headline");
    const elSubheadline = modal.querySelector("#ticket-modal-subheadline");
    const elSource = modal.querySelector("#ticket-modal-source");
    const elDetails = modal.querySelector("#ticket-modal-details");
    let lastTrigger = null;

    function open(ticket) {
      lastTrigger = ticket;
      elHeadline.textContent = ticket.dataset.headline || "";
      elSubheadline.textContent = ticket.dataset.subheadline || "";
      elSource.textContent = ticket.dataset.source || "";
      elDetails.textContent = ticket.dataset.details || "(no details)";
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
      const closeBtn = modal.querySelector(".ticket-modal__close");
      if (closeBtn) closeBtn.focus();
    }

    function close() {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
      if (lastTrigger) {
        lastTrigger.focus();
        lastTrigger = null;
      }
    }

    document.addEventListener("click", function (ev) {
      const ticket = ev.target.closest(".ticket");
      if (ticket) {
        ev.preventDefault();
        open(ticket);
        return;
      }
      if (ev.target.matches("[data-modal-close]")) {
        close();
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !modal.hidden) {
        close();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
