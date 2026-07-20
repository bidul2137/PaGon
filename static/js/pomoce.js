/* ===================================================================
   POMOCE / LINKI — ulubione kafelki (stan w localStorage)
   Kafelki renderuje serwer; ten skrypt oznacza gwiazdki i przenosi
   ulubione na górę listy. Gwiazdka działa niezależnie od kliknięcia
   kafelka (nie otwiera linku/podstrony).
   =================================================================== */
(function () {
  "use strict";

  var FAV_KEY = "pagon_pomoce_ulubione"; // [slug, ...]

  function readJSON(k, f) {
    try { var r = localStorage.getItem(k); return r ? JSON.parse(r) : f; }
    catch (e) { return f; }
  }
  function writeJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  var fav = readJSON(FAV_KEY, []);
  if (!Array.isArray(fav)) fav = [];

  // "Rozwiń / Zwiń" opis (karty zatrzymania PJ) — działa też na podstronie listy
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest(".pom-rozwin") : null;
    if (!btn) return;
    var desc = btn.parentNode.querySelector(".pom-zpj-desc");
    if (!desc) return;
    var willOpen = desc.hidden;
    desc.hidden = !willOpen;
    btn.setAttribute("aria-expanded", willOpen ? "true" : "false");
    btn.textContent = willOpen ? "Zwiń" : "Rozwiń";
  });

  // ---------- wspólne: normalizacja i dopasowanie (jak po stronie serwera) ----------
  var filtr = "";
  function bezOgonkow(s) {
    var m = { "ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ż":"z","ź":"z" };
    return String(s).toLowerCase().replace(/[ąćęłńóśźż]/g, function (c) { return m[c]; });
  }
  function dopasuj(hay) {
    if (!filtr) return true;
    if (filtr.length <= 3) {  // krótkie zapytania (uk, zea, rpa) — całe słowo
      return new RegExp("(?:^|[^0-9a-z])" + filtr.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![0-9a-z])").test(hay);
    }
    return hay.indexOf(filtr) !== -1;
  }

  // ---------- filtr listy pozycji (podstrona kategorii) ----------
  var lista = document.querySelector(".prz-lista");
  function odswiezListe() {
    if (!lista) return;
    var items = Array.prototype.slice.call(lista.querySelectorAll(".prz-rekord"));
    var widoczne = 0;
    items.forEach(function (li) {
      var hay = bezOgonkow(li.getAttribute("data-szukaj") || li.textContent || "");
      var ok = dopasuj(hay);
      li.hidden = !ok;
      if (ok) widoczne++;
    });
    var brak = document.getElementById("pom-brak-lista");
    if (brak) brak.hidden = widoczne !== 0;
  }

  var box = document.getElementById("pom-tiles");

  function czyUlubiony(slug) { return fav.indexOf(slug) !== -1; }

  function pasuje(t) {
    var nazwa = (t.querySelector(".prz-tile-name") || {}).textContent || "";
    return dopasuj(bezOgonkow(nazwa));
  }

  function odswiez() {
    odswiezListe();
    if (!box) return;
    var tiles = Array.prototype.slice.call(box.querySelectorAll(".prz-tile"));
    tiles.forEach(function (t) {
      var slug = t.getAttribute("data-slug");
      t.hidden = !pasuje(t);
      var star = t.querySelector(".prz-star");
      if (star) {
        var u = czyUlubiony(slug);
        var nazwa = (t.querySelector(".prz-tile-name") || {}).textContent || "";
        star.classList.toggle("is-fav", u);
        star.setAttribute("aria-pressed", u ? "true" : "false");
        star.setAttribute("aria-label", (u ? "Usuń " : "Dodaj ") + nazwa + (u ? " z ulubionych" : " do ulubionych"));
      }
    });
    // widoczne: ulubione na górę (kolejność w obrębie grup zachowana)
    var widoczne = tiles.filter(function (t) { return !t.hidden; });
    var ukryte = tiles.filter(function (t) { return t.hidden; });
    var ulub = widoczne.filter(function (t) { return czyUlubiony(t.getAttribute("data-slug")); });
    var reszta = widoczne.filter(function (t) { return !czyUlubiony(t.getAttribute("data-slug")); });
    ulub.concat(reszta).concat(ukryte).forEach(function (t) { box.appendChild(t); });

    var brak = document.getElementById("pom-brak");
    if (brak) brak.hidden = widoczne.length !== 0;
  }

  function toggle(slug) {
    var i = fav.indexOf(slug);
    if (i === -1) fav.push(slug); else fav.splice(i, 1);
    writeJSON(FAV_KEY, fav);
    odswiez();
  }

  if (box) box.addEventListener("click", function (e) {
    var star = e.target.closest ? e.target.closest(".prz-star") : null;
    if (star) {
      e.preventDefault();   // nie otwieraj kafelka
      e.stopPropagation();
      toggle(star.getAttribute("data-slug"));
    }
  });

  // wyszukiwarka na żywo: kafelki (nazwa) oraz lista pozycji (indeks data-szukaj)
  var szukajInput = document.querySelector(".tar-searchbar input[name='q']");
  if (szukajInput) {
    filtr = bezOgonkow(szukajInput.value.trim());
    szukajInput.addEventListener("input", function () {
      filtr = bezOgonkow(szukajInput.value.trim());
      odswiez();
    });
    var form = szukajInput.form;
    if (form) form.addEventListener("submit", function (e) { e.preventDefault(); });
  }

  odswiez();
})();
