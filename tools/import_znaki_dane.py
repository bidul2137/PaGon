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
# Ikona kategorii — domyslnie pierwszy znak serii. Tu nadpisujemy tam, gdzie
# pierwszy znak slabo reprezentuje kategorie (A-1 to waski zakret; A-30 "inne
# niebezpieczenstwo" czyta sie od razu jako znak ostrzegawczy).
IKONA_KAT = {"A": "A-30"}
PLIK_KAT = {s: p for s, _, p in KATEGORIE}

RE_KOD = re.compile(r"\b((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3}[a-z]?)\b")
# kod, po ktorym w cudzyslowie stoi nazwa urzedowa
RE_KOD_NAZWA = re.compile(r"\b((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3}[a-z]?)\s*„([^”]{2,300})”")
# Tabliczki serii T akt opisuje inaczej — kod, myslnik i znaczenie, np.
#   „2) T-10 – przeciecie drogi z bocznica kolejowa …;”
# To rownie wiazacy zapis jak nazwa w cudzyslowie, wiec czytamy oba.
RE_KOD_MYSLNIK = re.compile(
    r"\b((?:BT|AT|[ABCDEFGPRSTUW])-\d{1,3}[a-z]?)\s*[–—-]\s*([^;]{5,300}?)(?=;|\s*\d+\)\s*(?:BT|AT|[ABCDEFGPRSTUW])-|\.\s+[A-ZŁŚŻ§])")
RE_PARAGRAF = re.compile(r"§\s*(\d+[a-z]?)\.")
RE_CZASOWNIK = re.compile(
    r"ostrzega|oznacza|zakazuj|nakazuj|informuj|wskazuj|stosuje się|uprzedza|zabrania|"
    r"dotyczy|określa|zobowiązuj|umieszcza się|obowiązuj|zezwala|zwalnia|uprawnia|"
    r"potwierdza|odwołuje|zapowiada|sygnalizuj|wyznacza|wprowadza")


def RE_KOD_W_ZDANIU(kod: str):
    """Kod jako osobny wyraz — zeby T-1 nie trafialo w T-1a."""
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(kod) + r"(?![A-Za-z0-9])")


def wczytaj_tekst(pdf: Path) -> str:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    tekst = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    # PDF przenosi wyrazy miekkim lacznikiem, ktory po ekstrakcji zostaje jako
    # znak zastepczy — "tymczaso\ufffewą" zamiast "tymczasową". Sklejamy takie wyrazy.
    tekst = re.sub(r"[\u00ad\ufffe\ufffd\u200b]\s*", "", tekst)
    return tekst


def jednostki(tekst: str) -> list[tuple[str, str]]:
    """Dzieli akt na jednostki redakcyjne: [(numer_paragrafu, tresc)].

    Tekst z PDF nie ma pewnych podzialow na wiersze, wiec paragrafow szukamy
    w calym strumieniu, a nie tylko na poczatku linii.
    """
    plaski = re.sub(r"\s+", " ", tekst)
    granice = [(m.start(), m.group(1)) for m in re.finditer(r"§\s*(\d+[a-z]?)\.", plaski)]
    if not granice:
        return [("", plaski)]
    czesci = []
    for i, (poz, nr) in enumerate(granice):
        koniec = granice[i + 1][0] if i + 1 < len(granice) else len(plaski)
        czesci.append((nr, plaski[poz:koniec]))
    return czesci


def zdania(tekst: str) -> list[str]:
    t = re.sub(r"\s+", " ", tekst).strip()
    return [z.strip() for z in re.split(r"(?<=[.;])\s+(?=[A-ZŁŚŻŹĆÓĘĄ0-9])", t) if z.strip()]


