#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import Tabeli A ADR 2025 z oficjalnego PDF do data/adr/adr_2025_substances.json.

DLACZEGO TEN SKRYPT ISTNIEJE
----------------------------
Tabela A (dzial 3.2 ADR) zaczyna sie na str. 290 Tomu I i liczy ok. 3000 pozycji
rozlozonych na kilkuset stronach gestych tabel. Podczas budowy modulu nie dalo sie
jej zaimportowac automatycznie (srodowisko bez dostepu do pelnej tresci PDF), wiec
baza w repozytorium jest CZESCIOWA i tak oznaczona w metadanych.

Ten skrypt jest powtarzalna sciezka do pelnej bazy: uruchamiasz go lokalnie, tam
gdzie masz internet i mozesz doinstalowac pdfplumber.

UZYCIE
------
    pip install pdfplumber
    python tools/import_adr_tabela_a.py --pobierz
    python tools/import_adr_tabela_a.py --pdf ADR_tom_I_PL_2025.pdf

Opcje:
    --pobierz          pobiera Tom I PL 2025 z gov.pl do tools/zrodla/
    --pdf SCIEZKA      plik PDF z Tabela A (dzial 3.2)
    --od N --do N      zakres stron (domyslnie wykrywany po naglowku Tabeli A)
    --scal             scala wynik z istniejaca baza zamiast ja nadpisywac
    --wyjscie SCIEZKA  plik docelowy (domyslnie data/adr/adr_2025_substances.json)

Kolumny Tabeli A ADR (dzial 3.2.1):
    (1)  numer UN
    (2)  nazwa i opis
    (3a) klasa
    (3b) kod klasyfikacyjny
    (4)  grupa pakowania
    (5)  nalepki
    (6)  przepisy szczegolne
    (7a) ilosci ograniczone (LQ)
    (7b) ilosci wylaczone (EQ)
    (8)  instrukcje pakowania
    (9a) przepisy szczegolne pakowania
    (9b) przepisy dotyczace pakowania razem
    (10) instrukcje dot. cystern przenosnych
    (11) przepisy szczegolne dot. cystern przenosnych
    (12) kod cysterny ADR
    (13) przepisy szczegolne dot. cystern ADR
    (14) pojazd do przewozu w cysternie
    (15) kategoria transportowa
    (16) przepisy szczegolne dot. przewozu — sztuki przesylki
    (17) przepisy szczegolne dot. przewozu — luzem
    (18) przepisy szczegolne dot. zaladunku, rozladunku i manipulowania
    (19) przepisy szczegolne dot. przewozu — operacje transportowe
    (20) numer rozpoznawczy zagrozenia (kod Kemlera)

UWAGA: numer rozpoznawczy zagrozenia jest w kolumnie (20) i wystepuje tylko przy
pozycjach dopuszczonych do przewozu w cysternie lub luzem. Dla pozostalych zostaje
None — skrypt NIE uzupelnia go domyslami.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
DOMYSLNE_WYJSCIE = KATALOG / "data" / "adr" / "adr_2025_substances.json"
DOMYSLNY_RAPORT = KATALOG / "data" / "adr" / "adr_2025_import_report.md"
METADANE = KATALOG / "data" / "adr" / "adr_2025_metadata.json"

URL_TOM_I = "https://www.gov.pl/attachment/8856b22a-bfd8-4567-8386-b9709bba8da7"
URL_TOM_II = "https://www.gov.pl/attachment/b7292c03-ac9d-4f80-9a29-c22f53d847b8"

ZRODLO = {
    "title": "ADR 2025 — Tabela A, dział 3.2",
    "legal_reference": "Dz.U. 2025 poz. 642",
    "url": "https://eli.gov.pl/eli/DU/2025/642/ogl",
    "adr_version": "ADR 2025",
}

