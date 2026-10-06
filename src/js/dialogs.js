"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.dialogs — a question that needs an answer before anything happens.

  The app's own sheet rather than window.confirm: the engine's confirm is a
  plain system box with the page's address for a title, and it stops every
  timer on the page while it is up (the companion's pings included).
*/
Cmdly.dialogs = (function () {
  /**
   * Ask. Resolves true for the confirming button, false for anything else
   * (Cancel, Escape, a click beside the sheet).
   * opts: {title, text, confirm: "Delete", danger: true}
   */
  function confirm(opts) {
    const ui = Cmdly.ui;
    const o = opts || {};
    return new Promise((resolve) => {
      let answer = false;
      const body = document.createElement("div");
      body.className = "confirm-text";
      String(o.text || "").split("\n\n").forEach((para) => {
        const p = document.createElement("p");
        p.textContent = para;
        body.appendChild(p);
      });
      const yes = ui.button({
        variant: o.danger ? "danger" : "primary",
        label: o.confirm || "OK",
        onClick: () => { answer = true; dialog.close(); },
      });
      const no = ui.button({ variant: "secondary", label: "Cancel", onClick: () => dialog.close() });
      const dialog = ui.modal({
        title: o.title || "Are you sure?", size: "sm", body,
        actions: [no, yes],
        onClose: () => resolve(answer),
      });
      dialog.el.classList.add("confirm-overlay");
      dialog.open();
      setTimeout(() => yes.focus(), 0);
    });
  }

  return { confirm };
})();
