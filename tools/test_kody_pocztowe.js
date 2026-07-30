/* Test modułu "Kody pocztowe" bez przeglądarki.
 *
 * W środowisku nie ma jsdom ani dostępu do sieci, więc budujemy minimalną
 * atrapę DOM — na tyle wierną, żeby uruchomić prawdziwy plik
 * static/js/kody_pocztowe.js i sprawdzić logikę wyszukiwania oraz to, co
 * moduł faktycznie renderuje.
 *
 * Uruchomienie:
 *   node tools/test_kody_pocztowe.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const KATALOG = path.resolve(__dirname, "..");

/* ---------------- atrapa DOM ---------------- */

function Wezel(tag) {
  this.tagName = (tag || "").toUpperCase();
  this.children = [];
  this.attrs = {};
  this._text = "";
  this.className = "";
  this.hidden = false;
  this.style = {};
  this.sluchacze = {};
  this.parentNode = null;
}
Wezel.prototype.appendChild = function (w) { w.parentNode = this; this.children.push(w); return w; };
Wezel.prototype.insertBefore = function (w, przed) {
  w.parentNode = this;
  const i = this.children.indexOf(przed);
  this.children.splice(i < 0 ? 0 : i, 0, w);
  return w;
};
Wezel.prototype.removeChild = function (w) {
  const i = this.children.indexOf(w);
  if (i > -1) this.children.splice(i, 1);
  w.parentNode = null;
  return w;
};
Wezel.prototype.replaceChildren = function () { this.children = []; };
Wezel.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
Wezel.prototype.getAttribute = function (k) { return k in this.attrs ? this.attrs[k] : null; };
Wezel.prototype.removeAttribute = function (k) { delete this.attrs[k]; };
Wezel.prototype.addEventListener = function (typ, fn) {
  (this.sluchacze[typ] = this.sluchacze[typ] || []).push(fn);
};
Wezel.prototype.odpal = function (typ, zdarzenie) {
  (this.sluchacze[typ] || []).forEach((fn) => fn(zdarzenie || { preventDefault() {} }));
};
Wezel.prototype.focus = function () { globalThis.document.activeElement = this; };
Wezel.prototype.contains = function (w) {
  if (this === w) return true;
  return this.children.some((d) => d.contains(w));
};
Object.defineProperty(Wezel.prototype, "textContent", {
  get() {
    return this._text + this.children.map((d) => d.textContent).join("");
  },
  set(v) { this._text = v === null || v === undefined ? "" : String(v); this.children = []; },
});
Object.defineProperty(Wezel.prototype, "firstChild", {
  get() { return this.children[0] || null; },
});
Wezel.prototype.pasuje = function (sel) {
  if (sel.startsWith(".")) return (" " + this.className + " ").includes(" " + sel.slice(1) + " ");
  if (sel.startsWith("#")) return this.attrs.id === sel.slice(1);
  return this.tagName === sel.toUpperCase();
};
Wezel.prototype.querySelectorAll = function (sel) {
  const wynik = [];
  const idz = (w) => w.children.forEach((d) => { if (d.pasuje(sel)) wynik.push(d); idz(d); });
  idz(this);
  wynik.forEach = Array.prototype.forEach.bind(wynik);
  return wynik;
};
Wezel.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };

const wgId = new Map();

function stworz(tag, id, klasa) {
  const w = new Wezel(tag);
  if (id) { w.attrs.id = id; wgId.set(id, w); }
  if (klasa) w.className = klasa;
  return w;
}

const korzen = stworz("div", null, "kp-page");
korzen.attrs["data-wersja"] = "1.0.0-test";

const elementy = {
  kpForm: stworz("form", "kpForm"),
  kpWejscie: stworz("input", "kpWejscie"),
  kpCzysc: stworz("button", "kpCzysc"),
  kpLista: stworz("div", "kpLista", "kp-lista"),
  kpWyniki: stworz("div", "kpWyniki", "kp-wyniki"),
  kpHistoria: stworz("section", "kpHistoria"),
  kpHistoriaLista: stworz("div", "kpHistoriaLista"),
  kpCzyscHistorie: stworz("button", "kpCzyscHistorie"),
  kpLokalizacja: stworz("button", "kpLokalizacja"),
};
Object.values(elementy).forEach((w) => korzen.appendChild(w));
elementy.kpWejscie.value = "";

