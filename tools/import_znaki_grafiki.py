#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wycina pojedyncze znaki drogowe z arkuszy zbiorczych w obwieszczeniu.

SKAD SIE BIORA ARKUSZE
----------------------
Obwieszczenie (tekst jednolity rozporzadzenia o znakach i sygnalach drogowych)
ma zalaczniki w postaci 26 rastrowych ARKUSZY ZBIORCZYCH — kazdy zawiera siatke
znakow, a pod kazdym znakiem wydrukowany jest jego kod (np. "A-6c").

Skrypt:
  1) wyciaga arkusze z PDF (pdfimages),
  2) wykrywa siatke: pasma poziome na przemian "rzad znakow" / "rzad podpisow",
  3) tnie kazda komorke,
  4) odczytuje kod z podpisu (tesseract) i normalizuje go,
  5) zapisuje znak jako PNG o nazwie kodu.

UZYCIE
------
    python tools/import_znaki_grafiki.py --pdf "../zrodla/obwieszczenie.pdf"
    python tools/import_znaki_grafiki.py --pdf PLIK --sprawdz   # bez zapisu
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE_IMG = KATALOG / "static" / "img" / "znaki"
RAPORT = KATALOG / "data" / "znaki" / "grafiki_report.json"

# kod znaku: seria + numer + opcjonalna litera, np. A-6c, BT-3, T-6b, P-9b
RE_KOD = re.compile(r"^(AT|BT|[ABCDEFGPRSTUW])-?(\d{1,3})([a-z])?$", re.I)
SERIE = {"A", "B", "C", "D", "E", "F", "G", "P", "R", "S", "T", "U", "W", "AT", "BT"}


def pasma(maska: np.ndarray, os_: int, minprzerwa: int) -> list[tuple[int, int]]:
    """Zwraca zakresy (poczatek, koniec) ciaglej zawartosci wzdluz osi."""
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
                wynik.append((start, i - przerwa + 1))
                start = None
    if start is not None:
        wynik.append((start, len(proj)))
    return wynik


def normalizuj_kod(surowy: str) -> str | None:
    """OCR bywa niedokladny — sprowadzamy odczyt do kanonicznego kodu znaku."""
    s = re.sub(r"[^A-Za-z0-9\-]", "", (surowy or "").strip())
    if not s:
        return None
    # typowe pomylki OCR w czesci literowej
    s = s.replace("|", "1").replace("—", "-").replace("–", "-")
    m = RE_KOD.match(s)
    if not m:
        return None
    seria, numer, litera = m.group(1).upper(), m.group(2), (m.group(3) or "").lower()
    if seria not in SERIE:
        return None
    return f"{seria}-{numer}{litera}"


def odczytaj_kod(wycinek: Image.Image) -> tuple[str | None, str]:
    """OCR podpisu pod znakiem. Zwraca (kod_kanoniczny, surowy_odczyt)."""
    im = wycinek.convert("L")
    # podpisy sa male — powiekszamy, zeby tesseract mial z czym pracowac
    im = im.resize((im.width * 5, im.height * 5), Image.LANCZOS)
    # UWAGA: w wartosci -c nie moze byc spacji — tesseract utnie ja na spacji.
    konf = "--psm 7 -c tessedit_char_whitelist=ABCDEFGPRSTUWabcdefghijklmnopqrstuvwxyz0123456789-"
    proby = []
    for cfg in (konf, "--psm 7", "--psm 6"):
        try:
            surowy = pytesseract.image_to_string(im, config=cfg).strip()
        except Exception as e:
            return None, f"<blad OCR: {e}>"
        proby.append(surowy)
        kod = normalizuj_kod(surowy)
        if kod:
            return kod, surowy
    return None, " | ".join(proby)


def przytnij(im: Image.Image, prog: int = 235) -> Image.Image:
    """Obcina biale marginesy wokol znaku."""
    a = np.array(im.convert("L"))
    maska = a < prog
    if not maska.any():
        return im
    ys, xs = np.where(maska)
    m = 3
    return im.crop((max(0, xs.min() - m), max(0, ys.min() - m),
                    min(im.width, xs.max() + 1 + m), min(im.height, ys.max() + 1 + m)))


