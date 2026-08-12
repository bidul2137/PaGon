/* ===================================================================
   PaGon — service worker.

   Cztery magazyny, każdy z inną strategią, bo zasoby mają różny cykl życia:

   1. powłoka  — precache przy instalacji. CSS, JS, ikony, strona offline.
   2. strony   — network-first. Widoki renderuje serwer, więc po wdrożeniu
                 poprawki użytkownik ma zobaczyć nową wersję; cache jest
                 wyłącznie siatką bezpieczeństwa.
   3. dane     — cache-first, ale KLUCZEM JEST PEŁNY ADRES Z ?v=<wersja>.
                 Wersja pochodzi z metadata.json bazy, więc po aktualizacji
                 danych prawnych powstaje nowy klucz i stara treść fizycznie
                 nie może przykryć nowej. To jedyny powód, dla którego
                 wolno tu użyć cache-first.
   4. obrazy   — cache-first z limitem. 13 MB grafik znaków nie może rosnąć
                 bez końca, więc trzymamy najwyżej LIMIT_OBRAZOW plików.

   Czego NIE cache'ujemy nigdy: odpowiedzi innych niż 200, żądań innych niż
   GET, dokumentów PDF (jeden waży 37 MB), zapytań do innych origin.
   =================================================================== */

const WERSJA = "v1";
const MAGAZYN = {
  powloka: `pagon-powloka-${WERSJA}`,
  strony: `pagon-strony-${WERSJA}`,
  dane: `pagon-dane-${WERSJA}`,
  obrazy: `pagon-obrazy-${WERSJA}`,
};
const WSZYSTKIE = Object.values(MAGAZYN);

const STRONA_OFFLINE = "/offline";
const LIMIT_OBRAZOW = 250;

// Adresy danych, dla których wolno użyć cache-first (mają ?v= z wersją bazy).
const SCIEZKI_DANYCH = [
  "/pomoce/znaki/dane",
  "/pomoce/tablica-adr/dane",
  "/pomoce/kody-czynow/dane",
  "/pomoce/kody-pocztowe/dane",
  "/pomoce/kody-usterek/dane",
  "/api/taryfikator",
];

/* ------------------------------------------------------------------ */
/* instalacja                                                          */
/* ------------------------------------------------------------------ */

self.addEventListener("install", (zdarzenie) => {
  zdarzenie.waitUntil(
    (async () => {
      const magazyn = await caches.open(MAGAZYN.powloka);
      // Lista powstaje po stronie serwera (/static/precache.json), żeby nie
      // trzeba było ręcznie dopisywać każdego nowego pliku CSS/JS.
      let lista = [STRONA_OFFLINE, "/"];
      try {
        const odp = await fetch("/static/precache.json", { cache: "no-store" });
        if (odp.ok) lista = lista.concat(await odp.json());
      } catch (e) {
        // Brak listy nie może zablokować instalacji — powłoka dojdzie
        // przy pierwszym użyciu przez strategię dla stron i zasobów.
      }
      // addAll przerywa całość przy jednym błędzie, więc dokładamy pojedynczo.
      await Promise.all(
        lista.map((u) =>
          magazyn.add(new Request(u, { cache: "reload" })).catch(() => {})
        )
      );
    })()
  );
  // NIE wywołujemy tu skipWaiting — nowa wersja czeka, aż użytkownik ją
  // przyjmie. Automatyczne przejęcie potrafi przeładować stronę w chwili,
  // gdy ktoś ma na ekranie listę usterek albo wynik wyszukiwania.
});

/* ------------------------------------------------------------------ */
/* aktywacja                                                           */
/* ------------------------------------------------------------------ */

self.addEventListener("activate", (zdarzenie) => {
  zdarzenie.waitUntil(
    (async () => {
      const nazwy = await caches.keys();
      await Promise.all(
        nazwy
          .filter((n) => n.startsWith("pagon-") && !WSZYSTKIE.includes(n))
          .map((n) => caches.delete(n))
      );
      await sprzatnijStareDane();
      await self.clients.claim();
    })()
  );
});

/** Usuwa wpisy danych o nieaktualnym ?v= — po podmianie bazy prawnej
 *  stary zbiór nie ma prawa zostać na dysku i wprowadzać w błąd. */
async function sprzatnijStareDane() {
  const magazyn = await caches.open(MAGAZYN.dane);
  const wpisy = await magazyn.keys();
  const najnowsze = new Map();
  for (const zadanie of wpisy) {
    const u = new URL(zadanie.url);
    const poprzedni = najnowsze.get(u.pathname);
    if (!poprzedni || (u.searchParams.get("v") || "") > poprzedni.wersja) {
      najnowsze.set(u.pathname, { wersja: u.searchParams.get("v") || "", zadanie });
    }
  }
  const zachowane = new Set([...najnowsze.values()].map((x) => x.zadanie.url));
  await Promise.all(
    wpisy.filter((z) => !zachowane.has(z.url)).map((z) => magazyn.delete(z))
  );
}

/* ------------------------------------------------------------------ */
/* obsługa żądań                                                       */
/* ------------------------------------------------------------------ */

