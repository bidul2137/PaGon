#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import Tabeli A ADR 2025 wprost z oficjalnego PDF — bez zewnetrznych bibliotek.

DLACZEGO NIE pdfplumber
-----------------------
Tabela A w polskim wydaniu ADR jest rozlozona na SASIADUJACYCH stronach:
  • strona lewa  — kolumny (1)–(11)
  • strona prawa — kolumny (12)–(20) + powtorzony numer UN + nazwa angielska
Zaden gotowy ekstraktor tabel tego nie sklei. Za to sam PDF jest tekstowy
(strumienie FlateDecode z operatorami Tm/TJ), wiec wystarczy odczytac pozycje
kazdego fragmentu tekstu i przypisac go do kolumny po wspolrzednej X.

Ten skrypt nie wymaga niczego poza standardowa biblioteka Pythona.

UZYCIE
------
    python tools/import_adr_pdf_tekst.py --pdf ../zrodla/ADR_tom_I_PL_2025.pdf
    python tools/import_adr_pdf_tekst.py --pdf PLIK --sprawdz     # podglad, bez zapisu
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import zlib
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE = KATALOG / "data" / "adr" / "adr_2025_substances.json"
METADANE = KATALOG / "data" / "adr" / "adr_2025_metadata.json"

ZRODLO = {
    "title": "ADR 2025 — Tabela A, dział 3.2",
    "legal_reference": "Dz.U. 2025 poz. 642",
    "url": "https://eli.gov.pl/eli/DU/2025/642/ogl",
    "adr_version": "ADR 2025",
}

# Granice kolumn po wspolrzednej X, odczytane z naglowkow (1)…(20) w PDF.
KOLUMNY_LEWA = [
    ("un_number",                 40, 62),    # (1)
    ("proper_shipping_name_pl",   62, 185),   # (2)
    ("adr_class",                185, 208),   # (3a)
    ("classification_code",      208, 236),   # (3b)
    ("packing_group",            236, 268),   # (4)
    ("labels",                   268, 300),   # (5)
    ("special_provisions",       300, 327),   # (6)
    ("limited_quantities",       327, 366),   # (7a)
    ("excepted_quantities",      366, 396),   # (7b)
    ("packing_instructions",     396, 432),   # (8)
    ("_pak_szczegolne",          432, 462),   # (9a)
    ("mixed_packing_provisions", 462, 500),   # (9b)
    ("portable_tank_instructions", 500, 532), # (10)
    ("_cyst_przenosne_szcz",     532, 999),   # (11)
]
KOLUMNY_PRAWA = [
    ("vehicle_tank_instructions",  60, 112),  # (12) kod cysterny ADR
    ("_cyst_adr_szcz",            112, 150),  # (13)
    ("_pojazd_cysterna",          150, 186),  # (14)
    ("transport_category",        186, 225),  # (15) + kod tuneli w nawiasie
    ("_przewoz_sztuki",           225, 260),  # (16)
    ("_przewoz_luzem",            260, 295),  # (17)
    ("_zaladunek",                295, 333),  # (18)
    ("_operacje",                 333, 370),  # (19)
    ("danger_identification_number", 370, 396),  # (20)
    ("_un_kontrolny",             396, 415),  # (1) powtorzony
    ("proper_shipping_name_en",   415, 999),  # (2) nazwa angielska
]

RE_UN = re.compile(r"^\d{4}$")
# Tekst w tym PDF wystepuje w dwoch postaciach:
#   ( literal )   — bajty w cp1250, czcionki podstawowe
#   <00240030>    — kody glifow czcionki podzbiorowej, do przelozenia mapa ToUnicode
# Bez obslugi tej drugiej postaci gubi sie ok. 500 nazw przewozowych.
RE_STR = re.compile(rb"\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>", re.S)
RE_FONT = re.compile(rb"/(\w+)\s+[\d.]+\s+Tf")
RE_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
RE_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
RE_HEX = re.compile(rb"<([0-9A-Fa-f]+)>")
# Kolejnosc ma znaczenie: przed kazdym blokiem tekstu PDF ustawia prostokat
# przyciecia komorki (operator "re"). Jego wspolrzedna Y i wysokosc identyfikuja
# WIERSZ tabeli — pewniej niz pozycja tekstu, bo numer UN bywa wysrodkowany
# pionowo, a nazwa zaczyna sie od gornej krawedzi komorki.
RE_RUN = re.compile(
    rb"([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) re"
    rb"|1 0 0 1 ([\d.\-]+) ([\d.\-]+) Tm"
    rb"|\[(.*?)\]\s*TJ"
    rb"|\((?:\\.|[^()\\])*\)\s*Tj",
    re.S,
)
RE_TUNEL = re.compile(r"\(([A-E](?:/[A-E])*)\)")


