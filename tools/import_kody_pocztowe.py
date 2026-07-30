#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buduje lokalna baze kodow pocztowych z pliku zrodlowego.

ZRODLA
------
Obslugiwane sa dwa formaty i skrypt rozpoznaje je sam:

1. GeoNames Postal Codes, plik PL.zip albo PL.txt  (licencja CC BY 4.0)
   https://download.geonames.org/export/zip/PL.zip
   Tekst rozdzielany tabulatorami:
     kraj, kod, miejscowosc, wojewodztwo, kod1, powiat, kod2, gmina, kod3,
     szerokosc, dlugosc, dokladnosc
   Licencja pozwala przechowywac i rozpowszechniac dane pod warunkiem podania
   autorstwa — modul robi to w sekcji "O danych".

2. Oficjalny Spis Pocztowych Numerow Adresowych Poczty Polskiej, jako tekst
   wyciagniety z PDF. Wiersz ma postac:
     11-040 Barcikowo Dobre Miasto olsztynski warminsko-mazurskie
   UWAGA: spis jest utworem chronionym i zabrania przechowywania w bazie danych
   bez pisemnej zgody Poczty Polskiej. Ten tryb wlaczaj TYLKO majac licencje.

CZEGO SKRYPT NIE ROBI
---------------------
Nie dopisuje niczego od siebie. TERYT, poczta obsługujaca, ulica i zakres
numerow zostaja null, dopoki zrodlo ich nie poda. Rekord, ktorego nie da sie
jednoznacznie potwierdzic, dostaje status partial_verification z uwaga.

UZYCIE
------
    python tools/import_kody_pocztowe.py                     # szuka pliku w zrodla/
    python tools/import_kody_pocztowe.py --plik ../zrodla/PL.zip
    python tools/import_kody_pocztowe.py --plik PLIK --sprawdz   # bez zapisu
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import shutil
import sqlite3
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE = KATALOG / "data" / "kody_pocztowe"
SNAPSHOTY = WYJSCIE / "snapshots"
ZRODLA = KATALOG.parent / "zrodla"

WERSJA_ZBIORU = "1.0.0"

# Szesnascie wojewodztw — dane referencyjne z ustawy o zasadniczym trojstopniowym
# podziale terytorialnym panstwa. Sluza do kontroli, nie do uzupelniania brakow.
WOJEWODZTWA = {
    "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie",
    "małopolskie", "mazowieckie", "opolskie", "podkarpackie", "podlaskie",
    "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie",
    "wielkopolskie", "zachodniopomorskie",
}

ZRODLA_OPIS = {
    "geonames": {
        "title": "GeoNames Postal Codes — Poland (PL)",
        "publisher": "GeoNames",
        "url": "https://download.geonames.org/export/zip/PL.zip",
        "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
    },
    "pna": {
        "title": "Oficjalny Spis Pocztowych Numerów Adresowych",
        "publisher": "Poczta Polska S.A.",
        "url": "https://www.poczta-polska.pl/spis-pna/",
        "license": "materiał chroniony — wymaga pisemnej zgody wydawcy",
    },
}

RE_KOD = re.compile(r"^\d{5}$")
REFERENCJA = WYJSCIE / "teryt_referencja.json"
RE_WIERSZ_PNA = re.compile(r"^(\d{2}-\d{3})\s+(.+)$")


# --------------------------------------------------------------------------- #
# normalizacja
# --------------------------------------------------------------------------- #

def bez_ogonkow(tekst: str) -> str:
    """Male litery, bez polskich znakow, bez podwojnych spacji.

    'ł' nie ma formy rozlozonej w Unicode, wiec zamieniamy ja recznie przed
    usunieciem znakow diakrytycznych.
    """
    t = (tekst or "").replace("ł", "l").replace("Ł", "L")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(z for z in t if not unicodedata.combining(z))
    return re.sub(r"\s+", " ", t).strip().lower()


def normalizuj_kod(surowy: str) -> str | None:
    """'11040', ' 11-040 ', 'kod 11-040' -> '11-040'. Inaczej None.

    Kod zostaje stringiem — jako liczba stracilby wiodace zero.
    """
    cyfry = re.sub(r"\D", "", surowy or "")
    if not RE_KOD.match(cyfry):
        return None
    return f"{cyfry[:2]}-{cyfry[2:]}"


