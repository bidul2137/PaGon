/* ===================================================================
   KATEGORIE PRAWA JAZDY — szczegóły kategorii + tryb "co daje kierowcy"
   Dane wyłącznie z pliku JSON (art. 6 i art. 8 ustawy o kierujących
   pojazdami). Treści wstawiane przez textContent — bez surowego HTML.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("kpj-dane");
  if (!dataEl) return;
  var KAT = [];
  try { KAT = JSON.parse(dataEl.textContent) || []; } catch (e) { return; }

  function poId(id) {
    for (var i = 0; i < KAT.length; i++) if (KAT[i].id === id) return KAT[i];
    return null;
  }
  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function sekcja(tytul, budujTresc) {
    var s = el("section", "kpj-sekcja");
    s.appendChild(el("h3", null, tytul));
    budujTresc(s);
    return s;
  }
  function lista(items) {
    var ul = document.createElement("ul");
    items.forEach(function (t) { ul.appendChild(el("li", null, t)); });
    return ul;
  }

  // ---------- Modal ----------
  var modal = document.getElementById("kpj-modal");
  var mBadge = document.getElementById("kpj-modal-badge");
  var mTytul = document.getElementById("kpj-modal-tytul");
  var mBody = document.getElementById("kpj-modal-body");

  function otworz(id) {
    var k = poId(id);
    if (!k || !modal) return;
    mBadge.textContent = k.category;
    mTytul.textContent = k.title;
    mBody.innerHTML = "";

    if (k.permissions && k.permissions.length) {
      mBody.appendChild(sekcja("Uprawnia do kierowania", function (s) { s.appendChild(lista(k.permissions)); }));
    }
    if (k.limits && k.limits.length) {
      mBody.appendChild(sekcja("Najważniejsze limity", function (s) { s.appendChild(lista(k.limits)); }));
    }
    mBody.appendChild(sekcja("Minimalny wiek", function (s) {
      s.appendChild(el("p", null, k.minimum_age));
      if (k.minimum_age_notes && k.minimum_age_notes.length) s.appendChild(lista(k.minimum_age_notes));
    }));
    if (k.includes && k.includes.length) {
      mBody.appendChild(sekcja("Obejmuje również", function (s) { s.appendChild(lista(k.includes)); }));
    }
    if (k.exclusions && k.exclusions.length) {
      mBody.appendChild(sekcja("Nie obejmuje", function (s) { s.appendChild(lista(k.exclusions)); }));
    }
    if (k.notes && k.notes.length) {
      mBody.appendChild(sekcja("Uwagi", function (s) { s.appendChild(lista(k.notes)); }));
    }
    if (k.traps && k.traps.length) {
      mBody.appendChild(sekcja("Uwaga — częste wyjątki", function (s) {
        k.traps.forEach(function (t) {
          var box = el("div", "kpj-trap");
          box.appendChild(el("span", "kpj-trap-t", t.t));
          box.appendChild(el("span", "kpj-trap-d", t.d));
          box.appendChild(el("span", "kpj-trap-p", t.p));
          s.appendChild(box);
        });
      }));
    }
    mBody.appendChild(sekcja("Podstawa prawna", function (s) {
      s.appendChild(el("p", "kpj-podstawa", k.legal_basis));
      if (k.legal_text) {
        var btn = el("button", "kpj-przepis-btn", "Pokaż przepis");
        btn.type = "button";
        btn.setAttribute("aria-expanded", "false");
        var box = el("div", "kpj-przepis", k.legal_text);
        box.hidden = true;
        btn.addEventListener("click", function () {
          var open = box.hidden;
          box.hidden = !open;
          btn.setAttribute("aria-expanded", open ? "true" : "false");
          btn.textContent = open ? "Ukryj przepis" : "Pokaż przepis";
        });
        s.appendChild(btn);
        s.appendChild(box);
      }
    }));

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

  // ---------- Tryb "co daje kierowcy" ----------
  var toggle = document.getElementById("kpj-tryb-toggle");
  var panel = document.getElementById("kpj-tryb-panel");
  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      var open = panel.hidden;
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // rozszerzenia z art. 6 ust. 1 pkt 15 i 16
  function pochodne(sel) {
    function ma(c) { return sel.indexOf(c) !== -1; }
    var extra = [];
    if (ma("B") && !ma("B+E") && (ma("C1+E") || ma("D1+E") || ma("C+E") || ma("D+E"))) {
      extra.push({ kat: "B+E", pod: "art. 6 ust. 1 pkt 15" });
    }
    if (ma("C+E") && ma("D") && !ma("D+E")) {
      extra.push({ kat: "D+E", pod: "art. 6 ust. 1 pkt 16" });
    }
    return extra;
  }

  var wynik = document.getElementById("kpj-tryb-wynik");
  var checki = Array.prototype.slice.call(document.querySelectorAll(".kpj-chip-input"));
  var poleWiek = document.getElementById("kpj-wiek");
  var poleKody = document.getElementById("kpj-kody");
  var KODY = {};
  var kodyEl = document.getElementById("kpj-kody-dane");
  if (kodyEl) { try { KODY = JSON.parse(kodyEl.textContent) || {}; } catch (e) { KODY = {}; } }

  // rozpoznaje kody wpisane po przecinku/spacji, w tym subkody typu 01.02
  function parsujKody(txt) {
    if (!txt) return [];
    var out = [];
    (txt.match(/\d{1,3}(?:\.\d{1,2})?/g) || []).forEach(function (t) {
      if (out.indexOf(t) === -1) out.push(t);
    });
    return out;
  }
  var orzCheck = Array.prototype.slice.call(document.querySelectorAll(".kpj-orz"));
  var poleOrzInne = document.getElementById("kpj-orz-inne");

  function kat(c) {
    for (var i = 0; i < KAT.length; i++) if (KAT[i].category === c) return KAT[i];
    return null;
  }

  function przelicz() {
    if (!wynik) return;
    var sel = checki.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    var wiek = poleWiek && poleWiek.value !== "" ? parseInt(poleWiek.value, 10) : null;
    if (isNaN(wiek)) wiek = null;
    var kody = parsujKody(poleKody ? poleKody.value : "");
    var kod96 = kody.indexOf("96") !== -1;
    var orz = orzCheck.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    var orzInne = poleOrzInne ? poleOrzInne.value.trim() : "";
    if (orzInne) orz.push(orzInne);

    wynik.innerHTML = "";
    if (!sel.length && !kody.length && !orz.length && wiek === null) return;

    // --- blokada: orzeczenia / decyzje ---
    if (orz.length) {
      var b = el("div", "kpj-blok");
      b.appendChild(el("strong", null, "Uwaga — wskazano orzeczenie lub decyzję"));
      b.appendChild(el("p", null,
        "Zakres uprawnień poniżej może być wyłączony lub ograniczony. Zweryfikuj stan uprawnień w ewidencji przed oceną: " +
        orz.join("; ") + "."));
      wynik.appendChild(b);
    }

    var extra = pochodne(sel);
    var wszystkie = sel.concat(extra.map(function (x) { return x.kat; }));

    // --- podsumowanie: kategorie uwzględnione ---
    if (wszystkie.length) {
      var sChip = el("section");
      sChip.appendChild(el("h3", null, "Kategorie uwzględnione"));
      var row = el("div", "kpj-wynik-katy");
      sel.forEach(function (c) { row.appendChild(el("span", "kpj-kat-chip", c)); });
      extra.forEach(function (x) {
        var ch = el("span", "kpj-kat-chip kpj-kat-chip--extra", x.kat);
        ch.title = "Wynika z posiadanych kategorii (" + x.pod + ")";
        row.appendChild(ch);
      });
      sChip.appendChild(row);
      wynik.appendChild(sChip);
    }

    if (extra.length) {
      var s1 = el("section");
      s1.appendChild(el("h3", null, "Dodatkowo z posiadanych kategorii"));
      s1.appendChild(lista(extra.map(function (x) {
        return "Kategoria " + x.kat + " — wynika z posiadanych kategorii (" + x.pod + ").";
      })));
      wynik.appendChild(s1);
    }

    // --- ocena wieku ---
    if (wiek !== null && !wszystkie.length) {
      wynik.appendChild(el("p", "kpj-tryb-pusto",
        "Zaznacz kategorie z prawa jazdy, aby ocenić wiek i zobaczyć zakres uprawnień."));
    }
    if (wiek !== null && wszystkie.length) {
      var s0 = el("section");
      s0.appendChild(el("h3", null, "Wiek kierowcy: " + wiek + " lat — ocena"));
      var ul = document.createElement("ul");
      wszystkie.forEach(function (c) {
        var k = kat(c); if (!k) return;
        var li = document.createElement("li");
        if (wiek >= k.min_age_years) {
          li.className = "kpj-ok";
          li.textContent = c + " — spełnia wiek podstawowy (" + k.min_age_years + " lat).";
        } else if (wiek >= k.min_age_lowest) {
          li.className = "kpj-warn";
          li.textContent = c + " — poniżej wieku podstawowego (" + k.min_age_years +
            " lat); dopuszczalne wyłącznie przy udokumentowanym wyjątku (od " + k.min_age_lowest + " lat) — sprawdź uwagi w szczegółach kategorii.";
        } else {
          li.className = "kpj-bad";
          li.textContent = c + " — nie spełnia wymaganego wieku (minimum " + k.min_age_lowest +
            " lat nawet przy wyjątku).";
        }
        ul.appendChild(li);
      });
      s0.appendChild(ul);
      if (wiek === 17 && sel.indexOf("B") !== -1) {
        s0.appendChild(el("p", "kpj-warn",
          "Kategoria B w wieku 17 lat: uprawnia wyłącznie na terytorium RP do ukończenia 18 lat oraz — w pojeździe innym niż czterokołowiec — tylko z pasażerem spełniającym wymagania (art. 8a)."));
      }
      wynik.appendChild(s0);
    }

    // --- wpisy i kody ---
    if (kody.length || sel.indexOf("B") !== -1) {
      var sk = el("section");
      sk.appendChild(el("h3", null, "Wpisy i kody"));
      var lk = [];
      kody.forEach(function (c) {
        lk.push(KODY[c]
          ? "Kod " + c + " — " + KODY[c] + "."
          : "Kod " + c + " — nieznany w wykazie; zweryfikuj w dokumencie.");
      });
      if (sel.indexOf("B") !== -1) {
        lk.push(kod96
          ? "Skutek kodu 96: zespół kat. B z przyczepą inną niż lekka o DMC zespołu powyżej 3,5 t do 4,25 t jest dozwolony (art. 6 ust. 2)."
          : "Brak kodu 96 — zespół kat. B o DMC powyżej 3,5 t jest niedozwolony; dopuszczalny tylko zespół do 3,5 t (art. 6 ust. 1 pkt 6 lit. c w zw. z ust. 2).");
      }
      sk.appendChild(lista(lk));
      wynik.appendChild(sk);
    }

    // --- łączny zakres (pogrupowany po kategoriach) ---
    if (wszystkie.length) {
      var s2 = el("section");
      s2.appendChild(el("h3", null, "Łączny zakres uprawnień"));
      wszystkie.forEach(function (c) {
        var k = kat(c); if (!k) return;
        var sub = el("p", "kpj-zakres-kat");
        sub.appendChild(el("span", "kpj-zakres-badge", k.category));
        sub.appendChild(document.createTextNode(k.short_description || ""));
        s2.appendChild(sub);
        s2.appendChild(lista((k.permissions || []).concat(k.includes || [])));
      });
      wynik.appendChild(s2);

      wynik.appendChild(el("p", "kpj-tryb-pusto",
        "Zestawienie pomocnicze. Nie uwzględnia daty uzyskania uprawnień (staż wymagany m.in. dla motocykla 125 i paliw alternatywnych) ani ważności dokumentu i badań — zweryfikuj w ewidencji."));
    } else if (kody.length && wiek === null) {
      wynik.appendChild(el("p", "kpj-tryb-pusto",
        "Zaznacz kategorie z prawa jazdy, aby zobaczyć łączny zakres uprawnień."));
    }
  }

  var btnReset = document.getElementById("kpj-reset");
  if (btnReset) {
    btnReset.addEventListener("click", function () {
      checki.forEach(function (c) { c.checked = false; });
      orzCheck.forEach(function (c) { c.checked = false; });
      if (poleWiek) poleWiek.value = "";
      if (poleKody) poleKody.value = "";
      if (poleOrzInne) poleOrzInne.value = "";
      przelicz();
    });
  }

  checki.forEach(function (c) { c.addEventListener("change", przelicz); });
  orzCheck.forEach(function (c) { c.addEventListener("change", przelicz); });
  if (poleWiek) poleWiek.addEventListener("input", przelicz);
  if (poleKody) poleKody.addEventListener("input", przelicz);
  if (poleOrzInne) poleOrzInne.addEventListener("input", przelicz);
  przelicz();
})();
