#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buduje baze kodow czynow z zalacznika nr 1 do rozporzadzenia o ewidencji.

ZRODLO
------
Rozporzadzenie Ministra Spraw Wewnetrznych i Administracji z dnia 29 maja 2026 r.
w sprawie ewidencji kierujacych pojazdami naruszajacych przepisy ruchu drogowego
(Dz. U. 2026 poz. 724), obowiazujace od 3 czerwca 2026 r.

To rozporzadzenie UCHYLILO akt z 2023 r. (Dz.U. 2023 poz. 1897) wraz z nowelizacja
z lutego 2026 r. (Dz.U. 2026 poz. 144), wiec jest jedynym wlasciwym zrodlem.
Zalacznik nr 1 istnieje tylko w PDF — wersja HTML aktu odsyla do oryginalu.

CO IMPORTUJEMY, A CZEGO NIE
---------------------------
Z zalacznika: kod czynu, rodzaj naruszenia, kwalifikacja prawna, naruszone
przepisy ruchu drogowego i liczba punktow. Z § 3 rozporzadzenia: warunki
szczegolne (np. przy A 01 punkty tylko za przestepstwo).

KWOT MANDATOW TU NIE MA i nie beda tu kopiowane. Mandat wynika z innego aktu,
a w aplikacji siedzi juz w data/taryfikator.json. Modul laczy jedno z drugim po
kodzie czynu przy wyswietlaniu — dzieki temu kwota istnieje w jednym miejscu
i nie da sie doprowadzic do rozbieznosci miedzy modulami.

UKLAD TABELI
------------
Zalacznik ma dwa rodzaje wierszy:
  1. zwykly    "A 01 <rodzaj> <kwalifikacja> <przepisy p.r.d.> <punkty>"
  2. wariantowy — wspolny naglowek, a pod nim kilka pozycji roznicych sie
     tylko koncowka:  "J 10 – 1 osobe  6" / "J 11 – 2 osoby  7" …
Parser obsluguje oba; wariantom skleja naglowek z trescia wariantu.

UZYCIE
------
    python tools/import_kody_czynow.py
    python tools/import_kody_czynow.py --sprawdz     # bez zapisu
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import unicodedata
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
WYJSCIE = KATALOG / "data" / "kody_czynow"
ZRODLO_TXT = KATALOG.parent / "zrodla" / "DU_2026_724_ewidencja_kierujacych.txt"
RECZNE = WYJSCIE / "uzupelnienia_reczne.json"

WERSJA_ZBIORU = "1.0.0"

AKT = {
    "title": ("Rozporządzenie Ministra Spraw Wewnętrznych i Administracji "
              "z dnia 29 maja 2026 r. w sprawie ewidencji kierujących pojazdami "
              "naruszających przepisy ruchu drogowego"),
    "legal_reference": "Dz. U. 2026 poz. 724",
    "url": "https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260000724",
    "in_force_since": "2026-06-03",
    "annex": "Załącznik nr 1",
}

RE_SEKCJA = re.compile(r"^([A-J])\.\s+(Naruszenia.+)$")
RE_KOD = re.compile(r"\b([A-J])\s(\d{2})\b")
RE_KOD_POCZATEK = re.compile(r"^([A-J]\s\d{2})\s+(.*)$")
RE_WARIANT = re.compile(r"^([A-J]\s\d{2})\s+[–-]\s*(.+?)\s+(\d{1,2})\s*$")
RE_STOPKA = re.compile(r"^Dziennik Ustaw\s+–\s+\d+\s+–\s+Poz\.\s+\d+\s*$")


def bez_ogonkow(t: str) -> str:
    t = (t or "").replace("ł", "l").replace("Ł", "L")
    t = unicodedata.normalize("NFKD", t)
    return "".join(z for z in t if not unicodedata.combining(z)).lower()


