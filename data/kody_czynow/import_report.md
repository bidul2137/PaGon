# Raport importu — kody czynów

**Data:** 2026-08-04 · **Wersja zbioru:** 1.0.0

## 1. Źródło

- **Rozporządzenie Ministra Spraw Wewnętrznych i Administracji z dnia 29 maja 2026 r. w sprawie ewidencji kierujących pojazdami naruszających przepisy ruchu drogowego**
- Dz. U. 2026 poz. 724, obowiązuje od 2026-06-03
- Załącznik nr 1 — tabela kodów czynów
- https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260000724

Akt ten **uchylił** rozporządzenie z 2023 r. (Dz.U. 2023 poz. 1897) wraz z nowelizacją z lutego 2026 r. (Dz.U. 2026 poz. 144), więc jest jedynym obowiązującym źródłem kodów czynów.

## 2. Wynik

| Miara | Wartość |
|---|---|
| Kodów czynów | **133** |
| Działów | 9 |
| Pełna weryfikacja | **133** |
| Weryfikacja częściowa | 0 |
| Bez odczytanej liczby punktów | 3 |

| Dział | Nazwa | Kodów |
|---|---|---|
| A | Naruszenia o charakterze szczególnym | 11 |
| B | Naruszenia polegające na nieprawidłowym zachowaniu się wobec pieszych | 12 |
| C | Naruszenia polegające na niestosowaniu się do znaków i sygnałów drogowych | 20 |
| D | Naruszenia przepisów obowiązujących na skrzyżowaniach lub w innych miejscach przecinania się kierunków ruchu lub toru jazdy pojazdów | 6 |
| E | Naruszenia przepisów dotyczących dopuszczalnej prędkości Przekroczenie dopuszczalnej prędkości: | 11 |
| F | Naruszenia przepisów dotyczących wyprzedzania | 12 |
| G | Naruszenia przepisów dotyczących używania świateł zewnętrznych Niestosowanie się podczas jazdy do obowiązku używania wymaganych przepisami świateł: | 8 |
| H | Naruszenia innych przepisów o bezpieczeństwie lub porządku w ruchu drogowym Naruszenie zakazu cofania: | 29 |
| J | Naruszenia przepisów dotyczących przewożenia osób | 24 |

## 3. Czego tu nie ma

**Kwot mandatów.** Wynikają z innego aktu i w aplikacji są już w `data/taryfikator.json`. Moduł łączy jedno z drugim po kodzie czynu przy wyświetlaniu, więc kwota istnieje w jednym miejscu i nie da się doprowadzić do rozbieżności między modułami.

Nie każdy kod ma mandat — A 01 to przestępstwo, a nie wykroczenie. Przy takich kodach moduł nie pokazuje kwoty ani zera, tylko informację o charakterze czynu.

## 5. Powtórzenie
```bash
python tools/import_kody_czynow.py
```
