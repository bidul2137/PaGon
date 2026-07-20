/* Holowanie pojazdów — filtrowanie kart (tekst + rodzaj) */
(function () {
  "use strict";

  var input = document.getElementById("hol-szukaj");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".hol-chip"));
  var grupy = Array.prototype.slice.call(document.querySelectorAll(".hol-grupa"));
  var brak = document.getElementById("hol-brak");
  var filtrRodzaj = "wszystkie";

  function bezOgonkow(s) {
    var mapa = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return s.toLowerCase().replace(/[ąćęłńóśżź]/g, function (z) { return mapa[z] || z; });
  }

  function filtruj() {
    var q = bezOgonkow((input && input.value || "").trim());
    var widoczne = 0;

    grupy.forEach(function (g) {
      var karty = Array.prototype.slice.call(g.querySelectorAll(".hol-karta"));
      var wGrupie = 0;
      karty.forEach(function (k) {
        var pasujeRodzaj = filtrRodzaj === "wszystkie" || k.getAttribute("data-rodzaj") === filtrRodzaj;
        var pasujeTekst = !q || bezOgonkow(k.textContent).indexOf(q) !== -1;
        var pokaz = pasujeRodzaj && pasujeTekst;
        k.hidden = !pokaz;
        if (pokaz) wGrupie++;
      });
      g.hidden = wGrupie === 0;
      widoczne += wGrupie;
    });

    if (brak) brak.hidden = widoczne > 0;
  }

  if (input) input.addEventListener("input", filtruj);

  chips.forEach(function (ch) {
    ch.addEventListener("click", function () {
      chips.forEach(function (c) { c.classList.remove("is-active"); });
      ch.classList.add("is-active");
      filtrRodzaj = ch.getAttribute("data-filtr");
      filtruj();
    });
  });
})();
