#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buduje baze znakow drogowych z tekstu obwieszczenia (tekst jednolity).

ZRODLO
------
Obwieszczenie Ministra Infrastruktury z 31.10.2019 — tekst jednolity rozporzadzenia
Ministrow Infrastruktury oraz Spraw Wewnetrznych i Administracji w sprawie znakow
i sygnalow drogowych (Dz.U. 2019 poz. 2310).

CO ROBI
-------
Tekst aktu opisuje kazdy znak wzorcem:  Znak A-5 „skrzyzowanie drog” ostrzega o …
Skrypt wyciaga z niego:
  • kod znaku,
  • nazwe urzedowa (z cudzyslowu),
  • zdanie objasniajace znaczenie (short_description),
  • pelniejszy fragment jednostki redakcyjnej (details),
  • numer paragrafu, w ktorym znak jest opisany (legal_basis).

Nic nie jest dopisywane od siebie — jesli aktu nie da sie jednoznacznie odczytac,
rekord dostaje status partial_verification z notatka.

UZYCIE
------
    python tools/import_znaki_dane.py --pdf "../zrodla/obwieszczenie.pdf"
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE = KATALOG / "data" / "znaki"
GRAFIKI = KATALOG / "static" / "img" / "znaki"

AKT = {
    "act_title": ("Rozporządzenie Ministrów Infrastruktury oraz Spraw Wewnętrznych "
                  "i Administracji w sprawie znaków i sygnałów drogowych"),
    "journal_reference": "Dz.U. 2019 poz. 2310 z późn. zm. (tekst jednolity)",
}

KATEGORIE = [
    ("A",  "Znaki ostrzegawcze",                         "a_ostrzegawcze"),
    ("B",  "Znaki zakazu",                               "b_zakazu"),
    ("C",  "Znaki nakazu",                               "c_nakazu"),
    ("D",  "Znaki informacyjne",                         "d_informacyjne"),
    ("E",  "Znaki kierunku i miejscowości",              "e_kierunku_miejscowosci"),
    ("F",  "Znaki uzupełniające",                        "f_uzupelniajace"),
    ("G",  "Dodatkowe znaki przed przejazdami kolejowymi", "g_kolejowe"),
    ("P",  "Znaki poziome",                              "p_poziome"),
    ("S",  "Sygnały drogowe",                            "s_sygnaly"),
    ("T",  "Tabliczki do znaków drogowych",              "t_tabliczki"),
    ("R",  "Dodatkowe znaki szlaków i tras turystycznych", "r_szlaki"),
    ("BT", "Znaki i sygnały dla kierujących tramwajami", "bt_tramwaje"),
    ("AT", "Znaki ostrzegawcze dla kierujących tramwajami", "at_tramwaje"),
    ("W",  "Znaki W",                                    "w"),
    ("U",  "Urządzenia bezpieczeństwa ruchu",            "u_urzadzenia"),
]
NAZWA_KAT = {s: n for s, n, _ in KATEGORIE}
PLIK_KAT = {s: p for s, _, p in KATEGORIE}

RE_KOD = re.compile(r"\b((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3}[a-z]?)\b")
# kod, po ktorym w cudzyslowie stoi nazwa urzedowa
RE_KOD_NAZWA = re.compile(r"\b((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3}[a-z]?)\s*„([^”]{2,300})”")
RE_PARAGRAF = re.compile(r"§\s*(\d+[a-z]?)\.")


def wczytaj_tekst(pdf: Path) -> str:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))


def jednostki(tekst: str) -> list[tuple[str, str]]:
    """Dzieli akt na jednostki redakcyjne: [(numer_paragrafu, tresc)]."""
    czesci, ostatni, bufor = [], None, []
    for linia in tekst.split("\n"):
        m = RE_PARAGRAF.search(linia)
        if m and m.start() < 6:
            if ostatni is not None:
                czesci.append((ostatni, "\n".join(bufor)))
            ostatni, bufor = m.group(1), [linia]
        else:
            bufor.append(linia)
    if ostatni is not None:
        czesci.append((ostatni, "\n".join(bufor)))
    return czesci


def zdania(tekst: str) -> list[str]:
    t = re.sub(r"\s+", " ", tekst).strip()
    return [z.strip() for z in re.split(r"(?<=[.;])\s+(?=[A-ZŁŚŻŹĆÓĘĄ0-9])", t) if z.strip()]


