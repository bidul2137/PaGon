/* ===================================================================
   PRZELICZNIK mg/l – ‰ — dwukierunkowe przeliczenie (1 mg/l ≈ 2,1‰)
   oraz kwalifikacja stanu wg art. 46 ust. 2 i 3 ustawy o wychowaniu
   w trzeźwości. Klasyfikacja wg progów właściwych dla metody pomiaru
   (pola, w które wpisano wartość), nie wg wartości przeliczonej.
   =================================================================== */
(function () {
  "use strict";

  var WSPOLCZYNNIK = 2.1; // 1 mg/l wydychanego powietrza ≈ 2,1‰ we krwi (0,25 mg/l = 0,5‰)

  var poleMgl = document.getElementById("prz-mgl");
  var polePromile = document.getElementById("prz-promile");
  var wynik = document.getElementById("prz-wynik");
  if (!poleMgl || !polePromile || !wynik) return;

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function wiersz(etykieta, wartosc, klasa) {
    var d = el("div", "kal-fakt" + (klasa ? " " + klasa : ""));
    d.appendChild(el("span", "kal-fakt-label", etykieta));
    d.appendChild(el("span", "kal-fakt-val", wartosc));
    return d;
  }
  function fmt(v, miejsca) {
    return v.toFixed(miejsca).replace(".", ",");
  }

  // klasyfikacja wg progów ustawowych dla danej metody pomiaru
  function stanZmgl(mgl) {
    if (mgl > 0.25) return "nietrzezwosc";
    if (mgl >= 0.1) return "po-uzyciu";
    return "brak";
  }
  function stanZpromili(pm) {
    if (pm > 0.5) return "nietrzezwosc";
    if (pm >= 0.2) return "po-uzyciu";
    return "brak";
  }

  var OPIS_STANU = {
    "brak": {
      tytul: "Poniżej stanu po użyciu alkoholu",
      opis: "Wartość poniżej progu z art. 46 ust. 2 ustawy o wychowaniu w trzeźwości (poniżej 0,2‰ / 0,1 mg/dm³).",
      klasa: "kal-karta--ok"
    },
    "po-uzyciu": {
      tytul: "Stan po użyciu alkoholu",
      opis: "Od 0,2‰ do 0,5‰ we krwi albo od 0,1 mg do 0,25 mg w 1 dm³ wydychanego powietrza " +
        "(art. 46 ust. 2 ustawy o wychowaniu w trzeźwości). Kierujący: wykroczenie z art. 87 KW.",
      klasa: "kal-karta--stop"
    },
    "nietrzezwosc": {
      tytul: "Stan nietrzeźwości",
      opis: "Powyżej 0,5‰ we krwi albo powyżej 0,25 mg w 1 dm³ wydychanego powietrza " +
        "(art. 46 ust. 3 ustawy o wychowaniu w trzeźwości). Kierujący pojazdem mechanicznym: " +
        "przestępstwo z art. 178a KK; pojazd inny niż mechaniczny: wykroczenie z art. 87 § 1a KW.",
      klasa: "kal-karta--stop"
    }
  };

  function pokaz(mgl, promile, stan) {
    wynik.innerHTML = "";
    var o = OPIS_STANU[stan];
    var k = el("div", "kal-karta " + o.klasa);
    k.appendChild(el("p", "kal-stop-tytul", (stan === "brak" ? "" : "⚠ ") + o.tytul));
    var fakty = el("div", "kal-fakty");
    fakty.appendChild(wiersz("Wydychane powietrze", fmt(mgl, 3) + " mg/l", "is-gold"));
    fakty.appendChild(wiersz("Krew (przeliczenie)", fmt(promile, 2) + " ‰", "is-gold"));
    k.appendChild(fakty);
    k.appendChild(el("p", "kal-opis", o.opis));
    wynik.appendChild(k);
  }

  var blokada = false; // zapobiega pętli input -> input
  function zMgl() {
    if (blokada) return;
    var v = parseFloat(String(poleMgl.value).replace(",", "."));
    if (isNaN(v) || v < 0) { wynik.innerHTML = ""; return; }
    blokada = true;
    polePromile.value = (v * WSPOLCZYNNIK).toFixed(2);
    blokada = false;
    pokaz(v, v * WSPOLCZYNNIK, stanZmgl(v));
  }
  function zPromili() {
    if (blokada) return;
    var v = parseFloat(String(polePromile.value).replace(",", "."));
    if (isNaN(v) || v < 0) { wynik.innerHTML = ""; return; }
    blokada = true;
    poleMgl.value = (v / WSPOLCZYNNIK).toFixed(3);
    blokada = false;
    pokaz(v / WSPOLCZYNNIK, v, stanZpromili(v));
  }

  poleMgl.addEventListener("input", zMgl);
  polePromile.addEventListener("input", zPromili);

  // eksport do testów
  if (typeof window !== "undefined") {
    window.__przelicznik = { stanZmgl: stanZmgl, stanZpromili: stanZpromili, WSPOLCZYNNIK: WSPOLCZYNNIK };
  }
})();
