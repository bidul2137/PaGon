#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buduje baze komend Policji i wiaze je z powiatami.

PO CO
-----
Zeby z kodu pocztowego albo z lokalizacji dalo sie wskazac komende wlasciwa dla
terenu. Kod pocztowy prowadzi do powiatu (kod TERYT mamy w bazie kodow), a powiat
do komendy.

SKAD DANE
---------
data/jednostki_policji/_zrodlo_jednostki.json — wykaz zebrany ze stron komend
wojewodzkich. Kazdy wpis niesie adres strony i date pobrania.

JAK POWSTAJE PRZYPISANIE POWIATU
--------------------------------
Nie zgadujemy po nazwie. Miasto siedziby komendy odszukujemy w bazie kodow
pocztowych i bierzemy powiat, w ktorym ta miejscowosc lezy. Gdy miasto wystepuje
w kilku powiatach tego samego wojewodztwa, wpis trafia do listy do recznego
rozstrzygniecia — zaden rekord nie jest przypisywany "na oko".

Powiat ziemski bez wlasnej komendy (np. olsztynski) obsluguje komenda miejska
z miasta bedacego jego siedziba. Takie powiazanie tworzymy tylko wtedy, gdy
nazwa powiatu ziemskiego odpowiada miastu, w ktorym stoi komenda miejska.

TWARDA KONTROLA
---------------
Import KONCZY SIE BLEDEM, dopoki chocby jeden z 380 powiatow nie ma przypisanej
komendy. Lepiej brak bazy niz baza z dziurami, o ktorych nikt nie wie.

UZYCIE
------
    python tools/import_jednostki_policji.py            # pelny import
    python tools/import_jednostki_policji.py --stan     # co juz jest, czego brak
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE = KATALOG / "data" / "jednostki_policji"
ZRODLO = WYJSCIE / "_zrodlo_jednostki.json"
POWIATY = WYJSCIE / "powiaty_referencja.json"
BAZA_KODOW = KATALOG / "data" / "kody_pocztowe" / "postal_codes.sqlite"

WERSJA_ZBIORU = "1.0.0"


def bez_ogonkow(tekst: str) -> str:
    t = (tekst or "").replace("ł", "l").replace("Ł", "L")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(z for z in t if not unicodedata.combining(z))
    return re.sub(r"\s+", " ", t).strip().lower()


def wczytaj_powiaty() -> list[dict]:
    with open(POWIATY, encoding="utf-8") as f:
        return json.load(f)["powiaty"]


def wczytaj_jednostki() -> list[dict]:
    with open(ZRODLO, encoding="utf-8") as f:
        return json.load(f)["jednostki"]


def miejscowosci_powiatow() -> dict[tuple[str, str], set[str]]:
    """(nazwa_miejscowosci_bez_ogonkow, wojewodztwo) -> zbior kodow TERYT powiatow."""
    con = sqlite3.connect(BAZA_KODOW)
    mapa: dict[tuple[str, str], set[str]] = defaultdict(set)
    for nazwa, woj, teryt in con.execute(
            "SELECT DISTINCT locality_normalized, voivodeship, teryt_county "
            "FROM postal_codes WHERE teryt_county IS NOT NULL"):
        mapa[(nazwa, woj)].add(teryt)
    con.close()
    return mapa


def przypisz(jednostki: list[dict], powiaty: list[dict]) -> tuple[dict, list[str]]:
    """Zwraca (teryt_powiatu -> jednostka, lista problemow)."""
    mapa_miejsc = miejscowosci_powiatow()
    wg_teryt = {p["teryt"]: p for p in powiaty}
    problemy: list[str] = []
    przypisane: dict[str, dict] = {}

    komendy = [j for j in jednostki if j["typ"] in ("KPP", "KMP", "KSP")]

    for j in komendy:
        klucz = (bez_ogonkow(j["miasto"]), j["wojewodztwo"])
        kandydaci = mapa_miejsc.get(klucz, set())
        if not kandydaci:
            problemy.append(f"{j['nazwa']}: miasta „{j['miasto']}” nie ma w bazie kodów")
            continue
        # Miasto siedziby lezy w dokladnie jednym powiecie — wtedy przypisanie
        # jest jednoznaczne. Miasto na prawach powiatu ma kod 61+.
        if len(kandydaci) > 1:
            problemy.append(
                f"{j['nazwa']}: miasto „{j['miasto']}” występuje w powiatach "
                f"{', '.join(sorted(kandydaci))} — wymaga ręcznego rozstrzygnięcia")
            continue
        teryt = next(iter(kandydaci))
        if teryt in przypisane:
            problemy.append(
                f"powiat {teryt} ma już przypisaną jednostkę "
                f"{przypisane[teryt]['nazwa']}, a zgłasza się też {j['nazwa']}")
            continue
        przypisane[teryt] = j

    # Powiat ziemski bez wlasnej komendy obsluguje komenda z miasta o tej samej
    # nazwie — to reguła, nie domysl, ale i tak ja odnotowujemy w raporcie.
    for p in powiaty:
        if p["teryt"] in przypisane:
            continue
        rdzen = bez_ogonkow(p["nazwa"])
        for j in komendy:
            if j["wojewodztwo"] != p["wojewodztwo"]:
                continue
            miasto = bez_ogonkow(j["miasto"])
            # Przymiotnik od nazwy miasta bywa nieregularny: "olsztyński" od
            # Olsztyna, ale "elbląski" od Elbląga, a "ostródzki" od Ostródy.
            # Porownujemy wiec wspolny poczatek, a nie caly wyraz. Kazde takie
            # przypisanie jest oznaczane i wypisywane, wiec da sie je sprawdzic.
            wspolne = 0
            for a_, b_ in zip(rdzen, miasto):
                if a_ != b_:
                    break
                wspolne += 1
            if (wspolne >= 5 and len(rdzen) - wspolne <= 4
                    and len(miasto) - wspolne <= 2):
                przypisane[p["teryt"]] = dict(j, _przez_siedzibe=True)
                break

    return przypisane, problemy


