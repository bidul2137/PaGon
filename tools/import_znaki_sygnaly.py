#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wycina sygnalizatory (seria S) ze strony "SYGNAŁY ŚWIETLNE" obwieszczenia.

DLACZEGO OSOBNE NARZEDZIE
-------------------------
Na arkuszach ze znakami kazdy znak to jedna zwarta plama, wiec ogolny skrypt
tnie je po pasmach poziomych. Sygnalizator jest narysowany inaczej: to KILKA
osobnych czarnych prostokatow (czerwone, zolte, zielone swiatlo) rozdzielonych
biala przerwa. Ciecie po pasmach traktowalo kazde swiatlo jak osobny rzad i
zapisywalo tylko to lezace bezposrednio nad podpisem — stad sygnalizatory bez
czerwonego swiatla.

JAK TO ROBIMY
-------------
Strona ma uklad blokowy: rzad sygnalizatorow, pod nim rzad podpisow, i tak trzy
razy. Wiec:
  1) znajdujemy rzedy podpisow (niskie pasma z tekstem),
  2) blok = wszystko miedzy poprzednim rzedem podpisow a biezacym,
  3) w bloku szukamy KOLUMN z duza przerwa minimalna — jedna kolumna to caly
     sygnalizator razem ze wszystkimi swiatlami,
  4) kod czytamy z podpisu (OCR) i sprawdzamy, czy zgadza sie z kolejnoscia.

Gdy OCR nie potwierdzi przypisania, nic nie zapisujemy — lepiej brak grafiki
niz grafika pod zlym kodem.

UZYCIE
------
    python tools/import_znaki_sygnaly.py --pdf "../zrodla/obwieszczenie.pdf"
    python tools/import_znaki_sygnaly.py --pdf PLIK --sprawdz
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

import re

import numpy as np
from PIL import Image

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE_IMG = KATALOG / "static" / "img" / "znaki"

STRONA = 54          # "SYGNAŁY ŚWIETLNE" w tekscie jednolitym (Dz.U. 2019 poz. 2310)
DPI = 200
# kolejnosc z rozporzadzenia, rzedami
RE_KOD_S = re.compile(r"S-\d[A-Z]?")
OCZEKIWANE = [["S-1", "S-1a", "S-2"],
              ["S-3", "S-3a", "S-4"],
              ["S-5", "S-6", "S-7"]]

try:
    import pytesseract
except ImportError:
    pytesseract = None


def pasma(maska: np.ndarray, os_: int, minprzerwa: int) -> list[tuple[int, int]]:
    proj = maska.sum(axis=os_) > 0
    wynik, start, przerwa = [], None, 0
    for i, v in enumerate(proj):
        if v:
            if start is None:
                start = i
            przerwa = 0
        elif start is not None:
            przerwa += 1
            if przerwa >= minprzerwa:
                wynik.append((start, i - przerwa + 1)); start = None
    if start is not None:
        wynik.append((start, len(proj)))
    return wynik


def przytnij(im: Image.Image, prog: int = 235) -> Image.Image:
    a = np.array(im.convert("L")); m = a < prog
    if not m.any():
        return im
    ys, xs = np.where(m); r = 4
    return im.crop((max(0, xs.min() - r), max(0, ys.min() - r),
                    min(im.width, xs.max() + 1 + r), min(im.height, ys.max() + 1 + r)))


MYLONE = {"/": "7", "|": "1", "l": "1", "O": "0", "o": "0", "—": "-", "–": "-"}


def popraw_ocr(tekst: str) -> str:
    """Sprowadza odczyt podpisu do postaci kodu, prostujac typowe pomylki OCR."""
    return "".join(MYLONE.get(z, z) for z in (tekst or "")).upper().replace(" ", "")


def odczytaj(wyc: Image.Image) -> str:
    if pytesseract is None:
        return ""
    im = wyc.convert("L")
    im = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    try:
        return pytesseract.image_to_string(im, config="--psm 7").strip().replace(" ", "")
    except Exception:
        return ""


def renderuj(pdf: Path, katalog: Path) -> Path:
    subprocess.run(["pdftoppm", "-f", str(STRONA), "-l", str(STRONA), "-r", str(DPI),
                    "-png", str(pdf), str(katalog / "str")], check=True, capture_output=True)
    pliki = sorted(katalog.glob("str*.png"))
    if not pliki:
        raise SystemExit("pdftoppm nie wygenerował strony")
    return pliki[0]


