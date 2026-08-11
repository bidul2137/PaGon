# PaGon

Aplikacja webowa (PWA w budowie) dla policjantów: przepisy, procedury, taryfikator,
znaki drogowe, tablice ADR, kody pocztowe, kody czynów i kody usterek badania
technicznego. Flask + Jinja2, bez bazy danych po stronie serwera — dane leżą
w plikach JSON w `data/`.

## Wymagania

- Python 3.10 lub nowszy
- `pip`
- Do importerów danych dodatkowo: systemowy **Tesseract OCR** (kontrola grafik
  znaków) i **poppler-utils** (`pdftotext`, `pdfimages` przy imporcie z PDF)

## Instalacja

```bash
cd app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Sam serwer potrzebuje wyłącznie sekcji „aplikacja" z `requirements.txt`.
Reszta pakietów jest wymagana tylko przy ręcznym uruchamianiu importerów.

## Uruchomienie lokalne

```bash
cp .env.example .env             # opcjonalnie, wartości domyślne są bezpieczne
python app.py
```

Domyślnie serwer nasłuchuje na `127.0.0.1:5000`, **bez debuggera**.

Zmienne środowiskowe:

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `PAGON_DEBUG` | `0` | `1` włącza debugger Werkzeuga |
| `PAGON_HOST` | `127.0.0.1` | interfejs nasłuchu |
| `PAGON_PORT` | `5000` | port |

**Debugger daje dostęp do interaktywnej konsoli Pythona.** Nie uruchamiaj go
razem z `PAGON_HOST=0.0.0.0`. Żeby obejrzeć aplikację na telefonie w tej samej
sieci, ustaw wyłącznie host:

```bash
PAGON_HOST=0.0.0.0 python app.py
```

## Testy

```bash
python -m unittest discover -s tests -p "test_*.py" -v   # testy Pythona
node tests/kalkulator.test.js                            # testy JS
```

Testy bezpieczeństwa (`tests/test_bezpieczenstwo.py`) sprawdzają konfigurację
uruchomienia, weryfikację TLS przy pobieraniu dokumentów, limit czasu, nagłówki
cache oraz to, że dane w kwarantannie nie trafiają do żadnego endpointu.
Działają bez zainstalowanego Flaska — analizują kod źródłowy i pliki danych.

## Gdzie leżą dane

| Katalog | Zawartość |
|---|---|
| `data/przepisy.json`, `data/taryfikator.json` | przepisy i taryfikator mandatów |
| `data/znaki/` | znaki drogowe (JSON na serię) + grafiki w `static/` |
| `data/adr/` | ADR 2025: substancje i kody zagrożenia |
| `data/kody_pocztowe/` | indeks wyszukiwania; baza SQLite **nie jest w repozytorium** |
| `data/kody_czynow/` | kody czynów z taryfikatora punktowego |
| `data/kody_usterek/` | usterki badania technicznego, załącznik nr 1 |
| `data/kody_usterek/quarantine/` | dane odrzucone przez weryfikację, poza repozytorium |
| `tools/`, `data/*/scripts/` | importery uruchamiane ręcznie |

Kilka rzeczy jest celowo poza repozytorium i trzeba je odtworzyć lokalnie:

- `data/kody_pocztowe/postal_codes.sqlite` (16 MB) — powstaje z importera
  `tools/import_kody_pocztowe.py` na podstawie zbioru GeoNames (CC BY 4.0);
- `static/pdf_cache/` — dokumenty pobierane z oficjalnych źródeł przy pierwszym
  otwarciu kafelka.

## Zasada aktualizacji danych prawnych

**Żadna aktualizacja danych prawnych nie wchodzi do aplikacji automatycznie.**

1. Importer czyta wyłącznie oficjalne źródło (ISAP, ELI, Dziennik Ustaw,
   serwisy administracji) albo plik dostarczony ręcznie do `zrodla/`.
2. Importer nigdy nie uzupełnia braków domysłem. Czego nie da się potwierdzić
   w źródle, zapisuje jako `null` i oznacza `verification_status`
   jako `partial_verification` wraz z powodem.
3. Każdy rekord niesie podstawę prawną, jednostkę redakcyjną, adres źródła
   i datę weryfikacji.
4. Wynik importu opisuje `import_report.md` w katalogu danych: liczby rekordów,
   rozbieżności i lista pozycji do ręcznego sprawdzenia.
5. `metadata.json` ma `manual_approval_required: true`, dopóki zbiór nie zostanie
   przejrzany przez człowieka. Zbiory oznaczone jako `draft` albo
   `disabled_pending_verification` nie są serwowane użytkownikowi.
6. Dane, które nie przeszły weryfikacji, trafiają do `quarantine/` — nie są
   kasowane, ale też nie są wykorzystywane przez aplikację.

Informacje w aplikacji mają charakter pomocniczy. Ostateczna kwalifikacja prawna
należy do funkcjonariusza, a ocena stanu technicznego pojazdu — do uprawnionego
diagnosty.
