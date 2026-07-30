#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Domyka grafiki znakow: interpolacja miedzy kotwicami OCR.

METODA
------
1. Tniemy arkusz i odczytujemy podpis KAZDEJ komorki (jednorazowo).
2. Poprawnie odczytane kody sa KOTWICAMI. Sprawdzamy, ze ich pozycje na
   arkuszu i w liscie kodow serii rosna monotonicznie — inaczej ciecie
   rozjechalo sie i arkusz odrzucamy.
3. Luke miedzy dwiema kotwicami wypelniamy TYLKO wtedy, gdy liczba komorek
   w luce dokladnie odpowiada liczbie brakujacych kodow. Jesli sie nie zgadza,
   luka zostaje pusta — lepiej brak grafiki niz zla grafika.

Dzieki temu zbedna albo scalona komorka psuje najwyzej swoj fragment arkusza,
a nie cala serie.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from collections import Counter
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "import_znaki_grafiki.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
spec2 = importlib.util.spec_from_file_location("sz", Path(__file__).parent / "dopasuj_szukaj.py")
sz = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(sz)


def klucz(k):
    m = re.match(r"^([A-Z]+)-(\d+)([a-z]?)$", k)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (k, 0, "")


def serie_kodow():
    meta = json.loads((KATALOG / "data/znaki/metadata.json").read_text(encoding="utf-8"))
    out = {}
    for kat in meta["categories"]:
        lst = json.loads((KATALOG / "data/znaki" / kat["file"]).read_text(encoding="utf-8"))
        out[kat["id"]] = sorted((z["code"] for z in lst), key=klucz)
    return out


def przetworz(ark: Path, serie: dict, odst_k: int, zapisz: bool) -> dict:
    komorki = g.tnij_arkusz(ark) if odst_k == 7 else [
        (k, "", o) for k, o in sz.tnij(ark, 5, odst_k, 0.42)]
    odczyty = [k for k, *_ in komorki]
    obrazy = [c[-1] for c in komorki]
    kotwice = [k for k in odczyty if k]
    if not kotwice:
        return {"blad": "brak odczytanych kodów"}

    seria = Counter(k.split("-")[0] for k in kotwice).most_common(1)[0][0]
    lista = serie.get(seria)
    if not lista:
        return {"blad": f"nieznana seria {seria}"}
    poz = {k: i for i, k in enumerate(lista)}

    # kotwice: (indeks_komorki, indeks_w_liscie) — tylko rosnace
    pary, ostatni = [], -1
    for i, k in enumerate(odczyty):
        if k and k in poz and poz[k] > ostatni:
            pary.append((i, poz[k]))
            ostatni = poz[k]
    if len(pary) < 2:
        return {"blad": f"za mało kotwic ({len(pary)})", "seria": seria}

    przypisane: dict[int, str] = {}
    for i, j in pary:
        przypisane[i] = lista[j]
    luk_ok = luk_zle = 0
    for (i1, j1), (i2, j2) in zip(pary, pary[1:]):
        if (i2 - i1) == (j2 - j1):                 # liczby zgodne — mozna wypelnic
            for d in range(1, i2 - i1):
                przypisane[i1 + d] = lista[j1 + d]
            luk_ok += 1
        else:
            luk_zle += 1

    wy = KATALOG / "static/img/znaki"
    nowe = []
    for i, kod in sorted(przypisane.items()):
        if (wy / f"{kod}.png").exists():
            continue
        if zapisz:
            obrazy[i].save(wy / f"{kod}.png", optimize=True)
        nowe.append(kod)
    return {"seria": seria, "komorek": len(komorki), "kotwic": len(pary),
            "luki_ok": luk_ok, "luki_odrzucone": luk_zle, "nowe": nowe}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plik", required=True)
    p.add_argument("--kolumny", type=int, default=7, help="odstęp kolumn przy cięciu")
    p.add_argument("--zapisz", action="store_true")
    p.add_argument("--arkusze", type=Path, default=KATALOG / "tools/arkusze_sklejone")
    a = p.parse_args()
    w = przetworz(a.arkusze / a.plik, serie_kodow(), a.kolumny, a.zapisz)
    if "blad" in w:
        print(f"{a.plik}: {w['blad']}")
        return
    print(f"{a.plik} | seria {w['seria']} | komórek {w['komorek']} | kotwic {w['kotwic']} | "
          f"luki wypełnione {w['luki_ok']}, odrzucone {w['luki_odrzucone']}")
    print(f"  {'zapisano' if a.zapisz else 'do zapisania'} {len(w['nowe'])}: {', '.join(w['nowe'])}")


if __name__ == "__main__":
    main()
