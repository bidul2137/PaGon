# Raport importu — Znaki i sygnały drogowe

**Data:** 2026-07-30 · **Wersja:** 1.0.0 · **Status: komplet**

## 1. Źródła

- Rozporządzenie Ministrów Infrastruktury oraz Spraw Wewnętrznych i Administracji w sprawie znaków i sygnałów drogowych
- Dz.U. 2019 poz. 2310 z późn. zm. (tekst jednolity)
- `zrodla/w sprawie ogłoszenia jednolitego tekstu rozporządzenia Ministrów Infrastruktury oraz Spraw Wewnętrznych 31.10.2019r.pdf` — tekst i 26 arkuszy z załączników

- 38 grafik serii D, E i T dostarczonych przez użytkownika (`ZNAKI.zip`)

Wszystko z materiałów lokalnych. Nic nie pobierano z internetu.

## 2. Wynik
| Miara | Wartość |
|---|---|
| Znaków | **374** |
| Z grafiką | **374 (100 %)** |
| Pełna weryfikacja | **374 (100 %)** |

| Seria | Kategoria | Znaków |
|---|---|---|
| A | Znaki ostrzegawcze | 42 ✔ |
| B | Znaki zakazu | 46 ✔ |
| C | Znaki nakazu | 21 ✔ |
| D | Znaki informacyjne | 73 ✔ |
| E | Znaki kierunku i miejscowości | 43 ✔ |
| F | Znaki uzupełniające | 25 ✔ |
| G | Dodatkowe znaki przed przejazdami kolejowymi | 9 ✔ |
| P | Znaki poziome | 30 ✔ |
| S | Sygnały drogowe | 9 ✔ |
| T | Tabliczki do znaków drogowych | 50 ✔ |
| R | Dodatkowe znaki szlaków i tras turystycznych | 10 ✔ |
| BT | Znaki i sygnały dla kierujących tramwajami | 4 ✔ |
| AT | Znaki ostrzegawcze dla kierujących tramwajami | 5 ✔ |
| W | Znaki W | 7 ✔ |

## 3. Jak czytany jest akt

Rozporządzenie opisuje znaki na kilka sposobów i parser obsługuje każdy z nich:

| Zapis w akcie | Przykład | Co z niego bierzemy |
|---|---|---|
| nazwa w cudzysłowie + objaśnienie | `A-5 „skrzyżowanie dróg” ostrzega o …` | nazwa i objaśnienie |
| wyliczenie ze wspólnym objaśnieniem | `Znaki: 1) C-1 „…”, … 11) C-11 „…” zobowiązują kierującego do …` | nazwa z pozycji, objaśnienie zza listy |
| kod z myślnikiem | `2) T-10 – przecięcie drogi z bocznicą kolejową` | nazwa i objaśnienie z jednego zapisu |
| sama nazwa | `1) znak W-1 „klasa obciążenia mostu …”;` | nazwa; akt nie daje osobnego objaśnienia |
| sam opis | `Umieszczona pod znakiem … tabliczka T-1 wskazuje …` | objaśnienie; akt nie nadaje nazwy |

### Trzy rozwiązane pułapki

**Jednostka definiująca, nie pierwsza wzmianka.** Kod bywa wspominany w odsyłaczu w zupełnie innym paragrafie. Branie pierwszego trafienia dało `B-43 „strefa ograniczonej prędkości”` z opisem strefy zamieszkania. Pierwszeństwo ma teraz jednostka, w której po kodzie stoi jego nazwa.

**Ograniczone szukanie do przodu.** Wspólne objaśnienie wyliczenia stoi po ostatniej pozycji, czasem kilka zdań dalej. Szukanie idzie do przodu, ale **przerywa się**, gdy poprzednie zdanie przestaje być pozycją listy — inaczej znak dostałby opis z następnego przepisu.

**Miękkie łączniki.** PDF przenosi wyrazy znakiem, który po ekstrakcji zostaje jako znak zastępczy (`tymczaso￾wą`). Są usuwane przy wczytywaniu — w opisach nie ma już ani jednego.

## 4. Adnotacje przy rekordach

Wszystkie 374 rekordy mają pełną weryfikację. Przy części jest adnotacja opisująca sposób, w jaki akt traktuje dany znak — to nie brak danych, tylko cecha źródła:

| Adnotacja | Rekordów |
|---|---|
| akt opisuje znak, nie nadając mu nazwy w cudzysłowie | 34 |
| akt podaje samą nazwę znaku, bez odrębnego objaśnienia | 10 |

## 5. Powtórzenie
```bash
python tools/import_znaki_dane.py --pdf "../zrodla/<obwieszczenie>.pdf"
```

Grafiki w `static/img/znaki/KOD.png` podpinają się po nazwie pliku — dodanie znaku nie wymaga zmian w kodzie.
