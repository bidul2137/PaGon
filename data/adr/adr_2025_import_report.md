# Raport importu — ADR 2025, Tabela A

**Data importu:** 2026-07-29
**Wersja zbioru:** 1.0.0
**Status:** import **kompletny** — cała Tabela A działu 3.2.1

---

## 1. Źródła

| # | Źródło | Adres | Rola |
|---|---|---|---|
| 1 | API ELI Sejmu — Dz.U. 2025 poz. 642 | `api.sejm.gov.pl/eli/acts/DU/2025/642` | potwierdzenie aktu i statusu `IN_FORCE` |
| 2 | Dz.U. 2025 poz. 642 | `eli.gov.pl/eli/DU/2025/642/ogl` | podstawa prawna w każdym rekordzie |
| 3 | Ministerstwo Infrastruktury | `gov.pl/web/infrastruktura/towary-niebezpieczne` | wykaz oficjalnych plików ADR 2025 PL |
| 4 | **ADR tom I PL 2025** (PDF, 6,39 MB) | `gov.pl/attachment/8856b22a-bfd8-4567-8386-b9709bba8da7` | **źródło importu — dział 3.2.1, Tabela A** |
| 5 | ADR tom II PL 2025 (PDF, 7,50 MB) | `gov.pl/attachment/b7292c03-ac9d-4f80-9a29-c22f53d847b8` | kontrola krzyżowa nazw (tabela 4.1.1.21.6) |
| 6 | UNECE ADR 2025 | `unece.org/adr-2025-files` | **niedostępne** — strona zwróciła pustą treść |

Sprostowanie Dz.U. 2025 poz. 1575 — odnotowane, **nieuwzględnione**.

## 2. Sposób ekstrakcji

Import wykonuje `tools/import_adr_pdf_tekst.py` — czysty Python, **bez zewnętrznych bibliotek**.

Trzy problemy, które trzeba było rozwiązać:

1. **Tabela rozłożona na sąsiadujących stronach.** Polskie wydanie drukuje kolumny (1)–(11)
   na stronie lewej, a (12)–(20) plus powtórzony numer UN i nazwę angielską na prawej.
   Żaden gotowy ekstraktor tabel tego nie skleja. Skrypt paruje strony i łączy wiersze,
   sprawdzając zgodność numeru UN po obu stronach.
2. **Wiersze wielolinijkowe.** Numer UN bywa wyśrodkowany pionowo, a nazwa zaczyna się przy
   górnej krawędzi komórki — grupowanie po współrzędnej Y tekstu rozrywało wiersze.
   Rozwiązanie: wiersz wyznacza **prostokąt przycięcia komórki** (operator `re`), którego
   podstawa i wysokość są wspólne dla całego wiersza.
3. **Dwa sposoby kodowania tekstu.** Większość treści to literały `( … )` w cp1250, ale
   ok. 500 nazw przewozowych zapisano jako ciągi szesnastkowe `<0024><0030>…` w czcionkach
   podzbiorowych. Bez odczytania map **ToUnicode** te nazwy znikały. Skrypt parsuje
   `beginbfchar` / `beginbfrange` każdej czcionki i tłumaczy kody glifów na znaki.

Kolumny przypisywane są po współrzędnej X, według granic odczytanych z nagłówków (1)…(20).

## 3. Statystyki

| Miara | Wartość |
|---|---|
| Stron Tabeli A | 314–620 pliku (154 pary stron) |
| Wierszy Tabeli A | **2938** |
| Pozycji UN po scaleniu wariantów | **2346** |
| Scalonych wariantów (różne grupy pakowania) | 592 |
| Pełna weryfikacja (`verified`) | **2346 (100 %)** |
| Częściowa weryfikacja | **0** |
| Duplikaty numerów UN | 0 |
| Numery UN o złym formacie | 0 |
| Pozycji bez nazwy polskiej | 0 |
| Pozycji bez nazwy angielskiej | 0 |
| Pozycji bez klasy | 0 |
| Kody zagrożenia z literą `X` | 87 |
| Pozycji bez numeru rozpoznawczego zagrożenia | 639 |
| Zakres numerów UN | 0004 – 3559 |
| Rozmiar pliku | 2,4 MB |

Puste kolumny (20) to nie brak danych, tylko pozycje nieprzewożone w cysternie ani luzem —
Tabela A nie przewiduje dla nich numeru rozpoznawczego zagrożenia.

### Podział na klasy

