# Raport importu — kody usterek

Data importu: 2026-08-11

## Źródła

- `zrodla/DU_2024_141_badania_techniczne.pdf` — Dz.U. 2024 poz. 141, obwieszczenie Ministra
  Infrastruktury z 15.11.2023 ogłaszające tekst jednolity rozporządzenia Ministra Transportu,
  Budownictwa i Gospodarki Morskiej z 26.06.2012 (plik dostarczony lokalnie przez użytkownika).
- `zrodla/DU_2024_1811_zmiana.pdf` — Dz.U. 2024 poz. 1811, rozporządzenie Ministra Infrastruktury
  z 26.11.2024, ogłoszone 9.12.2024.
- Kontrolnie: https://api.sejm.gov.pl/eli/acts/DU/2024/141/text.pdf (ELI, Kancelaria Sejmu).

## Stan prawny na dzień importu

Poz. 141 uwzględnia zmiany do Dz.U. 2023 poz. 248 włącznie. Poz. 1811 weszła w życie
**10 grudnia 2024 r.** (§ 3: dzień następujący po ogłoszeniu). Nie odnaleziono późniejszego
tekstu jednolitego tego rozporządzenia.

## Czy Dz.U. 2024 poz. 1811 zmienia załączniki?

**Załącznik nr 1 — tak, ale nie tabelę usterek.** § 1 pkt 4 nowelizacji:

- lit. a — po dziale Ia dodaje **dział Ib** (zakres okresowego badania ciągnika rolniczego
  i gąsienicowego do 40 km/h oraz przyczep do nich). Dział Ib nie tworzy własnych kodów usterek —
  odsyła do tabeli z działu I, **z wyjątkiem pkt 1.1.23. oraz 2.4.**, i modyfikuje metody badania;
- lit. b — zmienia dział II § 1 ust. 5 (dopuszczenie pomiaru opóźnienia hamowania);
- lit. c — zmienia dział III § 6 ust. 1 (pomiar hałasu).

**Załącznik nr 2 — nie.** Nowelizacja go nie dotyka.

**Wniosek:** tabele usterek w dziale I obu załączników mają brzmienie z poz. 141.
Zaimportowane kody i kategorie są aktualne na 10.12.2024.

## Statystyki

| | Załącznik nr 1 | Załącznik nr 2 |
|---|---:|---:|
| Rekordów usterek | 635 | 31 |
| Z kategorią UD | 132 | 0 |
| Z kategorią UP | 579 | 21 |
| Z kategorią UN | 142 | 4 |
| Z wieloma możliwymi kategoriami | 212 | 2 |
| W pełni zweryfikowanych | 634 | 23 |
| Częściowo zweryfikowanych | 1 | 8 |

Działy załącznika nr 1 (0–10) odwzorowane w komplecie; kody usterek unikalne, bez duplikatów.

## Braki i rekordy do ręcznej kontroli

### Załącznik nr 1

- `6.2.11.c` — nie odnaleziono krzyżyka w kolumnie UD/UP/UN; kategoria nieustalona.
- Fragmenty przypisu nr 34 ze strony tytułowej załącznika, które wcześniej wsiąkały
  w nazwy elementów i opisy metod, są usuwane przez `bez_przypisow()`. Po poprawce
  **0 rekordów** ma zanieczyszczoną nazwę działu, elementu ani metody, i żaden z tych
  trzech pól nie jest pusty.

### Załącznik nr 2 — ODRZUCONY, W KWARANTANNIE

**Te dane nie są wyświetlane ani wykorzystywane przez aplikację.**

Plik przeniesiono do `data/kody_usterek/quarantine/additional_inspection.json`.
Nie czyta go żaden endpoint ani szablon; `metadata.json` wykazuje dla załącznika
nr 2 `record_count: 0` i `status: disabled_pending_verification`.

Powód odrzucenia: dział I załącznika nr 2 ma tę samą budowę kolumn co załącznik
nr 1, ale **nie oznacza usterek literami** — część numeruje cyframi, część nie ma
żadnego oznacznika, przez co parser napisany pod załącznik nr 1 dzieli je błędnie.

Stwierdzone wady ekstrakcji:

- 31 rekordów zamiast pełnego wykazu;
- 8 rekordów bez kategorii UD/UP/UN;
- duplikaty kodów `1.1.2.1` oraz `1.2.1`;
- opisy porozrywane na fragmenty (rekord `1.1.1` = „wyrywkowo śrub lub nakrętek.”).

Pliku nie usunięto — służy jako materiał do poprawienia parsera. Ponowne
podłączenie danych wymaga nowego importu, weryfikacji i ręcznej akceptacji.

Dział II załącznika nr 2 (ustalanie danych technicznych) nie jest tabelą usterek
i wymaga osobnej struktury danych.


## Kompletność metadanych rekordu

Każdy rekord ma: kod, kod znormalizowany, numer załącznika, rodzaj badania, dział, element
kontroli, opis usterki, listę dopuszczalnych kategorii, słowa kluczowe, podstawę prawną,
odsyłacz do jednostki redakcyjnej, URL źródła i datę weryfikacji.
