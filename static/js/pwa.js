/* ===================================================================
   Rejestracja service workera i pasek aktualizacji.

   Nowa wersja NIE przejmuje kontroli sama. Czeka, aż użytkownik kliknie
   „Odśwież" — inaczej przeładowanie mogłoby wypaść w chwili, gdy ktoś ma
   na ekranie listę wybranych usterek albo wynik wyszukiwania.
   =================================================================== */
(function () {
  "use strict";

  if (!("serviceWorker" in navigator)) return;

  var oczekujacy = null;

  function pokazPasek() {
    if (document.getElementById("pwaPasek")) return;
    var pasek = document.createElement("div");
    pasek.id = "pwaPasek";
    pasek.className = "pwa-pasek";
    pasek.setAttribute("role", "status");
    pasek.setAttribute("aria-live", "polite");

    var tekst = document.createElement("span");
    tekst.className = "pwa-pasek-tekst";
    tekst.textContent = "Dostępna jest nowa wersja aplikacji.";
    pasek.appendChild(tekst);

    var odswiez = document.createElement("button");
    odswiez.type = "button";
    odswiez.className = "pwa-pasek-btn pwa-pasek-btn--glowny";
    odswiez.textContent = "Odśwież";
    odswiez.addEventListener("click", function () {
      if (oczekujacy) oczekujacy.postMessage({ typ: "PRZEJMIJ" });
    });
    pasek.appendChild(odswiez);

    var pozniej = document.createElement("button");
    pozniej.type = "button";
    pozniej.className = "pwa-pasek-btn";
    pozniej.textContent = "Później";
    pozniej.addEventListener("click", function () { pasek.remove(); });
    pasek.appendChild(pozniej);

    document.body.appendChild(pasek);
  }

  navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function (rej) {
    if (rej.waiting) { oczekujacy = rej.waiting; pokazPasek(); }

    rej.addEventListener("updatefound", function () {
      var nowy = rej.installing;
      if (!nowy) return;
      nowy.addEventListener("statechange", function () {
        // "installed" przy istniejącym kontrolerze = jest już stara wersja,
        // czyli to aktualizacja, a nie pierwsza instalacja.
        if (nowy.state === "installed" && navigator.serviceWorker.controller) {
          oczekujacy = nowy;
          pokazPasek();
        }
      });
    });
  }).catch(function () {
    /* brak service workera nie może zepsuć aplikacji */
  });

  // Przeładowanie dopiero po faktycznej zmianie kontrolera, jeden raz.
  var przeladowano = false;
  navigator.serviceWorker.addEventListener("controllerchange", function () {
    if (przeladowano) return;
    przeladowano = true;
    window.location.reload();
  });

  /* ---- pobranie kompletu danych na żądanie ---- */

  window.PaGonOffline = {
    /**
     * @param {string[]} adresy  wersjonowane adresy endpointów danych
     * @param {function} naPostep  wywoływane z (gotowe, wszystkich)
     */
    pobierz: function (adresy, naPostep) {
      if (!navigator.serviceWorker.controller) return false;
      if (typeof naPostep === "function") {
        navigator.serviceWorker.addEventListener("message", function nasluch(e) {
          var d = e.data || {};
          if (d.typ === "POSTEP_OFFLINE") naPostep(d.gotowe, d.wszystkich);
          if (d.typ === "KONIEC_OFFLINE") {
            naPostep(d.gotowe, d.wszystkich, true);
            navigator.serviceWorker.removeEventListener("message", nasluch);
          }
        });
      }
      navigator.serviceWorker.controller.postMessage({
        typ: "POBIERZ_OFFLINE", adresy: adresy,
      });
      return true;
    },
  };
})();