def porzadkuj_nazwe(tekst: str) -> str:
    return re.sub(r"\s+", " ", (tekst or "").strip())


def czysc_powiat(nazwa: str) -> str:
    """'Powiat bolesławiecki' -> 'bolesławiecki'. Miasta na prawach powiatu
    zostaja bez zmian, bo ich nazwa to po prostu nazwa miasta."""
    n = porzadkuj_nazwe(nazwa)
    m = re.match(r"^Powiat\s+(.+)$", n, flags=re.I)
    return m.group(1).lower() if m else n


def czysc_gmine(nazwa: str) -> str:
    """'Gmina Dobre Miasto' -> 'Dobre Miasto'."""
    n = porzadkuj_nazwe(nazwa)
    m = re.match(r"^Gmina\s+(.+)$", n, flags=re.I)
    return m.group(1) if m else n


def wczytaj_referencje() -> dict:
    """Wykaz TERYT z GUS — sluzy do kontroli i do zastapienia angielskich nazw
    powiatow ich brzmieniem urzedowym. Brak pliku nie blokuje importu."""
    try:
        with open(REFERENCJA, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"wojewodztwa": {}, "powiaty": {}}


def normalizuj_wojewodztwo(tekst: str) -> str:
    """GeoNames zapisuje wojewodztwo roznie ('Województwo Mazowieckie',
    'Mazowieckie'). Sprowadzamy do postaci z ustawy: male litery, bez slowa
    'województwo'."""
    t = porzadkuj_nazwe(tekst)
    t = re.sub(r"^wojew[oó]dztwo\s+", "", t, flags=re.I)
    return t.lower()


# --------------------------------------------------------------------------- #
# odczyt zrodla
# --------------------------------------------------------------------------- #

def wczytaj_tekst(plik: Path) -> tuple[str, str]:
    """Zwraca (tresc, nazwa_wewnetrzna). Rozpakowuje zip w pamieci."""
    if plik.suffix.lower() == ".zip":
        with zipfile.ZipFile(plik) as z:
            kandydaci = [n for n in z.namelist() if n.lower().endswith((".txt", ".csv", ".tsv"))]
            if not kandydaci:
                raise SystemExit(f"W archiwum {plik.name} nie ma pliku tekstowego.")
            # PL.txt zamiast readme.txt
            nazwa = max(kandydaci, key=lambda n: z.getinfo(n).file_size)
            return z.read(nazwa).decode("utf-8", "replace"), nazwa
    return plik.read_text(encoding="utf-8", errors="replace"), plik.name


def rozpoznaj_format(tresc: str) -> str:
    """GeoNames ma tabulatory i kod kraju 'PL' w pierwszej kolumnie."""
    for wiersz in tresc.splitlines()[:50]:
        if wiersz.startswith("PL\t"):
            return "geonames"
    for wiersz in tresc.splitlines()[:400]:
        if RE_WIERSZ_PNA.match(wiersz.strip()):
            return "pna"
    raise SystemExit("Nie rozpoznano formatu pliku — oczekiwano GeoNames PL lub tekstu spisu PNA.")


def czytaj_geonames(tresc: str) -> list[dict]:
    surowe = []
    for wiersz in tresc.splitlines():
        p = wiersz.split("\t")
        if len(p) < 9 or p[0] != "PL":
            continue
        # p[6] i p[8] to prawdziwe kody TERYT powiatu i gminy — pewniejsze niz
        # nazwy, bo GeoNames miesza polskie i angielskie brzmienia
        surowe.append({
            "kod": p[1], "miejscowosc": p[2],
            "wojewodztwo": p[3], "powiat": p[5], "gmina": p[7],
            "teryt_powiat": p[6].strip(), "teryt_gmina": p[8].strip(),
        })
    return surowe