# kolejnosc kolumn Tabeli A -> nazwy pol rekordu
KOLUMNY = [
    "un_number",              # (1)
    "proper_shipping_name_pl",  # (2)
    "adr_class",              # (3a)
    "classification_code",    # (3b)
    "packing_group",          # (4)
    "labels",                 # (5)
    "special_provisions",     # (6)
    "limited_quantities",     # (7a)
    "excepted_quantities",    # (7b)
    "packing_instructions",   # (8)
    "_pak_szczegolne",        # (9a)
    "mixed_packing_provisions",  # (9b)
    "portable_tank_instructions",  # (10)
    "_cyst_przenosne_szcz",   # (11)
    "vehicle_tank_instructions",  # (12)
    "_cyst_adr_szcz",         # (13)
    "_pojazd_cysterna",       # (14)
    "transport_category",     # (15)
    "_przewoz_sztuki",        # (16)
    "_przewoz_luzem",         # (17)
    "_zaladunek",             # (18)
    "_operacje",              # (19)
    "danger_identification_number",  # (20)
]

RE_UN = re.compile(r"^\d{4}$")
RE_KEMLER = re.compile(r"^X?\d{2,3}$")


INSTRUKCJA_RECZNA = """
Pobierz plik ręcznie — to obejdzie problem w kilkanaście sekund:

  1. Otwórz: https://www.gov.pl/web/infrastruktura/towary-niebezpieczne
  2. Sekcja „Przepisy Umowy ADR 2025 r." -> „ADR tom I PL 2025" (6,39 MB)
  3. Zapisz jako: {cel}
  4. Uruchom ponownie z --pdf zamiast --pobierz:

     python tools/import_adr_tabela_a.py --pdf {cel} --sprawdz
"""


def znajdz_pdf_lokalnie() -> list[Path]:
    """Szuka pobranego Tomu I w typowych miejscach.

    Plik z gov.pl nazywa sie 'ADR_tom_I_PL_2025_.pdf' — z podkresleniem na
    koncu — wiec reczne wpisanie sciezki latwo pomylic. Szukamy po wzorcu.
    """
    tutaj = Path(__file__).resolve().parent          # app/tools
    katalogi = [
        tutaj / "zrodla",                            # app/tools/zrodla
        tutaj.parent / "zrodla",                     # app/zrodla
        tutaj.parent.parent / "zrodla",              # PaGon/zrodla  <- katalog źródeł projektu
        tutaj.parent.parent,                         # PaGon/
        Path.cwd(),
        Path.cwd() / "zrodla",
        Path.cwd() / "tools" / "zrodla",
        Path.home() / "Downloads",
        Path.home() / "Pobrane",
        Path.home() / "Desktop",
        Path.home() / "Pulpit",
    ]
    znalezione: list[Path] = []
    for k in katalogi:
        if not k.is_dir():
            continue
        for plik in k.glob("*.pdf"):
            n = plik.name.lower().replace(" ", "_")
            if "adr" not in n:
                continue
            # Tom I, ale nie Tom II
            if re.search(r"tom[_-]?i(?![i])", n) and plik.stat().st_size > 1_000_000:
                if plik not in znalezione:
                    znalezione.append(plik)
    return znalezione


def _kontekst_ssl():
    """Kontekst TLS korzystajacy z magazynu certyfikatow systemu.

    Na komputerach z antywirusem skanujacym HTTPS albo w sieci firmowej ruch
    idzie przez posrednika podmieniajacego certyfikaty. Jego CA jest zaufany
    w Windows, ale Python ma wlasna liste i zwraca CERTIFICATE_VERIFY_FAILED.
    Pakiet truststore podpina magazyn systemowy i problem znika.
    """
    try:
        import truststore
        import ssl

        print("  (używam magazynu certyfikatów systemu — truststore)")
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return None


