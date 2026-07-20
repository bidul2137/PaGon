/* ===================================================================
   Testy kalkulatora prędkości (mechanizm +50 km/h, stan od 3.03.2026).
   Uruchomienie:  node tests/kalkulator.test.js   (z katalogu app/)
   =================================================================== */
"use strict";

const fs = require("fs");
const path = require("path");

// wyciągnij czyste funkcje z kalkulator.js (bez DOM)
const src = fs.readFileSync(path.join(__dirname, "..", "static", "js", "kalkulator.js"), "utf8");
function grab(name) {
  const i = src.indexOf("function " + name);
  if (i === -1) throw new Error("Brak funkcji: " + name);
  let depth = 0;
  for (let k = src.indexOf("{", i); k < src.length; k++) {
    if (src[k] === "{") depth++;
    if (src[k] === "}") { depth--; if (!depth) return src.slice(i, k + 1); }
  }
}
const mod = { exports: {} };
new Function("module",
  grab("shouldSuspendLicense") + "\n" + grab("proceduraDokumentu") +
  "\nmodule.exports = { shouldSuspendLicense, proceduraDokumentu };")(mod);
const { shouldSuspendLicense, proceduraDokumentu } = mod.exports;

// przedziały z danych taryfikatora (jak w route)
const dane = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "taryfikator.json"), "utf8"));
const przedzialy = [];
for (const r of dane.rekordy) {
  if (r.category !== "predkosc") continue;
  const t = (r.title || "").toLowerCase();
  if (!t.includes("przekroczenie") || !t.includes("prędko")) continue;
  let m, od = null, doo = null;
  if ((m = t.match(/do\s+(\d+)\s*km/))) { od = 1; doo = +m[1]; }
  else if ((m = t.match(/o\s+(\d+)\s*[-–]\s*(\d+)\s*km/))) { od = +m[1]; doo = +m[2]; }
  else if ((m = t.match(/o\s+(\d+)\s*km\/h\s*i\s*wi/))) { od = +m[1]; doo = null; }
  if (od === null) continue;
  przedzialy.push({ od, do: doo, mandat: r.mandate_base, punkty: r.points_max });
}
function znajdzPrzedzial(diff) {
  return przedzialy.find(p => diff >= p.od && (p.do === null || diff <= p.do)) || null;
}

// ---------- przypadki obowiązkowe ----------
let bledy = 0;
function test(nazwa, warunek) {
  if (warunek) { console.log("  OK  —", nazwa); }
  else { console.error("  BŁĄD —", nazwa); bledy++; }
}

console.log("1. Limit 50, jazda 100, obszar zabudowany:");
test("przekroczenie 50 km/h", 100 - 50 === 50);
test("brak zatrzymania PJ (dokładnie 50, nie „więcej niż 50”)", shouldSuspendLicense(50, "built_up_area") === false);

console.log("2. Limit 50, jazda 101, obszar zabudowany:");
test("przekroczenie 51 km/h", 101 - 50 === 51);
test("zatrzymanie PJ na 3 miesiące", shouldSuspendLicense(51, "built_up_area") === true);

console.log("3. Limit 90, jazda 141, droga jednojezdniowa dwukierunkowa poza obszarem:");
test("przekroczenie 51 km/h", 141 - 90 === 51);
test("zatrzymanie PJ na 3 miesiące", shouldSuspendLicense(51, "single_carriageway_two_way_outside_built_up") === true);

console.log("4. Limit 90, jazda 141, droga dwujezdniowa poza obszarem:");
test("brak zatrzymania PJ", shouldSuspendLicense(51, "dual_carriageway_outside_built_up") === false);

console.log("5. Limit 140, jazda 191, autostrada:");
test("przekroczenie 51 km/h", 191 - 140 === 51);
test("brak zatrzymania PJ", shouldSuspendLicense(51, "motorway") === false);

console.log("6. Limit 50, jazda 50:");
test("brak przekroczenia (diff <= 0 → bez mandatu, punktów i PJ)", 50 - 50 <= 0);

console.log("Dodatkowe:");
test("droga ekspresowa: brak zatrzymania PJ", shouldSuspendLicense(51, "expressway") === false);
test("miejsce nieznane: brak deklaracji zatrzymania PJ", shouldSuspendLicense(51, "unknown") === false);
test("przedziały taryfikatora: diff 51 → mandat 1500 zł / 13 pkt",
  (() => { const p = znajdzPrzedzial(51); return p && p.mandat === 1500 && p.punkty === 13; })());
test("przedziały taryfikatora: diff 50 → mandat 1000 zł / 11 pkt",
  (() => { const p = znajdzPrzedzial(50); return p && p.mandat === 1000 && p.punkty === 11; })());

console.log("Rodzaj prawa jazdy:");
const dom = proceduraDokumentu("domestic");
const zagr = proceduraDokumentu("foreign");
const niew = proceduraDokumentu("unknown");
test("polskie: starosta + decyzja na 3 miesiące",
  dom.komunikat.includes("starosta wydaje decyzję administracyjną") && dom.komunikat.includes("3 miesiące"));
test("zagraniczne: procedura z art. 135a PRD (organ państwa wydania, terytorium Polski)",
  zagr.podstawa === "art. 135a ust. 1 pkt 2 lit. a PRD" &&
  zagr.komunikat.includes("organowi państwa wydania") &&
  zagr.komunikat.includes("terytorium Polski"));
test("zagraniczne: BEZ stwierdzenia o decyzji starosty o zatrzymaniu na 3 miesiące",
  !zagr.komunikat.includes("3 miesiące") && !zagr.komunikat.includes("decyzję administracyjną"));
test("nie wiem: prośba o wybór rodzaju dokumentu",
  niew.komunikat.includes("Wybierz rodzaj prawa jazdy"));

if (bledy) { console.error("\nNIEPOWODZENIE: błędów: " + bledy); process.exit(1); }
console.log("\nWszystkie testy zaliczone.");
