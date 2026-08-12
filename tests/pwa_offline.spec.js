/* ===================================================================
   Test PWA / offline — Chromium + Playwright.

   NIE URUCHOMIONY przez autora zmian: środowisko, w którym powstawał ten
   plik, nie ma ani przeglądarki, ani dostępu do sieci, więc Playwrighta
   nie dało się zainstalować. Skrypt czeka na pierwsze uruchomienie.

   Przygotowanie:
       npm init -y
       npm i -D @playwright/test
       npx playwright install chromium

   Uruchomienie (serwer musi działać osobno):
       PAGON_HOST=127.0.0.1 python app.py
       npx playwright test tests/pwa_offline.spec.js

   Adres serwera można podać przez PAGON_URL (domyślnie http://127.0.0.1:5000).
   =================================================================== */
const { test, expect } = require("@playwright/test");

const BAZA = process.env.PAGON_URL || "http://127.0.0.1:5000";

const MODULY = [
  { nazwa: "Znaki drogowe", url: "/pomoce/znaki", fraza: "B-2", pole: "#znSzukaj" },
  { nazwa: "Tablice ADR", url: "/pomoce/tablica-adr", fraza: "1203", pole: "#adrNameSearch" },
  { nazwa: "Kody czynów", url: "/pomoce/kody-czynow", fraza: "A01", pole: "#kczWejscie" },
  { nazwa: "Kody usterek", url: "/pomoce/kody-usterek", fraza: "0.1.a", pole: "#kusWejscie" },
  { nazwa: "Kody pocztowe", url: "/pomoce/kody-pocztowe", fraza: "00-001", pole: "#kpWejscie" },
];

/** Czeka, aż service worker przejmie kontrolę nad stroną. */
async function czekajNaServiceWorkera(page) {
  await page.waitForFunction(
    () => navigator.serviceWorker && navigator.serviceWorker.controller !== null,
    null,
    { timeout: 20000 }
  );
}

/** Rozgrzewa moduł: wchodzi, czeka na pobranie bazy, wraca. */
async function rozgrzej(page, url, pole) {
  await page.goto(BAZA + url, { waitUntil: "networkidle" });
  if (pole) await page.waitForSelector(pole, { timeout: 10000 });
  // moment na zapis bazy do Cache Storage przez service workera
  await page.waitForTimeout(1200);
}

test.describe("PaGon — działanie bez sieci", () => {
  test.describe.configure({ mode: "serial" });

  test("1. pierwsze załadowanie online rejestruje service workera", async ({ page }) => {
    await page.goto(BAZA + "/", { waitUntil: "networkidle" });
    await czekajNaServiceWorkera(page);

    const zarejestrowany = await page.evaluate(async () => {
      const r = await navigator.serviceWorker.getRegistration();
      return !!r && !!r.active;
    });
    expect(zarejestrowany).toBe(true);

    // manifest musi być osiągalny i mieć komplet ikon
    const odp = await page.request.get(BAZA + "/static/manifest.json");
    expect(odp.status()).toBe(200);
    const manifest = await odp.json();
    expect(manifest.icons.length).toBeGreaterThanOrEqual(3);
    expect(manifest.start_url).toBe("/");
    expect(manifest.display).toBe("standalone");
  });

  test("2-6. offline: strona główna, moduły i wyszukiwanie", async ({ page, context }) => {
    // rozgrzewka online — bazy muszą trafić do Cache Storage
    await page.goto(BAZA + "/", { waitUntil: "networkidle" });
    await czekajNaServiceWorkera(page);
    for (const m of MODULY) await rozgrzej(page, m.url, m.pole);

    // --- odłączenie internetu ---
    await context.setOffline(true);

    // 3. odświeżenie strony głównej
    await page.goto(BAZA + "/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    expect(await page.title()).toContain("PaGon");

    // 4 i 5. każdy moduł otwiera się i wyszukuje w lokalnych danych
    for (const m of MODULY) {
      await page.goto(BAZA + m.url, { waitUntil: "domcontentloaded" });
      await expect(page.locator(m.pole)).toBeVisible({ timeout: 10000 });

      await page.fill(m.pole, m.fraza);
      await page.waitForTimeout(700);   // po debounce wyszukiwarki

      const wyniki = await page.evaluate(() => {
        const sel = ["#kusWyniki", "#kczWyniki", "#kpWyniki", "#znLista", "#adrWyniki"];
        for (const s of sel) {
          const el = document.querySelector(s);
          if (el && el.children.length) return el.children.length;
        }
        return 0;
      });
      expect(wyniki, `${m.nazwa}: brak wyników offline dla „${m.fraza}”`).toBeGreaterThan(0);
    }

    await context.setOffline(false);
  });

  test("offline: nieodwiedzona strona pokazuje stronę zastępczą, a nie błąd", async ({ page, context }) => {
    await page.goto(BAZA + "/", { waitUntil: "networkidle" });
    await czekajNaServiceWorkera(page);
    await context.setOffline(true);

    await page.goto(BAZA + "/pomoce/statusy-pj-ksip", { waitUntil: "domcontentloaded" });
    const tresc = await page.textContent("body");
    expect(tresc).toMatch(/Brak połączenia|Statusy/);   // strona zastępcza albo z cache

    await context.setOffline(false);
  });

  test("6. aktualizacja wersji cache usuwa stare magazyny", async ({ page }) => {
    await page.goto(BAZA + "/", { waitUntil: "networkidle" });
    await czekajNaServiceWorkera(page);

    const magazyny = await page.evaluate(() => caches.keys());
    const pagon = magazyny.filter((n) => n.startsWith("pagon-"));
    expect(pagon.length).toBeGreaterThan(0);

    // wszystkie magazyny muszą należeć do jednej wersji
    const wersje = new Set(pagon.map((n) => n.split("-").pop()));
    expect(wersje.size, `magazyny z różnych wersji: ${pagon.join(", ")}`).toBe(1);

    // podszywamy się pod poprzednie wydanie i sprawdzamy sprzątanie
    await page.evaluate(() => caches.open("pagon-powloka-v0").then((c) => c.put(
      new Request("/stary-wpis"), new Response("stare"))));
    let po = await page.evaluate(() => caches.keys());
    expect(po).toContain("pagon-powloka-v0");

    await page.evaluate(async () => {
      const r = await navigator.serviceWorker.getRegistration();
      await r.update();
    });
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    po = await page.evaluate(() => caches.keys());
    expect(po, "magazyn z poprzedniej wersji nie został usunięty")
      .not.toContain("pagon-powloka-v0");
  });

  test("nie cache'ujemy błędów ani dokumentów PDF", async ({ page }) => {
    await page.goto(BAZA + "/", { waitUntil: "networkidle" });
    await czekajNaServiceWorkera(page);

    await page.request.get(BAZA + "/pomoce/kody-usterek/kod/NIEISTNIEJE");
    await page.request.get(BAZA + "/pomoce/nieistniejaca-strona");
    await page.waitForTimeout(800);

    const zle = await page.evaluate(async () => {
      const nazwy = await caches.keys();
      const znalezione = [];
      for (const n of nazwy) {
        const c = await caches.open(n);
        for (const z of await c.keys()) {
          if (z.url.includes("NIEISTNIEJE") || z.url.includes("nieistniejaca-strona")
              || z.url.includes("/pomoce/pdf/")) {
            znalezione.push(z.url);
          }
        }
      }
      return znalezione;
    });
    expect(zle, `w cache znalazły się zasoby, których nie wolno zapisywać: ${zle}`)
      .toHaveLength(0);
  });
});
