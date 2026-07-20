/* ===================================================================
   KALKULATOR PRĘDKOŚCI — przekroczenie, mandat/recydywa/punkty (dane
   z taryfikatora) oraz ocena obligatoryjnego zatrzymania prawa jazdy
   (mechanizm +50 km/h, stan prawny od 3.03.2026).
   Decyzje oparte o wewnętrzne identyfikatory pól, nie o teksty UI.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("kal-dane");
  if (!dataEl) return;
  var PRZEDZIALY = [];
  try { PRZEDZIALY = JSON.parse(dataEl.textContent) || []; } catch (e) { return; }

  var poleLimit = document.getElementById("kal-limit");
  var polePredkosc = document.getElementById("kal-predkosc");
  var poleMiejsce = document.getElementById("kal-miejsce");
  var poleDokument = document.getElementById("kal-dokument");
  var btnOblicz = document.getElementById("kal-oblicz");
  var wynik = document.getElementById("kal-wynik");
  var bladLimit = document.getElementById("kal-limit-blad");
  var bladPredkosc = document.getElementById("kal-predkosc-blad");
  if (!poleLimit || !polePredkosc || !poleMiejsce || !wynik) return;

  var ETYKIETY_MIEJSCA = {
    built_up_area: "obszarze zabudowanym",
    single_carriageway_two_way_outside_built_up: "drodze jednojezdniowej dwukierunkowej poza obszarem zabudowanym",
    dual_carriageway_outside_built_up: "drodze dwujezdniowej poza obszarem zabudowanym",
    motorway: "autostradzie",
    expressway: "drodze ekspresowej"
  };

  // ---------- logika mechanizmu +50 km/h (art. 135 ust. 1 pkt 2 lit. a PRD) ----------
  function shouldSuspendLicense(speedOver, roadType) {
    var coveredRoadTypes = [
      "built_up_area",
      "single_carriageway_two_way_outside_built_up"
    ];
    return speedOver > 50 && coveredRoadTypes.indexOf(roadType) !== -1;
  }

  // ---------- pomocnicze ----------
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
  function znajdzPrzedzial(diff) {
    for (var i = 0; i < PRZEDZIALY.length; i++) {
      var p = PRZEDZIALY[i];
      if (diff >= p.od && (p.do === null || diff <= p.do)) return p;
    }
    return null;
  }
  // wyróżnienie fragmentu tekstu przepisu (span.legal-highlight, bez innerHTML na danych)
  function wyroznij(elTekst, fraza) {
    if (!elTekst) return;
    var pelny = elTekst.getAttribute("data-tekst") || elTekst.textContent;
    elTekst.setAttribute("data-tekst", pelny);
    elTekst.textContent = "";
    var i = fraza ? pelny.indexOf(fraza) : -1;
    if (i === -1) { elTekst.textContent = pelny; return; }
    elTekst.appendChild(document.createTextNode(pelny.slice(0, i)));
    elTekst.appendChild(el("span", "legal-highlight", fraza));
    elTekst.appendChild(document.createTextNode(pelny.slice(i + fraza.length)));
  }
  // fragment paragrafu w art. 92a KW: od "§ n." do następnego "§" lub końca
  function fragmentParagrafu(tekst, n) {
    var re = new RegExp("§\\s*" + n + "\\.");
    var m = re.exec(tekst);
    if (!m) return null;
    var start = m.index;
    var next = tekst.indexOf("§", start + m[0].length);
    return tekst.slice(start, next === -1 ? tekst.length : next).trim();
  }

  // ---------- walidacja ----------
  function czytaj(pole, bladEl) {
    var v = pole.value === "" ? null : parseInt(pole.value, 10);
    var zly = v !== null && (isNaN(v) || v <= 0);
    if (bladEl) bladEl.hidden = !zly;
    pole.classList.toggle("kal-input--blad", zly);
    return zly ? NaN : v;
  }

  // ---------- karty wyniku ----------
  function kartaPrzekroczenie(diff) {
    var k = el("div", "kal-karta");
    k.appendChild(el("p", "kal-sekcja-tytul", "Przekroczenie prędkości"));
    k.appendChild(el("p", "kal-diff", "Przekroczenie o " + diff + " km/h"));
    return k;
  }
  function kartaMandat(p) {
    var k = el("div", "kal-karta");
    k.appendChild(el("p", "kal-sekcja-tytul", "Mandat i punkty"));
    if (!p) {
      k.appendChild(el("p", "kal-opis", "Nie znaleziono przedziału w taryfikatorze."));
      return k;
    }
    k.appendChild(el("p", "kal-tytul", p.title));
    k.appendChild(el("p", "kal-kwalifikacja", p.kwalifikacja || ""));
    var fakty = el("div", "kal-fakty");
    fakty.appendChild(wiersz("Mandat", p.mandat !== null && p.mandat !== undefined ? p.mandat + " zł" : "–", "is-gold"));
    if (p.recydywa) fakty.appendChild(wiersz("Recydywa (art. 38 § 2 KPW)", p.recydywa + " zł"));
    fakty.appendChild(wiersz("Punkty", (p.punkty || 0) + " pkt"));
    if (p.kod) fakty.appendChild(wiersz("Kod", p.kod));
    k.appendChild(fakty);
    return k;
  }
  // procedura zatrzymania dokumentu zależna od rodzaju prawa jazdy
  function proceduraDokumentu(typDokumentu) {
    if (typDokumentu === "domestic") {
      return {
        tytul: "⚠ Zatrzymanie prawa jazdy — 3 miesiące",
        podstawa: "art. 135 ust. 1 pkt 2 lit. a PRD",
        komunikat: "Policja zatrzymuje wydane w kraju prawo jazdy za pokwitowaniem; " +
          "starosta wydaje decyzję administracyjną o zatrzymaniu na 3 miesiące " +
          "(art. 102 ust. 1 pkt 4 ustawy o kierujących pojazdami)."
      };
    }
    if (typDokumentu === "foreign") {
      return {
        tytul: "⚠ Zatrzymanie zagranicznego prawa jazdy",
        podstawa: "art. 135a ust. 1 pkt 2 lit. a PRD",
        komunikat: "Policja zatrzymuje okazany zagraniczny dokument prawa jazdy. " +
          "Dokument przekazywany jest właściwemu staroście, a następnie organowi państwa wydania. " +
          "Ograniczenie dotyczy prowadzenia na terytorium Polski."
      };
    }
    return {
      tytul: "⚠ Przekroczenie o więcej niż 50 km/h — zatrzymanie prawa jazdy",
      podstawa: null,
      komunikat: "Wybierz rodzaj prawa jazdy, aby sprawdzić procedurę zatrzymania dokumentu."
    };
  }

  function kartaPrawoJazdy(diff, miejsce, typDokumentu) {
    if (shouldSuspendLicense(diff, miejsce)) {
      var proc = proceduraDokumentu(typDokumentu);
      var stop = el("div", "kal-karta kal-karta--stop");
      stop.appendChild(el("p", "kal-sekcja-tytul kal-sekcja-tytul--stop", "Prawo jazdy"));
      stop.appendChild(el("p", "kal-stop-tytul", proc.tytul));
      stop.appendChild(el("p", "kal-opis",
        "Przekroczenie prędkości o więcej niż 50 km/h na " + ETYKIETY_MIEJSCA[miejsce] +
        " powoduje obligatoryjne zatrzymanie prawa jazdy" +
        (proc.podstawa ? " (" + proc.podstawa + ")" : "") + "."));
      stop.appendChild(el("p", "kal-opis", proc.komunikat));
      return stop;
    }

    // przypadki bez obligatoryjnego zatrzymania — karta neutralna z wyjaśnieniem
    var k = el("div", "kal-karta kal-karta--neutral");
    k.appendChild(el("p", "kal-sekcja-tytul", "Prawo jazdy"));
    if (diff > 50 && miejsce === "unknown") {
      k.appendChild(el("p", "kal-neutral-tytul", "Nie można ustalić konsekwencji dla prawa jazdy"));
      k.appendChild(el("p", "kal-opis",
        "Aby ustalić możliwość zatrzymania prawa jazdy, wybierz rodzaj miejsca i drogi."));
      return k;
    }
    k.appendChild(el("p", "kal-neutral-tytul", "Brak automatycznego zatrzymania prawa jazdy z mechanizmu +50 km/h"));
    var powod;
    if (diff === 50) {
      powod = "Przekroczenie wynosi dokładnie 50 km/h, a przepis dotyczy przekroczenia o więcej niż 50 km/h.";
    } else if (diff < 50) {
      powod = "Przekroczenie nie przekracza 50 km/h — mechanizm obligatoryjnego zatrzymania prawa jazdy nie ma zastosowania.";
    } else if (miejsce === "dual_carriageway_outside_built_up") {
      powod = "Mechanizm +50 km/h poza obszarem zabudowanym obejmuje drogę jednojezdniową dwukierunkową, a nie drogę dwujezdniową.";
    } else if (miejsce === "motorway" || miejsce === "expressway") {
      powod = "Mechanizm +50 km/h poza obszarem zabudowanym obejmuje drogę jednojezdniową dwukierunkową — nie obejmuje " +
        (miejsce === "motorway" ? "autostrady" : "drogi ekspresowej") + ".";
    } else {
      powod = "Wybierz rodzaj miejsca, aby ustalić konsekwencję dla prawa jazdy.";
    }
    k.appendChild(el("p", "kal-opis", powod));
    return k;
  }

  // ---------- wyróżnienia w panelu "Podstawa prawna" ----------
  function odswiezPodstawy(p, miejsce, zatrzymanie) {
    var t92a = document.getElementById("kal-tekst-92a");
    if (t92a) {
      var frag = null;
      if (p && p.paragraf) {
        frag = fragmentParagrafu(t92a.getAttribute("data-tekst") || t92a.textContent, p.paragraf);
      }
      wyroznij(t92a, frag);
    }
    var fraza = null;
    if (zatrzymanie) {
      fraza = miejsce === "built_up_area"
        ? "na obszarze zabudowanym"
        : "na drodze jednojezdniowej dwukierunkowej poza obszarem zabudowanym";
    }
    wyroznij(document.getElementById("kal-tekst-135"), fraza);
    wyroznij(document.getElementById("kal-tekst-135a"), fraza);
  }

  // ---------- główna funkcja ----------
  function przelicz() {
    wynik.innerHTML = "";
    var limit = czytaj(poleLimit, bladLimit);
    var pred = czytaj(polePredkosc, bladPredkosc);
    if (limit === null || pred === null || isNaN(limit) || isNaN(pred)) return;

    var miejsce = poleMiejsce.value || "unknown";
    var dokument = poleDokument ? (poleDokument.value || "unknown") : "unknown";
    var diff = pred - limit;

    if (diff <= 0) {
      var ok = el("div", "kal-karta kal-karta--ok");
      ok.appendChild(el("p", "kal-diff", "Brak przekroczenia prędkości"));
      ok.appendChild(el("p", "kal-opis",
        "Rzeczywista prędkość (" + pred + " km/h) nie przekracza dopuszczalnej (" + limit + " km/h)."));
      wynik.appendChild(ok);
      odswiezPodstawy(null, miejsce, false);
      return;
    }

    var p = znajdzPrzedzial(diff);
    wynik.appendChild(kartaPrzekroczenie(diff));
    wynik.appendChild(kartaMandat(p));
    wynik.appendChild(kartaPrawoJazdy(diff, miejsce, dokument));
    odswiezPodstawy(p, miejsce, shouldSuspendLicense(diff, miejsce));
  }

  poleLimit.addEventListener("input", przelicz);
  polePredkosc.addEventListener("input", przelicz);
  poleMiejsce.addEventListener("change", przelicz);
  if (poleDokument) poleDokument.addEventListener("change", przelicz);
  if (btnOblicz) btnOblicz.addEventListener("click", przelicz);

  // eksport do testów (środowisko node / przeglądarka)
  if (typeof window !== "undefined") {
    window.__kalkulator = {
      shouldSuspendLicense: shouldSuspendLicense,
      znajdzPrzedzial: znajdzPrzedzial,
      proceduraDokumentu: proceduraDokumentu
    };
  }
})();
