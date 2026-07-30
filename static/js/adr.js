/* ===================================================================
   TABLICA ADR — logika modułu.

   Dane wyłącznie z lokalnych plików data/adr/ (jedno żądanie do
   /pomoce/tablica-adr/dane). Nic nie jest pobierane z internetu w czasie
   pracy użytkownika — po pierwszym otwarciu moduł działa offline.

   Cały DOM budujemy przez createElement/textContent. Żaden fragment JSON
   nie trafia do innerHTML, więc treść bazy nie może wstrzyknąć znaczników.
   =================================================================== */
(function () {
  "use strict";

  var KLUCZ_HISTORII = "pagon-adr-historia";
  var MAX_HISTORII = 5;
  var MAX_PODPOWIEDZI = 8;
  var DEBOUNCE_MS = 300;

  var BAZA = null;          // { substances, danger_codes, metadata }
  var INDEKS = {};          // un_number -> rekord

  var elForm = document.getElementById("adrForm");
  if (!elForm) return;
  var elKod = document.getElementById("dangerCodeInput");
  var elUn = document.getElementById("unNumberInput");
  var elWyczysc = document.getElementById("adrWyczysc");
  var elSzukaj = document.getElementById("adrNameSearch");
  var elPodpowiedzi = document.getElementById("adrPodpowiedzi");
  var elWyniki = document.getElementById("adrWyniki");
  var elHistoria = document.getElementById("adrHistoria");
  var elHistoriaLista = document.getElementById("adrHistoriaLista");
  var elWyczyscHistorie = document.getElementById("adrWyczyscHistorie");
  var elZrodlo = document.getElementById("adrZrodlo");

  /* ---------- pomocnicze ---------- */

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  function ikona(sciezka) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "16");
    svg.setAttribute("height", "16");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", "adr-komunikat-ikona");
    sciezka.forEach(function (d) {
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", d);
      svg.appendChild(p);
    });
    return svg;
  }

  var IKONA_UWAGA = ["M12 3.6 1.8 20.4h20.4z", "M12 9.6v4.2", "M12 17.2v.1"];
  var IKONA_INFO = ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 11v5", "M12 7.8v.1"];

  // typ: "info" | "uwaga" | "krytyczny"
  function komunikat(typ, tekst) {
    var box = el("p", "adr-komunikat adr-komunikat--" + typ);
    box.appendChild(ikona(typ === "info" ? IKONA_INFO : IKONA_UWAGA));
    box.appendChild(el("span", "adr-komunikat-tresc", tekst));
    if (typ !== "info") box.setAttribute("role", "alert");
    return box;
  }

  function wiersz(klucz, wartosc) {
    var w = el("div", "adr-wiersz");
    w.appendChild(el("span", "adr-klucz", klucz));
    var pusta = wartosc === null || wartosc === undefined || wartosc === "" ||
      (wartosc instanceof Array && !wartosc.length);
    if (pusta) {
      w.appendChild(el("span", "adr-wartosc adr-wartosc--brak", "brak danych w lokalnej bazie"));
    } else {
      w.appendChild(el("span", "adr-wartosc", wartosc instanceof Array ? wartosc.join(", ") : String(wartosc)));
    }
    return w;
  }

  // usuwa polskie znaki i nadmiarowe spacje — do porównań w wyszukiwarce
  function bezZnakow(s) {
    var mapa = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(s || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return mapa[z]; })
      .replace(/\s+/g, " ").trim();
  }

  // "UN 1203", "un1203", " 1203 " -> "1203"; inaczej null
  function normalizujUn(wpis) {
    var cyfry = String(wpis || "").toUpperCase().replace(/^UN\s*/, "").replace(/\D/g, "");
    return cyfry.length === 4 ? cyfry : null;
  }

  // dopuszczamy cyfry oraz X wyłącznie jako pierwszy znak
  function normalizujKod(wpis) {
    var s = String(wpis || "").toUpperCase().replace(/[^0-9X]/g, "");
    if (s.indexOf("X") > 0) s = s.charAt(0) === "X" ? "X" + s.slice(1).replace(/X/g, "") : s.replace(/X/g, "");
    return s.slice(0, 4);
  }

  /* ---------- opis kodu zagrożenia ---------- */

  function opiszKod(kod) {
    var kk = BAZA.danger_codes || {};
    var karta = el("div", "kal-karta adr-karta");
    karta.appendChild(el("p", "kal-sekcja-tytul", "Kod zagrożenia"));
    karta.appendChild(el("h2", "adr-kod-naglowek", "Kod zagrożenia: " + kod));

    var zX = kod.charAt(0) === "X";
    var cyfry = zX ? kod.slice(1) : kod;

    var pelny = (kk.combinations || {})[kod];
    if (pelny) karta.appendChild(wiersz("Znaczenie kodu", pelny));

    var lista = el("ul", "adr-kod-cyfry");
    if (zX) {
      var liX = el("li", "adr-kod-cyfra");
      liX.appendChild(el("span", "adr-kod-cyfra-znak", "X"));
      liX.appendChild(el("span", "adr-kod-cyfra-opis",
        (kk.rules && kk.rules.x_prefix) || "Materiał reaguje niebezpiecznie z wodą."));
      lista.appendChild(liX);
    }
    cyfry.split("").forEach(function (c, i) {
      var li = el("li", "adr-kod-cyfra");
      li.appendChild(el("span", "adr-kod-cyfra-znak", c));
      var opis = (kk.digit_meanings || {})[c] || "Cyfra bez opisu w lokalnej bazie.";
      li.appendChild(el("span", "adr-kod-cyfra-opis",
        (i === 0 ? "Zagrożenie główne — " : "Zagrożenie dodatkowe — ") + opis));
      lista.appendChild(li);
    });
    karta.appendChild(lista);

    // nasilenie: powtórzona cyfra
    var powt = null;
    for (var i = 0; i < cyfry.length - 1; i++) {
      if (cyfry.charAt(i) === cyfry.charAt(i + 1)) { powt = cyfry.charAt(i); break; }
    }
    if (powt) {
      var opisP = (kk.digit_meanings || {})[powt] || "";
      karta.appendChild(komunikat("info",
        "Podwójna cyfra " + powt + " oznacza nasilenie zagrożenia: " + opisP.toLowerCase() + "."));
    }

    if (zX) {
      karta.appendChild(komunikat("krytyczny",
        "REAGUJE NIEBEZPIECZNIE Z WODĄ. Nie podawaj wody na materiał — do gaszenia i działań " +
        "ratowniczych stosuj środki wskazane przez PSP lub eksperta."));
    }
    return karta;
  }

  /* ---------- karta materiału ---------- */

  function kartaMaterialu(rek) {
    var karta = el("div", "kal-karta adr-karta");
    karta.appendChild(el("p", "kal-sekcja-tytul", "Materiał"));
    karta.appendChild(el("h2", "adr-un-naglowek", "UN " + rek.un_number));
    karta.appendChild(el("p", "adr-nazwa-pl", rek.proper_shipping_name_pl || "—"));
    if (rek.proper_shipping_name_en) {
      karta.appendChild(el("p", "adr-nazwa-en", rek.proper_shipping_name_en));
    }

    var dane = el("div", "adr-dane");
    dane.appendChild(wiersz("Kod zagrożenia", rek.danger_identification_number));
    dane.appendChild(wiersz("Klasa ADR", rek.adr_class));
    dane.appendChild(wiersz("Zagrożenia dodatkowe",
      (rek.subsidiary_risks && rek.subsidiary_risks.length) ? rek.subsidiary_risks : "brak"));
    dane.appendChild(wiersz("Grupa pakowania", rek.packing_group));
    dane.appendChild(wiersz("Kod klasyfikacyjny", rek.classification_code));

    var wN = el("div", "adr-wiersz");
    wN.appendChild(el("span", "adr-klucz", "Nalepki ADR"));
    if (rek.labels && rek.labels.length) {
      var box = el("span", "adr-wartosc adr-nalepki");
      rek.labels.forEach(function (n) { box.appendChild(el("span", "adr-nalepka", n)); });
      wN.appendChild(box);
    } else {
      wN.appendChild(el("span", "adr-wartosc adr-wartosc--brak", "brak danych w lokalnej bazie"));
    }
    dane.appendChild(wN);

    dane.appendChild(wiersz("Kategoria transportowa", rek.transport_category));
    dane.appendChild(wiersz("Kod ograniczeń — tunele", rek.tunnel_restriction_code));
    karta.appendChild(dane);

    // pozostałe kolumny Tabeli A — zwinięte
    var det = document.createElement("details");
    det.className = "adr-szczegoly";
    det.appendChild(el("summary", null, "Pozostałe parametry z Tabeli A"));
    var wiecej = el("div", "adr-dane");
    [["Przepisy szczególne", rek.special_provisions],
     ["Ilości ograniczone (LQ)", rek.limited_quantities],
     ["Ilości wyłączone (EQ)", rek.excepted_quantities],
     ["Instrukcje pakowania", rek.packing_instructions],
     ["Pakowanie razem", rek.mixed_packing_provisions],
     ["Cysterny przenośne", rek.portable_tank_instructions],
     ["Cysterny ADR", rek.vehicle_tank_instructions]
    ].forEach(function (p) { wiecej.appendChild(wiersz(p[0], p[1])); });
    det.appendChild(wiecej);
    karta.appendChild(det);

    if (rek.verification_status === "partial_verification") {
      karta.appendChild(komunikat("info", "Część danych wymaga ponownej kontroli w ADR 2025."));
      if (rek.verification_note) {
        var nota = el("p", "adr-metryczka");
        nota.appendChild(el("span", null, rek.verification_note));
        karta.appendChild(nota);
      }
    }

    var zr = rek.source || {};
    var m = el("p", "adr-metryczka");
    m.appendChild(el("strong", null, "Źródło: "));
    m.appendChild(document.createTextNode((zr.title || "—") + " · " + (zr.legal_reference || "—")));
    m.appendChild(document.createElement("br"));
    m.appendChild(el("strong", null, "Wersja: "));
    m.appendChild(document.createTextNode(zr.adr_version || "—"));
    m.appendChild(document.createElement("br"));
    m.appendChild(el("strong", null, "Weryfikacja: "));
    m.appendChild(document.createTextNode(
      (rek.verification_status === "verified" ? "pełna" : "częściowa") +
      ", stan na " + (zr.verified_at || "—")));
    karta.appendChild(m);

    return karta;
  }

  /* ---------- historia ---------- */

  function wczytajHistorie() {
    try {
      var s = window.localStorage.getItem(KLUCZ_HISTORII);
      var t = s ? JSON.parse(s) : [];
      return t instanceof Array ? t : [];
    } catch (e) { return []; }
  }

  function dopiszHistorie(rek) {
    var h = wczytajHistorie().filter(function (p) { return p.un !== rek.un_number; });
    h.unshift({
      un: rek.un_number,
      nazwa: rek.proper_shipping_name_pl || "",
      kod: rek.danger_identification_number || "",
      czas: new Date().toISOString()
    });
    h = h.slice(0, MAX_HISTORII);
    try { window.localStorage.setItem(KLUCZ_HISTORII, JSON.stringify(h)); } catch (e) {}
    rysujHistorie();
  }

  function rysujHistorie() {
    var h = wczytajHistorie();
    elHistoriaLista.innerHTML = "";
    if (!h.length) { elHistoria.hidden = true; return; }
    elHistoria.hidden = false;
    h.forEach(function (p) {
      var li = document.createElement("li");
      var btn = el("button", "adr-historia-poz");
      btn.type = "button";
      btn.setAttribute("aria-label", "Sprawdź ponownie UN " + p.un);
      btn.appendChild(el("span", "adr-historia-un", "UN " + p.un));
      btn.appendChild(el("span", "adr-historia-nazwa", p.nazwa || "—"));
      var d = new Date(p.czas);
      var czas = isNaN(d.getTime()) ? "" :
        ("0" + d.getDate()).slice(-2) + "." + ("0" + (d.getMonth() + 1)).slice(-2) + " " +
        ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
      btn.appendChild(el("span", "adr-historia-czas", czas));
      btn.addEventListener("click", function () {
        elUn.value = p.un;
        elKod.value = p.kod || "";
        sprawdz();
        elWyniki.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      li.appendChild(btn);
      elHistoriaLista.appendChild(li);
    });
  }

  /* ---------- logika główna ---------- */

  function sprawdz() {
    elWyniki.innerHTML = "";
    if (!BAZA) return;

    var kod = normalizujKod(elKod.value);
    var un = normalizujUn(elUn.value);

    if (!kod && !un) {
      elWyniki.appendChild(komunikat("info",
        "Wpisz kod zagrożenia i numer UN tak, jak widnieją na tablicy pojazdu — na przykład 33 / 1203."));
      return;
    }

    // sam kod zagrożenia
    if (kod && !un) {
      elWyniki.appendChild(opiszKod(kod));
      elWyniki.appendChild(komunikat("uwaga",
        "Sam kod zagrożenia nie identyfikuje jednoznacznie substancji. Wpisz numer UN, aby ustalić materiał."));
      return;
    }

    var rek = INDEKS[un];
    if (!rek) {
      if (kod) elWyniki.appendChild(opiszKod(kod));
      elWyniki.appendChild(komunikat("uwaga",
        "Nie znaleziono numeru UN " + un + " w lokalnej bazie ADR 2025."));
      var meta = BAZA.metadata || {};
      if (meta.is_complete === false) {
        elWyniki.appendChild(komunikat("info",
          "Lokalna baza obejmuje " + (meta.record_count || 0) + " pozycji z Tabeli A i nie jest kompletna. " +
          "Brak rekordu nie oznacza, że numer UN nie istnieje."));
      }
      return;
    }

    if (kod) elWyniki.appendChild(opiszKod(kod));
    elWyniki.appendChild(kartaMaterialu(rek));

    // uzupełnienie kodu z bazy, gdy użytkownik podał sam numer UN
    if (!kod && rek.danger_identification_number) {
      elKod.value = rek.danger_identification_number;
      elWyniki.insertBefore(opiszKod(rek.danger_identification_number), elWyniki.firstChild);
    }

    // niezgodność odczytu z tablicy
    if (kod && rek.danger_identification_number && kod !== rek.danger_identification_number) {
      elWyniki.appendChild(komunikat("uwaga",
        "Uwaga: wpisany kod zagrożenia nie jest zgodny z kodem zapisanym w lokalnej bazie ADR dla UN " +
        rek.un_number + " (" + rek.danger_identification_number + "). Sprawdź odczyt tablicy."));
    }
    if (kod && !rek.danger_identification_number) {
      elWyniki.appendChild(komunikat("info",
        "Lokalna baza nie zawiera kodu zagrożenia dla UN " + rek.un_number +
        ", więc nie da się porównać go z odczytem z tablicy."));
    }

    dopiszHistorie(rek);
  }

  /* ---------- podpowiedzi po nazwie ---------- */

  function zamknijPodpowiedzi() {
    elPodpowiedzi.innerHTML = "";
    elPodpowiedzi.hidden = true;
    elSzukaj.setAttribute("aria-expanded", "false");
  }

  function szukajPoNazwie(fraza) {
    var q = bezZnakow(fraza);
    var qUn = normalizujUn(fraza);
    if (!q || q.length < 2) return [];
    var trafienia = [];
    BAZA.substances.forEach(function (r) {
      var pkt = -1;
      if (qUn && r.un_number === qUn) pkt = 0;
      else if (r.un_number.indexOf(q.replace(/\D/g, "")) === 0 && /^\d+$/.test(q.replace(/\s/g, ""))) pkt = 1;
      else {
        var pl = bezZnakow(r.proper_shipping_name_pl);
        var en = bezZnakow(r.proper_shipping_name_en);
        if (pl.indexOf(q) === 0) pkt = 2;
        else if (en.indexOf(q) === 0) pkt = 3;
        else if (pl.indexOf(q) > -1 || en.indexOf(q) > -1) pkt = 4;
        else if ((r.keywords || []).some(function (k) { return bezZnakow(k).indexOf(q) > -1; })) pkt = 5;
      }
      if (pkt > -1) trafienia.push({ pkt: pkt, rek: r });
    });
    trafienia.sort(function (a, b) { return a.pkt - b.pkt || a.rek.un_number.localeCompare(b.rek.un_number); });
    return trafienia.slice(0, MAX_PODPOWIEDZI).map(function (t) { return t.rek; });
  }

  function rysujPodpowiedzi(lista) {
    elPodpowiedzi.innerHTML = "";
    if (!lista.length) { zamknijPodpowiedzi(); return; }
    lista.forEach(function (r) {
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", "false");
      var btn = el("button", "adr-podpowiedz");
      btn.type = "button";
      btn.appendChild(el("span", "adr-podpowiedz-un", "UN " + r.un_number));
      btn.appendChild(el("span", "adr-podpowiedz-nazwa", r.proper_shipping_name_pl || ""));
      btn.addEventListener("click", function () {
        elUn.value = r.un_number;
        elKod.value = r.danger_identification_number || "";
        elSzukaj.value = "";
        zamknijPodpowiedzi();
        sprawdz();
        elWyniki.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      li.appendChild(btn);
      elPodpowiedzi.appendChild(li);
    });
    elPodpowiedzi.hidden = false;
    elSzukaj.setAttribute("aria-expanded", "true");
  }

  /* ---------- zdarzenia ---------- */

  var timerTablicy = null;
  function odlozoneSprawdzenie() {
    clearTimeout(timerTablicy);
    timerTablicy = setTimeout(function () {
      var un = normalizujUn(elUn.value);
      var kod = normalizujKod(elKod.value);
      if (un || kod.length >= 2) sprawdz();
    }, DEBOUNCE_MS);
  }

  elKod.addEventListener("input", function () {
    var poz = elKod.selectionStart;
    elKod.value = normalizujKod(elKod.value);
    try { elKod.setSelectionRange(poz, poz); } catch (e) {}
    odlozoneSprawdzenie();
  });
  elUn.addEventListener("input", odlozoneSprawdzenie);
  elForm.addEventListener("submit", function (e) { e.preventDefault(); clearTimeout(timerTablicy); sprawdz(); });
  elWyczysc.addEventListener("click", function () {
    elKod.value = ""; elUn.value = ""; elSzukaj.value = "";
    zamknijPodpowiedzi();
    elWyniki.innerHTML = "";
    elWyniki.appendChild(komunikat("info",
      "Wpisz kod zagrożenia i numer UN tak, jak widnieją na tablicy pojazdu — na przykład 33 / 1203."));
    elKod.focus();
  });

  var timerSzukania = null;
  elSzukaj.addEventListener("input", function () {
    clearTimeout(timerSzukania);
    var v = elSzukaj.value;
    timerSzukania = setTimeout(function () { rysujPodpowiedzi(szukajPoNazwie(v)); }, DEBOUNCE_MS);
  });
  elSzukaj.addEventListener("keydown", function (e) {
    if (e.key === "Escape") zamknijPodpowiedzi();
    if (e.key === "ArrowDown") {
      var pierwszy = elPodpowiedzi.querySelector(".adr-podpowiedz");
      if (pierwszy) { e.preventDefault(); pierwszy.focus(); }
    }
  });
  document.addEventListener("click", function (e) {
    if (!elPodpowiedzi.contains(e.target) && e.target !== elSzukaj) zamknijPodpowiedzi();
  });

  elWyczyscHistorie.addEventListener("click", function () {
    try { window.localStorage.removeItem(KLUCZ_HISTORII); } catch (e) {}
    rysujHistorie();
  });

  /* ---------- start ---------- */

  function opiszZrodlo() {
    var m = BAZA.metadata || {};
    elZrodlo.textContent = "Dane: " + (m.adr_version || "ADR 2025") + ", " +
      (m.legal_reference || "Dz.U. 2025 poz. 642") + ". Baza działa offline. " +
      "Rekordów: " + (m.record_count || 0) + ".";
    if (m.is_complete === false) {
      var b = komunikat("uwaga",
        "Lokalna baza ADR jest NIEKOMPLETNA — zawiera " + (m.record_count || 0) +
        " z ok. 3000 pozycji Tabeli A i żaden rekord nie ma pełnej weryfikacji. " +
        "Traktuj wynik jako wskazówkę, a nie jako źródło rozstrzygające.");
      elWyniki.parentNode.insertBefore(b, elWyniki);
    }
  }

  // wersja bazy w adresie — po imporcie przeglądarka pobierze plik na nowo,
  // a między importami korzysta z cache, więc tryb offline działa dalej
  var wersja = elWyniki.getAttribute("data-wersja") || "0";
  fetch("/pomoce/tablica-adr/dane?v=" + encodeURIComponent(wersja), { cache: "force-cache" })
    .then(function (r) { return r.json(); })
    .then(function (dane) {
      BAZA = dane;
      (BAZA.substances || []).forEach(function (r) { INDEKS[r.un_number] = r; });
      opiszZrodlo();
      rysujHistorie();
      elWyniki.appendChild(komunikat("info",
        "Wpisz kod zagrożenia i numer UN tak, jak widnieją na tablicy pojazdu — na przykład 33 / 1203."));
    })
    ["catch"](function () {
      elWyniki.appendChild(komunikat("uwaga",
        "Nie udało się wczytać lokalnej bazy ADR. Otwórz moduł raz przy dostępie do sieci, " +
        "aby przeglądarka zapisała dane do pracy offline."));
    });
})();