globalThis.document = {
  activeElement: null,
  querySelector: (sel) => (sel === ".kp-page" ? korzen : korzen.querySelector(sel)),
  getElementById: (id) => wgId.get(id) || null,
  createElement: (tag) => new Wezel(tag),
  createElementNS: (ns, tag) => new Wezel(tag),
  addEventListener() {},
  body: { appendChild() {}, removeChild() {} },
  execCommand() { return true; },
};

const pamiec = new Map();
globalThis.window = {
  localStorage: {
    getItem: (k) => (pamiec.has(k) ? pamiec.get(k) : null),
    setItem: (k, v) => pamiec.set(k, String(v)),
    removeItem: (k) => pamiec.delete(k),
  },
};
// w Node navigator jest tylko do odczytu — podmieniamy przez defineProperty
let odpowiedzGps = null;   // {coords} albo {blad:{code}}
const nawigator = {
  geolocation: {
    getCurrentPosition(sukces, blad) {
      if (!odpowiedzGps) return blad({ code: 2 });
      if (odpowiedzGps.blad) return blad(odpowiedzGps.blad);
      sukces({ coords: odpowiedzGps.coords });
    },
  },
};
Object.defineProperty(globalThis, "navigator", { value: nawigator, configurable: true });

/* ---------------- dane: dokładnie to, co odda Flask ---------------- */

// Bazę na potrzeby testu budujemy PRAWDZIWYM importerem z pliku wzorcowego.
// Czytamy dokładnie ten plik, który dostaje przeglądarka — search_index.json.
// Z opcją --prawdziwa test idzie na bazie użytkownika z data/kody_pocztowe/.
const { execFileSync } = require("child_process");
const NA_PRAWDZIWEJ = process.argv.includes("--prawdziwa");

let zrodloIndeksu;
if (NA_PRAWDZIWEJ) {
  zrodloIndeksu = path.join(KATALOG, "data/kody_pocztowe/search_index.json");
} else {
  const TMP = fs.mkdtempSync(path.join(require("os").tmpdir(), "kp-test-"));
  execFileSync("python3", [
    path.join(KATALOG, "tools/import_kody_pocztowe.py"),
    "--plik", path.join(KATALOG, "tools/fixtures/kody_pocztowe_TEST.txt"),
    "--wyjscie", TMP,
  ], { cwd: KATALOG, stdio: "pipe" });
  zrodloIndeksu = path.join(TMP, "search_index.json");
}
const ladunek = JSON.parse(fs.readFileSync(zrodloIndeksu, "utf8"));
console.log(`Baza testowa: ${NA_PRAWDZIWEJ ? "PRAWDZIWA" : "wzorcowa"} · ` +
            `rekordów: ${ladunek.rekordy.length}`);

let zapytaniaSieciowe = 0;
globalThis.fetch = (url) => {
  zapytaniaSieciowe++;
  return Promise.resolve({ ok: true, json: () => Promise.resolve(ladunek) });
};

/* ---------------- uruchomienie modułu ---------------- */

require(path.join(KATALOG, "static/js/kody_pocztowe.js"));

/* ---------------- narzędzia testowe ---------------- */

let zdane = 0, oblane = 0;
function sprawdz(nazwa, warunek, szczegol) {
  if (warunek) { zdane++; console.log(`  ok    ${nazwa}`); }
  else { oblane++; console.log(`  BŁĄD  ${nazwa}${szczegol ? "  → " + szczegol : ""}`); }
}

const tekstWynikow = () => elementy.kpWyniki.textContent;
const czekaj = (ms) => new Promise((r) => setTimeout(r, ms));

function wpiszISzukaj(tekst) {
  elementy.kpWejscie.value = tekst;
  elementy.kpForm.odpal("submit", { preventDefault() {} });
}

async function wpiszIPodpowiedz(tekst) {
  elementy.kpWejscie.value = tekst;
  elementy.kpWejscie.odpal("input");
  await czekaj(260);
  return elementy.kpLista.querySelectorAll(".kp-poz");
}

/* ---------------- testy ---------------- */

