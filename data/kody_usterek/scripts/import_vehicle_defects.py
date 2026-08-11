# -*- coding: utf-8 -*-
"""Importer kodow usterek z rozporzadzenia o badaniach technicznych pojazdow.

Zrodlo: Dz.U. 2024 poz. 141 (tekst jednolity rozporzadzenia z 26.06.2012),
        z uwzglednieniem Dz.U. 2024 poz. 1811.

Tabele obu zalacznikow sa w PDF obrocone o 90 stopni i maja szesc kolumn:
przedmiot i zakres badania | metoda | usterka | UD | UP | UN.
Krzyzyk w jednej z trzech ostatnich kolumn wyznacza kategorie usterki.

Nie parsujemy wierszy tabeli wprost, tylko slowa z ich wspolrzednymi. Powod:
jedna usterka potrafi zajmowac kilka linii, a krzyzyki stoja przy KONKRETNYCH
liniach — dopiero polozenie w pionie mowi, ktory warunek dostaje ktora ocene.
Wiersz tabeli tej informacji nie niesie, bo sklei wszystko w jedna komorke.

Skrypt nic nie zgaduje. Gdy nie potrafi przypisac kategorii, zapisuje rekord
ze statusem partial_verification i wypisuje go w raporcie.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import pdfplumber

KATALOG = Path(__file__).resolve().parent.parent
ZRODLA = KATALOG.parent.parent.parent / "zrodla"
PDF_141 = ZRODLA / "DU_2024_141_badania_techniczne.pdf"
PDF_1811 = ZRODLA / "DU_2024_1811_zmiana.pdf"

# Strony ustalone przez oglegdziny dokumentu (numeracja od 1).
STRONY = {
    1: range(13, 63),   # zalacznik nr 1, dzial I — tabela usterek
    2: range(82, 90),   # zalacznik nr 2, dzial I — tabela usterek
}
# Udzial szerokosci czesci opisowej, na ktorym stoja separatory kolumn 1|2 i 2|3.
# Wartosci sa wzgledne, wiec dzialaja mimo przesuniec ramki na poszczegolnych
# stronach (spotykane odchylki to nawet 30 pkt).
PROPORCJE = {1: (0.182, 0.445), 2: (0.303, 0.624)}

URL_141 = "https://api.sejm.gov.pl/eli/acts/DU/2024/141/text.pdf"
URL_1811 = "https://api.sejm.gov.pl/eli/acts/DU/2024/1811"

KATEGORIE = {
    "UD": (1, "Usterka drobna", "Priorytet 1 — drobna"),
    "UP": (2, "Usterka poważna", "Priorytet 2 — poważna"),
    "UN": (3, "Usterka niebezpieczna", "Priorytet 3 — niebezpieczna"),
}

RE_DZIAL = re.compile(r"^(\d+)\.\s+(.+)$")
RE_POZYCJA = re.compile(r"^(\d+(?:\.\d+)*)\.\s*(.*)$")
RE_LITERA = re.compile(r"^([a-ząćęłńóśżź])\)\s*(.*)$")
# Zalacznik nr 2 numeruje usterki cyframi zamiast liter.
RE_NUMER = re.compile(r"^(\d{1,2})\.\s+(.*)$")


# --------------------------------------------------------------------------
# geometria strony
# --------------------------------------------------------------------------

def klastry(wartosci, prog=12.0):
    """Skleja krawedzie ramki lezace blisko siebie.

    Ramki sa rysowane podwojnie albo potrojnie (obrys + wypelnienie), wiec jedna
    logiczna granica kolumny potrafi dac trzy krawedzie oddalone o 5–6 pkt.
    """
    w = sorted(wartosci)
    if not w:
        return []
    grupy = [[w[0]]]
    for x in w[1:]:
        if x - grupy[-1][-1] <= prog:
            grupy[-1].append(x)
        else:
            grupy.append([x])
    return [sum(g) / len(g) for g in grupy]


def granice_kolumn(strona, zalacznik):
    """Zwraca 7 wspolrzednych x: lewa, sep1, sep2, UD, UP, UN, prawa."""
    kraw = klastry({round(r["x0"], 1) for r in strona.rects}
                   | {round(r["x1"], 1) for r in strona.rects})
    if len(kraw) < 5:
        return None
    ud, up, un, prawa = kraw[-4:]
    lewa = kraw[0]
    szerokosc = ud - lewa
    if szerokosc <= 0:
        return None
    p1, p2 = PROPORCJE[zalacznik]
    sep1 = min(kraw, key=lambda x: abs(x - (lewa + p1 * szerokosc)))
    sep2 = min(kraw, key=lambda x: abs(x - (lewa + p2 * szerokosc)))
    if not (lewa < sep1 < sep2 < ud):
        return None
    return [lewa, sep1, sep2, ud, up, un, prawa]


def linie_strony(strona, granice):
    """Slowa strony zlozone w linie wizualne, z podzialem na kolumny.

    Zwraca liste slownikow: {opis, metoda, usterka, ocena}, gdzie `ocena`
    to 'UD' / 'UP' / 'UN' albo None.
    """
    lewa, sep1, sep2, ud, up, un, prawa = granice
    slowa = strona.extract_words(use_text_flow=False, keep_blank_chars=False)
    # Przypisy i stopka stoja POD tabela, ale w tym samym zakresie x co kolumna
    # metody — bez przyciecia do wysokosci ramki wsiakaja w opis metody kontroli.
    gora = min(r["top"] for r in strona.rects) - 2
    dol = max(r["bottom"] for r in strona.rects) + 2
    # Na pierwszej stronie zalacznika nad tabela stoi jej tytul wraz z odsylaczem
    # do przypisu; oba mieszcza sie w obrysie ramki, wiec samo przyciecie do
    # rects ich nie odsiewa. Gdy strona ma wiersz naglowkowy, zaczynamy pod nim.
    naglowki = [s for s in slowa
                if s["text"].strip() in ("UD", "UP", "UN")
                and (s["x0"] + s["x1"]) / 2 >= ud]
    if naglowki:
        gora = max(gora, max(s["bottom"] for s in naglowki) + 1)
    wiersze = {}
    for s in slowa:
        if not (gora <= s["top"] <= dol):
            continue
        srodek = (s["x0"] + s["x1"]) / 2
        klucz = round(s["top"] / 3.0)          # ~3 pkt tolerancji na te sama linie
        w = wiersze.setdefault(klucz, {"opis": [], "metoda": [], "usterka": [],
                                       "ocena": None, "top": s["top"]})
        if lewa <= srodek < sep1:
            w["opis"].append(s)
        elif sep1 <= srodek < sep2:
            w["metoda"].append(s)
        elif sep2 <= srodek < ud:
            w["usterka"].append(s)
        elif ud <= srodek < prawa and s["text"].strip().upper() == "X":
            w["ocena"] = "UD" if srodek < up else ("UP" if srodek < un else "UN")

    out = []
    for klucz in sorted(wiersze):
        w = wiersze[klucz]
        skl = lambda lst: " ".join(x["text"] for x in sorted(lst, key=lambda y: y["x0"])).strip()
        out.append({"opis": skl(w["opis"]), "metoda": skl(w["metoda"]),
                    "usterka": skl(w["usterka"]), "ocena": w["ocena"], "top": w["top"]})
    return out


# --------------------------------------------------------------------------
# skladanie rekordow
# --------------------------------------------------------------------------

def bez_ogonkow(t):
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def normalizuj_kod(kod):
    """'0.1.a' -> '01A'. Sluzy wyszukiwaniu: '0.1.a', '01a', '0 1 A' to to samo."""
    return re.sub(r"[^A-Za-z0-9]", "", kod).upper()


def slowa_kluczowe(*teksty):
    zbior = set()
    for t in teksty:
        if not t:
            continue
        for w in re.findall(r"[0-9A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź]{3,}", t.lower()):
            zbior.add(bez_ogonkow(w))
    return sorted(zbior)


# UWAGA: kazda alternatywa musi byc zakotwiczona. Samo "\d+" wycinaloby
# rowniez kody pozycji ("0.1. Tablice rejestracyjne"), przez co zaden rekord
# nie dostawalby przypisania do elementu kontroli.
SMIECI_NAGLOWKA = re.compile(
    r"^(?:Dziennik$|Ustaw$|Poz\.\s*\d+\s*$|[–—-]\s*\d+\s*[–—-]$|\d+$|"
    r"(?:\d+\s+)+\d+$|Przedmiot i zakres|Metoda$|Usterki skutkujące|"
    r"Wytyczne dotyczące|U[DPN]$|Tabela:|Dział\b|Załącznik|"
    r"WYMAGANIA DOTYCZĄCE|PODCZAS PRZEPROWADZANIA)", re.I)


# Odsylacze do przypisow ("34) W brzmieniu ustalonym...") stoja na pierwszej
# stronie zalacznika WEWNATRZ ramki, wiec przyciecie po wysokosci ich nie lapie.
# Rozpoznajemy je po numerze z nawiasem zamykajacym — usterki sa oznaczane
# literami, a pozycje cyframi z kropka, wiec kolizji nie ma.
RE_PRZYPIS = re.compile(r"^\d{1,3}\)\s")
RE_CID = re.compile(r"\(cid:\d+\)")


def czysc(linia):
    t = RE_CID.sub("", linia).strip()
    t = re.sub(r"\s{2,}", " ", t)
    if not t or SMIECI_NAGLOWKA.match(t) or RE_PRZYPIS.match(t):
        return ""
    return t


# Przypis nr 34 ze strony tytulowej zalacznika ("W brzmieniu ustalonym przez
# § 1 pkt 4 rozporzadzenia, o ktorym mowa w odnosniku 13.") jest zlozony
# obrocona ramka nad tabela i rozsypuje sie na fragmenty, ktore w kolejnosci
# czytania wpadaja miedzy nazwe pozycji a opis metody. Nie da sie ich odsiac
# geometria, bo leza w tym samym pasie co pierwsze wiersze tabeli — usuwamy je
# wiec po nazwie, na gotowym tekscie. Sa to stale zwroty z tego jednego
# przypisu, wiec nie ma ryzyka, ze zabiora tresc merytoryczna.
FRAGMENTY_PRZYPISU = [
    r"W brzmieniu ustalonym",
    r"przez § 1 pkt \d+ rozporządzenia,? o którym",
    r"o którym mowa w odnośniku \d+\.?",
    r"mowa w odnośniku \d+\.?",
    r"ze zmianami wprowadzonymi",
]
RE_FRAGMENT = re.compile("|".join(FRAGMENTY_PRZYPISU))


def bez_przypisow(tekst):
    if not tekst:
        return tekst
    t = RE_FRAGMENT.sub(" ", tekst)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;.")
    return t or None


# Nazwy trzech podgrup urywaja sie na spojniku, bo ich drugi wiersz przeplata
# sie w kolumnie z wierszami sasiedniej komorki (sklad obrocony o 90 stopni).
# Wartosci ponizej sa odczytane doslownie z tego samego PDF-u przez
# `pdftotext -layout`, ktory te komorki podaje w jednym kawalku — to nie sa
# uzupelnienia z pamieci ani domysly.
UZUPELNIENIA_PODGRUP = {
    "1.1": "Stan techniczny i działanie",
    "4.1": "Światła drogowe i mijania",
    "6.1": "Podwozie lub rama i elementy do nich przymocowane",
}


def zlacz_przenoszenia(tekst):
    """Skleja wyrazy rozdzielone myslnikiem na koncu wiersza PDF.

    Sklad lamie slowa ("hamulco- wego"), a poniewaz czytamy tekst linia po
    linii, myslnik zostaje w srodku zdania. Laczymy tylko male litery po obu
    stronach, wiec nazwy z prawdziwym lacznikiem (bez spacji) sa nietkniete.
    """
    if not tekst:
        return tekst
    return re.sub(r"([a-ząćęłńóśżź])-\s+([a-ząćęłńóśżź])", r"\1\2", tekst)


def rozdziel_uwagi(metoda):
    """Oddziela 'Uwaga:' od opisu metody.

    W tabeli uwaga stoi w tej samej komorce co metoda, ale jest ostrzezeniem
    o innej wadze ("sprawdzac przy wylaczonym silniku") i w interfejsie nalezy
    jej sie osobne miejsce, a nie doklejenie do zdania o metodzie.
    """
    if not metoda:
        return metoda, []
    # UWAGA na regex: "Uwagi?:" to "Uwag" + opcjonalne "i" + ":", wiec
    # NIE dopasowuje slowa "Uwaga:" — a wlasnie ono stoi w tabeli.
    czesci = re.split(r"\bUwag[ai]?:\s*", metoda)
    return (czesci[0].strip(" ,;.") or None,
            [c.strip(" ,;.") for c in czesci[1:] if c.strip(" ,;.")])


class Zbieracz:
    """Skleja linie w rekordy usterek, pilnujac dziedziczenia dzialu i pozycji."""

    def __init__(self, zalacznik):
        self.zal = zalacznik
        # Dzial i pozycja to obiekty wspoldzielone z rekordami, a nie kopie
        # tekstu. Nazwa bywa lamana na kilka linii i doklada sie JUZ PO tym, jak
        # powstal pierwszy rekord danej pozycji — kopia zostawialaby "Tablice"
        # zamiast "Tablice rejestracyjne (jeżeli są wymagane)".
        self.dzial = None
        self.pozycja = None
        self.biezaca = None
        self.rekordy = []
        self.osierocone = []
        self.oczekujace_oceny = []
        # Pozycje posrednie ("1.1. Stan techniczny i działanie") nie maja
        # wlasnych usterek, wiec nie powstaje z nich zaden rekord — a to one
        # niosa nazwe grupy pokazywanej nad lista. Trzymamy je osobno.
        self.wszystkie_pozycje = {}

    @property
    def poz_kod(self):
        return self.pozycja["kod"] if self.pozycja else None

    def zamknij(self):
        if self.biezaca:
            self.rekordy.append(self.biezaca)
            self.biezaca = None

    def nowy_dzial(self, kod, nazwa):
        self.zamknij()
        self.dzial = {"kod": kod, "czesci": [nazwa] if nazwa else []}
        self.pozycja = None

    def nowa_pozycja(self, kod, nazwa):
        self.zamknij()
        self.pozycja = {"kod": kod, "czesci": [nazwa] if nazwa else []}
        self.wszystkie_pozycje[kod] = self.pozycja
        self.oczekujace_oceny = []

    def linia(self, l):
        opis, metoda, usterka, ocena = (czysc(l["opis"]), czysc(l["metoda"]),
                                        czysc(l["usterka"]), l["ocena"])

        # Naglowek dzialu jest wypisany wersalikami W POPRZEK calej tabeli, wiec
        # jego dalszy ciag ("POJAZDU" po "0. IDENTYFIKACJA") siedzi w kolumnie
        # metody albo usterek. Czytanie samej kolumny pierwszej ucinaloby nazwy.
        cala = " ".join(x for x in (opis, metoda, usterka) if x).strip()
        naglowek = RE_POZYCJA.match(cala) if cala else None
        czy_naglowek = bool(
            naglowek and "." not in naglowek.group(1) and naglowek.group(2)
            and naglowek.group(2) == naglowek.group(2).upper()
            and not RE_LITERA.match(usterka or ""))

        if czy_naglowek:
            self.nowy_dzial(naglowek.group(1), naglowek.group(2).strip())
            self.ciag_dzialu = True
            return
        if getattr(self, "ciag_dzialu", False):
            if cala and cala == cala.upper() and not RE_POZYCJA.match(cala):
                self.dzial["czesci"].append(cala)
                return
            self.ciag_dzialu = False

        if opis:
            m = RE_POZYCJA.match(opis)
            if m and "." in m.group(1):
                self.nowa_pozycja(m.group(1), m.group(2))
            elif self.pozycja is not None:
                self.pozycja["czesci"].append(opis)

        if usterka:
            m = RE_LITERA.match(usterka) if self.zal == 1 else RE_NUMER.match(usterka)
            nowa = None
            if m:
                nowa = (m.group(1), m.group(2).strip())
            elif self.zal == 2 and not self.biezaca and self.pozycja is not None:
                # Zalacznik nr 2 czesto nie numeruje usterek — pozycja ma wtedy
                # jedna, nieoznaczona usterke. Nie dorabiamy jej litery.
                # W zalaczniku nr 1 tej sciezki NIE ma: kazda usterka jest tam
                # oznaczona litera, a tekst bez litery to zawijana nazwa pozycji,
                # ktora wystawala do kolumny usterek (np. „układu hamulcowego
                # (jeżeli występuje jako oddzielny układ)” przy pozycji 1.3).
                nowa = (None, usterka)
            if nowa is not None:
                self.zamknij()
                self.biezaca = {
                    "sufiks": nowa[0],
                    "dzial": self.dzial, "pozycja": self.pozycja,
                    "opis": [nowa[1]] if nowa[1] else [],
                    "oceny": list(self.oczekujace_oceny),
                }
                self.oczekujace_oceny = []
            elif self.biezaca:
                self.biezaca["opis"].append(usterka)
            else:
                self.osierocone.append(usterka)

        if ocena:
            # Krzyzyk bywa wysrodkowany w pionie wzgledem swojego wiersza, wiec
            # w kolejnosci czytania potrafi wyprzedzic opis usterki. Gdy nie ma
            # jeszcze otwartej usterki, odkladamy go dla najblizszej nastepnej —
            # inaczej zalacznik nr 2 gubilby prawie wszystkie oceny.
            if self.biezaca:
                self.biezaca["oceny"].append((ocena, usterka or None))
            else:
                self.oczekujace_oceny.append((ocena, usterka or None))


def zbuduj_rekordy(pdf, zalacznik, metadane):
    zb = Zbieracz(zalacznik)
    strony_bez_ramki = []
    for nr in STRONY[zalacznik]:
        strona = pdf.pages[nr - 1]
        gr = granice_kolumn(strona, zalacznik)
        if gr is None:
            strony_bez_ramki.append(nr)
            continue
        for l in linie_strony(strona, gr):
            l["_strona"] = nr
            zb.linia(l)
    zb.zamknij()

    etykieta = ("Okresowe badanie techniczne" if zalacznik == 1
                else "Dodatkowe badanie techniczne")
    typ = "periodic" if zalacznik == 1 else "additional"

    rekordy, niepelne = [], []
    for r in zb.rekordy:
        poz, dz = r["pozycja"], r["dzial"]
        if not poz or not r["opis"]:
            niepelne.append(r)
            continue
        kod = f"{poz['kod']}.{r['sufiks']}" if r["sufiks"] else poz["kod"]
        opis = " ".join(r["opis"]).strip()
        opis = zlacz_przenoszenia(re.sub(r"\s+", " ", opis))

        widziane, opcje = set(), []
        for sev, warunek in r["oceny"]:
            if sev in widziane:
                continue
            widziane.add(sev)
            prio, nazwa, etykieta_prio = KATEGORIE[sev]
            opcje.append({
                "severity_code": sev, "priority": prio,
                "severity_label": nazwa, "priority_label": etykieta_prio,
                "condition": (re.sub(r"\s+", " ", warunek).strip()
                              if warunek and len(r["oceny"]) > 1 else None),
            })
        opcje.sort(key=lambda o: o["priority"])

        status = "verified" if opcje else "partial_verification"
        nota = None if opcje else "Nie odnaleziono krzyżyka w kolumnie UD/UP/UN."

        rekordy.append({
            "id": f"annex-{zalacznik}:{kod}",
            "code": kod,
            "code_normalized": normalizuj_kod(kod),
            "source_annex": zalacznik,
            "test_type": typ,
            "test_type_label": etykieta,
            "section_code": dz["kod"] if dz else None,
            "section_name": bez_przypisow(re.sub(r"\s+", " ", " ".join(dz["czesci"])).strip()) if dz else None,
            "inspection_item_code": poz["kod"],
            "inspection_item_name": zlacz_przenoszenia(
                bez_przypisow(re.sub(r"\s+", " ", " ".join(poz["czesci"])).strip())),
            "inspection_method": None,          # uzupelniane nizej, per pozycja
            "defect": opis,
            "assessment_options": opcje,
            "guidance": None,
            "warnings": [],
            "keywords": slowa_kluczowe(kod, normalizuj_kod(kod), opis,
                                       " ".join(poz["czesci"]),
                                       " ".join(dz["czesci"]) if dz else ""),
            "source": {
                "legal_reference": metadane["podstawa"],
                "annex": zalacznik,
                "provision_reference": (f"Załącznik nr {zalacznik}, dział I, "
                                        f"pozycja {kod}"),
                "official_url": URL_141,
                "verified_at": metadane["data"],
            },
            "verification_status": status,
            "verification_note": nota,
        })
    return rekordy, niepelne, zb.osierocone, strony_bez_ramki, zb.wszystkie_pozycje


def dopisz_metody(pdf, rekordy, zalacznik):
    """Metoda kontroli jest wspolna dla pozycji, wiec zbieramy ja osobno.

    Kolumna 2 tabeli opisuje pozycje (np. 0.1.), a nie pojedyncza usterke —
    czytanie jej razem z wierszem usterki gubiloby fragmenty przy pozycjach
    rozbitych na kilka stron.
    """
    metody = {}
    for nr in STRONY[zalacznik]:
        strona = pdf.pages[nr - 1]
        gr = granice_kolumn(strona, zalacznik)
        if gr is None:
            continue
        biezaca = None
        for l in linie_strony(strona, gr):
            opis = czysc(l["opis"])
            m = RE_POZYCJA.match(opis) if opis else None
            if m and "." in m.group(1):
                biezaca = m.group(1)
            met = czysc(l["metoda"])
            if biezaca and met:
                metody.setdefault(biezaca, []).append(met)
    for r in rekordy:
        tekst = " ".join(metody.get(r["inspection_item_code"], [])).strip()
        czysta = zlacz_przenoszenia(bez_przypisow(re.sub(r"\s+", " ", tekst)))
        r["inspection_method"], r["warnings"] = rozdziel_uwagi(czysta)
    return metody


# --------------------------------------------------------------------------

def main():
    if not PDF_141.exists():
        sys.exit(f"Brak pliku zrodlowego: {PDF_141}")

    dzis = date.today().isoformat()
    metadane = {
        "podstawa": "Dz.U. 2024 poz. 141 ze zmianą Dz.U. 2024 poz. 1811",
        "data": dzis,
    }

    pdf = pdfplumber.open(PDF_141)
    raport = []
    wszystkie = {}
    elementy = {}
    for zal in (1, 2):
        rek, niepelne, osierocone, bez_ramki, pozycje = zbuduj_rekordy(pdf, zal, metadane)
        dopisz_metody(pdf, rek, zal)
        wszystkie[zal] = rek
        elementy[zal] = {
            k: (UZUPELNIENIA_PODGRUP[k]
                if zal == 1 and k in UZUPELNIENIA_PODGRUP
                else zlacz_przenoszenia(bez_przypisow(
                    re.sub(r"\s+", " ", " ".join(v["czesci"])).strip())))
            for k, v in pozycje.items()}
        raport.append({
            "zalacznik": zal, "rekordow": len(rek),
            "niepelnych": len(niepelne), "osieroconych_linii": len(osierocone),
            "strony_bez_ramki": bez_ramki,
            "bez_kategorii": [r["code"] for r in rek if not r["assessment_options"]],
            "wiele_kategorii": [r["code"] for r in rek if len(r["assessment_options"]) > 1],
            "wg_kategorii": {
                k: sum(1 for r in rek
                       if any(o["severity_code"] == k for o in r["assessment_options"]))
                for k in ("UD", "UP", "UN")
            },
        })

    KATALOG.mkdir(parents=True, exist_ok=True)
    (KATALOG / "periodic_defects.json").write_text(
        json.dumps({"records": wszystkie[1]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (KATALOG / "additional_inspection.json").write_text(
        json.dumps({"records": wszystkie[2]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (KATALOG / "inspection_items.json").write_text(json.dumps(
        {"annex_1": elementy[1], "annex_2": elementy[2]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    (KATALOG / "categories.json").write_text(json.dumps({
        "categories": [
            {"severity_code": k, "priority": v[0], "severity_label": v[1],
             "priority_label": v[2], "definition": d}
            for k, (v, d) in zip(
                ("UD", "UP", "UN"),
                [(KATEGORIE["UD"], "Usterki niemające istotnego wpływu na bezpieczeństwo "
                  "ruchu drogowego i ochrony środowiska, które nie powodują ograniczenia "
                  "w dalszym używaniu pojazdu."),
                 (KATEGORIE["UP"], "Usterki mogące zagrażać bezpieczeństwu ruchu drogowego "
                  "lub naruszać wymagania ochrony środowiska albo inne istotne "
                  "nieprawidłowości, które dają podstawę do ograniczenia dalszego używania "
                  "pojazdu oraz określenia warunków tego używania."),
                 (KATEGORIE["UN"], "Usterki powodujące bezpośrednie zagrożenie dla "
                  "bezpieczeństwa ruchu drogowego lub naruszające wymagania ochrony "
                  "środowiska, w stopniu uniemożliwiającym używanie pojazdu w ruchu "
                  "drogowym, które powodują niedopuszczenie do dalszego używania pojazdu.")])
        ],
        "source": {"legal_reference": metadane["podstawa"],
                   "provision_reference": "§ 2 ust. 4 rozporządzenia",
                   "official_url": URL_141, "verified_at": dzis},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