def porzadkuj(t: str) -> str:
    """Skleja zawijane wiersze i prostuje odstepy."""
    t = re.sub(r"\s+", " ", t or "").strip()
    return re.sub(r"\s+([,.;:])", r"\1", t)


def wczytaj() -> list[str]:
    if not ZRODLO_TXT.exists():
        raise SystemExit(
            f"Brak pliku źródłowego {ZRODLO_TXT}.\n"
            "Pobierz https://api.sejm.gov.pl/eli/acts/DU/2026/724/text.pdf, "
            "zapisz tekst i spróbuj ponownie.")
    tekst = ZRODLO_TXT.read_text(encoding="utf-8")
    # PDF przenosi wyrazy miekkim lacznikiem, ktory po ekstrakcji zostaje jako
    # znak zastepczy — "przy\ufffeczynilo" zamiast "przyczynilo". Sklejamy takie
    # wyrazy, inaczej w opisach widac kwadraciki w srodku slow.
    tekst = re.sub(r"[\u00ad\ufffe\ufffd\u200b\u200c\u200d]\s*", "", tekst)
    wiersze = tekst.splitlines()
    # stopka „Dziennik Ustaw – 15 – Poz. 724” potrafi wpasc w srodek wiersza tabeli
    return [w for w in wiersze if not RE_STOPKA.match(w.strip())]


def warunki_szczegolne(wiersze: list[str]) -> dict[str, list[str]]:
    """Reguly z § 3 rozporzadzenia, przypisane do kodow, ktorych dotycza.

    Bierzemy je doslownie z aktu — nie streszczamy wlasnymi slowami, bo to
    tresc normatywna, a nie opis.
    """
    tekst = porzadkuj(" ".join(wiersze[:200]))
    wynik: dict[str, list[str]] = {}
    for m in re.finditer(r"(\d+\.\s+(?:Jeżeli|Przepis|Naruszenie)[^§]*?)(?=\s\d+\.\s|\s§)", tekst):
        zdanie = porzadkuj(m.group(1))
        if len(zdanie) < 40:
            continue
        kody = {f"{a} {b}" for a, b in RE_KOD.findall(zdanie)}
        # zakresy typu "od C 06 do C 12" rozwijamy, bo dotycza kazdego kodu z zakresu
        for a, o1, b, o2 in re.findall(r"od ([A-J]) (\d{2}) do ([A-J]) (\d{2})", zdanie):
            if a == b:
                kody |= {f"{a} {n:02d}" for n in range(int(o1), int(o2) + 1)}
        for k in kody:
            wynik.setdefault(k, [])
            if zdanie not in wynik[k]:
                wynik[k].append(zdanie)
    return wynik


def wczytaj_reczne() -> dict:
    """Uzupelnienia wpisane po weryfikacji przez czlowieka.

    Czesci wierszy zalacznika nie da sie odczytac z PDF-a jednoznacznie (scalone
    komorki, kolumny przeniesione na kolejna strone). Zamiast zgadywac, bierzemy
    wartosci potwierdzone przez uzytkownika albo z autorytatywnego taryfikatora
    w aplikacji. Kazdy taki rekord jest oznaczony, wiec widac, ze nie pochodzi
    wprost z odczytu PDF.
    """
    try:
        with open(RECZNE, encoding="utf-8") as f:
            return json.load(f).get("uzupelnienia", {})
    except OSError:
        return {}


