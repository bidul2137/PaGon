import json
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response, redirect, abort

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
PRZEPISY_JSON = BASE_DIR / "data" / "przepisy.json"
TARYFIKATOR_JSON = BASE_DIR / "data" / "taryfikator.json"
POMOCE_JSON = BASE_DIR / "data" / "pomoce.json"

# Zewnetrzne PDF-y serwowane "inline" (przez wlasny serwer, aby nie wymuszaly pobierania
# i nie byly blokowane naglowkami X-Frame-Options / CORS zrodla).
PDF_ZRODLA = {
    "dowod-osobisty": "https://www.gov.pl/documents/1963407/2777240/weryfikacja_autentycznosci_dowodu_osobistego_25_06_2019.pdf",
    "paszport": "https://www.gov.pl/attachment/f5d4924e-edbf-4f59-a7dd-d503da10af12",
    "prawa-jazdy-ue": "https://op.europa.eu/o/opportal-service/download-handler?identifier=ae58b7c9-4716-46e2-8868-2920735bc95d&format=pdf&language=pl&productionSystem=cellar&part=",
}

# Lokalny cache pobranych PDF-ow (po 1. udanym pobraniu dziala offline i zawsze inline).
PDF_CACHE_DIR = BASE_DIR / "static" / "pdf_cache"


def _pobierz_pdf(url):
    """Pobiera PDF probujac najpierw z weryfikacja SSL, potem bez (typowy problem
    certyfikatow na Windows). Zwraca bajty albo None przy niepowodzeniu."""
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                return resp.read()
        except Exception:
            continue
    return None


