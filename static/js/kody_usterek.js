/* ===================================================================
   KODY USTEREK — wyszukiwarka i lista oceny.

   Indeks pobierany RAZ z /pomoce/kody-usterek/dane i zostaje w cache
   przeglądarki (adres zawiera wersję zbioru), więc moduł działa offline.

   Cały DOM budujemy przez createElement/textContent. Żaden fragment bazy
   ani wpis użytkownika nie trafia do innerHTML.
   =================================================================== */
(function () {
  "use strict";

  var K_LISTA = "pagon-usterki-lista";
  var K_HISTORIA = "pagon-usterki-historia";
  var STRONA = 25;          // ile wyników dokładamy na raz
  var DEBOUNCE_MS = 180;
  var MAX_HISTORII = 10;

  var strona = document.querySelector(".kus-page");
  if (!strona) return;
  var wersja = strona.getAttribute("data-wersja") || "0";

  var elWejscie = document.getElementById("kusWejscie");
  var elCzysc = document.getElementById("kusCzysc");
  var elWyniki = document.getElementById("kusWyniki");
  var elLicznik = document.getElementById("kusLicznik");
  var elWiecej = document.getElementById("kusWiecej");
  var elFiltry = document.getElementById("kusFiltry");
  var elPasek = document.getElementById("kusPasek");
  var elWybrane = document.getElementById("kusWybrane");
  var elStatus = document.getElementById("kusStatus");

  var BAZA = null;
  var wynik = [];
  var pokazano = 0;
  var ostatniElement = null, karta = null, listaKarty = null;
  var filtrKat = null;
  var filtrDzial = null;
  var lista = wczytajListe();

  var NAZWY = { UD: "drobna", UP: "poważna", UN: "niebezpieczna" };
  var PRIO = { UD: 1, UP: 2, UN: 3 };

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  function norm(t) {
    var m = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
              "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(t || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return m[z]; })
      .replace(/\s+/g, " ").trim();
  }

  // "0.1.a", "01a", "0 1 A" -> "01A"
  function normKod(t) {
    return String(t || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  }

  // Polski odmienia wszystko, a użytkownik wpisuje mianownik: „tablica” ma
  // trafić w „Tablice rejestracyjne”, „opona” w „opon”, „światło” w „światła”.
  // Dla słów od 5 znaków szukamy więc rdzenia bez dwóch ostatnich liter.
  // Krótkich nie ruszamy, bo z „koła” zostałby bezużyteczny fragment.
  function rdzen(s) {
    return s.length >= 5 ? s.slice(0, s.length - 2) : s;
  }

  /* ---------------- podświetlanie trafień ---------------- */

  var stemy = [];        // rdzenie słów z bieżącego zapytania
  var szukanyKod = "";

  // Wersja tekstu do szukania pozycji trafień. W przeciwieństwie do norm()
  // NIE scala spacji — każdy znak ma tu swój odpowiednik w oryginale jeden do
  // jednego, więc indeksy z tej wersji można bez przeliczania przyłożyć do
  // tekstu wyświetlanego.
  function normPozycyjnie(t) {
    var m = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
              "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(t || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return m[z]; });
  }

  // Łącznik traktujemy jak literę, żeby nazwy i kody złożone podświetlały
  // się w całości: „Goczałkowice-Zdrój”, „11-040”, „Rutka-Tartak”.
  var LITERA = /[0-9a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ-]/;

  function zakresyTrafien(tekst) {
    if (!stemy.length && !szukanyKod) return [];
    var n = normPozycyjnie(tekst);
    var zakresy = [];
    var szukane = stemy.slice();
    if (szukanyKod) szukane.push(normPozycyjnie(szukanyKod));

    szukane.forEach(function (s) {
      if (!s) return;
      var od = 0, i;
      while ((i = n.indexOf(s, od)) > -1) {
        // Rozciągamy trafienie do pełnego wyrazu — użytkownik wpisuje
        // „światła”, a szukamy rdzenia „świat”; podświetlenie samego rdzenia
        // wyglądałoby jak literówka.
        var a = i, b = i + s.length;
        while (a > 0 && LITERA.test(tekst.charAt(a - 1))) a--;
        while (b < tekst.length && LITERA.test(tekst.charAt(b))) b++;
        zakresy.push([a, b]);
        od = i + s.length;
      }
    });
    if (!zakresy.length) return [];

    zakresy.sort(function (x, y) { return x[0] - y[0]; });
    var scalone = [zakresy[0]];
    for (var j = 1; j < zakresy.length; j++) {
      var ost = scalone[scalone.length - 1];
      if (zakresy[j][0] <= ost[1]) ost[1] = Math.max(ost[1], zakresy[j][1]);
      else scalone.push(zakresy[j]);
    }
    return scalone;
  }

  // Zwraca fragment DOM, nie HTML — tekst bazy nigdy nie idzie przez innerHTML.
  function zPodswietleniem(tekst) {
    var frag = document.createDocumentFragment();
    var zakresy = zakresyTrafien(tekst);
    if (!zakresy.length) {
      frag.appendChild(document.createTextNode(tekst));
      return frag;
    }
    var poz = 0;
    zakresy.forEach(function (z) {
      if (z[0] > poz) frag.appendChild(document.createTextNode(tekst.slice(poz, z[0])));
      var m = document.createElement("mark");
      m.className = "kus-traf";
      m.textContent = tekst.slice(z[0], z[1]);
      frag.appendChild(m);
      poz = z[1];
    });
    if (poz < tekst.length) frag.appendChild(document.createTextNode(tekst.slice(poz)));
    return frag;
  }

  function spanZPodswietleniem(cls, tekst) {
    var s = el("span", cls);
    s.appendChild(zPodswietleniem(tekst || ""));
    return s;
  }

  /* ---------------- lista wybranych ---------------- */

  function wczytajListe() {
    try {
      var s = window.localStorage.getItem(K_LISTA);
      var l = s ? JSON.parse(s) : [];
      return (l instanceof Array) ? l : [];
    } catch (e) { return []; }
  }

  function zapiszListe() {
    try { window.localStorage.setItem(K_LISTA, JSON.stringify(lista)); }
    catch (e) { /* brak miejsca nie może przerwać pracy z listą */ }
  }

  function wLiscie(kod) {
    for (var i = 0; i < lista.length; i++) if (lista[i].k === kod) return lista[i];
    return null;
  }

  function najwyzszy() {
    var max = 0;
    lista.forEach(function (p) { if (PRIO[p.s] > max) max = PRIO[p.s]; });
    return max;
  }

  function rysujPasek() {
    elPasek.hidden = lista.length === 0;
    elWybrane.replaceChildren();
    lista.forEach(function (p) {
      var chip = el("span", "kus-wchip kus-wchip--" + p.s.toLowerCase());
      chip.appendChild(el("span", "kus-wchip-kod", p.k));
      chip.appendChild(el("span", "kus-wchip-sev", p.s));
      var x = el("button", "kus-wchip-x", "×");
      x.type = "button";
      x.setAttribute("aria-label", "Usuń usterkę " + p.k + " z listy");
      x.addEventListener("click", function () { usun(p.k); });
      chip.appendChild(x);
      elWybrane.appendChild(chip);
    });

    var m = najwyzszy();
    var tekst = m === 3 ? "Lista zawiera usterkę niebezpieczną"
      : m === 2 ? "Lista zawiera co najmniej jedną usterkę poważną"
      : m === 1 ? "Wybrano wyłącznie usterki drobne" : "Lista jest pusta";
    elStatus.replaceChildren();
    elStatus.className = "kus-pasek-status kus-pasek-status--" +
      (m === 3 ? "un" : m === 2 ? "up" : m === 1 ? "ud" : "pusty");
    elStatus.appendChild(el("strong", null, "Wybrane usterki: " + lista.length));
    elStatus.appendChild(el("span", "kus-pasek-opis", tekst));
  }

  function dodaj(kod, sev, warunek) {
    if (wLiscie(kod)) return;
    lista.push({ k: kod, s: sev, c: warunek || null });
    lista.sort(function (a, b) { return PRIO[b.s] - PRIO[a.s]; });
    zapiszListe(); rysujPasek(); odswiezPrzyciski();
  }

  function usun(kod) {
    lista = lista.filter(function (p) { return p.k !== kod; });
    zapiszListe(); rysujPasek(); odswiezPrzyciski();
  }

  function odswiezPrzyciski() {
    elWyniki.querySelectorAll("[data-kod]").forEach(function (btn) {
      var jest = !!wLiscie(btn.getAttribute("data-kod"));
      btn.classList.toggle("kus-dodaj--jest", jest);
      btn.replaceChildren();
      btn.appendChild(ikonaBtn(jest));
      btn.appendChild(el("span", null, jest ? "Usuń" : "Dodaj"));
      btn.setAttribute("aria-label",
        (jest ? "Usuń z listy usterkę " : "Dodaj do listy usterkę ") +
        btn.getAttribute("data-kod"));
    });
  }

  function ikonaBtn(jest) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", jest ? "M6 12h12" : "M12 6v12M6 12h12");
    p.setAttribute("stroke", "currentColor");
    p.setAttribute("stroke-width", "2.1");
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("fill", "none");
    svg.appendChild(p);
    return svg;
  }

  /* ---------------- wyniki ---------------- */

  // Nagłówek karty elementu — powtarza hierarchię z tabeli rozporządzenia:
  // dział, podgrupa, badany element, metoda i ewentualna uwaga. Bez tego
  // sam opis usterki wisi w próżni i nie wiadomo, czego dotyczy.
  function naglowekElementu(r) {
    var h = el("div", "kus-grupa-head");
    h.appendChild(el("p", "kus-grupa-dzial", r.s + ". " + r.sn));
    if (r.g && r.g !== r.i) {
      var pod = el("p", "kus-grupa-pod");
      pod.appendChild(zPodswietleniem(r.g));
      h.appendChild(pod);
    }
    var elem = el("p", "kus-grupa-el");
    elem.appendChild(zPodswietleniem(r.e + ". " + r.i));
    h.appendChild(elem);

    if (r.m) {
      var m = el("div", "kus-grupa-metoda");
      m.appendChild(el("span", "kus-grupa-etykieta", "Jak sprawdzić"));
      m.appendChild(el("span", "kus-grupa-metoda-tekst", r.m));
      h.appendChild(m);
    }
    (r.u || []).forEach(function (u) {
      var box = el("div", "kus-grupa-uwaga");
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24");
      svg.setAttribute("aria-hidden", "true");
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", "M12 4l9 16H3zM12 10v4M12 17.2v.1");
      p.setAttribute("stroke", "currentColor"); p.setAttribute("stroke-width", "1.8");
      p.setAttribute("fill", "none"); p.setAttribute("stroke-linejoin", "round");
      p.setAttribute("stroke-linecap", "round");
      svg.appendChild(p);
      box.appendChild(svg);
      var t = el("span", null);
      t.appendChild(el("strong", null, "Uwaga: "));
      t.appendChild(document.createTextNode(u));
      box.appendChild(t);
      h.appendChild(box);
    });
    return h;
  }

  function wiersz(r) {
    var box = el("div", "kus-poz");

    var link = el("a", "kus-poz-tresc");
    link.href = "/pomoce/kody-usterek/kod/" + encodeURIComponent(r.n);
    var gora = el("span", "kus-poz-gora");
    gora.appendChild(spanZPodswietleniem("kus-kod", r.k));
    r.p.forEach(function (s) {
      var b = el("span", "kus-sev kus-sev--" + s.toLowerCase());
      b.textContent = s + " · " + NAZWY[s];
      gora.appendChild(b);
    });
    if (r.p.length > 1) gora.appendChild(el("span", "kus-wielo", "wybór oceny"));
    link.appendChild(gora);
    link.appendChild(spanZPodswietleniem("kus-poz-opis", r.o));
    if (r.i) link.appendChild(spanZPodswietleniem("kus-poz-el", r.e + " " + r.i));
    box.appendChild(link);

    // Przycisk stoi POZA odnośnikiem, żeby kliknięcie w wiersz otwierało
    // szczegóły, a nie dopisywało usterkę przez przypadek.
    var btn = el("button", "kus-dodaj");
    btn.type = "button";
    btn.setAttribute("data-kod", r.k);
    btn.addEventListener("click", function () {
      if (wLiscie(r.k)) { usun(r.k); return; }
      if (r.p.length === 1) dodaj(r.k, r.p[0], null);
      else otworzModal(r);
    });
    box.appendChild(btn);
    return box;
  }

  function pokaz(dosyp) {
    if (!dosyp) { elWyniki.replaceChildren(); pokazano = 0; ostatniElement = null; }
    var do_ = Math.min(pokazano + STRONA, wynik.length);
    for (var i = pokazano; i < do_; i++) {
      var r = wynik[i];
      // Nowa karta zaczyna się przy każdej zmianie badanego elementu. Wyniki są
      // posortowane wg kodu, więc usterki jednego elementu zawsze idą razem.
      if (r.e !== ostatniElement) {
        karta = el("section", "kus-grupa");
        karta.appendChild(naglowekElementu(r));
        listaKarty = el("div", "kus-grupa-lista");
        karta.appendChild(listaKarty);
        elWyniki.appendChild(karta);
        ostatniElement = r.e;
      }
      listaKarty.appendChild(wiersz(r));
    }
    pokazano = do_;
    elWiecej.hidden = pokazano >= wynik.length;
    elLicznik.textContent = wynik.length
      ? ("Znaleziono: " + wynik.length + (pokazano < wynik.length
          ? " — pokazano " + pokazano : ""))
      : "Brak wyników. Spróbuj kodu, nazwy elementu albo słowa z opisu.";
    odswiezPrzyciski();
  }

  function szukaj() {
    if (!BAZA) return;
    var fraza = elWejscie.value;
    var q = norm(fraza);
    var kod = normKod(fraza);
    // Każde słowo zapytania musi wystąpić — kolejne słowa zawężają wynik.
    var slowa = q.split(" ").filter(Boolean).map(rdzen);
    // Te same rdzenie posłużą do podświetlenia trafień w wynikach.
    stemy = slowa;
    szukanyKod = kod && kod.length >= 2 ? fraza.trim() : "";

    wynik = BAZA.filter(function (r) {
      if (filtrKat && r.p.indexOf(filtrKat) < 0) return false;
      if (filtrDzial && r.s !== filtrDzial) return false;
      if (!q) return true;
      if (kod && r.n.indexOf(kod) === 0) return true;
      var siano = norm(r.o) + " " + norm(r.i) + " " + r.w.join(" ") + " " + r.n.toLowerCase();
      return slowa.every(function (w) { return siano.indexOf(w) > -1; });
    });
    // Porzadek naturalny po kodzie: 1.1.2 przed 1.1.10, a usterki jednego
    // elementu obok siebie — inaczej karty grup rozsypalyby sie na kawalki.
    wynik.sort(function (a, b) {
      var ka = a.k.split(/[.\s]/), kb = b.k.split(/[.\s]/);
      for (var i = 0; i < Math.max(ka.length, kb.length); i++) {
        var x = ka[i] || "", y = kb[i] || "";
        var lx = parseInt(x, 10), ly = parseInt(y, 10);
        if (!isNaN(lx) && !isNaN(ly)) { if (lx !== ly) return lx - ly; }
        else if (x !== y) return x < y ? -1 : 1;
      }
      return 0;
    });
    if (kod) {
      wynik.sort(function (a, b) {
        return (b.n === kod ? 1 : 0) - (a.n === kod ? 1 : 0);
      });
    }
    pokaz(false);
    if (q && wynik.length) zapiszHistorie(fraza);
  }

  function zapiszHistorie(fraza) {
    try {
      var s = window.localStorage.getItem(K_HISTORIA);
      var h = s ? JSON.parse(s) : [];
      if (!(h instanceof Array)) h = [];
      h = h.filter(function (x) { return x !== fraza; });
      h.unshift(fraza);
      window.localStorage.setItem(K_HISTORIA, JSON.stringify(h.slice(0, MAX_HISTORII)));
    } catch (e) { /* historia jest dodatkiem */ }
  }

  /* ---------------- modal wyboru kategorii ---------------- */

  var modal = document.getElementById("kusModal");
  var modalOpcje = document.getElementById("kusModalOpcje");
  var modalOpis = document.getElementById("kusModalOpis");
  var modalDodaj = document.getElementById("kusModalDodaj");
  var wybor = null, biezacyKod = null, ostatniFokus = null;

  function otworzModal(r) {
    biezacyKod = r.k; wybor = null;
    modalOpis.textContent = r.k + " — " + r.o;
    modalOpcje.replaceChildren();
    r.p.forEach(function (s, i) {
      var id = "kus-opt-" + i;
      var lab = el("label", "kus-opcja kus-opcja--" + s.toLowerCase());
      var inp = el("input");
      inp.type = "radio"; inp.name = "kus-ocena"; inp.id = id; inp.value = s;
      inp.className = "kus-opcja-radio";
      inp.addEventListener("change", function () {
        wybor = s; modalDodaj.disabled = false;
      });
      lab.appendChild(inp);
      var tre = el("span", "kus-opcja-tresc");
      tre.appendChild(el("span", "kus-opcja-tytul",
        "Priorytet " + PRIO[s] + " — usterka " + NAZWY[s]));
      tre.appendChild(el("span", "kus-opcja-kod", s));
      lab.appendChild(tre);
      modalOpcje.appendChild(lab);
    });
    // Brak zaznaczenia domyślnego: przy dwóch dopuszczalnych ocenach źródło
    // nie wskazuje żadnej jako podstawowej, a podpowiadanie surowszej byłoby
    // sugerowaniem kwalifikacji.
    modalDodaj.disabled = true;
    pokazModal(modal);
  }

  modalDodaj.addEventListener("click", function () {
    if (!wybor || !biezacyKod) return;
    dodaj(biezacyKod, wybor, null);
    zamknijModal(modal);
  });

  function pokazModal(m) {
    ostatniFokus = document.activeElement;
    m.hidden = false;
    var f = m.querySelector("input, button");
    if (f) f.focus();
  }

  function zamknijModal(m) {
    m.hidden = true;
    if (ostatniFokus && ostatniFokus.focus) ostatniFokus.focus();
  }

  document.querySelectorAll("[data-zamknij]").forEach(function (b) {
    b.addEventListener("click", function () {
      zamknijModal(b.closest(".kus-modal"));
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".kus-modal:not([hidden])").forEach(zamknijModal);
  });

  /* ---------------- podsumowanie ---------------- */

  var podsum = document.getElementById("kusPodsum");
  var podsumTresc = document.getElementById("kusPodsumTresc");

  function tekstOceny() {
    var m = najwyzszy();
    if (m === 3) return "Lista zawiera usterkę niebezpieczną — pomocniczo: wynik " +
      "negatywny oraz konieczność dalszego postępowania zgodnie z przepisami.";
    if (m === 2) return "Lista zawiera usterkę poważną — pomocniczo: wynik negatywny.";
    if (m === 1) return "Brak usterek poważnych i niebezpiecznych na liście.";
    return "Lista jest pusta.";
  }

  function budujPodsumowanie() {
    podsumTresc.replaceChildren();
    podsumTresc.appendChild(el("p", "kus-ps-typ",
      "Rodzaj badania: okresowe (załącznik nr 1)"));

    lista.forEach(function (p) {
      var r = null;
      for (var i = 0; i < BAZA.length; i++) if (BAZA[i].k === p.k) { r = BAZA[i]; break; }
      var k = el("div", "kus-ps-poz");
      var g = el("p", "kus-ps-gora");
      g.appendChild(el("span", "kus-kod", p.k));
      var b = el("span", "kus-sev kus-sev--" + p.s.toLowerCase());
      b.textContent = p.s + " · Priorytet " + PRIO[p.s] + " · " + NAZWY[p.s];
      g.appendChild(b);
      k.appendChild(g);
      k.appendChild(el("p", "kus-ps-opis", r ? r.o : ""));
      if (r && r.i) k.appendChild(el("p", "kus-ps-el", r.e + " " + r.i));
      podsumTresc.appendChild(k);
    });

    var ocena = el("div", "kus-ps-ocena kus-ps-ocena--" +
      (najwyzszy() === 3 ? "un" : najwyzszy() === 2 ? "up" : "ud"));
    ocena.appendChild(el("p", "kus-ps-ocena-tytul", "Ocena pomocnicza"));
    ocena.appendChild(el("p", "kus-ps-ocena-tekst", tekstOceny()));
    podsumTresc.appendChild(ocena);
  }

  function podsumowanieTekstem() {
    var w = ["Kody usterek — okresowe badanie techniczne (załącznik nr 1)", ""];
    lista.forEach(function (p) {
      var r = null;
      for (var i = 0; i < BAZA.length; i++) if (BAZA[i].k === p.k) { r = BAZA[i]; break; }
      w.push(p.k + "  [" + p.s + " / Priorytet " + PRIO[p.s] + " — " + NAZWY[p.s] + "]");
      if (r) { w.push("   " + r.o); if (r.i) w.push("   element: " + r.e + " " + r.i); }
    });
    w.push("", "Ocena pomocnicza: " + tekstOceny(), "",
      "Narzędzie pomocnicze. Ostateczną ocenę i kwalifikację usterki ustala " +
      "uprawniony diagnosta.");
    return w.join("\n");
  }

  document.getElementById("kusPodsumowanie").addEventListener("click", function () {
    budujPodsumowanie(); pokazModal(podsum);
  });
  document.getElementById("kusWyczysc").addEventListener("click", function () {
    lista = []; zapiszListe(); rysujPasek(); odswiezPrzyciski();
  });
  document.getElementById("kusKopiuj").addEventListener("click", function (e) {
    var t = podsumowanieTekstem();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(function () {
        e.target.textContent = "Skopiowano";
        setTimeout(function () { e.target.textContent = "Kopiuj podsumowanie"; }, 1600);
      });
    }
  });

  /* ---------------- filtry i pole ---------------- */

  elFiltry.querySelectorAll(".kus-chip").forEach(function (c) {
    c.addEventListener("click", function () {
      var kat = c.getAttribute("data-kategoria");
      var dz = c.getAttribute("data-dzial");
      var grupa = kat ? "data-kategoria" : "data-dzial";
      var aktywny = c.getAttribute("aria-pressed") === "true";
      elFiltry.querySelectorAll("[" + grupa + "]").forEach(function (x) {
        x.setAttribute("aria-pressed", "false");
      });
      c.setAttribute("aria-pressed", String(!aktywny));
      if (kat) filtrKat = aktywny ? null : kat;
      else filtrDzial = aktywny ? null : dz;
      szukaj();
    });
  });

  var timer = null;
  elWejscie.addEventListener("input", function () {
    elCzysc.hidden = !elWejscie.value;
    clearTimeout(timer);
    timer = setTimeout(szukaj, DEBOUNCE_MS);
  });
  elWejscie.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { elWejscie.value = ""; elCzysc.hidden = true; szukaj(); }
  });
  document.getElementById("kusForm").addEventListener("submit", function (e) {
    e.preventDefault(); clearTimeout(timer); szukaj();
  });
  elCzysc.addEventListener("click", function () {
    elWejscie.value = ""; elCzysc.hidden = true; szukaj(); elWejscie.focus();
  });
  elWiecej.addEventListener("click", function () { pokaz(true); });

  /* ---------------- start ---------------- */

  rysujPasek();
  fetch("/pomoce/kody-usterek/dane?v=" + encodeURIComponent(wersja))
    .then(function (o) { return o.json(); })
    .then(function (d) { BAZA = d; szukaj(); })
    .catch(function () {
      elLicznik.textContent = "Nie udało się wczytać bazy usterek.";
    });
})();