def rozdziel_sekcje(wiersze: list[str]) -> list[tuple[str, str, list[str]]]:
    """[(litera, nazwa_sekcji, wiersze)] — tylko część załącznikowa."""
    granice = [(i, m) for i, w in enumerate(wiersze)
               if (m := RE_SEKCJA.match(w.strip()))]
    sekcje = []
    for nr, (i, m) in enumerate(granice):
        koniec = granice[nr + 1][0] if nr + 1 < len(granice) else len(wiersze)
        nazwa = porzadkuj(m.group(2))
        # nazwa sekcji bywa zawijana; sklejamy dalsze wiersze, ale zatrzymujemy sie
        # na naglowku tabeli ("Kod Rodzaj Kwalifikacja prawna …")
        for j in range(i + 1, min(i + 3, koniec)):
            nast = wiersze[j].strip()
            if not nast or RE_KOD_POCZATEK.match(nast) or nast.startswith("Kod"):
                break
            if len(nast) < 90 and not re.match(r"^\d+(\s+\d+)*$", nast):
                nazwa = porzadkuj(nazwa + " " + nast)
        nazwa = re.sub(r"\s*Kod\s+Rodzaj.*$", "", nazwa).strip()
        sekcje.append((m.group(1), nazwa, wiersze[i + 1:koniec]))
    return sekcje


def rozbij_pozycje(tresc: str) -> dict:
    """Dzieli sklejony wiersz tabeli na kolumny.

    Kolejnosc kolumn w zalaczniku: rodzaj naruszenia, kwalifikacja prawna
    (konczy sie skrotem kodeksu), naruszone przepisy ruchu drogowego (p.r.d.),
    liczba punktow. Rozpoznajemy je po skrotach, bo granice kolumn gina przy
    odczycie PDF.
    """
    tresc = porzadkuj(tresc)
    punkty = None
    m = re.search(r"\s(\d{1,2})\s*$", tresc)
    if m:
        punkty = int(m.group(1))
        tresc = tresc[:m.start()].strip()

    # Ogon prawny czytamy jako CALOSC, a dopiero potem dzielimy na kolumny.
    # Proba wycinania kolumn osobnymi wyrazeniami zawodzila, bo jedna komorka
    # potrafi laczyc dwa akty ("§ 109 z.s.d. lub art. 129 … p.r.d."), a czesc
    # kodow w ogole nie ma wlasnej kwalifikacji — dziedziczy ja z naglowka grupy.
    SKROTY = r"k\.k\.|k\.w\.|p\.r\.d\.|z\.s\.d\.|u\.k\.p\."
    ogon = ""
    for m in re.finditer(r"(?:\bart\.|§)", tresc):
        kandydat = tresc[m.start():]
        if re.search(r"(?:%s)\s*$" % SKROTY, kandydat):
            ogon = kandydat
            tresc = tresc[:m.start()].strip()
            break

    if not ogon and re.search(SKROTY, tresc):
        m = re.search(r"(?:\bart\.|§)", tresc)
        if m:
            ogon = tresc[m.start():]
            tresc = tresc[:m.start()].strip()

    kwalifikacja = przepisy = None
    if ogon:
        # kwalifikacja konczy sie na kodeksie; wszystko po niej to przepisy ruchu
        mk = None
        for mm in re.finditer(r"k\.k\.|k\.w\.", ogon):
            mk = mm
        if mk:
            kwalifikacja = porzadkuj(ogon[:mk.end()])
            reszta = porzadkuj(ogon[mk.end():])
            przepisy = reszta or None
        else:
            przepisy = porzadkuj(ogon)

    # Kolumna przepisow konczy sie skrotem aktu. Jesli cos jest za nim, to wyciek
    # z nastepnego wiersza tabeli (odczyt PDF gubi granice komorek) — ucinamy go,
    # bo doklejony fragment cudzego przepisu jest gorszy niz jego brak.
    if przepisy:
        m = re.search(r"^.*?(?:p\.r\.d\.|z\.s\.d\.|k\.w\.|k\.k\.|u\.k\.p\.)", przepisy)
        przepisy = porzadkuj(m.group(0)) if m else None

    return {"rodzaj": porzadkuj(tresc), "kwalifikacja": kwalifikacja,
            "przepisy": przepisy, "punkty": punkty}


