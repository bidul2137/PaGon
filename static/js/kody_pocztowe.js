/* ===================================================================
   KODY POCZTOWE — jedno pole, które samo rozpoznaje kod albo miejscowość.

   Baza pobierana jest RAZ z /pomoce/kody-pocztowe/dane i zostaje w cache
   przeglądarki (adres zawiera wersję zbioru). Podczas wyszukiwania nie leci
   ani jedno żądanie — również do naszego serwera — więc moduł działa bez
   internetu, a wpisana lokalizacja nigdzie nie wychodzi.

   Cały DOM budujemy przez createElement/textContent. Żaden fragment bazy nie
   trafia do innerHTML, więc dane nie mogą wstrzyknąć znaczników.
   =================================================================== */
(function () {
  "use strict";

  var K_HISTORIA = "pagon-kody-historia";
  var MAX_HISTORII = 8;
  var MAX_PODPOWIEDZI = 8;
  var DEBOUNCE_MS = 180;
  var MIN_ZNAKOW = 2;

  var strona = document.querySelector(".kp-page");
  if (!strona) return;
  var wersja = strona.getAttribute("data-wersja") || "0";

  var elForm = document.getElementById("kpForm");
  var elWejscie = document.getElementById("kpWejscie");
  var elCzysc = document.getElementById("kpCzysc");
  var elLista = document.getElementById("kpLista");
  var elWyniki = document.getElementById("kpWyniki");
  var elHistoria = document.getElementById("kpHistoria");
  var elHistoriaLista = document.getElementById("kpHistoriaLista");
  var elCzyscHistorie = document.getElementById("kpCzyscHistorie");
  if (!elForm || !elWejscie) return;

  var BAZA = null;
  var WG_KODU = null;      // "11-040" -> [indeksy rekordów]
  var WG_NAZWY = null;     // "barcikowo" -> [indeksy rekordów]
  var NAZWY = null;        // posortowane unikalne nazwy znormalizowane
  var KODY = null;         // posortowane unikalne kody

  /* ================= drobiazgi ================= */

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  function svg(sciezki, klasa) {
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", "none");
    s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "1.8");
    s.setAttribute("stroke-linecap", "round");
    s.setAttribute("stroke-linejoin", "round");
    s.setAttribute("aria-hidden", "true");
    if (klasa) s.setAttribute("class", klasa);
    sciezki.forEach(function (d) {
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", d);
      s.appendChild(p);
    });
    return s;
  }

  var IKONA_INFO = ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 11v5", "M12 7.8v.1"];
  var IKONA_OK = ["M20 6.5L9.4 17.1 4 11.7"];

  // typ: "brak" | "uwaga" | "ok"
  function komunikat(typ, tekst) {
    var box = el("p", "kp-komunikat kp-komunikat--" + typ);
    box.appendChild(svg(typ === "ok" ? IKONA_OK : IKONA_INFO, "kp-komunikat-ikona"));
    box.appendChild(el("span", "kp-komunikat-tresc", tekst));
    return box;
  }

  // małe litery, bez polskich znaków, bez podwójnych spacji — tak samo jak importer
  function norm(tekst) {
    var mapa = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
                 "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(tekst || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return mapa[z]; })
      .replace(/\s+/g, " ").trim();
  }

  // "11040", " 11-040 ", "kod 11-040" -> "11-040"; inaczej null
  function normalizujKod(wpis) {
    var cyfry = String(wpis || "").replace(/\D/g, "");
    if (cyfry.length !== 5) return null;
    return cyfry.slice(0, 2) + "-" + cyfry.slice(2);
  }

  function maLitery(wpis) {
    return /[a-ząćęłńóśżźA-ZĄĆĘŁŃÓŚŻŹ]/.test(String(wpis || "").replace(/^\s*kod\s+/i, ""));
  }

  /* ================= odczyt rekordu ================= */

  function rek(i) {
    var r = BAZA.rekordy[i];
    var s = BAZA.slowniki;
    return {
      kod: r[0], miejscowosc: r[1], nazwaNorm: r[2],
      gmina: r[3] >= 0 ? s.gminy[r[3]] : null,
      powiat: r[4] >= 0 ? s.powiaty[r[4]] : null,
      wojewodztwo: r[5] >= 0 ? s.wojewodztwa[r[5]] : null,
      pewny: r[6] === 0,
      uwaga: r[7] >= 0 ? s.uwagi[r[7]] : null
    };
  }

  function kontekst(r) {
    var czesci = [];
    if (r.gmina) czesci.push("gmina " + r.gmina);
    if (r.powiat) czesci.push("powiat " + r.powiat);
    if (r.wojewodztwo) czesci.push(r.wojewodztwo);
    return czesci.join(" · ");
  }

  /* ================= wczytanie bazy ================= */

  function wczytaj() {
    if (BAZA) return Promise.resolve(BAZA);
    return fetch("/pomoce/kody-pocztowe/dane?v=" + encodeURIComponent(wersja))
      .then(function (o) {
        if (!o.ok) throw new Error("brak bazy");
        return o.json();
      })
      .then(function (d) {
        BAZA = d;
        WG_KODU = new Map();
        WG_NAZWY = new Map();
        for (var i = 0; i < d.rekordy.length; i++) {
          var kod = d.rekordy[i][0], nazwa = d.rekordy[i][2];
          if (!WG_KODU.has(kod)) WG_KODU.set(kod, []);
          WG_KODU.get(kod).push(i);
          if (!WG_NAZWY.has(nazwa)) WG_NAZWY.set(nazwa, []);
          WG_NAZWY.get(nazwa).push(i);
        }
        NAZWY = Array.from(WG_NAZWY.keys()).sort();
        KODY = Array.from(WG_KODU.keys()).sort();
        return d;
      });
  }

  /* ================= wyszukiwanie ================= */

  // Trafienia z przodu nazwy przed trafieniami w środku — "dobre" ma najpierw
  // pokazać Dobre Miasto, a nie Nowe Dobre.
  function szukajNazw(fraza, limit) {
    var q = norm(fraza);
    if (q.length < MIN_ZNAKOW) return [];
    var przod = [], srodek = [];
    for (var i = 0; i < NAZWY.length; i++) {
      var poz = NAZWY[i].indexOf(q);
      if (poz === 0) przod.push(NAZWY[i]);
      else if (poz > 0) srodek.push(NAZWY[i]);
      if (przod.length >= limit) break;
    }
    return przod.concat(srodek).slice(0, limit);
  }

  function szukajKodow(fraza, limit) {
    var cyfry = String(fraza || "").replace(/\D/g, "");
    if (cyfry.length < MIN_ZNAKOW) return [];
    var wzor = cyfry.length > 2 ? cyfry.slice(0, 2) + "-" + cyfry.slice(2) : cyfry;
    var wynik = [];
    for (var i = 0; i < KODY.length && wynik.length < limit; i++) {
      if (KODY[i].indexOf(wzor) === 0) wynik.push(KODY[i]);
    }
    return wynik;
  }

  /* ================= podpowiedzi ================= */

  function zamknijListe() {
    elLista.hidden = true;
    elLista.replaceChildren();
    elWejscie.setAttribute("aria-expanded", "false");
  }

  function pozycja(glowna, kontekstTekst, przyKliknieciu) {
    var b = el("button", "kp-poz");
    b.type = "button";
    b.setAttribute("role", "option");
    b.setAttribute("aria-selected", "false");
    b.appendChild(el("span", "kp-poz-glowna", glowna));
    if (kontekstTekst) b.appendChild(el("span", "kp-poz-kontekst", kontekstTekst));
    b.addEventListener("click", przyKliknieciu);
    return b;
  }

  function rysujPodpowiedzi(fraza) {
    if (!BAZA) return;
    elLista.replaceChildren();
    var pozycje = [];

    if (maLitery(fraza)) {
      szukajNazw(fraza, MAX_PODPOWIEDZI).forEach(function (nazwa) {
        // Ta sama nazwa w kilku gminach = kilka osobnych pozycji z pełnym
        // kontekstem. Nie grupujemy ich bez informacji i nie wybieramy za użytkownika.
        var wgKontekstu = new Map();
        WG_NAZWY.get(nazwa).forEach(function (i) {
          var r = rek(i);
          var k = kontekst(r);
          if (!wgKontekstu.has(k)) wgKontekstu.set(k, { r: r, kody: [] });
          if (wgKontekstu.get(k).kody.indexOf(r.kod) < 0) wgKontekstu.get(k).kody.push(r.kod);
        });
        wgKontekstu.forEach(function (wpis, k) {
          var kody = wpis.kody.slice().sort();
          var opis = k + (kody.length ? " · " + (kody.length > 3
            ? "kody: " + kody.slice(0, 3).join(", ") + " i " + (kody.length - 3) + " więcej"
            : "kod: " + kody.join(", ")) : "");
          pozycje.push(pozycja(wpis.r.miejscowosc, opis, function () {
            wybierzMiejscowosc(wpis.r.miejscowosc, wpis.r);
          }));
        });
      });
    } else {
      szukajKodow(fraza, MAX_PODPOWIEDZI).forEach(function (kod) {
        var idx = WG_KODU.get(kod);
        var pierwszy = rek(idx[0]);
        var opis = idx.length > 1
          ? idx.length + " miejscowości · " + (pierwszy.powiat ? "powiat " + pierwszy.powiat : "")
          : pierwszy.miejscowosc + " · " + kontekst(pierwszy);
        pozycje.push(pozycja(kod, opis, function () { wybierzKod(kod); }));
      });
    }

    if (!pozycje.length) { zamknijListe(); return; }
    pozycje.slice(0, MAX_PODPOWIEDZI).forEach(function (p) { elLista.appendChild(p); });
    elLista.hidden = false;
    elWejscie.setAttribute("aria-expanded", "true");
  }

  /* ================= karty wyników ================= */

  function wierszDanych(dl, etykieta, wartosc) {
    dl.appendChild(el("dt", null, etykieta));
    var dd = el("dd", wartosc ? null : "kp-brak", wartosc || "");
    dl.appendChild(dd);
  }

  function przyciskKopiuj(kod) {
    var b = el("button", "kp-btn");
    b.type = "button";
    b.setAttribute("aria-label", "Kopiuj kod " + kod);
    b.appendChild(svg(["M9.5 9.5h9v9h-9z", "M14.5 9.5V5.5h-9v9h4"]));
    b.appendChild(el("span", null, "Kopiuj kod"));
    b.addEventListener("click", function () { kopiuj(kod); });
    return b;
  }

  function przyciskNowe() {
    var b = el("button", "kp-btn");
    b.type = "button";
    b.appendChild(svg(["M4 12a8 8 0 1 1 2.4 5.7", "M4 12v4.4", "M4 12h4.4"]));
    b.appendChild(el("span", null, "Nowe wyszukiwanie"));
    b.addEventListener("click", function () {
      elWejscie.value = "";
      elCzysc.hidden = true;
      elWyniki.replaceChildren();
      zamknijListe();
      elWejscie.focus();
    });
    return b;
  }

  function kartaPojedyncza(r) {
    var k = el("div", "kp-karta");
    k.appendChild(el("span", "kp-kod-badge", r.kod));
    k.appendChild(el("h2", "kp-miejscowosc", r.miejscowosc));
    var dl = el("dl", "kp-dane");
    wierszDanych(dl, "Gmina", r.gmina);
    wierszDanych(dl, "Powiat", r.powiat);
    wierszDanych(dl, "Województwo", r.wojewodztwo);
    k.appendChild(dl);
    if (!r.pewny && r.uwaga) {
      k.appendChild(el("p", "kp-uwaga-rekordu", "Weryfikacja częściowa: " + r.uwaga));
    }
    var akcje = el("div", "kp-akcje");
    akcje.appendChild(przyciskKopiuj(r.kod));
    akcje.appendChild(przyciskNowe());
    k.appendChild(akcje);
    return k;
  }

  function wierszMiejscowosci(r) {
    var k = el("div", "kp-karta");
    k.appendChild(el("h3", "kp-miejscowosc", r.miejscowosc));
    var dl = el("dl", "kp-dane");
    wierszDanych(dl, "Gmina", r.gmina);
    wierszDanych(dl, "Powiat", r.powiat);
    wierszDanych(dl, "Województwo", r.wojewodztwo);
    k.appendChild(dl);
    if (!r.pewny && r.uwaga) {
      k.appendChild(el("p", "kp-uwaga-rekordu", "Weryfikacja częściowa: " + r.uwaga));
    }
    return k;
  }

  function odmianaMiejscowosci(n) {
    if (n === 1) return "1 miejscowość";
    var reszta10 = n % 10, reszta100 = n % 100;
    if (reszta10 >= 2 && reszta10 <= 4 && (reszta100 < 12 || reszta100 > 14)) {
      return n + " miejscowości";
    }
    return n + " miejscowości";
  }

  /* ================= wyszukiwanie i render ================= */

  function pokaz(dzieci) {
    elWyniki.replaceChildren();
    dzieci.forEach(function (d) { elWyniki.appendChild(d); });
  }

  function wybierzKod(kod) {
    elWejscie.value = kod;
    elCzysc.hidden = false;
    zamknijListe();
    var idx = WG_KODU.get(kod) || [];
    if (!idx.length) { brakWyniku(kod); return; }
    zapiszHistorie("kod", kod);

    if (idx.length === 1) {
      pokaz([kartaPojedyncza(rek(idx[0]))]);
      return;
    }
    var naglowek = el("div", "kp-karta");
    naglowek.appendChild(el("p", "kp-nadtytul", "Kod pocztowy"));
    naglowek.appendChild(el("span", "kp-kod-badge", kod));
    naglowek.appendChild(el("p", "kp-podpowiedz", "Obejmuje " + odmianaMiejscowosci(idx.length) + "."));
    var akcje = el("div", "kp-akcje");
    akcje.appendChild(przyciskKopiuj(kod));
    akcje.appendChild(przyciskNowe());
    naglowek.appendChild(akcje);

    var dzieci = [naglowek];
    idx.forEach(function (i) { dzieci.push(wierszMiejscowosci(rek(i))); });
    pokaz(dzieci);
  }

  function wybierzMiejscowosc(nazwa, wzorzec) {
    elWejscie.value = nazwa;
    elCzysc.hidden = false;
    zamknijListe();
    var idx = WG_NAZWY.get(norm(nazwa)) || [];
    if (!idx.length) { brakWyniku(nazwa); return; }
    zapiszHistorie("miejscowość", nazwa);

    // grupujemy po kontekście administracyjnym — nazwa może się powtarzać
    var grupy = new Map();
    idx.forEach(function (i) {
      var r = rek(i);
      var k = kontekst(r);
      if (!grupy.has(k)) grupy.set(k, { r: r, kody: [] });
      if (grupy.get(k).kody.indexOf(r.kod) < 0) grupy.get(k).kody.push(r.kod);
    });

    if (wzorzec) {
      var szukany = kontekst(wzorzec);
      if (grupy.has(szukany)) {
        var jedna = new Map();
        jedna.set(szukany, grupy.get(szukany));
        grupy = jedna;
      }
    }

    var dzieci = [];
    if (grupy.size > 1) {
      dzieci.push(komunikat("uwaga", "Nazwa „" + nazwa + "” występuje w " + grupy.size +
        " miejscach. Wybierz właściwy kontekst administracyjny."));
    }
    grupy.forEach(function (wpis) {
      dzieci.push(kartaMiejscowosci(wpis.r, wpis.kody.slice().sort()));
    });
    pokaz(dzieci);
  }

  function kartaMiejscowosci(r, kody) {
    var k = el("div", "kp-karta");
    k.appendChild(el("h2", "kp-miejscowosc", r.miejscowosc));
    k.appendChild(el("p", "kp-poz-kontekst", kontekst(r)));

    k.appendChild(el("p", "kp-nadtytul", kody.length === 1 ? "Kod pocztowy" : "Kody pocztowe"));
    var chipy = el("div", "kp-chipy");
    var szczegoly = el("div");
    kody.forEach(function (kod) {
      var b = el("button", "kp-chip", kod);
      b.type = "button";
      b.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-label", "Pokaż szczegóły kodu " + kod);
      b.addEventListener("click", function () {
        var byloWybrane = b.getAttribute("aria-pressed") === "true";
        chipy.querySelectorAll(".kp-chip").forEach(function (c) {
          c.setAttribute("aria-pressed", "false");
        });
        szczegoly.replaceChildren();
        if (byloWybrane) return;
        b.setAttribute("aria-pressed", "true");
        var dopasowane = (WG_KODU.get(kod) || []).map(rek).filter(function (x) {
          return x.nazwaNorm === r.nazwaNorm && kontekst(x) === kontekst(r);
        });
        var dl = el("dl", "kp-dane");
        wierszDanych(dl, "Kod", kod);
        wierszDanych(dl, "Gmina", r.gmina);
        wierszDanych(dl, "Powiat", r.powiat);
        wierszDanych(dl, "Województwo", r.wojewodztwo);
        szczegoly.appendChild(dl);
        var niepewne = dopasowane.filter(function (x) { return !x.pewny && x.uwaga; });
        if (niepewne.length) {
          szczegoly.appendChild(el("p", "kp-uwaga-rekordu",
            "Weryfikacja częściowa: " + niepewne[0].uwaga));
        }
        var akcje = el("div", "kp-akcje");
        akcje.appendChild(przyciskKopiuj(kod));
        szczegoly.appendChild(akcje);
      });
      chipy.appendChild(b);
    });
    k.appendChild(chipy);
    k.appendChild(szczegoly);

    var akcje = el("div", "kp-akcje");
    akcje.appendChild(przyciskNowe());
    k.appendChild(akcje);
    return k;
  }

  function brakWyniku(wpis) {
    pokaz([komunikat("brak", "Nie znaleziono danych dla „" + wpis +
      "”. Sprawdź pisownię lub wpisz kod w formacie 11-040.")]);
  }

  function szukaj() {
    var wpis = elWejscie.value.trim();
    if (!wpis) return;
    zamknijListe();
    if (!BAZA) {
      pokaz([komunikat("uwaga", "Baza kodów nie została jeszcze zaimportowana.")]);
      return;
    }
    var kod = normalizujKod(wpis);
    if (kod && !maLitery(wpis)) { wybierzKod(kod); return; }
    if (maLitery(wpis)) {
      var trafienia = szukajNazw(wpis, 1);
      if (trafienia.length) {
        var doklane = WG_NAZWY.has(norm(wpis)) ? norm(wpis) : trafienia[0];
        wybierzMiejscowosc(rek(WG_NAZWY.get(doklane)[0]).miejscowosc);
        return;
      }
      brakWyniku(wpis);
      return;
    }
    var cyfry = wpis.replace(/\D/g, "");
    if (cyfry.length && cyfry.length !== 5) {
      pokaz([komunikat("uwaga",
        "Wpisz pięciocyfrowy kod, np. 11-040, albo nazwę miejscowości.")]);
      return;
    }
    brakWyniku(wpis);
  }

  /* ================= kopiowanie ================= */

  function kopiuj(kod) {
    function potwierdz() {
      var box = komunikat("ok", "Skopiowano kod " + kod);
      box.setAttribute("role", "status");
      elWyniki.insertBefore(box, elWyniki.firstChild);
      setTimeout(function () { if (box.parentNode) box.parentNode.removeChild(box); }, 2600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(kod).then(potwierdz, zapasoweKopiowanie);
    } else {
      zapasoweKopiowanie();
    }
    function zapasoweKopiowanie() {
      var pom = document.createElement("textarea");
      pom.value = kod;
      pom.setAttribute("readonly", "");
      pom.style.position = "fixed";
      pom.style.opacity = "0";
      document.body.appendChild(pom);
      pom.select();
      try { document.execCommand("copy"); potwierdz(); } catch (e) { /* bez potwierdzenia */ }
      document.body.removeChild(pom);
    }
  }

  /* ================= historia ================= */

  function czytajHistorie() {
    try {
      var s = window.localStorage.getItem(K_HISTORIA);
      var t = s ? JSON.parse(s) : [];
      return t instanceof Array ? t : [];
    } catch (e) { return []; }
  }

  function zapiszHistorie(typ, wartosc) {
    var h = czytajHistorie().filter(function (w) {
      return !(w && w.wartosc === wartosc && w.typ === typ);
    });
    h.unshift({ typ: typ, wartosc: wartosc, data: new Date().toISOString().slice(0, 10) });
    try { window.localStorage.setItem(K_HISTORIA, JSON.stringify(h.slice(0, MAX_HISTORII))); }
    catch (e) { /* brak miejsca — historia jest dodatkiem, nie blokujemy wyszukiwania */ }
    rysujHistorie();
  }

  function rysujHistorie() {
    if (!elHistoria || !elHistoriaLista) return;
    var h = czytajHistorie();
    elHistoriaLista.replaceChildren();
    elHistoria.hidden = !h.length;
    h.forEach(function (w) {
      if (!w || !w.wartosc) return;
      var b = el("button", "kp-historia-poz");
      b.type = "button";
      b.setAttribute("aria-label", "Wyszukaj ponownie: " + w.wartosc);
      b.appendChild(el("span", "kp-historia-tresc", w.wartosc));
      b.appendChild(el("span", "kp-historia-typ", w.typ));
      b.addEventListener("click", function () {
        elWejscie.value = w.wartosc;
        elCzysc.hidden = false;
        szukaj();
      });
      elHistoriaLista.appendChild(b);
    });
  }

  /* ================= zdarzenia ================= */

  var timer = null;
  elWejscie.addEventListener("input", function () {
    elCzysc.hidden = !elWejscie.value;
    clearTimeout(timer);
    var v = elWejscie.value;
    timer = setTimeout(function () {
      if (!BAZA || norm(v).length < MIN_ZNAKOW) { zamknijListe(); return; }
      rysujPodpowiedzi(v);
    }, DEBOUNCE_MS);
  });

  elWejscie.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { zamknijListe(); return; }
    if (e.key === "ArrowDown" && !elLista.hidden) {
      var p = elLista.querySelector(".kp-poz");
      if (p) { e.preventDefault(); p.focus(); }
    }
  });

  elLista.addEventListener("keydown", function (e) {
    var pozycje = [].slice.call(elLista.querySelectorAll(".kp-poz"));
    var i = pozycje.indexOf(document.activeElement);
    if (e.key === "ArrowDown" && i > -1 && i + 1 < pozycje.length) {
      e.preventDefault(); pozycje[i + 1].focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (i > 0) pozycje[i - 1].focus(); else elWejscie.focus();
    } else if (e.key === "Escape") {
      zamknijListe(); elWejscie.focus();
    }
  });

  elForm.addEventListener("submit", function (e) { e.preventDefault(); szukaj(); });

  elCzysc.addEventListener("click", function () {
    elWejscie.value = "";
    elCzysc.hidden = true;
    zamknijListe();
    elWejscie.focus();
  });

  if (elCzyscHistorie) elCzyscHistorie.addEventListener("click", function () {
    try { window.localStorage.removeItem(K_HISTORIA); } catch (e) {}
    rysujHistorie();
  });

  document.addEventListener("click", function (e) {
    if (!elLista.contains(e.target) && e.target !== elWejscie) zamknijListe();
  });

  rysujHistorie();
  wczytaj().catch(function () {
    // brak bazy to stan przewidziany — szablon pokazuje już instrukcję importu,
    // więc nie zasypujemy użytkownika drugim komunikatem o błędzie sieci
  });
})();
