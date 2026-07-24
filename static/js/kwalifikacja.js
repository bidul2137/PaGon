/* ===================================================================
   KWALIFIKACJA ZDARZENIA DROGOWEGO — kreator (drzewo decyzyjne).
   Ulepszenia względem klasycznego "Wstecz": ścieżka odpowiedzi jest
   widoczna jako klikalne chipy (powrót do dowolnego kroku), wynik
   pokazuje mandat/punkty z taryfikatora i link do rekordów.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("kwz-dane");
  if (!dataEl) return;
  var DANE = null;
  try { DANE = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!DANE || !DANE.wezly) return;

  var panel = document.getElementById("kwz-panel");
  var sciezkaEl = document.getElementById("kwz-sciezka");
  var stos = []; // [{wezel, opcja}] — historia odpowiedzi

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  function aktualnyWezel() {
    if (!stos.length) return DANE.start;
    var ostatnia = stos[stos.length - 1];
    return DANE.wezly[ostatnia.wezel].opcje[ostatnia.opcja].next;
  }

  function rysujSciezke() {
    sciezkaEl.innerHTML = "";
    if (!stos.length) return;
    stos.forEach(function (krok, i) {
      var w = DANE.wezly[krok.wezel];
      var o = w.opcje[krok.opcja];
      var chip = el("button", "kwz-chip");
      chip.type = "button";
      chip.appendChild(el("span", "kwz-chip-q", (w.krotko || w.pytanie) + ":"));
      chip.appendChild(el("span", "kwz-chip-a", o.krotko || o.tekst));
      chip.title = "Wróć i zmień odpowiedź";
      chip.addEventListener("click", function () {
        stos = stos.slice(0, i); // cofnij do tego pytania
        rysuj();
      });
      sciezkaEl.appendChild(chip);
    });
    var reset = el("button", "kwz-chip kwz-chip--reset", "Od nowa ↺");
    reset.type = "button";
    reset.addEventListener("click", function () { stos = []; rysuj(); });
    sciezkaEl.appendChild(reset);
  }

  function rysujPytanie(id) {
    var w = DANE.wezly[id];
    var karta = el("div", "kal-karta kwz-karta");
    karta.appendChild(el("p", "kal-sekcja-tytul", "Pytanie " + (stos.length + 1)));
    karta.appendChild(el("h2", "kwz-pytanie", w.pytanie));
    if (w.podpowiedz) karta.appendChild(el("p", "kwz-podpowiedz", w.podpowiedz));
    var opcje = el("div", "kwz-opcje");
    w.opcje.forEach(function (o, idx) {
      var btn = el("button", "kwz-opcja", o.tekst);
      btn.type = "button";
      btn.addEventListener("click", function () {
        stos.push({ wezel: id, opcja: idx });
        rysuj();
      });
      opcje.appendChild(btn);
    });
    karta.appendChild(opcje);
    if (stos.length) {
      var wstecz = el("button", "kwz-wstecz", "‹ Wstecz");
      wstecz.type = "button";
      wstecz.addEventListener("click", function () { stos.pop(); rysuj(); });
      karta.appendChild(wstecz);
    }
    panel.appendChild(karta);
  }

  function rysujWynik(id) {
    var w = DANE.wyniki[id];
    var klasa = w.typ === "wypadek" ? " kal-karta--stop" : (w.typ === "brak" ? " kal-karta--ok" : " kwz-karta--wykroczenie");
    var karta = el("div", "kal-karta kwz-karta" + klasa);
    karta.appendChild(el("p", "kal-sekcja-tytul", "Wynik"));
    karta.appendChild(el("h2", "kwz-wynik-tytul" + (w.typ === "wypadek" ? " kwz-wynik-tytul--stop" : ""),
      (w.typ === "wypadek" ? "⚠ " : "") + w.tytul));
    karta.appendChild(el("p", "kal-opis", w.opis));

    (w.warianty || []).forEach(function (v) {
      if (v.etykieta) karta.appendChild(el("p", "kwz-wariant-tytul", v.etykieta));
      var fakty = el("div", "kal-fakty");
      var m = el("div", "kal-fakt is-gold");
      m.appendChild(el("span", "kal-fakt-label", "Mandat (taryfikator)"));
      m.appendChild(el("span", "kal-fakt-val", typeof v.mandat === "number" ? v.mandat + " zł" : String(v.mandat)));
      fakty.appendChild(m);
      var p = el("div", "kal-fakt");
      p.appendChild(el("span", "kal-fakt-label", v.recydywa ? "Punkty / recydywa" : "Punkty"));
      p.appendChild(el("span", "kal-fakt-val", (v.punkty || 0) + " pkt" + (v.recydywa ? " / " + v.recydywa + " zł" : "")));
      fakty.appendChild(p);
      karta.appendChild(fakty);
    });

    if (w.mrd2) {
      karta.appendChild(el("p", "kwz-mrd2", "Sporządź kartę zdarzenia drogowego MRD-2."));
    }
    if (w.czynnosci && w.czynnosci.length) {
      var naglowek = el("p", "kwz-srodki-tytul", "Wobec trzeźwego sprawcy zastosuj:");
      karta.appendChild(naglowek);
      var ul = document.createElement("ul");
      ul.className = "kwz-srodki";
      w.czynnosci.forEach(function (c) { ul.appendChild(el("li", null, c)); });
      karta.appendChild(ul);
    }
    if (w.taryfikator) {
      var link = document.createElement("a");
      link.className = "kwz-taryfikator";
      link.href = "/taryfikator?q=" + encodeURIComponent(w.taryfikator);
      link.textContent = "Zobacz w taryfikatorze ›";
      karta.appendChild(link);
    }
    karta.appendChild(el("p", "kwz-trzezwosc", DANE.uwaga_trzezwosc || ""));

    var restart = el("button", "kpj-szczegoly kwz-restart", "Nowa kwalifikacja");
    restart.type = "button";
    restart.addEventListener("click", function () { stos = []; rysuj(); });
    karta.appendChild(restart);

    panel.appendChild(karta);
  }

  function rysuj() {
    panel.innerHTML = "";
    rysujSciezke();
    var id = aktualnyWezel();
    if (DANE.wezly[id]) rysujPytanie(id);
    else if (DANE.wyniki && DANE.wyniki[id]) rysujWynik(id);
  }

  rysuj();
})();