| Klasa | Pozycji | | Klasa | Pozycji |
|---|---|---|---|---|
| 1 — materiały wybuchowe | 378 | | 5.1 — utleniające | 135 |
| 2 — gazy | 237 | | 5.2 — nadtlenki organiczne | 21 |
| 3 — ciecze zapalne | 405 | | 6.1 — trujące | 521 |
| 4.1 — stałe zapalne | 124 | | 6.2 — zakaźne | 5 |
| 4.2 — samozapalne | 77 | | 7 — promieniotwórcze | 25 |
| 4.3 — wydzielające gazy palne z wodą | 88 | | 8 — żrące | 281 |
| | | | 9 — różne | 49 |

## 4. Kontrola jakości

### Rekord kontrolny UN 1203

| Pole | Oczekiwane | W bazie | Zgodność |
|---|---|---|---|
| numer UN | 1203 | `1203` | ✔ |
| nazwa PL | benzyna | `BENZYNA SILNIKOWA lub PALIWO SILNIKOWE` | ✔ |
| nazwa EN | GASOLINE | `MOTOR SPIRIT or GASOLINE or PETROL` | ✔ |
| klasa | 3 | `3` | ✔ |
| grupa pakowania | II | `II` | ✔ |
| kod klasyfikacyjny | F1 | `F1` | ✔ |
| kod zagrożenia | 33 | `33` | ✔ |
| kod tuneli | — | `D/E` | ✔ |
| kategoria transportowa | — | `2` | ✔ |

### Pozycje sprawdzone dodatkowo

| UN | Klasa | Kod klas. | GP | Kemler | Tunele | Nazwa |
|---|---|---|---|---|---|---|
| 1005 | 2 | 2TC | — | 268 | C/D | AMONIAK BEZWODNY |
| 1017 | 2 | 2TOC | — | **265** | C/D | CHLOR |
| 1073 | 2 | 3O | — | 225 | C/E | TLEN SCHŁODZONY SKROPLONY |
| 1202 | 3 | F1 | III | 30 | D/E | OLEJ NAPĘDOWY lub OLEJ GAZOWY lub OLEJ OPAŁOWY LEKKI |
| 1428 | 4.3 | W2 | I | **X423** | B/E | SÓD |
| 1789 | 8 | C1 | II/III | 80 | E | KWAS CHLOROWODOROWY (KWAS SOLNY) |
| 1965 | 2 | 2F | — | 23 | B/D | WĘGLOWODORY GAZOWE, MIESZANINA SKROPLONA I.N.O. |
| 1972 | 2 | 3F | — | 223 | B/D | METAN SCHŁODZONY SKROPLONY lub GAZ ZIEMNY SCHŁODZONY SKROPLONY |
| 3480 | 9 | M4 | — | brak | E | BATERIE LITOWO-JONOWE |

## 5. Rozbieżności wykryte przy imporcie

**UN 1017 (chlor) — kod zagrożenia 265, a nie 268.** Popularne opracowania, w tym polska
Wikipedia, podają dla chloru 268 („gaz trujący i żrący"). ADR 2025 Tabela A podaje **265**
(„gaz trujący, utleniający"). Zachowano wartość ze źródła.

**Progi temperatury zapłonu.** Starsze opracowania opisują kod 30 jako 21–55 °C, a 33 jako
poniżej 21 °C. Obowiązujące ADR używa **23 °C i 60 °C** — słownik kodów w
`adr_2025_danger_codes.json` podaje wartości aktualne.

## 6. Rozbieżności PL ↔ UNECE

**Nie ustalono.** Wersja UNECE ADR 2025 była niedostępna (poz. 6 tabeli źródeł).
Porównanie pozostaje do wykonania.

## 7. Rekordy wymagające kontroli ręcznej

**Brak.** Wszystkie 2346 pozycji przeszły kontrolę automatyczną: numer UN w formacie
czterocyfrowym, brak duplikatów, obecna nazwa polska i angielska, obecna klasa, kod
zagrożenia w formacie `X?\d{2,3}` albo świadomie pusty.

Do rozważenia przy kolejnym wydaniu:

1. porównanie próbki z wersją UNECE ADR 2025;
2. naniesienie sprostowania Dz.U. 2025 poz. 1575;
3. pola kolumn (9a), (11), (13), (14), (16)–(19) są odczytywane, ale nie trafiają do
   rekordu — jeśli będą potrzebne, wystarczy zmienić nazwy w `KOLUMNY_LEWA`/`KOLUMNY_PRAWA`.

## 8. Powtórzenie importu

```bash
python tools/import_adr_pdf_tekst.py --pdf ../zrodla/ADR_tom_I_PL_2025.pdf --sprawdz
python tools/import_adr_pdf_tekst.py --pdf ../zrodla/ADR_tom_I_PL_2025.pdf
```

Skrypt sam wykrywa zakres stron Tabeli A, aktualizuje `adr_2025_metadata.json`
i na koniec wypisuje kontrolę jakości wraz z rekordem kontrolnym UN 1203.
Nie wymaga instalowania niczego poza Pythonem.
