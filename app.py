import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
PRZEPISY_JSON = BASE_DIR / "data" / "przepisy.json"
TARYFIKATOR_JSON = BASE_DIR / "data" / "taryfikator.json"


def load_przepisy():
    """Wczytuje kategorie i rekordy z pliku JSON (bez bazy danych)."""
    with open(PRZEPISY_JSON, encoding="utf-8") as f:
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
