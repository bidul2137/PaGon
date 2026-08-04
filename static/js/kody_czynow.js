/* ===================================================================
   KODY CZYNÓW — wyszukiwarka po kodzie i opisie naruszenia.

   Indeks pobierany RAZ z /pomoce/kody-czynow/dane i zostaje w cache
   przeglądarki (adres zawiera wersję zbioru). Wyszukiwanie nie wysyła
   żadnego żądania, więc moduł działa bez internetu.

   Cały DOM budujemy przez createElement/textContent — żaden fragment
   bazy nie trafia do innerHTML.
   =================================================================== */
(function () {
  "use strict";

  var K_HISTORIA = "pagon-czyny-historia";
  var MAX_WYNIKOW = 10;
  var MAX_HISTORII = 8;
  var DEBOUNCE_MS = 180;

  var strona = document.querySelector(".kcz-page");
  if (!strona) return;
  var wersja = strona.getAttribute("data-wersja") || "0";

  var elForm = document.getElementById("kczForm");
  var elWejscie = document.getElementById("kczWejscie");
  var elCzysc = document.getElementById("kczCzysc");
  var elWyniki = document.getElementById("kczWyniki");
  var elLicznik = document.getElementById("kczLicznik");
  var elKategorie = document.getElementById("kczKategorie");
  var elPowrot = document.getElementById("kczPowrot");
  if (!elForm || !elWejscie) return;

  var BAZA = null;
  var dzialFiltr = null;
  // nazwy działów czytamy z kafelków, żeby nie powielać ich w dwóch miejscach
  var NAZWY_DZIALOW = {};

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  // małe litery, bez polskich znaków — tak samo jak w importerze
  function norm(t) {
    var m = { "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
              "ó": "o", "ś": "s", "ż": "z", "ź": "z" };
    return String(t || "").toLowerCase()
      .replace(/[ąćęłńóśżź]/g, function (z) { return m[z]; })
      .replace(/\s+/g, " ").trim();
  }

  // "a-02", " A 02 ", "A2" -> "A02"; inaczej null
  function normKod(wpis) {
    var s = String(wpis || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    var m = /^([A-J])(\d{1,2})$/.exec(s);
    if (!m) return null;
    return m[1] + (m[2].length === 1 ? "0" + m[2] : m[2]);
  }

  function pozycja(r) {
    var a = el("a", "kcz-poz");
    a.href = "/pomoce/kody-czynow/kod/" + encodeURIComponent(r.n);
    var gora = el("span", "kcz-poz-gora");
    gora.appendChild(el("span", "kcz-kod", r.k));
    if (r.p !== null && r.p !== undefined) {
      gora.appendChild(el("span", "kcz-pkt", r.p + " pkt"));
    }
    if (r.m) gora.appendChild(el("span", "kcz-mand", "mandat w taryfikatorze"));
    a.appendChild(gora);
    a.appendChild(el("span", "kcz-poz-opis", r.t || "—"));
    return a;
  }

  function wyczyscDzial() {
    dzialFiltr = null;
    if (elKategorie) {
      elKategorie.querySelectorAll(".kcz-kat").forEach(function (x) {
        x.setAttribute("aria-pressed", "false");
      });
    }
    szukaj(elWejscie.value);
  }

  function pokaz(lista, opis) {
    elWyniki.replaceChildren();
    lista.slice(0, MAX_WYNIKOW).forEach(function (r) { elWyniki.appendChild(pozycja(r)); });

    if (elLicznik) {
      elLicznik.replaceChildren();
      // Gdy dział jest wybrany, sama liczba wyników nie wystarczy — trzeba widzieć,
      // CO jest wybrane i mieć czym z tego wyjść. Bez tego jedyną drogą powrotu
      // było odświeżenie strony.
      if (dzialFiltr) {
        var glowa = el("div", "kcz-dzial");
        glowa.appendChild(el("span", "kcz-dzial-litera", dzialFiltr));
        glowa.appendChild(el("span", "kcz-dzial-nazwa",
          NAZWY_DZIALOW[dzialFiltr] || ("Dział " + dzialFiltr)));
        glowa.appendChild(el("span", "kcz-dzial-ile", lista.length + " kodów"));
        elLicznik.appendChild(glowa);
      } else {
        elLicznik.textContent = lista.length
          ? (opis + ": " + lista.length + (lista.length > MAX_WYNIKOW
              ? " — pokazano pierwsze " + MAX_WYNIKOW : ""))
          : "Brak wyników.";
      }
    }
    if (elKategorie) elKategorie.hidden = lista.length > 0 || !!dzialFiltr;
  }

  function szukaj(fraza) {
    if (!BAZA) return;
    var q = norm(fraza);
    var kod = normKod(fraza);

    // Przycisk powrotu ma sens wyłącznie wtedy, gdy jest z czego wracać.
    // Ustawiamy go tutaj, bo poniżej są gałęzie kończące się wcześniej.
    if (elPowrot) elPowrot.hidden = !dzialFiltr;

    if (!q && !dzialFiltr) {
      elWyniki.replaceChildren();
      if (elLicznik) elLicznik.textContent = "";
      if (elKategorie) elKategorie.hidden = false;
      return;
    }
    if (!q && dzialFiltr) {
      pokaz(BAZA.filter(function (r) { return r.c === dzialFiltr; }), "Dział " + dzialFiltr);
      return;
    }

    // Dopasowanie SŁOWO PO SŁOWIE, a nie całą frazą: wpisane „pomoc ofiarom”
    // ma trafić w „Nieudzielenie pomocy ofiarom wypadku”. Każde słowo zapytania
    // musi wystąpić — dzięki temu kolejne słowa zawężają wynik, a nie poszerzają.
    var slowa = q.split(" ").filter(Boolean);
    var wynik = BAZA.filter(function (r) {
      if (dzialFiltr && r.c !== dzialFiltr) return false;
      if (kod && r.n === kod) return true;
      if (r.n.toLowerCase().indexOf(q.replace(/\s/g, "")) === 0) return true;
      var siano = norm(r.t) + " " + r.w.join(" ");
      return slowa.every(function (w) { return siano.indexOf(w) > -1; });
    });
    // dokładne trafienie w kod zawsze na górze
    if (kod) {
      wynik.sort(function (a, b) {
        return (b.n === kod ? 1 : 0) - (a.n === kod ? 1 : 0);
      });
    }
    pokaz(wynik, "Znaleziono");
    if (wynik.length) zapiszHistorie(fraza);
  }

  function zapiszHistorie(fraza) {
    try {
      var s = window.localStorage.getItem(K_HISTORIA);
      var h = s ? JSON.parse(s) : [];
      if (!(h instanceof Array)) h = [];
      h = h.filter(function (x) { return x !== fraza; });
      h.unshift(fraza);
      window.localStorage.setItem(K_HISTORIA, JSON.stringify(h.slice(0, MAX_HISTORII)));
    } catch (e) { /* historia jest dodatkiem — nie blokuje wyszukiwania */ }
  }

  if (elPowrot) elPowrot.addEventListener("click", function () {
    wyczyscDzial();
    elWejscie.focus();
  });

  var timer = null;
  elWejscie.addEventListener("input", function () {
    elCzysc.hidden = !elWejscie.value;
    clearTimeout(timer);
    var v = elWejscie.value;
    timer = setTimeout(function () { szukaj(v); }, DEBOUNCE_MS);
  });
  elWejscie.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { elWejscie.value = ""; elCzysc.hidden = true; szukaj(""); }
  });
  elForm.addEventListener("submit", function (e) { e.preventDefault(); szukaj(elWejscie.value); });
  elCzysc.addEventListener("click", function () {
    elWejscie.value = ""; elCzysc.hidden = true; szukaj(""); elWejscie.focus();
  });

  if (elKategorie) {
    elKategorie.querySelectorAll(".kcz-kat").forEach(function (a) {
      a.setAttribute("aria-pressed", "false");
      var nazwa = a.querySelector(".kcz-kat-nazwa");
      NAZWY_DZIALOW[a.getAttribute("data-dzial")] = nazwa ? nazwa.textContent : "";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        dzialFiltr = dzialFiltr === a.getAttribute("data-dzial")
          ? null : a.getAttribute("data-dzial");
        elKategorie.querySelectorAll(".kcz-kat").forEach(function (x) {
          x.setAttribute("aria-pressed", String(x.getAttribute("data-dzial") === dzialFiltr));
        });
        szukaj(elWejscie.value);
      });
    });
  }

  fetch("/pomoce/kody-czynow/dane?v=" + encodeURIComponent(wersja))
    .then(function (o) { if (!o.ok) throw new Error("brak bazy"); return o.json(); })
    .then(function (d) { BAZA = d; if (elWejscie.value) szukaj(elWejscie.value); })
    .catch(function () {
      // brak bazy to stan przewidziany — szablon pokazuje już instrukcję importu
    });
})();
