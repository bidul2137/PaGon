// Na biezaco aktualizuje DATA / GODZINA w pasku statusu (jesli sa na stronie).
(function () {
  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function tick() {
    var now = new Date();
    var dataEl = document.getElementById("live-data");
    var godzinaEl = document.getElementById("live-godzina");

    if (dataEl) {
      dataEl.textContent =
        pad(now.getDate()) + "." + pad(now.getMonth() + 1) + "." + now.getFullYear();
    }
    if (godzinaEl) {
      godzinaEl.textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
    }
  }

  tick();
  setInterval(tick, 1000);
})();