def _utf16(h: bytes) -> str:
    try:
        return bytes.fromhex(h.decode()).decode("utf-16-be", "replace")
    except ValueError:
        return ""


def czytaj_tounicode(strumien_cmap: bytes) -> dict[int, str]:
    """Buduje mape kod glifu -> znak z zasobu ToUnicode czcionki."""
    mapa: dict[int, str] = {}
    for blok in RE_BFCHAR.findall(strumien_cmap):
        kody = RE_HEX.findall(blok)
        for i in range(0, len(kody) - 1, 2):
            mapa[int(kody[i], 16)] = _utf16(kody[i + 1])
    for blok in RE_BFRANGE.findall(strumien_cmap):
        # postac 1: <lo> <hi> <dst>   postac 2: <lo> <hi> [<d1> <d2> …]
        for m in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)", blok):
            lo, hi, cel = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
            if cel.startswith(b"["):
                for i, h in enumerate(RE_HEX.findall(cel)):
                    mapa[lo + i] = _utf16(h)
            else:
                baza = _utf16(cel[1:-1])
                if baza:
                    for i in range(hi - lo + 1):
                        mapa[lo + i] = chr(ord(baza[0]) + i)
    return mapa


def odkoduj(literal: bytes) -> str:
    """Zamienia literal PDF ( ... ) na tekst. Polskie znaki sa w cp1250."""
    s = literal[1:-1]
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == 0x5C:  # backslash
            nast = s[i + 1:i + 2]
            if nast.isdigit():
                j, ok = i + 1, b""
                while j < len(s) and len(ok) < 3 and s[j:j + 1].isdigit():
                    ok += s[j:j + 1]
                    j += 1
                out.append(int(ok, 8))
                i = j
                continue
            out += {b"n": b"\n", b"t": b"\t", b"r": b"\r"}.get(nast, nast)
            i += 2
            continue
        out.append(c)
        i += 1
    return bytes(out).decode("cp1250", "replace")


def wczytaj_strony(sciezka: Path) -> list[bytes]:
    """Zwraca zdekompresowane strumienie tresci stron, w kolejnosci dokumentu."""
    dane = sciezka.read_bytes()
    obiekty = {
        int(m.group(1)): m.group(2)
        for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", dane, re.S)
    }

    def strumien(body: bytes) -> bytes | None:
        i = body.find(b"stream")
        if i < 0:
            return None
        # po slowie "stream" moze byc CRLF, LF albo samo CR (spotykane w praktyce)
        j = i + len(b"stream")
        if body[j:j + 2] == b"\r\n":
            j += 2
        elif body[j:j + 1] in (b"\n", b"\r"):
            j += 1
        k = body.find(b"endstream", j)
        surowy = body[j:k]
        if b"/FlateDecode" not in body[:i]:
            return surowy
        try:
            return zlib.decompress(surowy)
        except zlib.error:
            try:
                return zlib.decompressobj().decompress(surowy)
            except zlib.error:
                return None

    cache: dict[int, dict[int, str]] = {}

    def mapa_czcionki(nr_obj: int) -> dict[int, str]:
        """Mapa kod->znak dla czcionki; puste, gdy czcionka nie ma ToUnicode."""
        if nr_obj in cache:
            return cache[nr_obj]
        wynik: dict[int, str] = {}
        body = obiekty.get(nr_obj, b"")
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", body)
        if tu:
            cm = strumien(obiekty.get(int(tu.group(1)), b""))
            if cm:
                wynik = czytaj_tounicode(cm)
        cache[nr_obj] = wynik
        return wynik

    pary = []
    for nr, body in obiekty.items():
        if not re.search(rb"/Type\s*/Page[^s]", body):
            continue
        c = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        if not c:
            continue
        czcionki: dict[str, dict[int, str]] = {}
        fd = re.search(rb"/Font\s*<<(.*?)>>", body, re.S)
        if fd:
            for m in re.finditer(rb"/(\w+)\s+(\d+)\s+0\s+R", fd.group(1)):
                czcionki[m.group(1).decode()] = mapa_czcionki(int(m.group(2)))
        pary.append((nr, int(c.group(1)), czcionki))
    pary.sort()
    return [(strumien(obiekty[c]) or b"", cz) for _, c, cz in pary]