def zbuduj(tekst: str) -> list[dict]:
    dzis = datetime.date.today().isoformat()
    nazwy: dict[str, str] = {}
    for m in RE_KOD_NAZWA.finditer(tekst):
        kod, nazwa = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        nazwy.setdefault(kod, nazwa)

    lokalizacja: dict[str, tuple[str, str]] = {}   # kod -> (paragraf, tresc jednostki)
    for par, tresc in jednostki(tekst):
        for kod in set(RE_KOD.findall(tresc)):
            lokalizacja.setdefault(kod, (par, tresc))

    wszystkie = sorted(set(RE_KOD.findall(tekst)))
    rekordy = []
    for kod in wszystkie:
        seria = kod.split("-")[0]
        if seria not in NAZWA_KAT:
            continue
        nazwa = nazwy.get(kod)
        par, tresc = lokalizacja.get(kod, (None, ""))

        # zdania z jednostki, ktore odnosza sie do tego znaku
        pasujace = [z for z in zdania(tresc) if kod in z]
        krotki = None
        for z in pasujace:
            if re.search(r"ostrzega|oznacza|zakazuje|nakazuje|informuje|wskazuje|"
                         r"stosuje się|uprzedza|zabrania|dotyczy|określa", z):
                # akt czesto wylicza kilka znakow, a objasnienie stoi po ostatnim
                # cudzyslowie — bierzemy sama czesc objasniajaca
                obciety = re.sub(r"^.*”[,\s]*", "", z).strip()
                krotki = obciety if len(obciety) > 25 else z
                krotki = krotki[0].upper() + krotki[1:] if krotki else krotki
                break
        szczegoly = " ".join(pasujace[:4]) if pasujace else None

        braki = []
        if not nazwa:
            braki.append("nie odnaleziono nazwy w cudzysłowie")
        if not par:
            braki.append("nie ustalono jednostki redakcyjnej")
        if not krotki:
            braki.append("nie wyodrębniono zdania objaśniającego")

        grafika = GRAFIKI / f"{kod}.png"
        rekordy.append({
            "id": kod,
            "code": kod,
            "category_id": seria,
            "category_name": NAZWA_KAT[seria],
            "name": nazwa,
            "short_description": krotki or nazwa,
            "details": szczegoly,
            "image_path": f"img/znaki/{kod}.png" if grafika.exists() else None,
            "keywords": sorted({w.lower() for w in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź]{4,}", nazwa or "")}
                               | {kod.lower(), kod.lower().replace("-", "")}),
            "related_sign_ids": [],
            "legal_basis": {
                **AKT,
                "provision_reference": f"§ {par}" if par else None,
                "source_text": re.sub(r"\s+", " ", tresc).strip()[:1500] or None,
                "verified_at": dzis,
            },
            "verification_status": "verified" if not braki else "partial_verification",
            "verification_note": None if not braki else "; ".join(braki),
        })

    # znaki powiazane: ten sam numer bazowy w serii, np. A-6a/A-6b/A-6c
    grupy: dict[str, list[str]] = {}
    for r in rekordy:
        m = re.match(r"^((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3})", r["code"])
        if m:
            grupy.setdefault(m.group(1), []).append(r["code"])
    for r in rekordy:
        m = re.match(r"^((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3})", r["code"])
        if m:
            r["related_sign_ids"] = [k for k in sorted(grupy[m.group(1)]) if k != r["code"]][:6]
    return rekordy


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    a = p.parse_args()
    if not a.pdf.exists():
        raise SystemExit(f"Nie ma pliku: {a.pdf}")

    tekst = wczytaj_tekst(a.pdf)
    rekordy = zbuduj(tekst)
    WYJSCIE.mkdir(parents=True, exist_ok=True)

    wg_serii: dict[str, list[dict]] = {}
    for r in rekordy:
        wg_serii.setdefault(r["category_id"], []).append(r)

    kategorie = []
    for seria, nazwa, plik in KATEGORIE:
        lista = wg_serii.get(seria, [])
        if not lista:
            continue
        (WYJSCIE / f"{plik}.json").write_text(
            json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        z_grafika = sum(1 for r in lista if r["image_path"])
        kategorie.append({
            "id": seria, "name": nazwa, "file": f"{plik}.json",
            "count": len(lista), "with_image": z_grafika,
            "cover": next((r["code"] for r in lista if r["image_path"]), None),
        })
        print(f"  {seria:2} {nazwa:46} {len(lista):3} znaków, {z_grafika:3} z grafiką")

    dzis = datetime.date.today().isoformat()
    pelne = sum(1 for r in rekordy if r["verification_status"] == "verified")
    (WYJSCIE / "metadata.json").write_text(json.dumps({
        "dataset_name": "Znaki i sygnały drogowe",
        **AKT,
        "source_file": a.pdf.name,
        "imported_at": dzis,
        "categories": kategorie,
        "sign_count": len(rekordy),
        "with_image_count": sum(1 for r in rekordy if r["image_path"]),
        "fully_verified_count": pelne,
        "partially_verified_count": len(rekordy) - pelne,
        "dataset_version": "1.0.0",
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\nZnaków: {len(rekordy)} | z grafiką: {sum(1 for r in rekordy if r['image_path'])} "
          f"| pełna weryfikacja: {pelne}")


if __name__ == "__main__":
    main()