def czytaj_sekcje(litera: str, nazwa: str, wiersze: list[str]) -> list[dict]:
    """Zwraca rekordy kodow z jednej sekcji zalacznika."""
    rekordy: list[dict] = []
    naglowek: list[str] = []   # wspolny opis dla pozycji wariantowych
    biezacy: dict | None = None
    bufor: list[str] = []

    def domknij():
        nonlocal biezacy, bufor
        if biezacy is not None:
            biezacy["_tekst"] = " ".join(bufor)
            rekordy.append(biezacy)
        biezacy, bufor = None, []

    for w in wiersze:
        s = w.strip()
        if not s or s.startswith("Kod ") or re.match(r"^\d+(\s+\d+){2,}$", s):
            continue
        mw = RE_WARIANT.match(s)
        if mw:
            # pozycja wariantowa: wspolny naglowek + koncowka + punkty
            domknij()
            rekordy.append({
                "kod": porzadkuj(mw.group(1)),
                "_wariant": porzadkuj(mw.group(2)),
                "_naglowek": porzadkuj(" ".join(naglowek)),
                "_punkty": int(mw.group(3)),
            })
            continue
        # WYCOFANE: traktowanie kazdego wiersza z dwukropkiem jako naglowka grupy
        # wariantow. Podnosilo liczbe w pelni odczytanych rekordow, ale tnie opisy
        # zawijane dwukropkiem ("… przestepstwo z:") i podstawialo BLEDNE punkty
        # w serii E — E 01 dostawal 2 zamiast 15. Bledna wartosc przy kodzie czynu
        # jest grozniejsza niz jej brak, wiec zostaje luka i weryfikacja czesciowa.
        mk = RE_KOD_POCZATEK.match(s)
        if mk:
            domknij()
            naglowek = []
            biezacy = {"kod": porzadkuj(mk.group(1))}
            bufor = [mk.group(2)]
            continue
        if biezacy is not None:
            bufor.append(s)
        else:
            naglowek.append(s)
    domknij()
    return rekordy