def czytaj_pna(tresc: str) -> list[dict]:
    """Wiersz spisu: kod, miejscowosc, gmina, powiat, wojewodztwo.

    Nazwy bywaja wielowyrazowe, wiec czytamy od konca: ostatni wyraz to
    wojewodztwo, przedostatni powiat, a to, co zostanie miedzy kodem a gmina,
    jest miejscowoscia. Gmina i miejscowosc moga byc wielowyrazowe, wiec
    granice miedzy nimi ustalamy dopiero po zebraniu slownika gmin.
    """
    wiersze = []
    for wiersz in tresc.splitlines():
        m = RE_WIERSZ_PNA.match(wiersz.strip())
        if not m:
            continue
        reszta = m.group(2).split()
        if len(reszta) < 3:
            continue
        woj = reszta[-1]
        if normalizuj_wojewodztwo(woj) not in WOJEWODZTWA:
            continue
        wiersze.append((m.group(1), reszta[:-2], reszta[-2], woj))

    # gmina to zwykle ostatni wyraz przed powiatem; nazwy dwuwyrazowe
    # ("Dobre Miasto") poznajemy po tym, ze powtarzaja sie w calym zbiorze
    licznik = Counter(" ".join(srodek[-2:]) for _, srodek, _, _ in wiersze if len(srodek) >= 2)
    dwuwyrazowe = {n for n, ile in licznik.items() if ile >= 3}

    surowe = []
    for kod, srodek, powiat, woj in wiersze:
        if len(srodek) >= 3 and " ".join(srodek[-2:]) in dwuwyrazowe:
            miejsc, gmina = srodek[:-2], " ".join(srodek[-2:])
        else:
            miejsc, gmina = srodek[:-1], srodek[-1]
        if not miejsc:
            continue
        surowe.append({"kod": kod, "miejscowosc": " ".join(miejsc),
                       "wojewodztwo": woj, "powiat": powiat, "gmina": gmina})
    return surowe


# --------------------------------------------------------------------------- #
# budowa bazy
# --------------------------------------------------------------------------- #

def zbuduj(surowe: list[dict], rodzaj: str, plik: Path, dzis: str) -> tuple[list[dict], dict]:
    """Zwraca (rekordy, statystyki). Rekordy maja ksztalt ze specyfikacji."""
    zrodlo_meta = ZRODLA_OPIS[rodzaj]

    ref = wczytaj_referencje()
    ref_woj, ref_pow = ref.get("wojewodztwa", {}), ref.get("powiaty", {})

    rekordy: list[dict] = []
    widziane: set[tuple] = set()
    odrzucone_kody = 0
    powt = 0

    for r in surowe:
        kod = normalizuj_kod(r["kod"])
        if not kod:
            odrzucone_kody += 1
            continue
        miejsc = porzadkuj_nazwe(r["miejscowosc"])
        if not miejsc:
            odrzucone_kody += 1
            continue
        t_pow = (r.get("teryt_powiat") or "").strip()
        t_gm = (r.get("teryt_gmina") or "").strip()
        t_woj = t_pow[:2] if len(t_pow) == 4 else None

        gmina = czysc_gmine(r["gmina"]) or None
        powiat = czysc_powiat(r["powiat"]) or None

        uwagi_rek = []

        # Wojewodztwo bierzemy z kodu TERYT, a nie z nazwy — GeoNames podaje
        # nazwy angielskie ("Lower Silesia"), kod jest jednoznaczny.
        woj = ref_woj.get(t_woj) if t_woj else None
        if not woj:
            woj = normalizuj_wojewodztwo(r["wojewodztwo"]) or None
            if woj and woj not in WOJEWODZTWA:
                uwagi_rek.append(f"nazwa województwa tylko w brzmieniu ze źródła: {woj}")

        # Powiat: nazwa angielska ("Głogów County") nie nadaje sie do pokazania,
        # wiec podmieniamy ja na urzedowa z wykazu GUS. Gdy wykaz jej nie ma —
        # zostawiamy brzmienie zrodla i mowimy o tym wprost.
        if powiat and re.search(r"\b(County|City)\b", powiat):
            urzedowa = ref_pow.get(t_pow)
            if urzedowa:
                powiat = urzedowa
            else:
                uwagi_rek.append(
                    f"źródło podaje nazwę powiatu po angielsku ({powiat}); "
                    f"kod TERYT {t_pow} potwierdzony")

        # Pelny duplikat techniczny — ten sam kod, miejscowosc i gmina.
        # Rekordow roznacych sie ulica lub gmina NIE scalamy.
        klucz = (kod, bez_ogonkow(miejsc), bez_ogonkow(gmina or ""), bez_ogonkow(powiat or ""))
        if klucz in widziane:
            powt += 1
            continue
        widziane.add(klucz)

        braki = list(uwagi_rek)
        if not woj:
            braki.append("brak województwa w źródle")
        if not powiat:
            braki.append("brak powiatu w źródle")
        if not gmina:
            braki.append("brak gminy w źródle")

        # Spojnosc kodow TERYT: kod gminy musi zaczynac sie od kodu powiatu,
        # a ten od kodu wojewodztwa. To kontrola samego zrodla, nie zgadywanie.
        if t_pow and t_gm and not t_gm.startswith(t_pow):
            braki.append(f"niespójne kody TERYT w źródle: gmina {t_gm} poza powiatem {t_pow}")
        if not t_pow or not t_gm:
            braki.append("brak kodu TERYT w źródle")

        rekordy.append({
            "postal_code": kod,
            "locality": miejsc,
            "locality_normalized": bez_ogonkow(miejsc),
            "commune": gmina,
            "county": powiat,
            "voivodeship": woj,
            # kody TERYT pochodza wprost ze zrodla — nie sa niczym uzupelniane
            "teryt": {"voivodeship": t_woj or None, "county": t_pow or None,
                      "commune": t_gm or None, "locality": None},
            "post_office": None,
            "street": None,
            "address_range": None,
            "source": {
                "title": zrodlo_meta["title"],
                "publisher": zrodlo_meta["publisher"],
                "url": zrodlo_meta["url"],
                "license": zrodlo_meta["license"],
                "published_at": None,
                "downloaded_at": dzis,
                "verified_at": dzis,
            },
            "verification_status": "verified" if not braki else "partial_verification",
            "verification_note": "; ".join(braki) or None,
        })

    rekordy.sort(key=lambda r: (r["locality_normalized"], r["postal_code"]))
    staty = {
        "odrzucone_kody": odrzucone_kody,
        "duplikaty": powt,
        "plik": plik.name,
    }
    return rekordy, staty


