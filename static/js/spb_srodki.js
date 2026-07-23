/* ===================================================================
   PRZYPADKI UŻYCIA ŚPB — szczegóły środka przymusu bezpośredniego.
   Dane z ustawy o ŚPB i broni palnej. Treść przez textContent.
   =================================================================== */
(function () {
  "use strict";
  var dataEl = document.getElementById("spb-dane");
  if (!dataEl) return;
  var SR = [];
  try { SR = JSON.parse(dataEl.textContent) || []; } catch (e) { return; }

  var modal = document.getElementById("spb-modal");
  var mTytul = document.getElementById("spb-modal-tytul");
  var mBody = document.getElementById("spb-modal-body");

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function sekcja(tytul, items) {
    if (!items || !items.length) return null;
    var s = el("section", "kpj-sekcja");
    s.appendChild(el("h3", null, tytul));
    var ul = document.createElement("ul");
    items.forEach(function (t) { ul.appendChild(el("li", null, t)); });
    s.appendChild(ul);
    return s;
  }
  function poId(id) {
    for (var i = 0; i < SR.length; i++) if (SR[i].id === id) return SR[i];
    return null;
  }

  function otworz(id) {
    var s = poId(id);
    if (!s || !modal) return;
    mTytul.textContent = s.name;
    mBody.innerHTML = "";
    var s1 = sekcja("Przypadki użycia", s.cases); if (s1) mBody.appendChild(s1);
    var s2 = sekcja("Zasady szczególne / wyjątki", s.exceptions); if (s2) mBody.appendChild(s2);
    if (s.legal) {
      var s3 = el("section", "kpj-sekcja");
      s3.appendChild(el("h3", null, "Podstawa prawna"));
      s3.appendChild(el("p", "kpj-podstawa", s.legal));
      mBody.appendChild(s3);
    }
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    var x = modal.querySelector(".kpj-modal-x");
    if (x) x.focus();
  }
  function zamknij() { if (modal) { modal.hidden = true; document.body.style.overflow = ""; } }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".kpj-szczegoly") : null;
    if (btn) { otworz(btn.getAttribute("data-id")); return; }
    if (e.target.closest && e.target.closest("[data-close]")) zamknij();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal && !modal.hidden) zamknij();
  });
})();