def zbuduj() -> tuple[list[dict], list[dict], list[str]]:
    wiersze = wczytaj()
    warunki = warunki_szczegolne(wiersze)
    dzis = datetime.date.today().isoformat()
    kody: list[dict] = []
    kategorie: list[dict] = []
    problemy: list[str] = []

    for litera, nazwa, tresc in rozdziel_sekcje(wiersze):
        surowe = czytaj_sekcje(litera, nazwa, tresc)
        ile = 0
        for r in surowe:
            kod = r["kod"]
            if "_wariant" in r:
                rodzaj = porzadkuj(f'{r["_naglowek"]} {r["_wariant"]}')
                czesci = rozbij_pozycje(r["_naglowek"])
                dane = {"rodzaj": rodzaj, "kwalifikacja": czesci["kwalifikacja"],
                        "przepisy": czesci["przepisy"], "punkty": r["_punkty"]}
            else:
                dane = rozbij_pozycje(r["_tekst"])

            # W zalaczniku kwalifikacja bywa w komorce SCALONEJ obejmujacej kilka
            # kolejnych kodow (np. C 02–C 12 dziela "art. 92 § 1 k.w."). Odczyt PDF
            # gubi scalenie, wiec brakujaca kwalifikacje przejmujemy od poprzedniego
            # kodu tego samego dzialu — ale oznaczamy to w rekordzie, zeby bylo
            # widoczne, ze wynika z ukladu tabeli, a nie z wlasnego wiersza.
            odziedziczona = False
            if not dane["kwalifikacja"] and kody and kody[-1]["category_id"] == litera:
                poprz = kody[-1].get("legal_qualification")
                if poprz:
                    dane["kwalifikacja"] = poprz
                    odziedziczona = True

            # Jesli wiersz nie rozlozyl sie na kolumny, ostatnia liczba w tekscie
            # NIE musi byc liczba punktow — potrafi pochodzic z odsylacza ("§ 2").
            # Tak wlasnie E 01 dostawal 2 zamiast 15. Przy niepelnym odczycie
            # kasujemy wiec punkty zamiast pokazywac wartosc, ktorej nie ufamy.
            if not dane["kwalifikacja"] and not odziedziczona and dane["punkty"] is not None:
                dane["punkty"] = None
                dane["_punkty_odrzucone"] = True

            braki = []
            if dane.get("_punkty_odrzucone"):
                braki.append("liczba punktów odrzucona — wiersz nie rozłożył się na kolumny")
            if not dane["rodzaj"]:
                braki.append("nie odczytano opisu naruszenia")
            if dane["punkty"] is None:
                braki.append("nie odczytano liczby punktów")
            if not dane["kwalifikacja"]:
                braki.append("nie odczytano kwalifikacji prawnej")

            kody.append({
                "id": kod.replace(" ", "-"),
                "code": kod,
                "code_normalized": kod.replace(" ", ""),
                "category_id": litera,
                "category_name": nazwa,
                "title": dane["rodzaj"] or None,
                "points": dane["punkty"],
                "legal_qualification": dane["kwalifikacja"],
                "qualification_from_merged_cell": odziedziczona,
                "violated_traffic_rules": dane["przepisy"],
                "special_conditions": warunki.get(kod, []),
                "keywords": sorted({bez_ogonkow(x) for x in
                                    re.findall(r"\w{4,}", dane["rodzaj"] or "")} |
                                   {kod.replace(" ", "").lower()}),
                "source": {
                    "title": AKT["title"],
                    "legal_reference": AKT["legal_reference"],
                    "provision_reference": f'{AKT["annex"]}, dział {litera}, kod {kod}',
                    "url": AKT["url"],
                    "in_force_since": AKT["in_force_since"],
                    "verified_at": dzis,
                },
                "verification_status": "verified" if not braki else "partial_verification",
                "verification_note": "; ".join(braki) or None,
            })
            ile += 1
            if braki:
                problemy.append(f"{kod}: {'; '.join(braki)}")
        kategorie.append({"id": litera, "name": nazwa, "count": ile})

    # nanosimy uzupelnienia po parsowaniu, zeby bylo widac, co pochodzi z PDF,
    # a co z weryfikacji czlowieka
    reczne = wczytaj_reczne()
    for r in kody:
        u = reczne.get(r["code"])
        if not u:
            continue
        for pole in ("points", "title", "legal_qualification", "violated_traffic_rules"):
            if pole in u:
                r[pole] = u[pole]
        # Czesc kodow nie ma stalej liczby punktow — akt odsyla do innego kodu.
        # To nie brak danych, tylko tresc przepisu, wiec nie liczymy tego jako braku.
        if u.get("points_rule"):
            r["points_rule"] = u["points_rule"]
        r["manual_completion"] = {
            "source": u.get("_z", {}).get("source"),
            "verified_at": u.get("_z", {}).get("date"),
            "conflict_note": u.get("_konflikt"),
        }
        braki = []
        if r["points"] is None and not r.get("points_rule"):
            braki.append("brak liczby punktów")
        if not r["legal_qualification"]:
            braki.append("brak kwalifikacji prawnej")
        r["verification_status"] = "verified" if not braki else "partial_verification"
        r["verification_note"] = "; ".join(braki) or None
        problemy[:] = [p for p in problemy if not p.startswith(r["code"] + ":")]

    kody.sort(key=lambda r: (r["category_id"], int(r["code"].split()[1])))
    return kody, kategorie, problemy


