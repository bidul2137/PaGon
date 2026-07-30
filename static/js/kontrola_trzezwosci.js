/* ===================================================================
   KONTROLA TRZEŹWOŚCI — BADANY NA MIEJSCU — kreator (drzewo decyzyjne).
   Ten sam mechanizm co w "Kwalifikacji zdarzenia": chipy ścieżki
   (powrót do dowolnego kroku), przycisk Wstecz, karta wyniku.
   =================================================================== */
(function () {
  "use strict";

  var dataEl = document.getElementById("ktr-dane");
  if (!dataEl) return;
  var DANE = null;
  try { DANE = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!DANE || !DANE.wezly) return;

  var panel = document.getElementById("ktr-panel");
  var sciezkaEl = document.getElementById("ktr-sciezka");
  var stos = []; // [{wezel, opcja}] — historia odpowiedzi

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = txt;
    return n;
  }

  // Tekst przepisu zawsze zwiniety — karta ma prowadzic przez czynnosci,
  // a cytat z rozporzadzenia jest materialem do sprawdzenia, nie do czytania
  // przy kazdym uzyciu kreatora.
  function blokPrzepis(przepis) {
    var box = el("div", "kal-przepis");
    String(przepis.body).split("\n").forEach(function (l) {
      if (l.trim()) box.appendChild(el("p", "kal-przepis-body", l.trim()));
    });
    var det = document.createElement("details");
    det.className = "kal-podstawy";
    det.appendChild(el("summary", null, "Podstawa prawna — " + przepis.head));
    det.appendChild(box);
    return det;
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
    // wyliczenie przypadkow, w ktorych pytanie ma zastosowanie
    if (w.kroki && w.kroki.length) {
      var listaP = el("ul", "kwz-srodki");
      w.kroki.forEach(function (k) { listaP.appendChild(el("li", null, k)); });
      karta.appendChild(listaP);
    }
    if (w.instrukcja) karta.appendChild(el("p", "kwz-mrd2", w.instrukcja));
    if (w.przepis) karta.appendChild(blokPrzepis(w.przepis));
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

  function linkTaryfikator(q, tekst) {
    var link = document.createElement("a");
    link.className = "kwz-taryfikator";
    link.href = "/taryfikator?q=" + encodeURIComponent(q);
    link.textContent = tekst || "Zobacz w taryfikatorze ›";
    return link;
  }

  function rysujWynik(id) {
    var w = DANE.wyniki[id];
    var klasa = (w.typ === "stop" || w.typ === "krew") ? " kal-karta--stop"
      : (w.typ === "ok" ? " kal-karta--ok" : " kwz-karta--wykroczenie");
    var karta = el("div", "kal-karta kwz-karta" + klasa);
    karta.appendChild(el("p", "kal-sekcja-tytul", "Wynik"));

    var prefiks = (w.typ === "stop" || w.typ === "krew") ? "⚠ " : (w.typ === "ok" ? "✓ " : "");
    karta.appendChild(el("h2", "kwz-wynik-tytul" + ((w.typ === "stop" || w.typ === "krew") ? " kwz-wynik-tytul--stop" : ""),
      prefiks + w.tytul));

    if (w.kwalifikacja) karta.appendChild(el("p", "ktr-kwalifikacja", w.kwalifikacja));
    if (w.opis) karta.appendChild(el("p", "kal-opis", w.opis));

    // kolejne czynnosci do wykonania (np. harmonogram pomiarow) — lista kropkowana
    if (w.kroki && w.kroki.length) {
      var lista = el("ul", "kwz-srodki");
      w.kroki.forEach(function (k) { lista.appendChild(el("li", null, k)); });
      karta.appendChild(lista);
    }

    // warianty kwalifikacji (pojazd mechaniczny vs inny pojazd) — art. 87 KW
    // rozroznia je w paragrafach, a tryb mandatowy jest mozliwy tylko dla
    // pojazdow innych niz mechaniczne (przy § 1 zakaz z § 3 jest obligatoryjny)
    (w.warianty || []).forEach(function (v) {
      var blok = el("div", "ktr-wariant");
      if (v.etykieta) blok.appendChild(el("p", "kwz-wariant-tytul", v.etykieta));
      if (v.kwalifikacja) blok.appendChild(el("p", "ktr-kwalifikacja", v.kwalifikacja));
      if (v.opis) blok.appendChild(el("p", "kal-opis", v.opis));
      // tryb mandatowy — kluczowa informacja operacyjna, wyroznamy ja badgem
      if (v.mandat) {
        var typM = v.mandat_typ === "ok" ? "ok" : "brak";
        var bMandat = el("p", "ktr-mandat ktr-mandat--" + typM);
        bMandat.appendChild(el("span", "ktr-mandat-ikona", typM === "ok" ? "✓" : "✕"));
        bMandat.appendChild(el("span", "ktr-mandat-tekst", v.mandat));
        blok.appendChild(bMandat);
      }
      if (v.taryfikator) blok.appendChild(linkTaryfikator(v.taryfikator, v.taryfikator_tekst));
      karta.appendChild(blok);
    });

    if (w.uwaga) karta.appendChild(el("p", "kwz-mrd2", w.uwaga));
    if (w.przepis) karta.appendChild(blokPrzepis(w.przepis));

    if (w.taryfikator) karta.appendChild(linkTaryfikator(w.taryfikator, w.taryfikator_tekst));
    if (w.podstawa) karta.appendChild(el("p", "kwz-trzezwosc", "Podstawa: " + w.podstawa));

    var restart = el("button", "kpj-szczegoly kwz-restart", "Nowa kontrola");
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
