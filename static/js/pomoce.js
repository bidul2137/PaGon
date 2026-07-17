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

  var box = document.getElementById("pom-tiles");
  if (!box) return;

  function czyUlubiony(slug) { return fav.indexOf(slug) !== -1; }

  function odswiez() {
    var tiles = Array.prototype.slice.call(box.querySelectorAll(".prz-tile"));
    tiles.forEach(function (t) {
      var slug = t.getAttribute("data-slug");
      var star = t.querySelector(".prz-star");
      if (star) {
        var u = czyUlubiony(slug);
        var nazwa = (t.querySelector(".prz-tile-name") || {}).textContent || "";
        star.classList.toggle("is-fav", u);
        star.setAttribute("aria-pressed", u ? "true" : "false");
        star.setAttribute("aria-label", (u ? "Usuń " : "Dodaj ") + nazwa + (u ? " z ulubionych" : " do ulubionych"));
      }
    });
    // ulubione na górę (kolejność w obrębie grup zachowana)
    var ulub = tiles.filter(function (t) { return czyUlubiony(t.getAttribute("data-slug")); });
    var reszta = tiles.filter(function (t) { return !czyUlubiony(t.getAttribute("data-slug")); });
    ulub.concat(reszta).forEach(function (t) { box.appendChild(t); });
  }

  function toggle(slug) {
    var i = fav.indexOf(slug);
    if (i === -1) fav.push(slug); else fav.splice(i, 1);
    writeJSON(FAV_KEY, fav);
    odswiez();
  }

  box.addEventListener("click", function (e) {
    var star = e.target.closest ? e.target.closest(".prz-star") : null;
    if (star) {
      e.preventDefault();   // nie otwieraj kafelka
      e.stopPropagation();
      toggle(star.getAttribute("data-slug"));
    }
  });

  odswiez();
})();