def raport(kody, kategorie, problemy, dzis) -> str:
    pelne = sum(1 for k in kody if k["verification_status"] == "verified")
    bez_pkt = [k["code"] for k in kody if k["points"] is None]
    w = [f"# Raport importu — kody czynów\n",
         f"**Data:** {dzis} · **Wersja zbioru:** {WERSJA_ZBIORU}\n",
         "## 1. Źródło\n",
         f"- **{AKT['title']}**",
         f"- {AKT['legal_reference']}, obowiązuje od {AKT['in_force_since']}",
         f"- {AKT['annex']} — tabela kodów czynów",
         f"- {AKT['url']}\n",
         "Akt ten **uchylił** rozporządzenie z 2023 r. (Dz.U. 2023 poz. 1897) wraz "
         "z nowelizacją z lutego 2026 r. (Dz.U. 2026 poz. 144), więc jest jedynym "
         "obowiązującym źródłem kodów czynów.\n",
         "## 2. Wynik\n", "| Miara | Wartość |", "|---|---|",
         f"| Kodów czynów | **{len(kody)}** |",
         f"| Działów | {len(kategorie)} |",
         f"| Pełna weryfikacja | **{pelne}** |",
         f"| Weryfikacja częściowa | {len(kody) - pelne} |",
         f"| Bez odczytanej liczby punktów | {len(bez_pkt)} |\n",
         "| Dział | Nazwa | Kodów |", "|---|---|---|"]
    for k in kategorie:
        w.append(f"| {k['id']} | {k['name']} | {k['count']} |")
    w.append("\n## 3. Czego tu nie ma\n")
    w.append("**Kwot mandatów.** Wynikają z innego aktu i w aplikacji są już "
             "w `data/taryfikator.json`. Moduł łączy jedno z drugim po kodzie czynu "
             "przy wyświetlaniu, więc kwota istnieje w jednym miejscu i nie da się "
             "doprowadzić do rozbieżności między modułami.\n")
    w.append("Nie każdy kod ma mandat — A 01 to przestępstwo, a nie wykroczenie. "
             "Przy takich kodach moduł nie pokazuje kwoty ani zera, tylko informację "
             "o charakterze czynu.\n")
    if problemy:
        w.append("## 4. Rekordy do sprawdzenia\n")
        for p in problemy[:40]:
            w.append(f"- {p}")
        w.append("")
    w.append("## 5. Powtórzenie\n```bash\npython tools/import_kody_czynow.py\n```\n")
    return "\n".join(w)


def main() -> None:
    ap = argparse.ArgumentParser(description="Importuje kody czynów z załącznika nr 1.")
    ap.add_argument("--sprawdz", action="store_true")
    a = ap.parse_args()

    kody, kategorie, problemy = zbuduj()
    pelne = sum(1 for k in kody if k["verification_status"] == "verified")
    print(f"Kodów czynów: {len(kody)} | działów: {len(kategorie)} | "
          f"pełna weryfikacja: {pelne}")
    for k in kategorie:
        print(f"  {k['id']}  {k['name'][:58]:60} {k['count']:3}")

    if problemy:
        print(f"\nDo sprawdzenia ({len(problemy)}):")
        for p in problemy[:12]:
            print("  -", p)

    if a.sprawdz:
        print("\nTryb sprawdzenia — nic nie zapisano.")
        return

    dzis = datetime.date.today().isoformat()
    WYJSCIE.mkdir(parents=True, exist_ok=True)
    (WYJSCIE / "codes.json").write_text(
        json.dumps(kody, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (WYJSCIE / "categories.json").write_text(
        json.dumps(kategorie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (WYJSCIE / "metadata.json").write_text(json.dumps({
        "dataset_name": "Kody czynów — załącznik nr 1",
        "dataset_version": WERSJA_ZBIORU,
        "source": AKT,
        "coverage": ("Wszystkie kody czynów z załącznika nr 1. Kwoty mandatów nie "
                     "wchodzą w skład tego zbioru — pochodzą z data/taryfikator.json "
                     "i są dołączane po kodzie czynu."),
        "verified_at": dzis,
        "record_count": len(kody),
        "fully_verified_count": pelne,
        "partially_verified_count": len(kody) - pelne,
        "manual_approval_required": True,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (WYJSCIE / "import_report.md").write_text(
        raport(kody, kategorie, problemy, dzis), encoding="utf-8")
    print(f"\nZapisano do {WYJSCIE}")


if __name__ == "__main__":
    main()
