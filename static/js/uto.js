/* ===================================================================
   UTO — hulajnoga elektryczna / urządzenie transportu osobistego /
   urządzenie wspomagające ruch. Szczegóły w modalu.
   Dane z pliku JSON (PRD + ustawa o kierujących pojazdami).
   Treść wstawiana przez textContent — bez surowego HTML.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("uto-dane");
  if (!dataEl) return;
  var URZ = [];
  try { URZ = JSON.parse(dataEl.textContent) || []; } catch (e) { return; }

  var modal = document.getElementById("uto-modal");
  var mTytul = document.getElementById("uto-modal-tytul");
  var mBody = document.getElementById("uto-modal-body");

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function lista(items) {
    var ul = document.createElement("ul");
    items.forEach(function (t) { ul.appendChild(el("li", null, t)); });
    return ul;
  }
  function sekcja(tytul, items) {
    if (!items || !items.length) return null;
    var s = el("section", "kpj-sekcja");
    s.appendChild(el("h3", null, tytul));
    s.appendChild(lista(items));
    return s;
  }

  function poId(id) {
    for (var i = 0; i < URZ.length; i++) if (URZ[i].id === id) return URZ[i];
    return null;
  }

  function otworz(id) {
    var u = poId(id);
    if (!u || !modal) return;
    mTytul.textContent = u.name;
    mBody.innerHTML = "";

    var defS = el("section", "kpj-sekcja");
    defS.appendChild(el("h3", null, "Definicja"));
    defS.appendChild(el("p", null, u.definition));
    mBody.appendChild(defS);

    [["Uprawnienia", u.uprawnienia],
     ["Poruszanie się", u.poruszanie],
     ["Prędkość", u.predkosc],
     ["Zabrania się", u.zabrania],
     ["Zachowanie wobec pieszego", u.pieszy],
     ["Postój", u.postoj]].forEach(function (p) {
      var s = sekcja(p[0], p[1]);
      if (s) mBody.appendChild(s);
    });

    modal.hidden = false;
    document.body.style.overflow = "hidden";
    var x = modal.querySelector(".kpj-modal-x");
    if (x) x.focus();
  }
  function zamknij() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = "";
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".kpj-szczegoly") : null;
    if (btn) { otworz(btn.getAttribute("data-id")); return; }
    if (e.target.closest && e.target.closest("[data-close]")) zamknij();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal && !modal.hidden) zamknij();
  });
})();
