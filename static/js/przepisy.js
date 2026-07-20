/* ===================================================================
   PRZEPISY — dokumenty offline + ulubione (stan w localStorage)
   Kafelki są renderowane przez serwer (wszystkie kategorie). Ten skrypt
   steruje ich widocznością i kolejnością oraz obsługuje modal "Dokumenty
   offline". Pobieranie jest na razie SYMULOWANE (flaga w localStorage) —
   struktura gotowa pod późniejsze realne pobieranie PDF.
   =================================================================== */
(function () {
  "use strict";

  var OFFLINE_KEY = "pagon_przepisy_offline"; // { slug: bool }  (pobrany/offline)
  var FAV_KEY = "pagon_przepisy_ulubione";    // [slug, ...]      (ulubione)

  function readJSON(key, fallback) {
    try { var r = localStorage.getItem(key); return r ? JSON.parse(r) : fallback; }
    catch (e) { return fallback; }
  }
  function writeJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  }

  var offline = readJSON(OFFLINE_KEY, {});
  var fav = readJSON(FAV_KEY, []);
  if (!Array.isArray(fav)) fav = [];
  if (!offline || typeof offline !== "object") offline = {};

  var tilesBox = document.getElementById("prz-tiles");
  var modal = document.getElementById("prz-docs-modal");
  var pdfBtn = document.getElementById("prz-pdf-toggle");

  // Rdzeń = "główna paczka" (pakiet != "dodatkowa"): zawsze offline, nie da się odznaczyć.
  function jestRdzen(pakiet) { return pakiet !== "dodatkowa"; }
  function czyPobrany(slug, pakiet) {
    if (jestRdzen(pakiet)) return true;                  // rdzeń zawsze dostępny offline
    return (slug in offline) ? !!offline[slug] : false;  // dodatkowe: wg localStorage (domyślnie niepobrane)
  }
  function czyUlubiony(slug) { return fav.indexOf(slug) !== -1; }

  // ---------- Kafelki: widoczność + kolejność + gwiazdki ----------
  function odswiezKafelki() {
    if (!tilesBox) return;
    var tiles = Array.prototype.slice.call(tilesBox.querySelectorAll(".prz-tile"));

    tiles.forEach(function (t) {
      var slug = t.getAttribute("data-slug");
      var pak = t.getAttribute("data-pakiet");
      t.hidden = !czyPobrany(slug, pak);

      var star = t.querySelector(".prz-star");
      if (star) {
        var ulub = czyUlubiony(slug);
        var nazwa = t.getAttribute("data-title") || "";
        star.classList.toggle("is-fav", ulub);
        star.setAttribute("aria-pressed", ulub ? "true" : "false");
        star.setAttribute("aria-label",
          (ulub ? "Usuń „" + nazwa + "” z ulubionych" : "Dodaj „" + nazwa + "” do ulubionych"));
      }
    });

    // kolejność: ulubione (alfabetycznie) -> reszta (alfabetycznie)
    function cmp(a, b) {
      return (a.getAttribute("data-title") || "")
        .localeCompare(b.getAttribute("data-title") || "", "pl");
    }
    var widoczne = tiles.filter(function (t) { return !t.hidden; });
    var ukryte = tiles.filter(function (t) { return t.hidden; });
    widoczne.sort(function (a, b) {
      var fa = czyUlubiony(a.getAttribute("data-slug"));
      var fb = czyUlubiony(b.getAttribute("data-slug"));
      if (fa !== fb) return fa ? -1 : 1;
      return cmp(a, b);
    });
    widoczne.concat(ukryte).forEach(function (t) { tilesBox.appendChild(t); });
  }

  // ---------- Akcje ----------
  function toggleUlubiony(slug) {
    var i = fav.indexOf(slug);
    if (i === -1) fav.push(slug); else fav.splice(i, 1);
    writeJSON(FAV_KEY, fav);
    odswiezKafelki();
  }
  function ustawPobrany(slug, val) {
    offline[slug] = !!val;
    writeJSON(OFFLINE_KEY, offline);
    odswiezStatusModal(slug);
    odswiezKafelki();
  }

  // ---------- Modal ----------
  function odswiezStatusModal(slug) {
    if (!modal) return;
    var rows = modal.querySelectorAll(".prz-doc");
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].getAttribute("data-slug") !== slug) continue;
      var row = rows[i];
      var pak = row.getAttribute("data-pakiet");
      var on = czyPobrany(slug, pak);
      var rdzen = jestRdzen(pak);
      var chk = row.querySelector(".prz-doc-check");
      var st = row.querySelector(".prz-doc-status");
      if (chk && !rdzen) chk.checked = on; // rdzeń zostaje checked+disabled (ustawiony w initModal)
      if (st) {
        st.textContent = rdzen ? "W pakiecie — zawsze offline" : (on ? "Dostępny offline" : "Nie pobrany");
        st.classList.toggle("is-on", on);
      }
      return;
    }
  }
  function initModal() {
    if (!modal) return;
    var rows = modal.querySelectorAll(".prz-doc");
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var chk = row.querySelector(".prz-doc-check");
      if (jestRdzen(row.getAttribute("data-pakiet"))) {
        row.classList.add("prz-doc--core");
        if (chk) { chk.checked = true; chk.disabled = true; }
      }
      odswiezStatusModal(row.getAttribute("data-slug"));
    }
    modal.querySelectorAll(".prz-doc-check").forEach(function (chk) {
      if (chk.disabled) return; // rdzeń — bez obsługi zmian
      chk.addEventListener("change", function () {
        ustawPobrany(chk.getAttribute("data-slug"), chk.checked);
      });
    });
    modal.querySelectorAll("[data-close]").forEach(function (el) {
      el.addEventListener("click", zamknijModal);
    });
    var search = document.getElementById("prz-docs-search");
    if (search) search.addEventListener("input", function () { filtrujDokumenty(search.value); });
  }
  // wyszukiwarka w modalu (odporna na brak polskich znaków)
  function bezOgonkow(s) {
    var m = { "ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ż":"z","ź":"z" };
    return String(s).toLowerCase()
      .replace(/[ąćęłńóśźż]/g, function (c) { return m[c]; })
      .replace(/-/g, ""); // usuń myślnik: "B-11" == "B11"
  }
  // "rdzeń" — obcina typowe polskie końcówki fleksyjne (imprez/imprezy/impreza -> imprez)
  var KONCOWKI = ["iami","owie","ego","emu","ami","ach","owi","ymi","imi","ych","ich","ow","om","em","ie","ia","y","i","a","e","u","o"];
  function rdzen(w) {
    for (var k = 0; k < KONCOWKI.length; k++) {
      var e = KONCOWKI[k];
      if (w.length > e.length + 2 && w.slice(-e.length) === e) return w.slice(0, w.length - e.length);
    }
    return w;
  }
  function tokeny(s) {
    return bezOgonkow(s).split(/[^0-9a-z]+/).filter(function (t) { return t.length >= 2; });
  }
  function pasujeTekst(haystack, q) {
    var nq = bezOgonkow(q).trim();
    if (!nq) return true;
    if (bezOgonkow(haystack).indexOf(nq) !== -1) return true;
    var ht = tokeny(haystack).map(rdzen);
    var qt = tokeny(q).map(rdzen);
    if (!qt.length) return false;
    return qt.every(function (qs) {
      return ht.some(function (h) {
        return h === qs || (qs.length >= 3 && h.indexOf(qs) === 0) || (h.length >= 3 && qs.indexOf(h) === 0);
      });
    });
  }
  function filtrujDokumenty(q) {
    if (!modal) return;
    var widocznych = 0;
    modal.querySelectorAll(".prz-doc").forEach(function (row) {
      var title = row.querySelector(".prz-doc-title");
      var badge = row.querySelector(".prz-doc-badge");
      var hay = (title ? title.textContent : "") + " " + (badge ? badge.textContent : "");
      var pokaz = pasujeTekst(hay, q);
      row.style.display = pokaz ? "" : "none";
      if (pokaz) widocznych++;
    });
    var empty = document.getElementById("prz-docs-empty") ||
                (modal.querySelector(".prz-docs-empty"));
    if (empty) empty.hidden = widocznych !== 0;
  }

  function otworzModal() {
    if (!modal) return;
    var search = document.getElementById("prz-docs-search");
    if (search) { search.value = ""; filtrujDokumenty(""); }
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function zamknijModal() { if (modal) { modal.hidden = true; document.body.style.overflow = ""; } }

  // ---------- Filtrowanie kafelków na żywo (widok kategorii) ----------
  // Baza rekordów do wyszukiwania serwerowego jest w przygotowaniu, więc na
  // ekranie kafelków pasek wyszukiwania filtruje dokumenty bez przeładowania.
  var searchForm = document.querySelector(".prz-searchbar");
  var searchInput = searchForm ? searchForm.querySelector(".tar-search-input") : null;
  var tilesBrak = document.getElementById("prz-tiles-brak");

  function filtrujKafelki(q) {
    if (!tilesBox) return;
    var widocznych = 0;
    tilesBox.querySelectorAll(".prz-tile").forEach(function (t) {
      var hay = (t.getAttribute("data-title") || "") + " " + (t.getAttribute("data-abbr") || "");
      var pokaz = pasujeTekst(hay, q);
      t.style.display = pokaz ? "" : "none";
      if (pokaz && !t.hidden) widocznych++;
    });
    if (tilesBrak) tilesBrak.hidden = widocznych !== 0;
  }

  if (tilesBox && searchInput) {
    searchInput.addEventListener("input", function () { filtrujKafelki(searchInput.value); });
    if (searchForm) {
      searchForm.addEventListener("submit", function (e) {
        e.preventDefault(); // na kafelkach filtrujemy lokalnie — Enter nie przeładowuje strony
      });
    }
    if (searchInput.value) filtrujKafelki(searchInput.value);
  }

  // ---------- Zdarzenia ----------
  if (tilesBox) {
    tilesBox.addEventListener("click", function (e) {
      var star = e.target.closest ? e.target.closest(".prz-star") : null;
      if (star) {
        e.preventDefault();   // nie otwieraj kafelka / nie nawiguj
        e.stopPropagation();
        toggleUlubiony(star.getAttribute("data-slug"));
      }
    });
  }
  if (pdfBtn) pdfBtn.addEventListener("click", otworzModal);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal && !modal.hidden) zamknijModal();
  });

  initModal();
  odswiezKafelki();
})();