def pobierz_pdf(url: str, cel: Path) -> Path:
    """Pobiera PDF. Wymaga internetu — uruchamiaj lokalnie, nie na produkcji."""
    import urllib.error
    import urllib.request

    cel.parent.mkdir(parents=True, exist_ok=True)
    print(f"Pobieram {url}\n  -> {cel}")
    try:
        ctx = _kontekst_ssl()
        zadanie = urllib.request.Request(url, headers={"User-Agent": "PaGon-ADR-import/1.0"})
        with urllib.request.urlopen(zadanie, context=ctx) as odp, open(cel, "wb") as f:
            while True:
                kawalek = odp.read(262_144)
                if not kawalek:
                    break
                f.write(kawalek)
    except urllib.error.URLError as e:
        powod = getattr(e, "reason", e)
        if "CERTIFICATE_VERIFY_FAILED" in str(powod):
            raise SystemExit(
                "\nBŁĄD TLS: Python nie ufa certyfikatowi serwera.\n"
                "Najczęstsza przyczyna: antywirus ze skanowaniem HTTPS albo sieć firmowa\n"
                "podmieniająca certyfikaty. Przeglądarka to akceptuje, Python nie.\n\n"
                "Rozwiązanie A (zalecane) — użyj magazynu certyfikatów Windows:\n"
                "    pip install truststore\n"
                "  i uruchom polecenie ponownie.\n"
                + INSTRUKCJA_RECZNA.format(cel=cel)
            )
        raise SystemExit(f"\nBŁĄD pobierania: {powod}\n" + INSTRUKCJA_RECZNA.format(cel=cel))

    rozmiar = cel.stat().st_size
    if rozmiar < 1_000_000:
        raise SystemExit(
            f"\nPobrany plik ma tylko {rozmiar} B — to nie jest Tom I (oczekiwane ok. 6,4 MB).\n"
            "Serwer prawdopodobnie zwrócił stronę błędu."
            + INSTRUKCJA_RECZNA.format(cel=cel)
        )
    print(f"  gotowe, {rozmiar / 1_048_576:.1f} MB")
    return cel


def znajdz_zakres(pdf) -> tuple[int, int]:
    """Wykrywa strony Tabeli A.

    Szuka pierwszej strony, na ktorej sa wiersze zaczynajace sie od 4-cyfrowego
    numeru UN, i ostatniej takiej strony. Naglowek '3.2.1' bywa tylko na
    pierwszej stronie dzialu, wiec samo szukanie naglowka jest zawodne.
    """
    strony_un = []
    for i, strona in enumerate(pdf.pages):
        tekst = strona.extract_text() or ""
        if len(re.findall(r"(?m)^\s*\d{4}\s", tekst)) >= 3:
            strony_un.append(i)
    if not strony_un:
        raise SystemExit(
            "Nie znaleziono stron Tabeli A. Otwórz PDF, sprawdź numery stron działu 3.2.1 "
            "i podaj je ręcznie: --od 290 --do 700"
        )
    # bierzemy najdluzszy ciagly blok stron — to jest Tabela A
    bloki, biezacy = [], [strony_un[0]]
    for a, b in zip(strony_un, strony_un[1:]):
        if b - a <= 2:
            biezacy.append(b)
        else:
            bloki.append(biezacy)
            biezacy = [b]
    bloki.append(biezacy)
    najdluzszy = max(bloki, key=len)
    return najdluzszy[0], najdluzszy[-1] + 1


USTAWIENIA_TABELI = [
    # 1. domyslne — dziala, gdy tabela ma pelna siatke linii
    None,
    # 2. linie pionowe + wykrywanie wierszy po tekscie
    {"vertical_strategy": "lines", "horizontal_strategy": "text"},
    # 3. wszystko po tekscie — ostatnia deska ratunku
    {"vertical_strategy": "text", "horizontal_strategy": "text"},
]


def tabele_ze_strony(strona) -> list:
    """Probuje kolejnych strategii, az ktoras zwroci wiersze z numerem UN."""
    for ust in USTAWIENIA_TABELI:
        try:
            tabele = strona.extract_tables(ust) if ust else strona.extract_tables()
        except Exception:
            continue
        for tab in tabele or []:
            for w in tab:
                if w and w[0] and RE_UN.match(re.sub(r"\s+", "", str(w[0]))):
                    return tabele
    return []


