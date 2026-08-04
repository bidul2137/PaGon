/* ===================================================================
   NUMERY ITD — filtrowanie województw i oddziałów.

   Cała treść jest już w HTML (renderowana po stronie serwera), więc
   strona działa bez internetu i bez tego skryptu — filtr tylko ukrywa
   niepasujące pozycje i rozwija te z trafieniem.
   =================================================================== */
(function () {
  "use strict";

  var strona = document.querySelector(".itd-page");
  if (!strona) return;
  var pole = document.getElementById("itdSzukaj");
  var licznik = document.getElementById("itdLicznik");
  if (!pole) return;

  var woje = [].slice.call(strona.querySelectorAll(".itd-woj"));

  function norm(t) {
    var m = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
              "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(t || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return m[z]; })
      .replace(/\s+/g, " ").trim();
  }

  function filtruj() {
    var q = norm(pole.value);
    if (!q) {
      woje.forEach(function (w) { w.hidden = false; w.open = false; });
      if (licznik) licznik.textContent = "";
      return;
    }
    // Każde słowo zapytania musi wystąpić — „olsztyn ełk” zawęża, a nie poszerza.
    var slowa = q.split(" ").filter(Boolean);
    var ile = 0;
    woje.forEach(function (w) {
      var siano = norm(w.getAttribute("data-szukaj"));
      var pasuje = slowa.every(function (s) { return siano.indexOf(s) > -1; });
      w.hidden = !pasuje;
      w.open = pasuje;          // trafienie od razu rozwijamy
      if (pasuje) ile++;
    });
    if (licznik) {
      licznik.textContent = ile
        ? ("Pasujące województwa: " + ile)
        : "Brak wyników. Spróbuj nazwy miasta albo województwa.";
    }
  }

  var timer = null;
  pole.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(filtruj, 160);
  });
  pole.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { pole.value = ""; filtruj(); }
  });
})();
