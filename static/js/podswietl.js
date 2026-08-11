/* ===================================================================
   PODŚWIETLANIE TRAFIEŃ — wspólne dla wszystkich wyszukiwarek PaGon.

   Zamiast przerabiać renderowanie w każdym module, skrypt działa na
   gotowym wyniku: przechodzi po węzłach tekstowych kontenera i owija
   trafienia w <mark>. Dzięki temu obejmuje tak samo wyszukiwarki
   javascriptowe (kody czynów, znaki, kody pocztowe, ADR, taryfikator)
   jak i te renderowane po stronie serwera (przepisy, pomoce), gdzie
   frazę bierzemy z parametru ?q=.

   Dopasowanie musi być takie samo jak w samych wyszukiwarkach: bez
   względu na wielkość liter i polskie znaki, po RDZENIU wyrazu — inaczej
   „światła” nie podświetliłoby „światło”. Trafienie rozciągamy do granic
   wyrazu, żeby nie zostawiać podświetlonego kikuta „świat”.

   Podświetlenia nie wstawiamy przez innerHTML — wyłącznie createElement
   i textContent, więc treść bazy ani wpis użytkownika nie mogą wnieść
   znaczników.
   =================================================================== */
(function () {
  "use strict";

  // Pole wyszukiwania -> kontener z wynikami. Gdy kontenera nie ma na
  // stronie, wpis jest po prostu pomijany.
  var MODULY = [
    { pole: "#kczWejscie", wyniki: "#kczWyniki" },
    { pole: "#kpWejscie", wyniki: "#kpWyniki, #kpLista" },
    { pole: "#znSzukaj", wyniki: "#znLista, #znWidokLista" },
    { pole: "#itdSzukaj", wyniki: ".itd-page .tar-frame" },
    { pole: "#hol-szukaj", wyniki: ".tar-frame" },
    { pole: "#tar-search-input", wyniki: "#tar-lista" },
    { pole: "#adrNameSearch", wyniki: "#adrWyniki" },
    { pole: "#prz-docs-search", wyniki: "#prz-docs-modal .prz-docs-panel" },
    // Przepisy i Pomoce filtrują listę na żywo tym samym polem, którym
    // wysyłają formularz — stąd jeden wpis obsługuje obie strony.
    { pole: ".tar-searchbar input[name='q']", wyniki: ".prz-lista, .prz-tiles" }
    // Kody usterek mają własne podświetlanie wplecione w budowanie wierszy
    // (podświetla też nagłówki kart grup), więc świadomie ich tu nie ma —
    // dwa mechanizmy naraz zagnieżdżałyby <mark> w <mark>.
  ];

  // Strony renderowane po stronie serwera (Przepisy i Pomoce) — obie wypisują
  // wyniki w ul.prz-lista, a frazę mamy w adresie.
  var Z_ADRESU = ".prz-lista";

  // Łącznik traktujemy jak literę, żeby nazwy i kody złożone podświetlały
  // się w całości: „Goczałkowice-Zdrój”, „11-040”, „Rutka-Tartak”.
  var LITERA = /[0-9a-zA-ZąćęłńóśżźĄĆĘŁŃÓŚŻŹ-]/;
  var POMIJANE = { SCRIPT: 1, STYLE: 1, MARK: 1, INPUT: 1, TEXTAREA: 1,
                   BUTTON: 1, SELECT: 1, SVG: 1 };

  function norm(t) {
    var m = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
              "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    // Bez scalania spacji: każdy znak ma odpowiednik w oryginale jeden do
    // jednego, więc indeksy trafień pasują wprost do wyświetlanego tekstu.
    return String(t || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return m[z]; });
  }

  function rdzenie(fraza) {
    return norm(fraza).split(/[^0-9a-z]+/).filter(function (s) {
      return s.length >= 2;
    }).map(function (s) {
      // Ten sam rdzeń co w wyszukiwarkach: od 5 znaków ucinamy końcówkę.
      return s.length >= 5 ? s.slice(0, s.length - 2) : s;
    });
  }

  function zakresy(tekst, stemy) {
    var n = norm(tekst), z = [];
    stemy.forEach(function (s) {
      var od = 0, i;
      while ((i = n.indexOf(s, od)) > -1) {
        var a = i, b = i + s.length;
        while (a > 0 && LITERA.test(tekst.charAt(a - 1))) a--;
        while (b < tekst.length && LITERA.test(tekst.charAt(b))) b++;
        z.push([a, b]);
        od = i + s.length;
      }
    });
    if (!z.length) return z;
    z.sort(function (x, y) { return x[0] - y[0]; });
    var out = [z[0]];
    for (var j = 1; j < z.length; j++) {
      var ost = out[out.length - 1];
      if (z[j][0] <= ost[1]) ost[1] = Math.max(ost[1], z[j][1]);
      else out.push(z[j]);
    }
    return out;
  }

  function wezlyTekstowe(korzen) {
    var out = [];
    var it = document.createTreeWalker(korzen, NodeFilter.SHOW_TEXT, {
      acceptNode: function (w) {
        if (!w.nodeValue || !w.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        var r = w.parentNode;
        while (r && r !== korzen) {
          if (POMIJANE[r.nodeName.toUpperCase()]) return NodeFilter.FILTER_REJECT;
          r = r.parentNode;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var w;
    while ((w = it.nextNode())) out.push(w);
    return out;
  }

  function zdejmij(korzen) {
    korzen.querySelectorAll("mark.pg-traf").forEach(function (m) {
      var t = document.createTextNode(m.textContent);
      m.parentNode.replaceChild(t, m);
    });
    korzen.normalize();   // scala rozbite węzły, inaczej trafienia na granicy przepadają
  }

  function naloz(korzen, fraza) {
    zdejmij(korzen);
    var stemy = rdzenie(fraza);
    if (!stemy.length) return;

    wezlyTekstowe(korzen).forEach(function (wezel) {
      var tekst = wezel.nodeValue;
      var zk = zakresy(tekst, stemy);
      if (!zk.length) return;
      var frag = document.createDocumentFragment(), poz = 0;
      zk.forEach(function (z) {
        if (z[0] > poz) frag.appendChild(document.createTextNode(tekst.slice(poz, z[0])));
        var m = document.createElement("mark");
        m.className = "pg-traf";
        m.textContent = tekst.slice(z[0], z[1]);
        frag.appendChild(m);
        poz = z[1];
      });
      if (poz < tekst.length) frag.appendChild(document.createTextNode(tekst.slice(poz)));
      wezel.parentNode.replaceChild(frag, wezel);
    });
  }

  function podepnij(pole, selektorWynikow) {
    var wejscie = document.querySelector(pole);
    if (!wejscie) return;
    var cele = [].slice.call(document.querySelectorAll(selektorWynikow));
    if (!cele.length) return;

    var wStrakcie = false;
    function odswiez() {
      if (wStrakcie) return;
      wStrakcie = true;                     // własne zmiany nie mogą wywołać kolejnego przebiegu
      obserwatorzy.forEach(function (o) { o.disconnect(); });
      cele.forEach(function (c) { naloz(c, wejscie.value); });
      obserwatorzy.forEach(function (o, i) {
        o.observe(cele[i], { childList: true, subtree: true });
      });
      wStrakcie = false;
    }

    // Moduły przerysowują wyniki same, więc nie wystarczy reagować na wpisywanie —
    // trzeba złapać moment, gdy w kontenerze pojawi się nowa treść.
    var obserwatorzy = cele.map(function () {
      return new MutationObserver(function () {
        if (!wStrakcie) window.requestAnimationFrame(odswiez);
      });
    });

    var timer = null;
    wejscie.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(odswiez, 220);     // po debounce samej wyszukiwarki
    });
    odswiez();
  }

  function start() {
    MODULY.forEach(function (m) { podepnij(m.pole, m.wyniki); });

    var q = new URLSearchParams(window.location.search).get("q");
    if (q && q.trim()) {
      document.querySelectorAll(Z_ADRESU).forEach(function (c) { naloz(c, q); });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