def czysc(v: str | None) -> str | None:
    if v is None:
        return None
    v = re.sub(r"\s+", " ", v.replace("\n", " ")).strip()
    return v or None


def wiersz_na_rekord(kom: list[str | None], dzis: str) -> dict | None:
    un = czysc(kom[0] if kom else None)
    if not un or not RE_UN.match(un):
        return None

    rek: dict = {}
    for idx, pole in enumerate(KOLUMNY):
        wart = czysc(kom[idx]) if idx < len(kom) else None
        if pole.startswith("_"):
            continue
        rek[pole] = wart

    braki: list[str] = []

    din = rek.get("danger_identification_number")
    if din and not RE_KEMLER.match(din):
        braki.append(f"kolumna (20) nie wygląda na numer rozpoznawczy zagrożenia: {din!r}")
        din = None
    rek["danger_identification_number"] = din

    # kolumna (5): numery nalepek rozdzielone "+". Odrzucamy zapisy w nawiasach
    # (np. kody dodatkowe), bo nie sa numerami nalepek.
    etyk = rek.get("labels") or ""
    rek["labels"] = [e.strip() for e in re.split(r"[+/,]", etyk)
                     if e.strip() and re.match(r"^\d", e.strip())]

    # zagrozenia dodatkowe = nalepki inne niz klasa glowna
    kl = rek.get("adr_class")
    rek["subsidiary_risks"] = [e for e in rek["labels"] if kl and not e.startswith(kl)]

    rek["proper_shipping_name_en"] = None
    rek["keywords"] = []
    rek["source"] = dict(ZRODLO, verified_at=dzis)

    puste = [p for p in ("adr_class", "classification_code") if not rek.get(p)]
    if puste:
        braki.append("brak wartości w kolumnach: " + ", ".join(puste))

    rek["verification_status"] = "verified" if not braki else "partial_verification"
    rek["verification_note"] = None if not braki else "; ".join(braki)
    return rek


def importuj(pdf_path: Path, od: int | None, do: int | None) -> tuple[list[dict], list[str]]:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("Brak pdfplumber. Zainstaluj: pip install pdfplumber")

    dzis = datetime.date.today().isoformat()
    rekordy: list[dict] = []
    uwagi: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        if od is None or do is None:
            od, do = znajdz_zakres(pdf)
            print(f"Wykryty zakres Tabeli A: strony {od + 1}–{do}")
        puste_strony = 0
        for nr in range(od, min(do, len(pdf.pages))):
            strona = pdf.pages[nr]
            przed = len(rekordy)
            for tabela in tabele_ze_strony(strona):
                for wiersz in tabela:
                    rek = wiersz_na_rekord(wiersz, dzis)
                    if rek:
                        rekordy.append(rek)
            if len(rekordy) == przed:
                puste_strony += 1
            if (nr - od) % 25 == 0:
                print(f"  strona {nr + 1}: {len(rekordy)} rekordów")
        if puste_strony > (do - od) * 0.5:
            uwagi.append(
                f"Na {puste_strony} z {do - od} stron nie wyodrębniono żadnego wiersza — "
                "sprawdź zakres stron albo uruchom z --sprawdz, żeby zobaczyć surowy odczyt."
            )

    # scalanie wierszy wielolinijkowych o tym samym UN
    scalone: dict[str, dict] = {}
    duplikaty: list[str] = []
    for r in rekordy:
        un = r["un_number"]
        if un in scalone:
            duplikaty.append(un)
            stary = scalone[un]
            for k, v in r.items():
                if not stary.get(k) and v:
                    stary[k] = v
        else:
            scalone[un] = r
    if duplikaty:
        uwagi.append(f"Numery UN występujące w kilku wierszach (scalone): {sorted(set(duplikaty))}")

    for un, r in scalone.items():
        if not RE_UN.match(un):
            uwagi.append(f"UN o nieprawidłowym formacie: {un!r}")
        if not r.get("danger_identification_number"):
            r.setdefault("verification_note", None)

    return sorted(scalone.values(), key=lambda r: r["un_number"]), uwagi


