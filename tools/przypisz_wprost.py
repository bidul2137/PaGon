#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Przypisuje kody komorkom arkusza WPROST — dla arkuszy, na ktorych OCR zawodzi.

Uzywac tylko wtedy, gdy zawartosc arkusza zostala obejrzana, a liczba komorek
zgadza sie z podana lista kodow. Skrypt odmawia zapisu przy niezgodnosci liczb,
zeby nie przesunac calej listy o jedna pozycje.

    python tools/przypisz_wprost.py --plik str47.png --kody E-21,E-22a,E-22b,E-22c --zapisz
"""
from __future__ import annotations
import argparse, importlib.util
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "import_znaki_grafiki.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
spec2 = importlib.util.spec_from_file_location("sz", Path(__file__).parent / "dopasuj_szukaj.py")
sz = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(sz)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plik", required=True)
    p.add_argument("--kody", required=True, help="lista kodów po przecinku, w kolejności na arkuszu")
    p.add_argument("--kolumny", type=int, default=7)
    p.add_argument("--wiersze", type=int, default=5)
    p.add_argument("--pomin", type=int, default=0, help="ile pierwszych komórek pominąć")
    p.add_argument("--nadpisz", action="store_true")
    p.add_argument("--zapisz", action="store_true")
    p.add_argument("--arkusze", type=Path, default=KATALOG / "tools/arkusze_sklejone")
    a = p.parse_args()

    kody = [k.strip() for k in a.kody.split(",") if k.strip()]
    komorki = sz.tnij(a.arkusze / a.plik, a.wiersze, a.kolumny, 0.42)
    obrazy = [o for _, o in komorki][a.pomin:]
    print(f"{a.plik}: komórek {len(komorki)} (po pominięciu {a.pomin}: {len(obrazy)}), kodów {len(kody)}")
    if len(obrazy) != len(kody):
        raise SystemExit("  liczby się nie zgadzają — nie zapisuję")

    wy = KATALOG / "static/img/znaki"
    zapisane, pominiete = [], []
    for kod, obraz in zip(kody, obrazy):
        plik = wy / f"{kod}.png"
        if plik.exists() and not a.nadpisz:
            pominiete.append(kod)
            continue
        if a.zapisz:
            obraz.save(plik, optimize=True)
        zapisane.append(kod)
    print(f"  {'zapisano' if a.zapisz else 'do zapisania'}: {', '.join(zapisane) or '—'}")
    if pominiete:
        print(f"  pominięto (już są): {', '.join(pominiete)}")


if __name__ == "__main__":
    main()
