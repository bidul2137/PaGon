#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uzupelnia brakujace grafiki znakow, dopasowujac komorki arkusza PO KOLEJNOSCI.

Arkusz zawiera znaki jednej serii w kolejnosci z rozporzadzenia, ale bywa tylko
JEJ FRAGMENTEM. Skrypt szuka wiec przesuniecia, przy ktorym pewne odczyty OCR
(kotwice) trafiaja we wlasciwe pozycje listy kodow serii. Zapis nastepuje tylko
wtedy, gdy kotwic jest dosc i zgadzaja sie w zdecydowanej wiekszosci — inaczej
arkusz jest pomijany, zeby nie podmienic znaku na sasiedni.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from collections import Counter
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "import_znaki_grafiki.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

def klucz(k):
    m = re.match(r"^([A-Z]+)-(\d+)([a-z]?)$", k)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (k, 0, "")

def kody_serii() -> dict[str, list[str]]:
    meta = json.loads((KATALOG / "data/znaki/metadata.json").read_text(encoding="utf-8"))
    out = {}
    for kat in meta["categories"]:
        lista = json.loads((KATALOG / "data/znaki" / kat["file"]).read_text(encoding="utf-8"))
        out[kat["id"]] = sorted((z["code"] for z in lista), key=klucz)
    return out

def dopasuj(arkusz: Path, serie: dict[str, list[str]], wyjscie: Path,
            min_kotwic: int = 3, prog: float = 0.7, zapisuj: bool = True) -> dict:
    komorki = g.tnij_arkusz(arkusz)
    odczyty = [k for k, _, _ in komorki]
    kotwice = [k for k in odczyty if k]
    wynik = {"arkusz": arkusz.name, "komorek": len(komorki), "kotwic": len(kotwice)}
    if len(kotwice) < min_kotwic:
        wynik["pominiety"] = "za mało pewnych odczytów"
        return wynik

    dominujaca = Counter(k.split("-")[0] for k in kotwice).most_common(1)[0][0]
    lista = serie.get(dominujaca)
    if not lista:
        wynik["pominiety"] = f"nieznana seria {dominujaca}"
        return wynik
    wynik["seria"] = dominujaca

    najlepsze, najlepszy_wynik = None, -1
    for off in range(0, max(1, len(lista) - len(komorki) + 1)):
        traf = sum(1 for i, k in enumerate(odczyty)
                   if k and off + i < len(lista) and k == lista[off + i])
        if traf > najlepszy_wynik:
            najlepsze, najlepszy_wynik = off, traf
    wynik["przesuniecie"] = najlepsze
    wynik["trafien"] = najlepszy_wynik
    kotwic_serii = sum(1 for k in odczyty if k and k.split("-")[0] == dominujaca)
    if kotwic_serii == 0 or najlepszy_wynik < kotwic_serii * prog:
        wynik["pominiety"] = ("kotwice nie potwierdzają kolejności "
                              f"({najlepszy_wynik}/{kotwic_serii})")
        return wynik
    if najlepsze + len(komorki) > len(lista):
        wynik["pominiety"] = "arkusz wykracza poza listę kodów serii"
        return wynik

    nowe = []
    wyjscie.mkdir(parents=True, exist_ok=True)
    for i, (_, _, obraz) in enumerate(komorki):
        kod = lista[najlepsze + i]
        plik = wyjscie / f"{kod}.png"
        if plik.exists():
            continue                      # nie nadpisujemy juz poprawnych grafik
        if zapisuj:
            obraz.save(plik, optimize=True)
        nowe.append(kod)
    wynik["dodane"] = nowe
    return wynik

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arkusze", type=Path, default=KATALOG / "tools/arkusze_sklejone")
    p.add_argument("--od", type=int, default=0)
    p.add_argument("--do", type=int, default=999)
    p.add_argument("--sprawdz", action="store_true")
    a = p.parse_args()
    serie = kody_serii()
    pliki = sorted(x for x in a.arkusze.iterdir() if x.suffix.lower() in (".png", ".jpg", ".ppm"))[a.od:a.do]
    lacznie = []
    for ark in pliki:
        w = dopasuj(ark, serie, KATALOG / "static/img/znaki", zapisuj=not a.sprawdz)
        if "pominiety" in w:
            print(f"  {ark.name:14} POMINIĘTY — {w['pominiety']}")
        else:
            print(f"  {ark.name:14} seria {w.get('seria'):2} | komórek {w['komorek']:3} | "
                  f"kotwic {w['trafien']}/{w['kotwic']} | dodano {len(w.get('dodane', []))}")
            lacznie += w.get("dodane", [])
    print(f"\nDodano grafik: {len(lacznie)}")
    if lacznie:
        print(", ".join(sorted(set(lacznie), key=klucz)))

if __name__ == "__main__":
    main()