(async function () {
  await czekaj(60);   // wczytanie bazy

  console.log("\n1. Kod z myślnikiem: 11-040");
  wpiszISzukaj("11-040");
  let t = tekstWynikow();
  sprawdz("znajduje kod", t.includes("11-040"), t.slice(0, 90));
  sprawdz("pokazuje Barcikowo", t.includes("Barcikowo"));
  sprawdz("pokazuje gminę Dobre Miasto", t.includes("Dobre Miasto"));
  sprawdz("pokazuje powiat olsztyński", t.includes("olsztyński"));
  sprawdz("pokazuje województwo", t.includes("warmińsko-mazurskie"));
  sprawdz("liczy miejscowości pod kodem", /Obejmuje \d+ miejscowości/.test(t), t.slice(0, 120));

  console.log("\n2. Kod bez myślnika: 11040");
  wpiszISzukaj("11040");
  sprawdz("formatuje do 11-040", elementy.kpWejscie.value === "11-040", elementy.kpWejscie.value);
  sprawdz("daje ten sam wynik", tekstWynikow().includes("Barcikowo"));

  console.log("\n3. Kod z prefiksem: kod 11-040");
  wpiszISzukaj("kod 11-040");
  sprawdz("rozpoznaje kod mimo słowa", elementy.kpWejscie.value === "11-040",
          elementy.kpWejscie.value);

  console.log("\n4. Miejscowość: Barcikowo");
  wpiszISzukaj("Barcikowo");
  t = tekstWynikow();
  sprawdz("znajduje miejscowość", t.includes("Barcikowo"));
  sprawdz("gmina Dobre Miasto", t.includes("Dobre Miasto"));
  sprawdz("powiat olsztyński", t.includes("olsztyński"));
  sprawdz("pokazuje kod 11-040", t.includes("11-040"));

  // Nazwę występującą w kilku miejscach wybieramy z DANYCH, a nie na sztywno —
  // inaczej test przechodziłby tylko na wzorcowej bazie.
  const wgNazwy = new Map();
  ladunek.rekordy.forEach((r) => {
    const kontekst = r[3] + "/" + r[4] + "/" + r[5];
    if (!wgNazwy.has(r[2])) wgNazwy.set(r[2], new Set());
    wgNazwy.get(r[2]).add(kontekst);
  });
  let nazwaWieloznaczna = null, ileMiejsc = 0;
  for (const [nazwa, konteksty] of wgNazwy) {
    if (konteksty.size > ileMiejsc) { nazwaWieloznaczna = nazwa; ileMiejsc = konteksty.size; }
    if (ileMiejsc >= 3) break;
  }

  console.log(`\n5. Nazwa w kilku miejscach: „${nazwaWieloznaczna}" (${ileMiejsc})`);
  wpiszISzukaj(nazwaWieloznaczna);
  t = tekstWynikow();
  sprawdz("ostrzega o wieloznaczności", /występuje w \d+ miejscach/.test(t), t.slice(0, 120));
  sprawdz("pokazuje wszystkie konteksty",
          elementy.kpWyniki.querySelectorAll(".kp-karta").length === ileMiejsc,
          "kart: " + elementy.kpWyniki.querySelectorAll(".kp-karta").length + " z " + ileMiejsc);
  sprawdz("nie wybiera pierwszego automatycznie", ileMiejsc > 1 &&
          elementy.kpWyniki.querySelectorAll(".kp-karta").length > 1);
  sprawdz("każda karta ma powiat", t.includes("powiat"));

  console.log("\n6. Bez polskich znaków: Zary");
  wpiszISzukaj("Zary");
  t = tekstWynikow();
  sprawdz("znajduje Żary", t.includes("Żary"), t.slice(0, 90));
  sprawdz("pokazuje jakiś kod", /\d{2}-\d{3}/.test(t));

  console.log("\n7. Nadmiarowe spacje i wielkość liter: '  dObRe   mIaStO '");
  wpiszISzukaj("  dObRe   mIaStO ");
  sprawdz("radzi sobie z zapisem", tekstWynikow().includes("Dobre Miasto"));

  console.log("\n8. Nieistniejący kod: 99-999");
  wpiszISzukaj("99-999");
  t = tekstWynikow();
  sprawdz("mówi o braku wyniku", t.includes("Nie znaleziono danych"), t.slice(0, 90));
  sprawdz("nie zmyśla miejscowości", !t.includes("Barcikowo"));

  console.log("\n9. Niepełny kod: 11-0");
  wpiszISzukaj("11-0");
  sprawdz("nie pokazuje błędu, tylko podpowiedź formatu",
          tekstWynikow().includes("pięciocyfrowy kod"), tekstWynikow().slice(0, 90));

  console.log("\n10. Podpowiedzi");
  let poz = await wpiszIPodpowiedz("dobre");
  sprawdz("podpowiada po fragmencie nazwy", poz.length >= 2, "pozycji: " + poz.length);
  sprawdz("każda ma kontekst administracyjny",
          poz.every((p) => p.textContent.includes("powiat")));
  poz = await wpiszIPodpowiedz("11");
  sprawdz("podpowiada po dwóch cyfrach kodu", poz.length >= 1, "pozycji: " + poz.length);
  sprawdz("nie przekracza ośmiu pozycji", poz.length <= 8);

  console.log("\n11. Kod dla mojej lokalizacji");
  // punkt tuż obok Barcikowa (11-040) — współrzędne z samej bazy, nie z zewnątrz
  const wzorzec = ladunek.rekordy.find((r) => r[0] === "11-040" && r[1] === "Barcikowo")
                  || ladunek.rekordy.find((r) => typeof r[8] === "number");
  const zapytaniaPrzedGps = zapytaniaSieciowe;
  odpowiedzGps = { coords: { latitude: wzorzec[8] + 0.004, longitude: wzorzec[9], accuracy: 12 } };
  elementy.kpLokalizacja.odpal("click");
  await czekaj(30);
  t = tekstWynikow();
  sprawdz("wskazuje najbliższą miejscowość", t.includes(wzorzec[1]), t.slice(0, 110));
  sprawdz("podaje jej kod", t.includes(wzorzec[0]));
  sprawdz("pokazuje odległość", /\d+\s?(m|km)/.test(t), t.slice(0, 110));
  sprawdz("uprzedza, że odległość jest orientacyjna", t.includes("orientacyjna"));
  sprawdz("mówi, że pozycja nie wychodzi z urządzenia",
          t.includes("Nie została nigdzie wysłana"));
  sprawdz("nie wysyła pozycji nigdzie", zapytaniaSieciowe === zapytaniaPrzedGps,
          "żądań: " + (zapytaniaSieciowe - zapytaniaPrzedGps));
  sprawdz("odblokowuje przycisk po zakończeniu",
          elementy.kpLokalizacja.disabled === false);

  console.log("\n11b. Odmowa zgody na lokalizację");
  odpowiedzGps = { blad: { code: 1 } };
  elementy.kpLokalizacja.odpal("click");
  await czekaj(30);
  t = tekstWynikow();
  sprawdz("tłumaczy brak zgody", t.includes("Brak zgody"), t.slice(0, 110));
  sprawdz("podpowiada ręczne wpisanie", t.includes("ręcznie"));
  sprawdz("nie udaje wyniku", !/\d{2}-\d{3}/.test(t));

  console.log("\n12. Historia");
  const h = JSON.parse(pamiec.get("pagon-kody-historia") || "[]");
  sprawdz("zapisuje wyszukiwania", h.length > 0, "wpisów: " + h.length);
  sprawdz("nie przekracza ośmiu wpisów", h.length <= 8);
  sprawdz("wpis ma typ, wartość i datę",
          h[0] && h[0].typ && h[0].wartosc && /^\d{4}-\d{2}-\d{2}$/.test(h[0].data));

  console.log("\n13. Praca offline");
  sprawdz("baza pobrana dokładnie raz", zapytaniaSieciowe === 1,
          "żądań: " + zapytaniaSieciowe);
  const przed = zapytaniaSieciowe;
  wpiszISzukaj("Barcikowo");
  wpiszISzukaj("11-040");
  await wpiszIPodpowiedz("dob");
  sprawdz("wyszukiwanie nie wysyła żadnego żądania", zapytaniaSieciowe === przed,
          "żądań: " + (zapytaniaSieciowe - przed));

  console.log(`\n════ zdane: ${zdane} · oblane: ${oblane} ════`);
  process.exit(oblane ? 1 : 0);
})();
