/* ===================================================================
   STATUSY PRAWA JAZDY KSIP — opis statusu i wskazania w modalu.
   Dane z pliku JSON; treść wstawiana przez textContent — bez HTML.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("spj-dane");
  if (!dataEl) return;
  var STATUSY = [];
  try { STATUSY = JSON.parse(dataEl.textContent) || []; } catch (e) { return; }

  var modal = document.getElementById("spj-modal");
  var mBadge = document.getElementById("spj-modal-badge");
  var mTytul = document.getElementById("spj-modal-tytul");
  var mBody = document.getElementById("spj-modal-body");

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function poId(id) {
    for (var i = 0; i < STATUSY.length; i++) if (STATUSY[i].id === id) return STATUSY[i];
    return null;
  }

  function otworz(id) {
    var s = poId(id);
    if (!s || !modal) return;
    mBadge.textContent = s.numer;
    mTytul.textContent = "Status " + s.numer + " — " + s.nazwa;
    mBody.innerHTML = "";

    var op = el("section", "kpj-sekcja");
    op.appendChild(el("h3", null, "Opis statusu"));
    op.appendChild(el("p", null, s.opis));
    mBody.appendChild(op);

    var wsk = el("section", "kpj-sekcja");
    wsk.appendChild(el("h3", null, "Wskazania"));
    var box = el("div", s.typ_wskazania === "zatrzymanie" ? "spj-wskazania spj-wskazania--stop" : "spj-wskazania");
    box.appendChild(el("p", null, s.wskazania));
    wsk.appendChild(box);
    mBody.appendChild(wsk);

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