def main() -> None:
    ap = argparse.ArgumentParser(description="Buduje bazę komend Policji.")
    ap.add_argument("--stan", action="store_true", help="pokaż postęp zbierania danych")
    a = ap.parse_args()

    powiaty = wczytaj_powiaty()
    jednostki = wczytaj_jednostki()
    przypisane, problemy = przypisz(jednostki, powiaty)

    brakujace = [p for p in powiaty if p["teryt"] not in przypisane]
    wg_woj: dict[str, list] = defaultdict(list)
    for p in brakujace:
        wg_woj[p["wojewodztwo"]].append(p)

    komendy = [j for j in jednostki if j["typ"] in ("KPP", "KMP", "KSP")]
    print(f"Jednostek w źródle: {len(jednostki)}  (w tym komend: {len(komendy)})")
    print(f"Powiatów pokrytych: {len(przypisane)} z {len(powiaty)}")

    if a.stan:
        print("\nBrakuje jeszcze w województwach:")
        for woj in sorted(wg_woj):
            print(f"  {woj:22} {len(wg_woj[woj]):3} powiatów")
        if problemy:
            print("\nDo rozstrzygnięcia:")
            for x in problemy[:20]:
                print("  -", x)
        return

    if problemy:
        print("\nProblemy z przypisaniem:")
        for x in problemy:
            print("  -", x)

    if brakujace:
        print(f"\nPRZERWANO: {len(brakujace)} powiatów nie ma przypisanej komendy.")
        print("Baza nie zostanie zapisana, dopóki wykaz nie będzie kompletny.")
        print("Uruchom z --stan, żeby zobaczyć, czego brakuje.")
        raise SystemExit(1)

    dzis = datetime.date.today().isoformat()
    rekordy = []
    for p in powiaty:
        j = przypisane[p["teryt"]]
        rekordy.append({
            "teryt_county": p["teryt"],
            "county": p["nazwa"],
            "voivodeship": p["wojewodztwo"],
            "unit_name": j["nazwa"],
            "unit_type": j["typ"],
            "city": j["miasto"],
            "address": j["adres"],
            "phone": j.get("telefon"),
            "website": j.get("www"),
            "assigned_via_seat": bool(j.get("_przez_siedzibe")),
            "source": j["zrodlo"],
            "verified_at": dzis,
        })

    WYJSCIE.mkdir(parents=True, exist_ok=True)
    (WYJSCIE / "jednostki.json").write_text(
        json.dumps(rekordy, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (WYJSCIE / "metadata.json").write_text(json.dumps({
        "dataset_name": "Komendy Policji według powiatów",
        "dataset_version": WERSJA_ZBIORU,
        "primary_source": "strony internetowe komend wojewódzkich Policji",
        "attribution": "Dane pochodzą ze stron Policji. Źródło: policja.pl.",
        "county_count": len(powiaty),
        "unit_count": len({j["nazwa"] for j in komendy}),
        "assigned_via_seat_count": sum(1 for r in rekordy if r["assigned_via_seat"]),
        "verified_at": dzis,
        "coverage_note": (
            "Zbiór obejmuje komendy powiatowe i miejskie. Nie zawiera komisariatów "
            "ani telefonów. Właściwość miejscowa Policji nie pokrywa się dokładnie "
            "z granicą powiatu — wskazanie ma charakter pomocniczy."),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nZapisano {len(rekordy)} powiązań powiat → komenda do {WYJSCIE}")


if __name__ == "__main__":
    main()
