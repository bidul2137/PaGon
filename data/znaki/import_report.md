# Raport importu — Znaki i sygnały drogowe

**Data:** 2026-07-30 · **Wersja:** 1.0.0

## 1. Źródło

- Rozporządzenie Ministrów Infrastruktury oraz Spraw Wewnętrznych i Administracji w sprawie znaków i sygnałów drogowych
- Dz.U. 2019 poz. 2310 z późn. zm. (tekst jednolity)
- plik lokalny: `zrodla/w sprawie ogłoszenia jednolitego tekstu rozporządzenia Ministrów Infrastruktury oraz Spraw Wewnętrznych 31.10.2019r.pdf`

Tekst i grafiki pochodzą z tego samego pliku: treść jako warstwa tekstowa, rysunki jako 26 rastrowych arkuszy zbiorczych w załącznikach. Nic nie pobierano z internetu.

## 2. Przebieg importu

**Dane** — `tools/import_znaki_dane.py`: kod, nazwa z cudzysłowu, zdanie objaśniające, treść jednostki redakcyjnej i numer paragrafu.

**Grafiki** — dwa etapy:

1. `tools/import_znaki_grafiki.py` — sklejenie pionowych wycinków strony, wykrycie siatki, wycięcie komórek, odczyt podpisu (tesseract).

2. `tools/dopasuj_serie.py` — uzupełnienie braków przez dopasowanie komórek **po kolejności**. Arkusz zawiera znaki serii w kolejności z aktu, więc gdy pewne odczyty (kotwice) trafiają we właściwe pozycje listy kodów, resztę można przypisać bez zgadywania. Skrypt szuka przesunięcia, bo arkusz bywa fragmentem serii, i **odmawia zapisu**, gdy kotwice nie potwierdzą kolejności w co najmniej 70 %.

## 3. Liczby
| Miara | Wartość |
|---|---|
| Znaków w bazie | **374** |
| Z grafiką | **280** (75 %) |
| Bez grafiki | 94 |
| Pełna weryfikacja opisu | 236 |
| Częściowa weryfikacja | 138 |
| Grafik odrzuconych (błąd OCR) | 30 |

| Seria | Kategoria | Znaków | Z grafiką |
|---|---|---|---|
| A | Znaki ostrzegawcze | 42 | 42 ✔ |
| B | Znaki zakazu | 46 | 35 |
| C | Znaki nakazu | 21 | 21 ✔ |
| D | Znaki informacyjne | 73 | 46 |
| E | Znaki kierunku i miejscowości | 43 | 19 |
| F | Znaki uzupełniające | 25 | 25 ✔ |
| G | Dodatkowe znaki przed przejazdami kolejowymi | 9 | 9 ✔ |
| P | Znaki poziome | 30 | 30 ✔ |
| S | Sygnały drogowe | 9 | 8 |
| T | Tabliczki do znaków drogowych | 50 | 31 |
| R | Dodatkowe znaki szlaków i tras turystycznych | 10 | 7 |
| BT | Znaki i sygnały dla kierujących tramwajami | 4 | 0 |
| AT | Znaki ostrzegawcze dla kierujących tramwajami | 5 | 0 |
| W | Znaki W | 7 | 7 ✔ |

Komplet grafik: **A, C, F, G, P, W**.

## 4. Kontrola jakości

Każdy kod odczytany z arkusza porównano z listą kodów z tekstu aktu. Pliki o kodzie nieistniejącym w akcie przeniesiono do `static/img/znaki/_do_kontroli/` — nie trafiają do aplikacji.

Serie A, C, F, G, P, W sprawdzone dodatkowo wzrokowo na kontaktówkach: przypisania zgodne ze wzorami.

Dwie grafiki (`C-18`, `C-19`) i `P-11` wciągnęły do kadru własny podpis — obcięte.

## 5. Braki

**94 znaków bez grafiki.**

- **BT (4) i AT (5)** — te serie nie mają rysunków w załączniku; trzeba je dostarczyć osobno.

- **E (24 braki), D (27), T (19), B (11)** — arkusze tych serii zostały odrzucone przez kontrolę kolejności (segmentacja scaliła sąsiednie komórki). Wymagają dopracowania cięcia.

Znaki bez grafiki:

`AT-1`, `AT-2`, `AT-3`, `AT-4`, `AT-5`, `B-34`, `B-35`, `B-36`, `B-37`, `B-38`, `B-39`, `B-40`, `B-41`, `B-42`, `B-43`, `B-44`, `BT-1`, `BT-2`, `BT-3`, `BT-4`, `D-7`, `D-19`, `D-20`, `D-21`, `D-21a`, `D-22`, `D-23`, `D-23a`, `D-24`, `D-25`, `D-30`, `D-32`, `D-33`, `D-34`, `D-34a`, `D-35`, `D-36`, `D-36a`, `D-38`, `D-39`, `D-39a`, `D-40`, `D-41`, `D-42`, `D-43`, `D-44`, `D-45`, `E-1`, `E-1a`, `E-2a`, `E-2b`, `E-2c`, `E-2d`, `E-2e`, `E-6a`, `E-6b`, `E-7`, `E-8`, `E-9`, `E-11`, `E-12`, `E-12a`, `E-14a`, `E-15g`, `E-17a`, `E-18a`, `E-19a`, `E-21`, `E-22a`, `E-22b`, `E-22c`, `R-4a`, `R-4b`, `R-4c`, `S-1a`, `T-1`, `T-1a`, `T-1b`, `T-2`, `T-3`, `T-3a`, `T-7`, `T-17`, `T-23i`, `T-23j`, `T-24`, `T-25a`, `T-27`, `T-29`, `T-30`, `T-31`, `T-32`, `T-33`, `T-34`

## 6. Znane usterki do naprawy

- Część grafik serii **E** ma scalone sąsiednie komórki (np. `E-13` zawiera fragment `E-12a`). Do poprawy przez zawężenie progu odstępu kolumn dla tych arkuszy.

- W tekście jednolitym z 2019 r. znak `P-9` nie ma wariantów literowych; spotykany gdzie indziej `P-9b` pochodzi z innego wydania.

## 7. Powtórzenie
```bash
python tools/import_znaki_grafiki.py --arkusze tools/arkusze_sklejone
python tools/dopasuj_serie.py
python tools/import_znaki_dane.py --pdf "../zrodla/<obwieszczenie>.pdf"
```