self.addEventListener("fetch", (zdarzenie) => {
  const zadanie = zdarzenie.request;
  if (zadanie.method !== "GET") return;

  const url = new URL(zadanie.url);
  if (url.origin !== self.location.origin) return;   // Google Fonts itd. — bez cache
  if (url.pathname.startsWith("/pomoce/pdf/")) return; // jeden PDF ma 37 MB

  if (SCIEZKI_DANYCH.includes(url.pathname)) {
    zdarzenie.respondWith(daneNajpierwZCache(zadanie));
  } else if (zadanie.mode === "navigate") {
    zdarzenie.respondWith(stronaNajpierwZSieci(zadanie));
  } else if (url.pathname.startsWith("/static/img/")) {
    zdarzenie.respondWith(obrazNajpierwZCache(zadanie));
  } else if (url.pathname.startsWith("/static/")) {
    zdarzenie.respondWith(zasobNajpierwZCache(zadanie));
  }
});

/** Dane prawne: cache-first po pełnym adresie (z wersją bazy). */
async function daneNajpierwZCache(zadanie) {
  const magazyn = await caches.open(MAGAZYN.dane);
  const zCache = await magazyn.match(zadanie);
  if (zCache) return zCache;
  const odp = await fetch(zadanie);
  if (odp && odp.status === 200) magazyn.put(zadanie, odp.clone());
  return odp;
}

/** Strony: sieć, potem cache, na końcu strona offline. */
async function stronaNajpierwZSieci(zadanie) {
  const magazyn = await caches.open(MAGAZYN.strony);
  try {
    const odp = await fetch(zadanie);
    if (odp && odp.status === 200) magazyn.put(zadanie, odp.clone());
    return odp;
  } catch (e) {
    const zCache = await magazyn.match(zadanie);
    if (zCache) return zCache;
    const powloka = await caches.open(MAGAZYN.powloka);
    return (
      (await powloka.match(STRONA_OFFLINE)) ||
      new Response("Brak połączenia.", {
        status: 503,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      })
    );
  }
}

/** Zasoby statyczne: cache-first (adresy mają ?v= z czasu modyfikacji pliku). */
async function zasobNajpierwZCache(zadanie) {
  const magazyn = await caches.open(MAGAZYN.powloka);
  const zCache = await magazyn.match(zadanie, { ignoreSearch: false });
  if (zCache) return zCache;
  try {
    const odp = await fetch(zadanie);
    if (odp && odp.status === 200) magazyn.put(zadanie, odp.clone());
    return odp;
  } catch (e) {
    // Bez wersji w adresie zasób mógł trafić do cache pod innym ?v=
    const luzniej = await magazyn.match(zadanie, { ignoreSearch: true });
    if (luzniej) return luzniej;
    throw e;
  }
}

/** Grafiki: cache-first z ograniczeniem liczby wpisów. */
async function obrazNajpierwZCache(zadanie) {
  const magazyn = await caches.open(MAGAZYN.obrazy);
  const zCache = await magazyn.match(zadanie);
  if (zCache) return zCache;
  const odp = await fetch(zadanie);
  if (odp && odp.status === 200) {
    await magazyn.put(zadanie, odp.clone());
    przytnijMagazyn(magazyn, LIMIT_OBRAZOW);
  }
  return odp;
}

async function przytnijMagazyn(magazyn, limit) {
  const wpisy = await magazyn.keys();
  if (wpisy.length <= limit) return;
  // Cache Storage zachowuje kolejność wstawiania, więc najstarsze są z przodu.
  await Promise.all(wpisy.slice(0, wpisy.length - limit).map((z) => magazyn.delete(z)));
}

/* ------------------------------------------------------------------ */
/* komunikacja ze stroną                                               */
/* ------------------------------------------------------------------ */

self.addEventListener("message", (zdarzenie) => {
  const dane = zdarzenie.data || {};
  if (dane.typ === "PRZEJMIJ") {
    // Wywoływane dopiero po kliknięciu „Odśwież" w pasku aktualizacji.
    self.skipWaiting();
  }
  if (dane.typ === "POBIERZ_OFFLINE" && Array.isArray(dane.adresy)) {
    zdarzenie.waitUntil(pobierzDoOffline(dane.adresy, zdarzenie.source));
  }
  if (dane.typ === "WERSJA") {
    zdarzenie.source?.postMessage({ typ: "WERSJA", wersja: WERSJA });
  }
});

/** Świadome pobranie kompletu danych — na żądanie użytkownika. */
async function pobierzDoOffline(adresy, klient) {
  const magazyn = await caches.open(MAGAZYN.dane);
  let gotowe = 0;
  for (const adres of adresy) {
    try {
      const zadanie = new Request(adres, { cache: "reload" });
      const odp = await fetch(zadanie);
      if (odp && odp.status === 200) await magazyn.put(zadanie, odp.clone());
    } catch (e) {
      /* pojedyncze niepowodzenie nie przerywa reszty */
    }
    gotowe += 1;
    klient?.postMessage({ typ: "POSTEP_OFFLINE", gotowe, wszystkich: adresy.length });
  }
  klient?.postMessage({ typ: "KONIEC_OFFLINE", gotowe, wszystkich: adresy.length });
}