def zapisz(rekordy: list[dict], wyjscie: Path, scal: bool) -> None:
    if scal and wyjscie.exists():
        istniejace = {r["un_number"]: r for r in json.loads(wyjscie.read_text(encoding="utf-8"))}
        for r in rekordy:
            istniejace[r["un_number"]] = r
        rekordy = sorted(istniejace.values(), key=lambda r: r["un_number"])

    wyjscie.parent.mkdir(parents=True, exist_ok=True)
    wyjscie.write_text(json.dumps(rekordy, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if METADANE.exists():
        meta = json.loads(METADANE.read_text(encoding="utf-8"))
        pelne = sum(1 for r in rekordy if r.get("verification_status") == "verified")
        meta.update(
            record_count=len(rekordy),
            fully_verified_count=pelne,
            partially_verified_count=len(rekordy) - pelne,
            downloaded_at=datetime.date.today().isoformat(),
            verified_at=datetime.date.today().isoformat(),
            is_complete=len(rekordy) > 2500,
        )
        METADANE.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Zapisano {len(rekordy)} rekordów do {wyjscie}")


def sprawdz_podglad(pdf_path: Path, od: int | None, do: int | None) -> None:
    """Tryb --sprawdz: pokazuje surowy odczyt kilku stron, nic nie zapisuje.

    Uruchom to NAJPIERW. Jesli w podgladzie widac sensowne wiersze, pelny
    import tez zadziala. Jesli nie — popraw zakres stron.
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Stron w dokumencie: {len(pdf.pages)}")
        if od is None or do is None:
            od, do = znajdz_zakres(pdf)
        print(f"Zakres Tabeli A: strony {od + 1}–{do}  ({do - od} stron)\n")
        pokazane = 0
        for nr in range(od, min(od + 6, do, len(pdf.pages))):
            tabele = tabele_ze_strony(pdf.pages[nr])
            print(f"--- strona {nr + 1}: tabel {len(tabele)} ---")
            for tab in tabele:
                for w in tab:
                    rek = wiersz_na_rekord(w, "podgląd")
                    if rek:
                        print(f"  UN {rek['un_number']} | kl. {rek['adr_class']} | "
                              f"{rek['classification_code']} | GP {rek['packing_group']} | "
                              f"Kemler {rek['danger_identification_number']} | "
                              f"{(rek['proper_shipping_name_pl'] or '')[:52]}")
                        pokazane += 1
                        if pokazane >= 25:
                            print("\n(podgląd ucięty na 25 wierszach)")
                            return
        if not pokazane:
            print("\nNie rozpoznano żadnego wiersza. Spróbuj podać zakres ręcznie:"
                  "\n  python tools/import_adr_tabela_a.py --pdf PLIK --sprawdz --od 290 --do 700")


def kontrola_po_imporcie(rekordy: list[dict]) -> None:
    """Kontrola jakosci wymagana w specyfikacji modulu."""
    print("\n=== KONTROLA JAKOŚCI ===")
    zle_un = [r["un_number"] for r in rekordy if not RE_UN.match(r["un_number"])]
    print(f"UN spoza formatu 4 cyfr: {zle_un or 'brak'}")

    licznik: dict[str, int] = {}
    for r in rekordy:
        licznik[r["un_number"]] = licznik.get(r["un_number"], 0) + 1
    print(f"Duplikaty UN: {[u for u, n in licznik.items() if n > 1] or 'brak'}")

    z_x = [r["un_number"] for r in rekordy
           if (r.get("danger_identification_number") or "").startswith("X")]
    print(f"Kody z literą X (zachowane): {len(z_x)} — np. {z_x[:5]}")

    bez_kemlera = sum(1 for r in rekordy if not r.get("danger_identification_number"))
    print(f"Bez numeru rozpoznawczego zagrożenia (kol. 20 pusta): {bez_kemlera}")

    wzorzec = next((r for r in rekordy if r["un_number"] == "1203"), None)
    print("\nRekord kontrolny UN 1203:")
    if not wzorzec:
        print("  BRAK — import nie objął tej pozycji, sprawdź zakres stron.")
        return
    for pole, oczek in (("adr_class", "3"), ("packing_group", "II"),
                        ("classification_code", "F1"), ("danger_identification_number", "33")):
        mam = wzorzec.get(pole)
        print(f"  {pole:32} = {mam!r:12} (oczekiwane {oczek!r}) "
              f"{'✓' if mam == oczek else '← ROZBIEŻNOŚĆ, opisz ją w raporcie'}")
    print(f"  proper_shipping_name_pl          = {wzorzec.get('proper_shipping_name_pl')!r}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Import Tabeli A ADR 2025 z oficjalnego PDF.",
        epilog="Najpierw uruchom z --sprawdz, potem bez niego.",
    )
    p.add_argument("--pdf", type=Path, help="PDF z Tabelą A (Tom I PL 2025)")
    p.add_argument("--pobierz", action="store_true", help="pobierz Tom I z gov.pl")
    p.add_argument("--sprawdz", action="store_true", help="podgląd odczytu, bez zapisu")
    p.add_argument("--od", type=int, help="pierwsza strona (licząc od 1)")
    p.add_argument("--do", type=int, help="ostatnia strona (licząc od 1)")
    p.add_argument("--scal", action="store_true", help="scal z istniejącą bazą")
    p.add_argument("--wyjscie", type=Path, default=DOMYSLNE_WYJSCIE)
    a = p.parse_args()

    pdf_path = a.pdf
    if a.pobierz:
        pdf_path = pobierz_pdf(URL_TOM_I, Path(__file__).parent / "zrodla" / "ADR_tom_I_PL_2025.pdf")

    if pdf_path and not pdf_path.exists():
        print(f"Nie ma pliku: {pdf_path}")
        pdf_path = None

    # bez --pdf (albo gdy podana sciezka nie istnieje) probujemy znalezc plik sami
    if not pdf_path:
        kandydaci = znajdz_pdf_lokalnie()
        if len(kandydaci) == 1:
            pdf_path = kandydaci[0]
            print(f"Znaleziono Tom I: {pdf_path}  ({pdf_path.stat().st_size / 1_048_576:.1f} MB)\n")
        elif len(kandydaci) > 1:
            print("Znaleziono kilka plików — wskaż jeden przez --pdf:")
            for k in kandydaci:
                print(f"  {k}  ({k.stat().st_size / 1_048_576:.1f} MB)")
            raise SystemExit(1)

    if not pdf_path:
        raise SystemExit(
            "Nie znalazłem pliku „ADR tom I PL 2025”.\n"
            "Szukałem w: tools/zrodla, bieżącym katalogu, Downloads, Pobrane, Desktop, Pulpit.\n"
            + INSTRUKCJA_RECZNA.format(cel=Path(__file__).parent / "zrodla" / "ADR_tom_I_PL_2025.pdf")
            + "\nMożesz też wskazać plik wprost, np.:\n"
            '     python tools/import_adr_tabela_a.py --pdf "%USERPROFILE%\\Downloads\\ADR_tom_I_PL_2025_.pdf" --sprawdz\n'
        )

    od = (a.od - 1) if a.od else None
    do = a.do if a.do else None

    if a.sprawdz:
        sprawdz_podglad(pdf_path, od, do)
        return

    rekordy, uwagi = importuj(pdf_path, od, do)
    if not rekordy:
        raise SystemExit(
            "Nie wyodrębniono żadnego rekordu. Uruchom najpierw:\n"
            f"  python {Path(__file__).name} --pdf {pdf_path} --sprawdz"
        )
    zapisz(rekordy, a.wyjscie, a.scal)
    kontrola_po_imporcie(rekordy)

    for u in uwagi:
        print("\nUWAGA:", u)
    print(f"\nUzupełnij raport ręcznie: {DOMYSLNY_RAPORT}")


if __name__ == "__main__":
    sys.exit(main())