def zbuduj_indeks(rekordy: list[dict]) -> list[dict]:
    """Indeks miejscowosci: jedna nazwa, wiele lokalizacji administracyjnych.

    Miejscowosci o tej samej nazwie w roznych gminach zostaja OSOBNYMI
    pozycjami w 'matches' — aplikacja ma pokazac wybor, a nie zgadywac.
    """
    wg_nazwy: dict[str, dict] = {}
    for r in rekordy:
        n = r["locality_normalized"]
        wpis = wg_nazwy.setdefault(n, {"normalized_name": n,
                                       "display_name": r["locality"],
                                       "matches": {}})
        klucz = (r["commune"], r["county"], r["voivodeship"])
        traf = wpis["matches"].setdefault(klucz, {
            "commune": r["commune"], "county": r["county"],
            "voivodeship": r["voivodeship"], "postal_codes": [],
        })
        if r["postal_code"] not in traf["postal_codes"]:
            traf["postal_codes"].append(r["postal_code"])

    indeks = []
    for wpis in wg_nazwy.values():
        trafienia = list(wpis["matches"].values())
        for t in trafienia:
            t["postal_codes"].sort()
        indeks.append({"normalized_name": wpis["normalized_name"],
                       "display_name": wpis["display_name"],
                       "matches": trafienia})
    indeks.sort(key=lambda w: w["normalized_name"])
    return indeks