def wytnij(strona: Path) -> list[tuple[str, str, Image.Image]]:
    """Zwraca [(kod_oczekiwany, odczyt_ocr, obraz)]."""
    im = Image.open(strona).convert("RGB")
    maska = np.array(im.convert("L")) < 235

    wiersze = pasma(maska, 1, 12)
    # Rzad podpisow rozpoznajemy po TRESCI, nie po wymiarach: naglowek strony
    # i tytuly tez sa niskimi pasmami tekstu i mylily podzial na bloki.
    # Pasmo jest podpisem, gdy odczytuje sie z niego kod serii S.
    podpisy = []
    for a, b in wiersze:
        if (b - a) > DPI * 0.35:          # za wysokie na wiersz tekstu
            continue
        odczyt = odczytaj(im.crop((0, max(0, a - 4), im.width, b + 4))).upper()
        if RE_KOD_S.search(odczyt.replace("—", "-").replace("–", "-")):
            podpisy.append((a, b))

    wynik = []
    poprz_koniec = 0
    for nr, (py0, py1) in enumerate(podpisy[:len(OCZEKIWANE)]):
        blok = maska[poprz_koniec:py0].copy()
        # Wewnatrz bloku kasujemy wszystkie cienkie pasma — to naglowek strony
        # i tytuly. Sygnalizator ma zawsze wysokie prostokaty, wiec nic nie tracimy,
        # a wysrodkowany tytul potrafil zmostkowac dwie sasiednie kolumny w jedna.
        for ba, bb in pasma(blok, 1, 12):
            if (bb - ba) <= DPI * 0.35:
                blok[ba:bb] = False
        if blok.any():
            # duza przerwa minimalna: swiatla jednego sygnalizatora stoja blisko,
            # sasiednie sygnalizatory dzieli szeroki odstep
            kolumny = pasma(blok, 0, int(DPI * 0.35))
            podp_kol = pasma(maska[py0:py1], 0, int(DPI * 0.35))
            # liczba sygnalizatorow w rzedzie musi zgadzac sie z akta — inaczej
            # doszlo do sklejenia albo rozbicia kolumny i przypisanie byloby zgadywaniem
            if len(kolumny) != len(OCZEKIWANE[nr]):
                raise SystemExit(
                    f"Rząd {nr + 1}: wykryto {len(kolumny)} kolumn, "
                    f"a akt wymienia {len(OCZEKIWANE[nr])} — przerywam bez zapisu.")
            for i, (x0, x1) in enumerate(kolumny):
                ys = np.where(blok[:, x0:x1].any(axis=1))[0]
                if not len(ys):
                    continue
                obraz = przytnij(im.crop((x0, poprz_koniec + ys.min(),
                                          x1, poprz_koniec + ys.max() + 1)))
                kod = OCZEKIWANE[nr][i] if i < len(OCZEKIWANE[nr]) else "?"
                ocr = ""
                if i < len(podp_kol):
                    qx0, qx1 = podp_kol[i]
                    ocr = odczytaj(im.crop((qx0 - 4, py0 - 4, qx1 + 4, py1 + 4)))
                wynik.append((kod, ocr, obraz))
        poprz_koniec = py1
    return wynik


def main() -> None:
    p = argparse.ArgumentParser(description="Wycina sygnalizatory serii S.")
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sprawdz", action="store_true")
    p.add_argument("--wyjscie", type=Path, default=WYJSCIE_IMG)
    a = p.parse_args()

    with tempfile.TemporaryDirectory() as td:
        strona = renderuj(a.pdf, Path(td))
        pozycje = wytnij(strona)

        zgodne = [(k, o, im) for k, o, im in pozycje if popraw_ocr(o) == k.upper()]
        print(f"Wyciętych sygnalizatorów: {len(pozycje)}")
        for kod, ocr, im in pozycje:
            zgoda = "ok" if popraw_ocr(ocr) == kod.upper() else f"ROZBIEŻNOŚĆ (OCR: {ocr or '—'})"
            print(f"  {kod:6} {im.width:4}x{im.height:<4} {zgoda}")

        if len(zgodne) != len(pozycje):
            print("\nPodpisy nie potwierdzają wszystkich przypisań — nic nie zapisano.")
            raise SystemExit(1)

        if a.sprawdz:
            print("\nTryb sprawdzenia — bez zapisu.")
            return
        a.wyjscie.mkdir(parents=True, exist_ok=True)
        for kod, _, im in zgodne:
            im.save(a.wyjscie / f"{kod}.png", optimize=True)
        print(f"\nZapisano {len(zgodne)} grafik do {a.wyjscie}")


if __name__ == "__main__":
    main()