def runy(tresc: bytes, czcionki: dict[str, dict[int, str]] | None = None
         ) -> list[tuple[float, float, float, float, str]]:
    """[(wiersz_y, wiersz_h, y, x, tekst)] — tekst z komorka, do ktorej nalezy."""
    czcionki = czcionki or {}
    res = []
    rect = (0.0, 0.0)
    poz = None
    mapa: dict[int, str] = {}
    for m in re.finditer(
        rb"([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) re"
        rb"|1 0 0 1 ([\d.\-]+) ([\d.\-]+) Tm"
        rb"|/(\w+)\s+[\d.]+\s+Tf"
        rb"|\[(.*?)\]\s*TJ"
        rb"|(?:\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>)\s*Tj",
        tresc, re.S):
        if m.group(1) is not None:
            rect = (float(m.group(2)), float(m.group(4)))
        elif m.group(5) is not None:
            poz = (float(m.group(6)), float(m.group(5)))
        elif m.group(7) is not None:
            mapa = czcionki.get(m.group(7).decode(), {})
        elif poz is not None:
            frag = m.group(8) if m.group(8) is not None else m.group(0)
            txt = "".join(odkoduj_fragment(s, mapa) for s in RE_STR.findall(frag))
            if txt.strip():
                res.append((rect[0], rect[1], poz[0], poz[1], txt))
    return res


def odkoduj_fragment(s: bytes, mapa: dict[int, str]) -> str:
    """Literal ( … ) albo ciag szesnastkowy < … > na tekst."""
    if s.startswith(b"<"):
        h = re.sub(rb"\s", b"", s[1:-1])
        if len(h) % 4:                       # kody 1-bajtowe
            return "".join(mapa.get(b, chr(b)) for b in bytes.fromhex(h.decode()))
        kody = [int(h[i:i + 4], 16) for i in range(0, len(h), 4)]
        return "".join(mapa.get(k, "") for k in kody)
    return odkoduj(s)


def wiersze_strony(strona, uklad, pole_un: str) -> list[dict[str, str]]:
    """Dzieli strone na wiersze Tabeli A po prostokatach komorek.

    Wiersz = wszystkie fragmenty tekstu o tej samej podstawie i wysokosci
    komorki. Wewnatrz wiersza tekst ukladamy wg Y (od gory), potem wg X,
    i przypisujemy do kolumny po wspolrzednej X.
    """
    grupy: dict[tuple[float, float], list[tuple[float, float, str]]] = {}
    for ry, rh, y, x, t in runy(strona[0], strona[1]):
        if rh <= 0 or rh > 400:      # pomijamy prostokat calej strony
            continue
        grupy.setdefault((round(ry, 1), round(rh, 1)), []).append((y, x, t))

    wiersze = []
    for (ry, _rh), elementy in sorted(grupy.items(), key=lambda kv: -kv[0][0]):
        kom: dict[str, str] = {}
        for _y, x, t in sorted(elementy, key=lambda e: (-e[0], e[1])):
            for nazwa, x0, x1 in uklad:
                if x0 <= x < x1:
                    kom[nazwa] = (kom.get(nazwa, "") + " " + t).strip()
                    break
        if RE_UN.match((kom.get(pole_un) or "").strip()):
            wiersze.append(kom)
    return wiersze


def czy_lewa_tabeli(strona) -> bool:
    ile = 0
    for _ry, _rh, _y, x, t in runy(strona[0], strona[1]):
        if 40 <= x < 62 and RE_UN.match(t.strip()):
            ile += 1
    return ile >= 3


