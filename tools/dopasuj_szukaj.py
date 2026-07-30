#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Domyka brakujace grafiki: przeszukuje warianty ciecia arkusza.

DLACZEGO
--------
Jeden zestaw progow nie pasuje do wszystkich arkuszy: znaki serii D i E sa
szerokimi tablicami i przy malym odstepie kolumn sklejaja sie z sasiadem,
a przy duzym — rozpadaja na kawalki. Zamiast dobierac progi recznie, dla
kazdego arkusza przechodzimy kilka wariantow i wybieramy ten, ktory po
dopasowaniu do listy kodow serii daje NAJWIECEJ zgodnych kotwic OCR.

Zapis nastepuje tylko przy wysokiej zgodnosci — inaczej arkusz jest pomijany.
"""
from __future__ import annotations
import argparse, importlib.util, json, re
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

KATALOG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "import_znaki_grafiki.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

WARIANTY = [
    # (odstep_wierszy, odstep_kolumn, mnoznik_progu_podpisu)
    (5, 7, 0.42), (5, 14, 0.42), (5, 22, 0.42), (5, 32, 0.42), (5, 45, 0.42),
]
# OCR jest kosztowny — do oceny wariantu wystarczy kilka kotwic rozsianych po arkuszu
MAX_KOTWIC = 8

def klucz(k):
    m = re.match(r"^([A-Z]+)-(\d+)([a-z]?)$", k)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (k, 0, "")

def tnij(sciezka: Path, odst_w: int, odst_k: int, mnoznik: float):
    """Wariant tnij_arkusz z parametrami — reszta logiki jak w module bazowym."""
    im = Image.open(sciezka).convert("RGB")
    maska = np.array(im.convert("L")) < 235
    if not maska.any():
        return []
    wiersze = g.pasma(maska, 1, odst_w)
    if not wiersze:
        return []
    wysokosci = [b - a for a, b in wiersze]
    prog = max(20, int(np.percentile(wysokosci, 75) * mnoznik))
    wynik = []
    i = 0
    while i < len(wiersze):
        y0, y1 = wiersze[i]
        wys = y1 - y0
        if wys <= prog:
            i += 1
            continue
        podpisy = wiersze[i + 1] if i + 1 < len(wiersze) else None
        if podpisy and (podpisy[1] - podpisy[0]) > prog:
            podpisy = None
        for x0, x1 in g.pasma(maska[y0:y1], 0, odst_k):
            if (x1 - x0) < 12:
                continue
            obraz = g.przytnij(im.crop((x0, y0, x1, y1)))
            pole_podpisu = None
            if podpisy:
                mar = max(6, (x1 - x0) // 4)
                pole_podpisu = (max(0, x0 - mar), podpisy[0],
                                min(im.width, x1 + mar), podpisy[1])
            wynik.append((None, obraz, pole_podpisu))
        i += 2 if podpisy else 1

    # OCR tylko probki — rownomiernie rozlozonej po arkuszu
    if wynik:
        idx = [round(j * (len(wynik) - 1) / max(1, min(MAX_KOTWIC, len(wynik)) - 1))
               for j in range(min(MAX_KOTWIC, len(wynik)))]
        for j in sorted(set(idx)):
            _, obraz, pole = wynik[j]
            if pole:
                kod, _ = g.odczytaj_kod(im.crop(pole))
                wynik[j] = (kod, obraz, pole)
    return [(k, o) for k, o, _ in wynik]

def ocen(komorki, lista):
    """Najlepsze przesuniecie i liczba zgodnych kotwic."""
    odczyty = [k for k, _ in komorki]
    pewne = sum(1 for k in odczyty if k)
    if not pewne or len(komorki) > len(lista):
        return None, 0, pewne
    najl, najw = 0, -1
    for off in range(0, len(lista) - len(komorki) + 1):
        traf = sum(1 for i, k in enumerate(odczyty) if k and k == lista[off + i])
        if traf > najw:
            najl, najw = off, traf
    return najl, najw, pewne

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arkusze", type=Path, default=KATALOG / "tools/arkusze_sklejone")
    p.add_argument("--plik", type=str, required=True, help="nazwa arkusza, np. str44.png")
    p.add_argument("--prog", type=float, default=0.75)
    p.add_argument("--zapisz", action="store_true")
    a = p.parse_args()

    meta = json.loads((KATALOG / "data/znaki/metadata.json").read_text(encoding="utf-8"))
    serie = {}
    for kat in meta["categories"]:
        lst = json.loads((KATALOG / "data/znaki" / kat["file"]).read_text(encoding="utf-8"))
        serie[kat["id"]] = sorted((z["code"] for z in lst), key=klucz)

    ark = a.arkusze / a.plik
    najlepszy = None
    for (ow, ok_, mn) in WARIANTY:
        kom = tnij(ark, ow, ok_, mn)
        if not kom:
            continue
        kotwice = [k for k, _ in kom if k]
        if not kotwice:
            continue
        seria = Counter(k.split("-")[0] for k in kotwice).most_common(1)[0][0]
        lista = serie.get(seria)
        if not lista:
            continue
        off, traf, pewne = ocen(kom, lista)
        udzial = traf / pewne if pewne else 0
        print(f"  wiersze={ow:2} kolumny={ok_:2} próg={mn}  komórek={len(kom):3} "
              f"seria={seria:2} kotwice={traf}/{pewne} ({udzial:.0%})")
        if najlepszy is None or (traf, udzial) > (najlepszy[1], najlepszy[2]):
            najlepszy = (kom, traf, udzial, seria, lista, off, (ow, ok_, mn))

    if not najlepszy:
        print("  brak wariantu z odczytami")
        return
    kom, traf, udzial, seria, lista, off, param = najlepszy
    print(f"\nNAJLEPSZY: {param} | seria {seria} | zgodność {udzial:.0%} | przesunięcie {off}")
    if udzial < a.prog:
        print("  poniżej progu — nie zapisuję")
        return
    wy = KATALOG / "static/img/znaki"
    nowe = []
    for i, (_, obraz) in enumerate(kom):
        kod = lista[off + i]
        if (wy / f"{kod}.png").exists():
            continue
        if a.zapisz:
            obraz.save(wy / f"{kod}.png", optimize=True)
        nowe.append(kod)
    print(f"  {'zapisano' if a.zapisz else 'do zapisania'}: {len(nowe)} — {', '.join(nowe)}")

if __name__ == "__main__":
    main()
