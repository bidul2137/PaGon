# Raport importu — kody pocztowe

**Data:** 2026-07-30 · **Wersja zbioru:** 1.0.0

## 1. Źródło

- **GeoNames Postal Codes — Poland (PL)** — GeoNames
- Adres: https://download.geonames.org/export/zip/PL.zip
- Licencja: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Plik: `PL.zip` (kopia w `snapshots/`)

## 2. Wynik

| Miara | Wartość |
|---|---|
| Rekordów | **72899** |
| Unikalnych kodów | **20299** |
| Miejscowości | **35332** |
| Pełna weryfikacja | **70675** |
| Weryfikacja częściowa | **2224** |
| Odrzucone wiersze (zły kod lub brak nazwy) | 0 |
| Usunięte pełne duplikaty | 0 |

## 3. Jak czytane jest źródło

GeoNames podaje nazwy jednostek **niekonsekwentnie** — województwa po angielsku (`Lower Silesia`), powiaty raz po polsku (`Powiat bolesławiecki`), raz po angielsku (`Głogów County`). Za to w kolumnach `admin code2` i `admin code3` ma **prawdziwe kody TERYT**, i to one są podstawą importu.

| Pole | Skąd pochodzi |
|---|---|
| województwo | z dwóch pierwszych cyfr kodu TERYT powiatu — nazwa angielska jest ignorowana |
| powiat | nazwa ze źródła bez przedrostka `Powiat`; formy angielskie podmieniane na urzędowe z wykazu GUS |
| gmina | nazwa ze źródła bez przedrostka `Gmina` |
| TERYT | wprost ze źródła, bez uzupełniania |

Miasta na prawach powiatu (kod 61 i wyżej) zostają pod nazwą miasta — tak brzmi ich nazwa urzędowa.

## 4. Kontrole przed zapisem

- kod sprowadzany do `XX-XXX` i trzymany jako **tekst**, żeby nie zgubić wiodącego zera;
- nazwa miejscowości zachowana w oryginale, obok wersja bez polskich znaków do wyszukiwania;
- usuwane są wyłącznie **pełne** duplikaty techniczne — rekordy różniące się gminą zostają;
- kod gminy musi zaczynać się od kodu powiatu, a ten od kodu województwa;
- rozbieżność nie kasuje rekordu, tylko nadaje mu status weryfikacji częściowej z uwagą, którą widać w karcie wyniku.

## 5. Powody weryfikacji częściowej

| Powód | Rekordów |
|---|---|
| źródło podaje nazwę powiatu po angielsku (Konin County); kod TERYT 3010 potwierdzony | 640 |
| źródło podaje nazwę powiatu po angielsku (Radom County); kod TERYT 1425 potwierdzony | 398 |
| źródło podaje nazwę powiatu po angielsku (Łomża County); kod TERYT 2007 potwierdzony | 285 |
| źródło podaje nazwę powiatu po angielsku (Staszów County); kod TERYT 2612 potwierdzony | 204 |
| źródło podaje nazwę powiatu po angielsku (Warsaw West County); kod TERYT 1432 potwierdzony | 169 |
| źródło podaje nazwę powiatu po angielsku (Gdańsk County); kod TERYT 2204 potwierdzony | 168 |
| źródło podaje nazwę powiatu po angielsku (Rzeszów County); kod TERYT 1816 potwierdzony | 130 |
| źródło podaje nazwę powiatu po angielsku (Głubczyce County); kod TERYT 1602 potwierdzony | 107 |
| źródło podaje nazwę powiatu po angielsku (Wodzisław County); kod TERYT 2415 potwierdzony | 70 |
| źródło podaje nazwę powiatu po angielsku (Bielsko-Biała County); kod TERYT 2402 potwierdzony | 52 |
| brak powiatu w źródle; brak gminy w źródle; brak kodu TERYT w źródle | 1 |

## 6. Czego nie ma w bazie

Poczta obsługująca, ulica i zakres numerów są zapisane jako `null` — źródło ich nie zawiera i nie są uzupełniane szacunkami. Kody TERYT województwa, powiatu i gminy są kompletne; identyfikator miejscowości (SIMC) w źródle nie występuje.

## 7. Jak dane leżą na dysku

| Plik | Rola |
|---|---|
| `postal_codes.sqlite` | pełne rekordy i indeks miejscowości, do zapytań i audytu |
| `search_index.json` | lekki indeks dla przeglądarki (~3,5 MB, ~0,7 MB po gzip) |
| `teryt_referencja.json` | wykaz TERYT z GUS użyty do kontroli nazw |
| `snapshots/` | kopia pliku źródłowego z dnia importu |

Pełnych rekordów **nie** trzymamy w JSON — przy 73 tys. pozycji plik miał 44 MB, co obciążałoby repozytorium i pamięć aplikacji przy każdym starcie.

## 8. Powtórzenie

```bash
python tools/import_kody_pocztowe.py --plik ../zrodla/PL.zip
```