def raport(rekordy: list[dict], indeks: list[dict], staty: dict,
           rodzaj: str, dzis: str) -> str:
    pelne = sum(1 for r in rekordy if r["verification_status"] == "verified")
    czesciowe = len(rekordy) - pelne
    powody = Counter(r["verification_note"] for r in rekordy if r["verification_note"])
    kody = {r["postal_code"] for r in rekordy}
    z = ZRODLA_OPIS[rodzaj]

    w = [f"# Raport importu — kody pocztowe\n",
         f"**Data:** {dzis} · **Wersja zbioru:** {WERSJA_ZBIORU}\n",
         "## 1. Źródło\n",
         f"- **{z['title']}** — {z['publisher']}",
         f"- Adres: {z['url']}",
         f"- Licencja: {z['license']}",
         f"- Plik: `{staty['plik']}` (kopia w `snapshots/`)\n",
         "## 2. Wynik\n",
         "| Miara | Wartość |", "|---|---|",
         f"| Rekordów | **{len(rekordy)}** |",
         f"| Unikalnych kodów | **{len(kody)}** |",
         f"| Miejscowości | **{len(indeks)}** |",
         f"| Pełna weryfikacja | **{pelne}** |",
         f"| Weryfikacja częściowa | **{czesciowe}** |",
         f"| Odrzucone wiersze (zły kod lub brak nazwy) | {staty['odrzucone_kody']} |",
         f"| Usunięte pełne duplikaty | {staty['duplikaty']} |\n",
         "## 3. Jak czytane jest źródło\n",
         "GeoNames podaje nazwy jednostek **niekonsekwentnie** — województwa po angielsku "
         "(`Lower Silesia`), powiaty raz po polsku (`Powiat bolesławiecki`), raz po angielsku "
         "(`Głogów County`). Za to w kolumnach `admin code2` i `admin code3` ma **prawdziwe kody "
         "TERYT**, i to one są podstawą importu.\n",
         "| Pole | Skąd pochodzi |\n|---|---|",
         "| województwo | z dwóch pierwszych cyfr kodu TERYT powiatu — nazwa angielska jest ignorowana |",
         "| powiat | nazwa ze źródła bez przedrostka `Powiat`; formy angielskie podmieniane na urzędowe z wykazu GUS |",
         "| gmina | nazwa ze źródła bez przedrostka `Gmina` |",
         "| TERYT | wprost ze źródła, bez uzupełniania |",
         "",
         "Miasta na prawach powiatu (kod 61 i wyżej) zostają pod nazwą miasta — tak brzmi ich "
         "nazwa urzędowa.\n",
         "## 4. Kontrole przed zapisem\n",
         "- kod sprowadzany do `XX-XXX` i trzymany jako **tekst**, żeby nie zgubić wiodącego zera;",
         "- nazwa miejscowości zachowana w oryginale, obok wersja bez polskich znaków do wyszukiwania;",
         "- usuwane są wyłącznie **pełne** duplikaty techniczne — rekordy różniące się gminą zostają;",
         "- kod gminy musi zaczynać się od kodu powiatu, a ten od kodu województwa;",
         "- rozbieżność nie kasuje rekordu, tylko nadaje mu status weryfikacji częściowej z uwagą, "
         "którą widać w karcie wyniku.\n"]

    if powody:
        w.append("## 5. Powody weryfikacji częściowej\n")
        w.append("| Powód | Rekordów |"); w.append("|---|---|")
        for p, ile in powody.most_common(15):
            w.append(f"| {p} | {ile} |")
        w.append("")

    w.append("## 6. Czego nie ma w bazie\n")
    w.append("Poczta obsługująca, ulica i zakres numerów są zapisane jako `null` — źródło ich "
             "nie zawiera i nie są uzupełniane szacunkami. Kody TERYT województwa, powiatu "
             "i gminy są kompletne; identyfikator miejscowości (SIMC) w źródle nie występuje.\n")
    w.append("## 7. Jak dane leżą na dysku\n")
    w.append("| Plik | Rola |\n|---|---|")
    w.append("| `postal_codes.sqlite` | pełne rekordy i indeks miejscowości, do zapytań i audytu |")
    w.append("| `search_index.json` | lekki indeks dla przeglądarki (~3,5 MB, ~0,7 MB po gzip) |")
    w.append("| `teryt_referencja.json` | wykaz TERYT z GUS użyty do kontroli nazw |")
    w.append("| `snapshots/` | kopia pliku źródłowego z dnia importu |")
    w.append("")
    w.append("Pełnych rekordów **nie** trzymamy w JSON — przy 73 tys. pozycji plik miał 44 MB, "
             "co obciążałoby repozytorium i pamięć aplikacji przy każdym starcie.\n")
    w.append("## 8. Powtórzenie\n")
    w.append("```bash\npython tools/import_kody_pocztowe.py --plik ../zrodla/PL.zip\n```\n")
    return "\n".join(w)