def scal(lewa: dict, prawa: dict, dzis: str) -> dict | None:
    un = (lewa.get("un_number") or "").strip()
    if not RE_UN.match(un):
        return None

    def w(d, k):
        v = (d.get(k) or "").strip()
        v = re.sub(r"\s+", " ", v)
        return v or None

    kat = w(prawa, "transport_category") or ""
    tunel = RE_TUNEL.search(kat)
    kategoria = re.sub(r"\(.*?\)", "", kat).strip() or None

    etykiety = [e.strip() for e in re.split(r"[+]", w(lewa, "labels") or "")
                if e.strip() and re.match(r"^\d", e.strip())]
    klasa = w(lewa, "adr_class")
    kemler = w(prawa, "danger_identification_number")
    if kemler and not re.match(r"^X?\d{2,3}$", kemler):
        kemler = None

    nazwa_pl = w(lewa, "proper_shipping_name_pl")
    nazwa_en = w(prawa, "proper_shipping_name_en")

    braki = []
    if not klasa:
        braki.append("brak klasy (kol. 3a)")
    if not nazwa_pl:
        braki.append("brak nazwy polskiej (kol. 2)")
    kontrolny = (prawa.get("_un_kontrolny") or "").strip()
    if kontrolny and kontrolny != un:
        braki.append(f"numer UN na stronie prawej ({kontrolny}) różni się od lewej ({un})")

    slowa = []
    for zrodlo in (nazwa_pl, nazwa_en):
        if zrodlo:
            slowa += [s.lower() for s in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź]{4,}", zrodlo)]

    return {
        "un_number": un,
        "proper_shipping_name_pl": nazwa_pl,
        "proper_shipping_name_en": nazwa_en,
        "danger_identification_number": kemler,
        "adr_class": klasa,
        "subsidiary_risks": [e for e in etykiety if klasa and not e.startswith(klasa)],
        "classification_code": w(lewa, "classification_code"),
        "packing_group": w(lewa, "packing_group"),
        "labels": etykiety,
        "special_provisions": w(lewa, "special_provisions"),
        "limited_quantities": w(lewa, "limited_quantities"),
        "excepted_quantities": w(lewa, "excepted_quantities"),
        "packing_instructions": w(lewa, "packing_instructions"),
        "mixed_packing_provisions": w(lewa, "mixed_packing_provisions"),
        "portable_tank_instructions": w(lewa, "portable_tank_instructions"),
        "vehicle_tank_instructions": w(prawa, "vehicle_tank_instructions"),
        "transport_category": kategoria,
        "tunnel_restriction_code": tunel.group(1) if tunel else None,
        "keywords": sorted(set(slowa))[:12],
        "source": dict(ZRODLO, verified_at=dzis),
        "verification_status": "verified" if not braki else "partial_verification",
        "verification_note": None if not braki else "; ".join(braki),
    }


def importuj(sciezka: Path, podglad: bool) -> list[dict]:
    dzis = datetime.date.today().isoformat()
    print(f"Wczytuję {sciezka.name} …")
    strony = wczytaj_strony(sciezka)
    print(f"  stron: {len(strony)}")

    indeksy = [i for i, s in enumerate(strony) if s[0] and czy_lewa_tabeli(s)]
    if not indeksy:
        raise SystemExit("Nie znaleziono stron Tabeli A.")
    print(f"  strony Tabeli A (lewe): {indeksy[0] + 1}–{indeksy[-1] + 1}, sztuk {len(indeksy)}")

    rekordy: list[dict] = []
    niesparowane = 0
    for i in indeksy:
        if i + 1 >= len(strony):
            continue
        lewe = wiersze_strony(strony[i], KOLUMNY_LEWA, "un_number")
        prawe = wiersze_strony(strony[i + 1], KOLUMNY_PRAWA, "_un_kontrolny")
        for k, l in enumerate(lewe):
            p = prawe[k] if k < len(prawe) else {}
            if not p:
                niesparowane += 1
            r = scal(l, p, dzis)
            if r:
                rekordy.append(r)
        if podglad and len(rekordy) >= 12:
            break

    # scalenie powtorzen (jedna pozycja UN moze miec kilka wierszy — rozne grupy pakowania)
    scalone: dict[str, dict] = {}
    warianty = 0
    for r in rekordy:
        un = r["un_number"]
        if un not in scalone:
            scalone[un] = r
            continue
        warianty += 1
        stary = scalone[un]
        for k, v in r.items():
            if k in ("keywords", "labels", "subsidiary_risks"):
                stary[k] = sorted(set(stary.get(k) or []) | set(v or []))
            elif not stary.get(k) and v:
                stary[k] = v
        # warianty tej samej pozycji roznia sie zwykle grupa pakowania
        gp = []
        for zrodlo in (stary.get("packing_group"), r.get("packing_group")):
            for czesc in re.split(r"[/ ]+", zrodlo or ""):
                if czesc and czesc not in gp:
                    gp.append(czesc)
        stary["packing_group"] = "/".join(gp) if gp else None

    print(f"  wierszy: {len(rekordy)} → pozycji UN: {len(scalone)} (scalono {warianty} wariantów)")
    if niesparowane:
        print(f"  UWAGA: {niesparowane} wierszy bez odpowiednika na stronie prawej")
    return sorted(scalone.values(), key=lambda r: r["un_number"])