def tnij_arkusz(sciezka: Path) -> list[tuple[str | None, str, Image.Image]]:
    """Dzieli arkusz na pojedyncze znaki. Zwraca [(kod, surowy_ocr, obraz)]."""
    im = Image.open(sciezka).convert("RGB")
    maska = np.array(im.convert("L")) < 235
    if not maska.any():
        return []

    # odstep miedzy pasmami jest staly i maly — proporcjonalny zlewal
    # rzad znakow z rzedem podpisow na wysokich arkuszach
    wiersze = pasma(maska, 1, 5)
    if not wiersze:
        return []

    wysokosci = [b - a for a, b in wiersze]
    # pasmo podpisow rozpoznajemy po BEZWZGLEDNEJ wysokosci: podpisy to jeden
    # wiersz drobnego tekstu, znaki sa kilkukrotnie wyzsze
    prog_podpisu = max(24, int(np.percentile(wysokosci, 75) * 0.42))
    wyniki: list[tuple[str | None, str, Image.Image]] = []

    i = 0
    while i < len(wiersze):
        y0, y1 = wiersze[i]
        wys = y1 - y0
        # pasmo podpisow jest wyraznie nizsze niz pasmo znakow
        if wys <= prog_podpisu:
            i += 1                      # to pasmo podpisow bez znakow nad nim
            continue

        pasmo_podpisow = wiersze[i + 1] if i + 1 < len(wiersze) else None
        if pasmo_podpisow and (pasmo_podpisow[1] - pasmo_podpisow[0]) > prog_podpisu:
            pasmo_podpisow = None       # kolejne pasmo to znowu znaki, nie podpisy

        kolumny = pasma(maska[y0:y1], 0, 7)
        for x0, x1 in kolumny:
            if (x1 - x0) < 12 or wys < 12:
                continue
            znak = przytnij(im.crop((x0, y0, x1, y1)))
            kod, surowy = (None, "")
            if pasmo_podpisow:
                py0, py1 = pasmo_podpisow
                margines = max(6, (x1 - x0) // 4)
                pod = im.crop((max(0, x0 - margines), py0,
                               min(im.width, x1 + margines), py1))
                kod, surowy = odczytaj_kod(pod)
            wyniki.append((kod, surowy, znak))
        i += 2 if pasmo_podpisow else 1

    return wyniki


def wyciagnij_arkusze(pdf: Path, katalog: Path) -> list[Path]:
    katalog.mkdir(parents=True, exist_ok=True)
    if not shutil.which("pdfimages"):
        raise SystemExit("Brak narzędzia pdfimages (pakiet poppler-utils).")
    subprocess.run(["pdfimages", "-j", str(pdf), str(katalog / "ark")],
                   check=True, capture_output=True)
    return sorted(katalog.glob("ark*"))


def main() -> None:
    p = argparse.ArgumentParser(description="Wycina znaki drogowe z arkuszy w obwieszczeniu.")
    p.add_argument("--pdf", type=Path)
    p.add_argument("--arkusze", type=Path, help="katalog z gotowymi arkuszami")
    p.add_argument("--od", type=int, default=0)
    p.add_argument("--do", type=int, default=999)
    p.add_argument("--sprawdz", action="store_true", help="nie zapisuj, tylko podsumuj")
    p.add_argument("--wyjscie", type=Path, default=WYJSCIE_IMG)
    a = p.parse_args()
    if a.arkusze:
        arkusze = sorted(p for p in a.arkusze.iterdir() if p.suffix.lower() in (".png",".jpg",".ppm"))
        tmpdir = None
    elif a.pdf and a.pdf.exists():
        tmpdir = tempfile.TemporaryDirectory()
        arkusze = wyciagnij_arkusze(a.pdf, Path(tmpdir.name))
    else:
        raise SystemExit("Podaj --pdf albo --arkusze")
    arkusze = arkusze[a.od:a.do]
    print(f"Arkuszy do przetworzenia: {len(arkusze)}")

    if True:

        zapisane: dict[str, str] = {}
        nierozpoznane: list[dict] = []
        konflikty: list[str] = []

        if not a.sprawdz:
            a.wyjscie.mkdir(parents=True, exist_ok=True)

        for ark in arkusze:
            komorki = tnij_arkusz(ark)
            ok = sum(1 for k, _, _ in komorki if k)
            print(f"  {ark.name}: komórek {len(komorki)}, rozpoznanych kodów {ok}")
            for kod, surowy, obraz in komorki:
                if not kod:
                    nierozpoznane.append({"arkusz": ark.name, "ocr": surowy,
                                          "rozmiar": list(obraz.size)})
                    continue
                if kod in zapisane or (not a.sprawdz and (a.wyjscie / f"{kod}.png").exists()):
                    konflikty.append(kod)
                    continue
                zapisane[kod] = ark.name
                if not a.sprawdz:
                    obraz.save(a.wyjscie / f"{kod}.png", optimize=True)

        print(f"\nZapisanych grafik: {len(zapisane)}")
        print(f"Nierozpoznanych podpisów: {len(nierozpoznane)}")
        print(f"Powtórzonych kodów (pominięto): {len(set(konflikty))}")
        if zapisane:
            from collections import Counter
            serie = Counter(k.split("-")[0] for k in zapisane)
            print("Wg serii:", dict(sorted(serie.items())))

        if not a.sprawdz:
            RAPORT.parent.mkdir(parents=True, exist_ok=True)
            stary = {}
            if RAPORT.exists():
                try: stary = json.loads(RAPORT.read_text(encoding="utf-8"))
                except Exception: stary = {}
            laczne = dict(stary.get("zapisane", {})); laczne.update(zapisane)
            RAPORT.write_text(json.dumps({
                "zapisane": laczne,
                "nierozpoznane": (stary.get("nierozpoznane") or []) + nierozpoznane,
                "konflikty": sorted(set(stary.get("konflikty", [])) | set(konflikty)),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"Raport: {RAPORT}  (łącznie grafik: {len(laczne)})")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Dopasowanie po KOLEJNOSCI — ratunek dla podpisow, ktorych OCR nie odczytal.
#
# Arkusz zawiera znaki jednej serii w kolejnosci z rozporzadzenia. Jesli liczba
# komorek zgadza sie z liczba kodow serii, a pewne odczyty OCR trafiaja we
# wlasciwe pozycje, mozna bezpiecznie przypisac kody z listy — bez zgadywania,
# bo kolejnosc jest ta sama co w akcie.
# ---------------------------------------------------------------------------
def dopasuj_po_kolejnosci(arkusz: Path, oczekiwane: list[str], wyjscie: Path,
                          zapisuj: bool = True) -> dict:
    komorki = tnij_arkusz(arkusz)
    odczyty = [k for k, _, _ in komorki]
    wynik = {"arkusz": arkusz.name, "komorek": len(komorki),
             "oczekiwanych": len(oczekiwane), "zapisane": [], "kotwice_ok": 0,
             "kotwice_zle": []}
    if len(komorki) != len(oczekiwane):
        wynik["blad"] = "liczba komórek nie zgadza się z liczbą kodów serii"
        return wynik

    for i, kod in enumerate(odczyty):
        if not kod:
            continue
        if kod == oczekiwane[i]:
            wynik["kotwice_ok"] += 1
        else:
            wynik["kotwice_zle"].append({"pozycja": i, "ocr": kod, "oczekiwany": oczekiwane[i]})

    # wymagamy, by zdecydowana wiekszosc pewnych odczytow potwierdzala kolejnosc
    pewne = sum(1 for k in odczyty if k)
    if pewne and wynik["kotwice_ok"] < pewne * 0.6:
        wynik["blad"] = "odczyty OCR nie potwierdzają kolejności — dopasowanie odrzucone"
        return wynik

    wyjscie.mkdir(parents=True, exist_ok=True)
    for i, (_, _, obraz) in enumerate(komorki):
        kod = oczekiwane[i]
        if zapisuj:
            obraz.save(wyjscie / f"{kod}.png", optimize=True)
        wynik["zapisane"].append(kod)
    return wynik