# --------------------------------------------------------------------------- #

def znajdz_zrodlo() -> Path | None:
    if not ZRODLA.is_dir():
        return None
    wzorce = ["PL.zip", "PL.txt", "*postal*", "*pna*", "*PNA*", "*kody*"]
    for wz in wzorce:
        for p in sorted(ZRODLA.glob(wz)):
            if p.is_file():
                return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Buduje lokalną bazę kodów pocztowych.")
    ap.add_argument("--plik", type=Path, help="PL.zip / PL.txt / tekst spisu PNA")
    ap.add_argument("--sprawdz", action="store_true", help="nie zapisuj, tylko podsumuj")
    ap.add_argument("--wyjscie", type=Path, default=WYJSCIE,
                    help="katalog docelowy (używane przez testy)")
    a = ap.parse_args()
    wyjscie, snapshoty = a.wyjscie, a.wyjscie / "snapshots"

    plik = a.plik or znajdz_zrodlo()
    if not plik or not plik.exists():
        raise SystemExit(
            "Nie znalazłem pliku źródłowego.\n"
            "Pobierz https://download.geonames.org/export/zip/PL.zip i zapisz go w katalogu "
            f"{ZRODLA}, albo wskaż plik przez --plik."
        )

    print(f"Plik źródłowy: {plik}")
    tresc, wewnetrzna = wczytaj_tekst(plik)
    rodzaj = rozpoznaj_format(tresc)
    print(f"Rozpoznany format: {rodzaj} ({wewnetrzna})")

    surowe = czytaj_geonames(tresc) if rodzaj == "geonames" else czytaj_pna(tresc)
    print(f"Wierszy w źródle: {len(surowe)}")
    if not surowe:
        raise SystemExit("Źródło nie zawiera żadnych wierszy do zaimportowania.")

    dzis = datetime.date.today().isoformat()
    rekordy, staty = zbuduj(surowe, rodzaj, plik, dzis)
    indeks = zbuduj_indeks(rekordy)
    pelne = sum(1 for r in rekordy if r["verification_status"] == "verified")

    print(f"Rekordów: {len(rekordy)} | kodów: {len({r['postal_code'] for r in rekordy})} | "
          f"miejscowości: {len(indeks)} | pełna weryfikacja: {pelne}")

    if a.sprawdz:
        print("\nTryb sprawdzenia — nic nie zapisano.")
        return

    wyjscie.mkdir(parents=True, exist_ok=True)
    snapshoty.mkdir(parents=True, exist_ok=True)

    # Pelne rekordy ida do SQLite, a nie do JSON-a. Przy 73 tys. pozycji plik
    # JSON mial 44 MB — za duzo dla repozytorium i za ciezki do sparsowania przy
    # kazdym starcie aplikacji. SQLite czyta sie punktowo i zajmuje kilkanascie MB.
    baza = wyjscie / "postal_codes.sqlite"
    if baza.exists():
        baza.unlink()
    con = sqlite3.connect(baza)
    con.executescript("""
        CREATE TABLE postal_codes (
            id INTEGER PRIMARY KEY,
            postal_code TEXT NOT NULL,
            locality TEXT NOT NULL,
            locality_normalized TEXT NOT NULL,
            commune TEXT, county TEXT, voivodeship TEXT,
            teryt_voivodeship TEXT, teryt_county TEXT, teryt_commune TEXT,
            post_office TEXT, street TEXT, address_range TEXT,
            verification_status TEXT NOT NULL,
            verification_note TEXT
        );
        CREATE INDEX ix_kod  ON postal_codes(postal_code);
        CREATE INDEX ix_nazwa ON postal_codes(locality_normalized);
        CREATE TABLE localities_index (
            normalized_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            commune TEXT, county TEXT, voivodeship TEXT,
            postal_codes TEXT NOT NULL
        );
        CREATE INDEX ix_idx_nazwa ON localities_index(normalized_name);
        CREATE TABLE metadata (klucz TEXT PRIMARY KEY, wartosc TEXT);
    """)
    con.executemany(
        "INSERT INTO postal_codes (postal_code, locality, locality_normalized, commune,"
        " county, voivodeship, teryt_voivodeship, teryt_county, teryt_commune,"
        " post_office, street, address_range, verification_status, verification_note)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r["postal_code"], r["locality"], r["locality_normalized"], r["commune"],
          r["county"], r["voivodeship"], r["teryt"]["voivodeship"], r["teryt"]["county"],
          r["teryt"]["commune"], r["post_office"], r["street"], r["address_range"],
          r["verification_status"], r["verification_note"]) for r in rekordy])
    con.executemany(
        "INSERT INTO localities_index VALUES (?,?,?,?,?,?)",
        [(w["normalized_name"], w["display_name"], t["commune"], t["county"],
          t["voivodeship"], json.dumps(t["postal_codes"], ensure_ascii=False))
         for w in indeks for t in w["matches"]])

    z = ZRODLA_OPIS[rodzaj]
    meta = {
        "dataset_name": "Polskie kody pocztowe i miejscowości",
        "dataset_version": WERSJA_ZBIORU,
        "primary_source": z["title"],
        "primary_source_publisher": z["publisher"],
        "license": z["license"],
        "source_urls": [z["url"]],
        "source_file": plik.name,
        "reference_source": ("Wykaz identyfikatorów i nazw jednostek podziału "
                             "terytorialnego kraju, GUS"),
        "downloaded_at": dzis,
        "verified_at": dzis,
        "record_count": len(rekordy),
        "postal_code_count": len({r["postal_code"] for r in rekordy}),
        "locality_count": len(indeks),
        "fully_verified_count": pelne,
        "partially_verified_count": len(rekordy) - pelne,
        "coverage_note": (
            "Kod pocztowy służy obsłudze pocztowej i jego zasięg nie zawsze pokrywa się "
            "z granicami gminy ani powiatu. Poczta obsługująca, ulica i zakres numerów "
            "nie występują w źródle i pozostają puste. Kody TERYT pochodzą wprost ze źródła."),
    }
    con.executemany("INSERT INTO metadata VALUES (?,?)",
                    [(k, json.dumps(v, ensure_ascii=False)) for k, v in meta.items()])
    con.commit()
    con.close()

    # Lekki indeks dla przegladarki: nazwy gmin, powiatow i wojewodztw zamieniamy
    # na indeksy do slownikow, wiec z 44 MB robi sie ~3,5 MB (0,7 MB po gzip).
    # Dzieki temu modul dziala offline, nie odpytujac serwera przy kazdym wpisie.
    gminy, powiaty, woje, uwagi = [], [], [], []
    mapy = ({}, {}, {}, {})

    def do_slownika(wartosc, lista, mapa):
        if wartosc is None:
            return -1
        if wartosc not in mapa:
            mapa[wartosc] = len(lista)
            lista.append(wartosc)
        return mapa[wartosc]

    zwiezle = [[r["postal_code"], r["locality"], r["locality_normalized"],
                do_slownika(r["commune"], gminy, mapy[0]),
                do_slownika(r["county"], powiaty, mapy[1]),
                do_slownika(r["voivodeship"], woje, mapy[2]),
                0 if r["verification_status"] == "verified" else 1,
                do_slownika(r["verification_note"], uwagi, mapy[3])] for r in rekordy]

    (wyjscie / "search_index.json").write_text(json.dumps({
        "meta": meta,
        "slowniki": {"gminy": gminy, "powiaty": powiaty,
                     "wojewodztwa": woje, "uwagi": uwagi},
        "rekordy": zwiezle,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    (wyjscie / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (wyjscie / "import_report.md").write_text(
        raport(rekordy, indeks, staty, rodzaj, dzis), encoding="utf-8")

    kopia = snapshoty / f"{dzis}_{plik.name}"
    if not kopia.exists():
        shutil.copy2(plik, kopia)

    print(f"\nZapisano do {wyjscie}")
    print(f"Snapshot źródła: {kopia.name}")


if __name__ == "__main__":
    main()