def load_przepisy():
    """Wczytuje kategorie i rekordy z pliku JSON (bez bazy danych)."""
    with open(PRZEPISY_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_pomoce():
    """Wczytuje kategorie i linki 'Pomoce / Linki' z pliku JSON."""
    with open(POMOCE_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_taryfikator():
    """Wczytuje kategorie i rekordy taryfikatora z pliku JSON (bez bazy danych)."""
    with open(TARYFIKATOR_JSON, encoding="utf-8") as f:
        return json.load(f)


def find_kategoria(kategorie, slug):
    for kat in kategorie:
        if kat["slug"] == slug:
            return kat
    return None


def szukaj_rekordow(rekordy, query, kategoria_slug=None):
    """Proste wyszukiwanie tekstowe po title / article / keywords."""
    q = query.strip().lower()
    wynik = []
    for r in rekordy:
        if kategoria_slug and r["category"] != kategoria_slug:
            continue
        haystack = " ".join(
            [r.get("title", ""), r.get("article", ""), " ".join(r.get("keywords", []))]
        ).lower()
        if q in haystack:
            wynik.append(r)
    return wynik


@app.route("/")
def index():
    """Ekran glowny (menu) aplikacji PaGon.

    Na tym etapie budujemy wylacznie wyglad i uklad -- dane ponizej
    to placeholdery pod przyszla logike (sesja uzytkownika itp.).
    """
    now = datetime.now()
    context = {
        "data": now.strftime("%d.%m.%Y"),
        "godzina": now.strftime("%H:%M"),
        "uzytkownik": "Funkcjonariusz",
    }
    return render_template("index.html", **context)


@app.route("/przepisy")
def przepisy():
    """Zakladka Przepisy.

    Bez parametrow: ekran kafelkow kategorii.
    ?kategoria=<slug>: lista rekordow przypisanych do kategorii.
    ?q=<fraza>: wyszukiwanie po title / article / keywords
                (opcjonalnie zawezone do wybranej kategorii).
    """
    dane = load_przepisy()
    kategorie = dane["kategorie"]
    rekordy = dane["rekordy"]

    kategoria_slug = request.args.get("kategoria", "").strip() or None
    query = request.args.get("q", "").strip()
    aktualna_kategoria = find_kategoria(kategorie, kategoria_slug) if kategoria_slug else None

    if query:
        wyniki = szukaj_rekordow(rekordy, query, kategoria_slug)
        return render_template(
            "przepisy.html",
            widok="wyszukiwanie",
            kategorie=kategorie,
            kategoria=aktualna_kategoria,
            query=query,
            rekordy=wyniki,
        )

    if kategoria_slug:
        wyniki = [r for r in rekordy if r["category"] == kategoria_slug]
        return render_template(
            "przepisy.html",
            widok="rekordy",
            kategorie=kategorie,
            kategoria=aktualna_kategoria,
            query="",
            rekordy=wyniki,
        )

    return render_template(
        "przepisy.html",
        widok="kafelki",
        kategorie=kategorie,
        kategoria=None,
        query="",
        rekordy=[],
    )


@app.route("/pomoce")
def pomoce():
    """Zakladka Pomoce / Linki.

    Uklad jak w Przepisach: kafelki kategorii, lista linkow w kategorii,
    oraz wyszukiwanie po nazwie / opisie / keywords.
    """
    dane = load_pomoce()
    kategorie = dane["kategorie"]
    linki = dane.get("linki", [])

    kategoria_slug = request.args.get("kategoria", "").strip() or None
    query = request.args.get("q", "").strip()
    aktualna_kategoria = find_kategoria(kategorie, kategoria_slug) if kategoria_slug else None

    def szukaj_linkow(items, q, slug=None):
        ql = q.strip().lower()
        out = []
        for r in items:
            if slug and r.get("category") != slug:
                continue
            hay = " ".join(
                [r.get("title", ""), r.get("description", ""), " ".join(r.get("keywords", []))]
            ).lower()
            if ql in hay:
                out.append(r)
        return out

    if query:
        return render_template(
            "pomoce.html", widok="wyszukiwanie", kategorie=kategorie,
            kategoria=aktualna_kategoria, query=query,
            linki=szukaj_linkow(linki, query, kategoria_slug),
        )

    if kategoria_slug:
        return render_template(
            "pomoce.html", widok="linki", kategorie=kategorie,
            kategoria=aktualna_kategoria, query="",
            linki=[r for r in linki if r.get("category") == kategoria_slug],
        )

    return render_template(
        "pomoce.html", widok="kafelki", kategorie=kategorie,
        kategoria=None, query="", linki=[],
    )


@app.route("/pomoce/pdf/<klucz>")
def pomoce_pdf(klucz):
    """Pobiera zewnetrzny PDF po stronie serwera i podaje go 'inline'.

    Dzieki temu dokument wyswietla sie w przegladarce (a nie pobiera), oraz
    dziala z tego samego origin (brak blokad X-Frame-Options / CORS zrodla).
    Kolejnosc: cache lokalny -> pobranie i zapis do cache -> strona z osadzonym PDF.
    """
    url = PDF_ZRODLA.get(klucz)
    if not url:
        abort(404)

    def inline(dane):
        return Response(
            dane,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{klucz}.pdf"'},
        )

    cache_path = PDF_CACHE_DIR / f"{klucz}.pdf"

    # 1) z lokalnego cache -> dziala offline, zawsze inline
    if cache_path.exists():
        return inline(cache_path.read_bytes())

    # 2) pobierz raz, zapisz do cache, podaj inline
    dane = _pobierz_pdf(url)
    if dane:
        try:
            PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(dane)
        except Exception:
            pass
        return inline(dane)

    # 3) ostatecznosc: osadz PDF w stronie zamiast wymuszac pobieranie
    return Response(
        "<!doctype html><meta charset='utf-8'><title>Podgląd PDF</title>"
        "<style>html,body{margin:0;height:100%;background:#0b132b}</style>"
        f"<object data='{url}' type='application/pdf' width='100%' height='100%'>"
        "<p style='color:#c1cfe6;font-family:sans-serif;padding:20px'>"
        "Nie udało się wyświetlić dokumentu w podglądzie. "
        f"<a style='color:#e0b23a' href='{url}' target='_blank' rel='noopener'>"
        "Otwórz w nowej karcie</a></p></object>",
        mimetype="text/html",
    )


@app.route("/taryfikator")
def taryfikator():
    """Zakladka Taryfikator (mandaty i punkty karne).

    Strona-powloka: dane (kategorie + rekordy) sa wczytywane po stronie
    klienta z /api/taryfikator, a wyszukiwanie / filtrowanie / ulubione
    dzieja sie w calosci w JS (localStorage, bez sesji/logowania).
    """
    dane = load_taryfikator()
    return render_template("taryfikator.html", kategorie=dane["kategorie"])


@app.route("/api/taryfikator")
def api_taryfikator():
    """Zwraca kategorie i rekordy taryfikatora jako JSON dla static/js/taryfikator.js."""
    dane = load_taryfikator()
    return jsonify(dane)


@app.route("/konto")
def konto():
    """Zakladka Twoje konto (profil uzytkownika).

    Widok jest w calosci obslugiwany po stronie klienta (static/js/konto.js,
    stan w localStorage). Bez backendu uwierzytelniania -- akcje demo.
    """
    return render_template("konto.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