def kontrola(rekordy: list[dict]) -> None:
    print("\n=== KONTROLA JAKOŚCI ===")
    print(f"Pozycji: {len(rekordy)}")
    zle = [r['un_number'] for r in rekordy if not RE_UN.match(r['un_number'])]
    print(f"UN spoza formatu 4 cyfr: {zle or 'brak'}")
    licz: dict[str, int] = {}
    for r in rekordy:
        licz[r['un_number']] = licz.get(r['un_number'], 0) + 1
    print(f"Duplikaty: {[u for u, n in licz.items() if n > 1] or 'brak'}")
    zx = [r['un_number'] for r in rekordy if (r.get('danger_identification_number') or '').startswith('X')]
    print(f"Kody z literą X: {len(zx)} — np. {zx[:6]}")
    print(f"Bez kodu zagrożenia (kol. 20 pusta): "
          f"{sum(1 for r in rekordy if not r.get('danger_identification_number'))}")
    pelne = sum(1 for r in rekordy if r['verification_status'] == 'verified')
    print(f"Pełna weryfikacja: {pelne} | częściowa: {len(rekordy) - pelne}")

    w = next((r for r in rekordy if r['un_number'] == '1203'), None)
    print("\nRekord kontrolny UN 1203:")
    if not w:
        print("  BRAK!")
        return
    for pole, oczek in (("adr_class", "3"), ("packing_group", "II"),
                        ("classification_code", "F1"), ("danger_identification_number", "33")):
        mam = w.get(pole)
        print(f"  {pole:31} = {str(mam):10} (oczekiwane {oczek}) {'✓' if mam == oczek else '← ROZBIEŻNOŚĆ'}")
    print(f"  nazwa PL  = {w.get('proper_shipping_name_pl')}")
    print(f"  nazwa EN  = {w.get('proper_shipping_name_en')}")
    print(f"  tunele    = {w.get('tunnel_restriction_code')}  kat. transp. = {w.get('transport_category')}")


def main() -> None:
    p = argparse.ArgumentParser(description="Import Tabeli A ADR 2025 z PDF (bez zależności).")
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sprawdz", action="store_true", help="podgląd kilkunastu pozycji, bez zapisu")
    p.add_argument("--wyjscie", type=Path, default=WYJSCIE)
    a = p.parse_args()

    if not a.pdf.exists():
        raise SystemExit(f"Nie ma pliku: {a.pdf}")

    rekordy = importuj(a.pdf, a.sprawdz)

    if a.sprawdz:
        print("\n--- PODGLĄD ---")
        for r in rekordy[:12]:
            print(f"UN {r['un_number']} | kl {r['adr_class']:4} | {str(r['classification_code']):6} | "
                  f"GP {str(r['packing_group']):6} | Kemler {str(r['danger_identification_number']):5} | "
                  f"tunel {str(r['tunnel_restriction_code']):5} | {(r['proper_shipping_name_pl'] or '')[:44]}")
        return

    a.wyjscie.parent.mkdir(parents=True, exist_ok=True)
    a.wyjscie.write_text(json.dumps(rekordy, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nZapisano {len(rekordy)} pozycji → {a.wyjscie}")

    if METADANE.exists():
        meta = json.loads(METADANE.read_text(encoding="utf-8"))
        pelne = sum(1 for r in rekordy if r['verification_status'] == 'verified')
        dzis = datetime.date.today().isoformat()
        meta.update(
            dataset_name="ADR 2025 — Tabela A",
            record_count=len(rekordy), fully_verified_count=pelne,
            partially_verified_count=len(rekordy) - pelne,
            downloaded_at=dzis, verified_at=dzis,
            is_complete=len(rekordy) > 2500, dataset_version="1.0.0",
            completeness_note="Import pełnej Tabeli A z oficjalnego PDF „ADR tom I PL 2025”.",
            import_script="tools/import_adr_pdf_tekst.py",
        )
        METADANE.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Zaktualizowano {METADANE.name}")

    kontrola(rekordy)


if __name__ == "__main__":
    main()
