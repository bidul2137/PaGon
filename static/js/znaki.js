/* ===================================================================
   ZNAKI DROGOWE — wyszukiwarka, filtr w kategorii, ulubione, historia.

   Dane wyszukiwarki pobierane raz z /pomoce/znaki/dane i cache'owane;
   podstrony znaków są renderowane po stronie serwera, więc moduł działa
   offline po pierwszym wejściu. Cały DOM budowany przez createElement —
   żaden tekst z JSON nie trafia do innerHTML.
   =================================================================== */
(function () {
  "use strict";

  var K_ULUBIONE = "pagon-znaki-ulubione";
  var K_HISTORIA = "pagon-znaki-historia";
  var MAX_WYNIKOW = 10;
  var MAX_HISTORII = 4;      // ile ostatnio ogladanych znakow pokazujemy
  var ULUBIONE_ZWIN = 6;     // powyzej tylu ulubionych lista sie zwija

  var strona = document.querySelector(".zn-page");
  if (!strona) return;
  var wersja = strona.getAttribute("data-wersja") || "0";

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }
  function czytaj(klucz) {
    try { var s = window.localStorage.getItem(klucz); var t = s ? JSON.parse(s) : []; return t instanceof Array ? t : []; }
    catch (e) { return []; }
  }
  function zapisz(klucz, tab) {
    try { window.localStorage.setItem(klucz, JSON.stringify(tab)); } catch (e) {}
  }
  // "A 6C", "a6c", "A-6c" -> "a6c";  usuwa też polskie znaki
  function norm(s) {
    var mapa = { "ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ż":"z","ź":"z" };
    return String(s || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return mapa[z]; })
      .replace(/\s+/g, " ").trim();
  }
  function kodNorm(s) { return norm(s).replace(/[\s\-]/g, ""); }

  /* ---------- wspólny kafelek mini ---------- */
  function miniKarta(z) {
    var a = el("a", "zn-mini-karta");
    a.href = "/pomoce/znaki/znak/" + encodeURIComponent(z.code);
    var ik = el("span", "zn-mini-ikona");
    if (z.img) {
      var img = document.createElement("img");
      img.src = "/static/" + z.img + "?v=" + wersja; img.alt = ""; img.loading = "lazy";
      ik.appendChild(img);
    } else ik.appendChild(el("span", "zn-brak-ikony", z.code));
    a.appendChild(ik);
    a.appendChild(el("span", "zn-mini-kod", z.code));
    a.appendChild(el("span", "zn-mini-nazwa", z.name || ""));
    return a;
  }

  /* ================= strona główna ================= */
  var wejscie = document.getElementById("znSzukaj");
  if (wejscie) {
    var wyniki = document.getElementById("znWyniki");
    var BAZA = null, INDEKS = {};

    fetch("/pomoce/znaki/dane?v=" + encodeURIComponent(wersja), { cache: "force-cache" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        BAZA = d.znaki || [];
        BAZA.forEach(function (z) { INDEKS[z.code] = z; });
        rysujSekcje();
      })["catch"](function () {});

    function szukaj(fraza) {
      var q = norm(fraza), qk = kodNorm(fraza);
      if (!q || q.length < 2) return [];
      var tr = [];
      BAZA.forEach(function (z) {
        var kod = kodNorm(z.code), pkt = -1;
        if (kod === qk) pkt = 0;
        else if (kod.indexOf(qk) === 0) pkt = 1;
        else if (norm(z.name).indexOf(q) === 0) pkt = 2;
        else if (norm(z.name).indexOf(q) > -1) pkt = 3;
        else if (norm(z.short).indexOf(q) > -1) pkt = 4;
        else if ((z.kw || []).some(function (k) { return norm(k).indexOf(q) > -1; })) pkt = 5;
        if (pkt > -1) tr.push({ p: pkt, z: z });
      });
      tr.sort(function (a, b) { return a.p - b.p || a.z.code.localeCompare(b.z.code); });
      return tr.slice(0, MAX_WYNIKOW).map(function (t) { return t.z; });
    }

    function rysujWyniki(lista, pusteZapytanie) {
      wyniki.innerHTML = "";
      if (pusteZapytanie) { wyniki.hidden = true; wejscie.setAttribute("aria-expanded", "false"); return; }
      if (!lista.length) {
        wyniki.appendChild(el("p", "zn-brak-wynikow",
          "Nie znaleziono znaku. Spróbuj wpisać symbol, np. A-6c, lub inne słowo."));
      } else {
        lista.forEach(function (z) {
          var a = el("a", "zn-wynik");
          a.href = "/pomoce/znaki/znak/" + encodeURIComponent(z.code);
          a.setAttribute("role", "option");
          var ik = el("span", "zn-wynik-ikona");
          if (z.img) {
            var img = document.createElement("img");
            img.src = "/static/" + z.img + "?v=" + wersja; img.alt = ""; img.loading = "lazy";
            ik.appendChild(img);
          } else ik.appendChild(el("span", "zn-brak-ikony", z.code));
          a.appendChild(ik);
          var tr = el("span", "zn-wynik-tresc");
          tr.appendChild(el("span", "zn-kod", z.code));
          tr.appendChild(el("span", "zn-poz-nazwa", z.name || ""));
          tr.appendChild(el("span", "zn-wynik-opis", z.short || ""));
          a.appendChild(tr);
          wyniki.appendChild(a);
        });
      }
      wyniki.hidden = false;
      wejscie.setAttribute("aria-expanded", "true");
    }

    var timer = null;
    wejscie.addEventListener("input", function () {
      clearTimeout(timer);
      var v = wejscie.value;
      timer = setTimeout(function () {
        if (!BAZA) return;
        rysujWyniki(szukaj(v), norm(v).length < 2);
      }, 200);
    });
    wejscie.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { wyniki.hidden = true; wejscie.setAttribute("aria-expanded", "false"); }
      if (e.key === "ArrowDown") {
        var p = wyniki.querySelector(".zn-wynik");
        if (p) { e.preventDefault(); p.focus(); }
      }
    });
    document.addEventListener("click", function (e) {
      if (!wyniki.contains(e.target) && e.target !== wejscie) {
        wyniki.hidden = true; wejscie.setAttribute("aria-expanded", "false");
      }
    });

    var ulubioneRozwiniete = false;

    function rysujSekcje() {
      // ostatnio ogladane: krotka lista, zawsze przycieta
      var sekH = document.getElementById("znOstatnie");
      var lisH = document.getElementById("znOstatnieLista");
      if (sekH && lisH) {
        lisH.innerHTML = "";
        var poz = czytaj(K_HISTORIA).map(function (k) { return INDEKS[k]; })
                    .filter(Boolean).slice(0, MAX_HISTORII);
        sekH.hidden = !poz.length;
        poz.forEach(function (z) { lisH.appendChild(miniKarta(z)); });
      }

      // ulubione: przy wiekszej liczbie zwijamy, zeby nie spychac reszty strony
      var sekU = document.getElementById("znUlubione");
      var lisU = document.getElementById("znUlubioneLista");
      var przU = document.getElementById("znUlubioneWiecej");
      if (!sekU || !lisU) return;
      lisU.innerHTML = "";
      var ulub = czytaj(K_ULUBIONE).map(function (k) { return INDEKS[k]; }).filter(Boolean);
      if (!ulub.length) {
        sekU.hidden = true;
        if (przU) przU.hidden = true;
        return;
      }
      sekU.hidden = false;
      var zwijamy = ulub.length > ULUBIONE_ZWIN;
      var widoczne = (zwijamy && !ulubioneRozwiniete) ? ulub.slice(0, ULUBIONE_ZWIN) : ulub;
      widoczne.forEach(function (z) { lisU.appendChild(miniKarta(z)); });

      if (!przU) return;
      przU.hidden = !zwijamy;
      if (!zwijamy) { ulubioneRozwiniete = false; return; }
      przU.textContent = ulubioneRozwiniete
        ? "Zwiń"
        : "Pokaż wszystkie (" + ulub.length + ")";
      przU.setAttribute("aria-expanded", String(ulubioneRozwiniete));
    }

    var przWiecej = document.getElementById("znUlubioneWiecej");
    if (przWiecej) przWiecej.addEventListener("click", function () {
      ulubioneRozwiniete = !ulubioneRozwiniete;
      rysujSekcje();
      if (!ulubioneRozwiniete) przWiecej.focus();
    });

    var czysc = document.getElementById("znWyczyscHistorie");
    if (czysc) czysc.addEventListener("click", function () {
      zapisz(K_HISTORIA, []); rysujSekcje();
    });
  }

  /* ================= widok kategorii ================= */
  var filtr = document.getElementById("znFiltr");
  if (filtr) {
    var lista = document.getElementById("znLista");
    var pozycje = [].slice.call(lista.querySelectorAll(".zn-poz"));
    var brak = document.getElementById("znBrak");
    filtr.addEventListener("input", function () {
      var q = norm(filtr.value), qk = kodNorm(filtr.value), widoczne = 0;
      pozycje.forEach(function (li) {
        var h = li.getAttribute("data-szukaj") || "";
        var ok = !q || norm(h).indexOf(q) > -1 || kodNorm(h).indexOf(qk) > -1;
        li.hidden = !ok;
        if (ok) widoczne++;
      });
      if (brak) brak.hidden = widoczne > 0;
    });

    var bLista = document.getElementById("znWidokLista");
    var bKafelki = document.getElementById("znWidokKafelki");
    function ustawWidok(kafelki) {
      lista.classList.toggle("zn-lista--kafelki", kafelki);
      bLista.setAttribute("aria-pressed", String(!kafelki));
      bKafelki.setAttribute("aria-pressed", String(kafelki));
      try { window.localStorage.setItem("pagon-znaki-widok", kafelki ? "kafelki" : "lista"); } catch (e) {}
    }
    bLista.addEventListener("click", function () { ustawWidok(false); });
    bKafelki.addEventListener("click", function () { ustawWidok(true); });
    var zapisany = null;
    try { zapisany = window.localStorage.getItem("pagon-znaki-widok"); } catch (e) {}
    if (zapisany === "kafelki") ustawWidok(true);
  }

  /* ================= szczegóły znaku ================= */
  var kod = strona.getAttribute("data-kod");
  if (kod) {
    // historia oglądanych
    var h = czytaj(K_HISTORIA).filter(function (k) { return k !== kod; });
    h.unshift(kod);
    zapisz(K_HISTORIA, h.slice(0, MAX_HISTORII));

    var gw = document.getElementById("znGwiazdka");
    if (gw) {
      var odswiez = function () {
        gw.setAttribute("aria-pressed", String(czytaj(K_ULUBIONE).indexOf(kod) > -1));
      };
      odswiez();
      gw.addEventListener("click", function () {
        var u = czytaj(K_ULUBIONE);
        var i = u.indexOf(kod);
        if (i > -1) u.splice(i, 1); else u.unshift(kod);
        zapisz(K_ULUBIONE, u);
        odswiez();
      });
    }

    var podglad = document.getElementById("znPodglad");
    var otworz = document.getElementById("znPowieksz");
    var zamknij = document.getElementById("znPodgladZamknij");
    if (podglad && otworz && zamknij) {
      var pokaz = function (widoczny) {
        podglad.hidden = !widoczny;
        (widoczny ? zamknij : otworz).focus();
      };
      otworz.addEventListener("click", function () { pokaz(true); });
      zamknij.addEventListener("click", function () { pokaz(false); });
      podglad.addEventListener("click", function (e) { if (e.target === podglad) pokaz(false); });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !podglad.hidden) pokaz(false);
      });
    }
  }
})();