def zbuduj(tekst: str) -> list[dict]:
    dzis = datetime.date.today().isoformat()
    nazwy: dict[str, str] = {}
    zrodlo_nazwy: dict[str, str] = {}
    for m in RE_KOD_NAZWA.finditer(tekst):
        kod, nazwa = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        if kod not in nazwy:
            nazwy[kod] = nazwa
            zrodlo_nazwy[kod] = "cudzysłów"
    for m in RE_KOD_MYSLNIK.finditer(tekst):
        kod = m.group(1)
        if kod in nazwy:
            continue
        nazwa = re.sub(r"\s+", " ", m.group(2)).strip().rstrip(",;.")
        if 5 <= len(nazwa) <= 300:
            nazwy[kod] = nazwa
            zrodlo_nazwy[kod] = "myślnik"

    # Kod -> (paragraf, tresc). Pierwszenstwo ma jednostka DEFINIUJACA, czyli ta,
    # w ktorej po kodzie stoi nazwa w cudzyslowie. Zwykle wspomnienie kodu w innym
    # paragrafie (odsylacz) daloby opis zupelnie innego znaku.
    lokalizacja: dict[str, tuple[str, str]] = {}
    wspomnienia: dict[str, tuple[str, str]] = {}
    czesci = jednostki(tekst)
    for par, tresc in czesci:
        for m in RE_KOD_NAZWA.finditer(tresc):
            lokalizacja.setdefault(m.group(1), (par, tresc))
    for par, tresc in czesci:
        for m in RE_KOD_MYSLNIK.finditer(tresc):
            lokalizacja.setdefault(m.group(1), (par, tresc))
    for par, tresc in czesci:
        for kod in set(RE_KOD.findall(tresc)):
            wspomnienia.setdefault(kod, (par, tresc))

    wszystkie = sorted(set(RE_KOD.findall(tekst)))
    rekordy = []
    for kod in wszystkie:
        seria = kod.split("-")[0]
        if seria not in NAZWA_KAT:
            continue
        nazwa = nazwy.get(kod)
        par, tresc = lokalizacja.get(kod) or wspomnienia.get(kod, (None, ""))

        # zdania z jednostki, ktore odnosza sie do tego znaku
        wszystkie_zdania = zdania(tresc)
        indeksy = [i for i, z in enumerate(wszystkie_zdania) if RE_KOD_W_ZDANIU(kod).search(z)]
        pasujace = [wszystkie_zdania[i] for i in indeksy]

        krotki = None
        for i in indeksy:
            # akt wylicza znaki, a wspolne objasnienie stoi po ostatniej pozycji —
            # czasem kilka zdan dalej. Szukamy wiec do przodu w tej samej jednostce.
            for j in range(i, min(i + 8, len(wszystkie_zdania))):
                z = wszystkie_zdania[j]
                if j > i:
                    poprz = wszystkie_zdania[j - 1]
                    # przerywamy, gdy poprzednie zdanie nie jest juz pozycja wyliczenia
                    if not (re.match(r"^\s*\d+\)", poprz) or "”" in poprz):
                        break
                if not RE_CZASOWNIK.search(z):
                    continue
                obciety = re.sub(r"^.*”[,;\s]*", "", z).strip()
                obciety = re.sub(r"^\d+\)\s*", "", obciety)
                krotki = obciety if len(obciety) > 25 else z
                krotki = krotki[0].upper() + krotki[1:] if krotki else krotki
                break
            if krotki:
                break
        szczegoly = " ".join(pasujace[:4]) if pasujace else krotki

        if not krotki and nazwa and zrodlo_nazwy.get(kod) == "myślnik":
            krotki = nazwa[0].upper() + nazwa[1:]

        # Rozrozniamy trzy sytuacje:
        #  • akt daje nazwe I objasnienie            -> pelna weryfikacja
        #  • akt daje sama nazwe (np. seria W)       -> pelna, z adnotacja
        #  • akt opisuje znak, ale nie nadaje nazwy  -> pelna, nazwa = null
        # Brakiem jest dopiero sytuacja, gdy nie ma ani nazwy, ani objasnienia.
        braki, uwagi = [], []
        if not par:
            braki.append("nie ustalono jednostki redakcyjnej")
        if not nazwa and not krotki:
            braki.append("akt nie podaje ani nazwy, ani objaśnienia tego znaku")
        elif not nazwa:
            uwagi.append("akt opisuje znak, nie nadając mu nazwy w cudzysłowie")
        elif krotki == nazwa or not krotki:
            uwagi.append("akt podaje samą nazwę znaku, bez odrębnego objaśnienia")

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
            "verification_note": "; ".join(braki + uwagi) or None,
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
            "cover": (IKONA_KAT.get(seria)
                      if any(r["code"] == IKONA_KAT.get(seria) and r["image_path"] for r in lista)
                      else next((r["code"] for r in lista if r["image_path"]), None)),
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
