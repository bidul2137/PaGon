# Raport importu — Znaki i sygnały drogowe

**Data:** 2026-07-30 · **Wersja:** 1.0.0 · **Status: komplet**

## 1. Źródła

- Rozporządzenie Ministrów Infrastruktury oraz Spraw Wewnętrznych i Administracji w sprawie znaków i sygnałów drogowych
- Dz.U. 2019 poz. 2310 z późn. zm. (tekst jednolity)
- `zrodla/w sprawie ogłoszenia jednolitego tekstu rozporządzenia Ministrów Infrastruktury oraz Spraw Wewnętrznych 31.10.2019r.pdf` — tekst i 26 rastrowych arkuszy z załączników

- 38 grafik serii D, E i T dostarczonych przez użytkownika (`ZNAKI.zip`), po jednej na kod

## 2. Przebieg

**Dane** — `tools/import_znaki_dane.py`: kod, nazwa z cudzysłowu, zdanie objaśniające, treść jednostki redakcyjnej, numer paragrafu. Nic dopisanego od siebie.

**Grafiki** — cztery narzędzia, w kolejności użycia:

1. `import_znaki_grafiki.py` — sklejenie pionowych wycinków strony, wykrycie siatki, wycięcie komórek, OCR podpisu.

2. `dopasuj_serie.py` — dopasowanie po kolejności z przesunięciem, gdy arkusz jest fragmentem serii.

3. `domknij_serie.py` — interpolacja między kotwicami OCR; luka wypełniana tylko przy zgodnej liczbie komórek.

4. `przypisz_wprost.py` — jawne przypisanie dla arkuszy, na których OCR zawodzi (inny krój podpisu), z twardym warunkiem zgodności liczb.

Braki, których nie dało się odczytać z arkuszy, uzupełniono plikami z `ZNAKI.zip`.

## 3. Liczby
| Miara | Wartość |
|---|---|
| Znaków w bazie | **374** |
| Z grafiką | **374 (100 %)** |
| Pełna weryfikacja opisu | 236 |
| Częściowa weryfikacja opisu | 138 |
| Grafik odrzuconych przez kontrolę kodu | 30 |

| Seria | Kategoria | Znaków | Z grafiką |
|---|---|---|---|
| A | Znaki ostrzegawcze | 42 | 42 ✔ |
| B | Znaki zakazu | 46 | 46 ✔ |
| C | Znaki nakazu | 21 | 21 ✔ |
| D | Znaki informacyjne | 73 | 73 ✔ |
| E | Znaki kierunku i miejscowości | 43 | 43 ✔ |
| F | Znaki uzupełniające | 25 | 25 ✔ |
| G | Dodatkowe znaki przed przejazdami kolejowymi | 9 | 9 ✔ |
| P | Znaki poziome | 30 | 30 ✔ |
| S | Sygnały drogowe | 9 | 9 ✔ |
| T | Tabliczki do znaków drogowych | 50 | 50 ✔ |
| R | Dodatkowe znaki szlaków i tras turystycznych | 10 | 10 ✔ |
| BT | Znaki i sygnały dla kierujących tramwajami | 4 | 4 ✔ |
| AT | Znaki ostrzegawcze dla kierujących tramwajami | 5 | 5 ✔ |
| W | Znaki W | 7 | 7 ✔ |

## 4. Kontrola jakości

- każdy kod odczytany z arkusza porównany z listą kodów z tekstu aktu; niepasujące pliki trafiły do `static/img/znaki/_do_kontroli/` (30 szt.) i nie są używane;

- serie A, B, C, F, G, P, R, S, W, AT, BT oraz komplet z `ZNAKI.zip` sprawdzone wzrokowo na kontaktówkach — przypisania zgodne ze wzorami;

- grafiki, które wciągnęły do kadru własny podpis (`C-18`, `C-19`, `P-11`, część serii B), obcięte;

- routing: kody mają mieszaną wielkość liter (`A-11a`), więc wyszukiwanie znaku działa zarówno na dopasowaniu dokładnym, jak i bez względu na wielkość liter — sprawdzone na wszystkich 374.

## 5. Opisy do uzupełnienia (138)

Rekordy, w których nie udało się wyodrębnić z aktu zdania objaśniającego albo jednostki redakcyjnej. Mają nazwę urzędową i grafikę, brakuje im pełnego opisu:

`B-43`, `C-11`, `C-16`, `C-2`, `C-3`, `C-4`, `C-5`, `C-6`, `C-7`, `C-8`, `C-9`, `D-18`, `D-18a`, `D-18b`, `D-21`, `D-21a`, `D-22`, `D-23a`, `D-24`, `D-26a`, `D-26b`, `D-26d`, `D-27`, `D-28`, `D-29`, `D-30`, `D-31`, `D-32`, `D-33`, `D-35`, `D-35a`, `D-36`, `D-36a`, `D-38`, `D-44`, `D-51`, `D-51a`, `D-51b`, `E-10`, `E-11`, `E-12`, `E-12a`, `E-14`, `E-14a`, `E-16`, `E-7`, `E-8`, `E-9`, `F-12`, `F-13`, `F-14a`, `F-14b`, `F-14c`, `F-4`, `G-1a`, `G-1b`, `G-1c`, `G-1d`, `G-1e`, `G-1f`, `G-3`, `G-4`, `P-15`, `P-16`, `P-17`, `P-18`, `P-19`, `P-20`, `S-1`, `S-1a`, `S-2`, `S-3`, `S-3a`, `S-4`, `S-5`, `S-6`, `S-7`, `T-1`, `T-10`, `T-11`, `T-12`, `T-13`, `T-14`, `T-15`, `T-16`, `T-17`, `T-18`, `T-19`, `T-1a`, `T-1b`, `T-2`, `T-20`, `T-21`, `T-23a`, `T-23b`, `T-23c`, `T-23d`, `T-23e`, `T-23f`, `T-23g`, `T-23h`, `T-23i`, `T-23j`, `T-24`, `T-25a`, `T-25b`, `T-25c`, `T-26`, `T-27`, `T-28`, `T-29`, `T-3`, `T-30`, `T-31`, `T-32`, `T-33`, `T-34`, `T-3a`, `T-4`, `T-5`, `T-6a`, `T-6b`, `T-6c`, `T-6d`, `T-7`, `T-8`, `T-9`, `R-4c`, `R-4d`, `R-4e`, `BT-2`, `W-1`, `W-2`, `W-3`, `W-4`, `W-5`, `W-6`, `W-7`

## 6. Powtórzenie importu
```bash
python tools/import_znaki_dane.py --pdf "../zrodla/<obwieszczenie>.pdf"
```

Grafiki leżą w `static/img/znaki/KOD.png` i podpinają się po nazwie pliku — dorzucenie nowego znaku nie wymaga zmian w kodzie.
