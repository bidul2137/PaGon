import json
import re
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response, redirect, abort, url_for

app = Flask(__name__)

# W trybie dev nie cache'ujemy plikow statycznych, a do URL-i CSS/JS doklejamy
# znacznik czasu modyfikacji (static_v) -- dzieki temu po kazdej zmianie przegladarka
# (takze na telefonie) pobiera swieza wersje, bez recznego czyszczenia cache.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.context_processor
def _inject_static_v():
    def static_v(filename):
        try:
            wersja = int((Path(app.static_folder) / filename).stat().st_mtime)
        except OSError:
            wersja = 0
        return url_for("static", filename=filename, v=wersja)

    return {"static_v": static_v}

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


KATEGORIE_PJ_JSON = BASE_DIR / "data" / "kategorie_prawa_jazdy.json"


def load_kategorie_pj():
    """Kategorie prawa jazdy (art. 6 i 8 ustawy o kierujacych pojazdami)."""
    with open(KATEGORIE_PJ_JSON, encoding="utf-8") as f:
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
        "nowosci_unread": True,
    }
    return render_template("index.html", **context)


@app.route("/nowosci")
def nowosci():
    """Nowosci -- zmiany w prawie i aktualizacje aplikacji (placeholder)."""
    return render_template("nowosci.html")


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

    # liczba rekordow na kategorie — kafelek bez rekordow, ale z PDF-em,
    # prowadzi bezposrednio do dokumentu (bez pustej strony posredniej)
    liczniki = {}
    for r in rekordy:
        liczniki[r["category"]] = liczniki.get(r["category"], 0) + 1

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
        liczniki=liczniki,
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

    def bez_ogonkow(s):
        tab = str.maketrans("ąćęłńóśżź", "acelnoszz")
        return s.lower().translate(tab)

    def szukaj_linkow(items, q, slug=None):
        ql = bez_ogonkow(q.strip())
        out = []
        for r in items:
            if slug and r.get("category") != slug:
                continue
            hay = bez_ogonkow(" ".join([
                r.get("title", ""), r.get("description", ""),
                r.get("tag", ""), r.get("article", ""), r.get("summary", ""),
                r.get("effect", ""), " ".join(r.get("keywords", [])),
            ]))
            # krotkie zapytania (np. "uk", "zea") dopasowujemy jako cale slowo,
            # zeby nie trafialy w srodek innych wyrazow (Luksemburg, zealand)
            if len(ql) <= 3:
                trafienie = re.search(r"(?<![0-9a-z])" + re.escape(ql) + r"(?![0-9a-z])", hay) is not None
            else:
                trafienie = ql in hay
            if trafienie:
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


@app.route("/pomoce/kategorie-prawa-jazdy")
def kategorie_prawa_jazdy():
    """Podstrona 'Kategorie prawa jazdy' — karty kategorii + szczegoly.

    Dane pochodza wylacznie z ustawy o kierujacych pojazdami (art. 6 i art. 8).
    """
    dane = load_kategorie_pj()
    with open(BASE_DIR / "data" / "kody_prawa_jazdy.json", encoding="utf-8") as f:
        kody = json.load(f).get("kody", {})
    return render_template(
        "kategorie_prawa_jazdy.html",
        kategorie=dane["kategorie"],
        zrodlo=dane.get("_zrodlo", ""),
        kody=kody,
    )


@app.route("/pomoce/spb")
def pomoce_spb():
    """Hub 'Wszystko o ŚPB' — podstrona z kafelkami tematów ŚPB."""
    dane = load_pomoce()
    podkafelki = [k for k in dane["kategorie"] if k.get("grupa") == "spb"]
    return render_template("spb.html", kategorie=podkafelki)


@app.route("/pomoce/spb-srodki")
def pomoce_spb_srodki():
    """Podstrona 'Przypadki użycia ŚPB' — kafelek na każdy środek przymusu.

    Dane z ustawy o ŚPB i broni palnej (art. 11 – przypadki; art. 12–33 – środki).
    """
    with open(BASE_DIR / "data" / "spb_srodki.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template("spb_srodki.html", srodki=dane["srodki"], zrodlo=dane.get("_zrodlo", ""))


@app.route("/pomoce/uto")
def uto():
    """Podstrona UTO: hulajnoga elektryczna, UTO i urzadzenie wspomagajace ruch.

    Dane wylacznie z ustawy Prawo o ruchu drogowym i ustawy o kierujacych pojazdami.
    """
    with open(BASE_DIR / "data" / "uto.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template(
        "uto.html",
        urzadzenia=dane["urzadzenia"],
        zrodlo=dane.get("_zrodlo", ""),
    )


@app.route("/pomoce/holowanie-pojazdow")
def holowanie_pojazdow():
    """Podstrona 'Holowanie pojazdów'.

    Podstawy usuwania / zabezpieczania pojazdow: dyspozycje z ustawy
    Prawo o ruchu drogowym (art. 50a i 130a) oraz zlecenia holowania
    na potrzeby czynnosci procesowych (KPK / KPOW).
    """
    with open(BASE_DIR / "data" / "holowanie.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template(
        "holowanie.html",
        grupy=dane["grupy"],
        legenda=dane.get("legenda", {}),
        zrodlo=dane.get("_zrodlo", ""),
    )


@app.route("/pomoce/statusy-pj-ksip")
def statusy_pj_ksip():
    """Podstrona 'Statusy Prawa Jazdy KSIP'.

    Znaczenie statusow 0-7 z ewidencji kierowcow naruszajacych przepisy
    ruchu drogowego wraz ze wskazaniami do dalszych czynnosci.
    """
    with open(BASE_DIR / "data" / "statusy_pj_ksip.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template(
        "statusy_pj_ksip.html",
        statusy=dane["statusy"],
        zrodlo=dane.get("_zrodlo", ""),
    )


@app.route("/pomoce/kalkulator-predkosci")
def kalkulator_predkosci():
    """Podstrona 'Kalkulator prędkości'.

    Ograniczenie + predkosc zmierzona + miejsce zdarzenia -> przekroczenie,
    rekord taryfikatora (kwalifikacja, mandat, recydywa, punkty, kod) oraz
    ocena obligatoryjnego zatrzymania prawa jazdy (mechanizm +50 km/h,
    stan prawny od 3.03.2026). Teksty przepisow z lokalnej bazy aktow.
    """
    dane = load_taryfikator()
    przedzialy = []
    tekst_92a = None
    for r in dane["rekordy"]:
        if r.get("category") != "predkosc":
            continue
        t = (r.get("title") or "").lower()
        if "przekroczenie" not in t or "prędko" not in t:
            continue
        m = re.search(r"do\s+(\d+)\s*km", t)
        od, do = None, None
        if m:
            od, do = 1, int(m.group(1))
        elif (m := re.search(r"o\s+(\d+)\s*[-–]\s*(\d+)\s*km", t)):
            od, do = int(m.group(1)), int(m.group(2))
        elif (m := re.search(r"o\s+(\d+)\s*km/h\s*i\s*wi", t)):
            od, do = int(m.group(1)), None
        if od is None:
            continue  # np. przekroczenie predkosci indywidualnej — poza przedzialami
        # paragraf art. 92a KW z kwalifikacji ("§1" / "§2") — do wyroznienia w tekscie
        mp = re.search(r"92a\s*§\s*(\d)", r.get("legal_qualification") or "")
        przedzialy.append({
            "od": od, "do": do,
            "title": r.get("title"),
            "kwalifikacja": r.get("legal_qualification"),
            "mandat": r.get("mandate_base"),
            "recydywa": r.get("mandate_recidive"),
            "punkty": r.get("points_max"),
            "kod": r.get("code"),
            "paragraf": mp.group(1) if mp else None,
        })
        # pelny tekst art. 92a KW — pierwszy blok kwalifikacji prawnej rekordu
        if tekst_92a is None and r.get("legal_qualification_text"):
            blok = str(r["legal_qualification_text"]).split("\n\n")[0].split("\n")
            if blok and "92a" in blok[0]:
                tekst_92a = " ".join(blok[1:]).strip() or None
    przedzialy.sort(key=lambda p: p["od"])

    # art. 135 ust. 1 pkt 2 lit. a PRD — brzmienie od 3.03.2026 z lokalnej bazy aktow
    tekst_135 = None
    try:
        with open(BASE_DIR / "data" / "_prd_articles.json", encoding="utf-8") as f:
            prd_art = json.load(f)

        def _znajdz(obj, klucz):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k) == klucz:
                        return v
                    w = _znajdz(v, klucz)
                    if w:
                        return w
            return None

        def _lit_a(tekst):
            # nowe brzmienie lit. a (od 3.03.2026) jest w bazie w nawiasach katowych <...>
            m = re.search(r"<a\)\s*(kierowaniu pojazdem z prędkością[^>]+?)\s*(?:lub\s*)?>", tekst)
            if not m:
                return None
            frag = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
            return frag.replace("zabudo wanym", "zabudowanym")

        frag_135 = _lit_a(_znajdz(prd_art, "135") or "")
        if frag_135:
            tekst_135 = ("Policjant zatrzyma wydane w kraju prawo jazdy za pokwitowaniem "
                         "w przypadku ujawnienia czynu polegającego na " + frag_135 + ".")
        frag_135a = _lit_a(_znajdz(prd_art, "135a") or "")
        if frag_135a:
            tekst_135a = ("Policjant zatrzyma prawo jazdy wydane przez państwo inne niż Rzeczpospolita "
                          "Polska za pokwitowaniem w przypadku ujawnienia czynu polegającego na " + frag_135a + ".")
        else:
            tekst_135a = None
    except OSError:
        tekst_135a = None
    if not tekst_135:
        tekst_135 = ("Policjant zatrzyma wydane w kraju prawo jazdy za pokwitowaniem w przypadku "
                     "ujawnienia czynu polegającego na kierowaniu pojazdem z prędkością przekraczającą "
                     "dopuszczalną o więcej niż 50 km/h na obszarze zabudowanym lub na drodze "
                     "jednojezdniowej dwukierunkowej poza obszarem zabudowanym.")

    podstawy = {
        "art92a": tekst_92a,
        "art135": tekst_135,
        "art135a": tekst_135a,
        "art102": None,  # ustawa o kierujacych pojazdami — poza lokalna baza aktow (sam przypis)
    }
    return render_template("kalkulator_predkosci.html", przedzialy=przedzialy, podstawy=podstawy)


@app.route("/pomoce/przelicznik-mgl-promile")
def przelicznik_mgl_promile():
    """Podstrona 'Przelicznik mg/l – ‰'.

    Dwukierunkowe przeliczenie stezenia alkoholu (1 mg/l ~ 2,1 promila)
    oraz kwalifikacja stanu wg art. 46 ust. 2 i 3 ustawy o wychowaniu
    w trzezwosci (progi ustawowe odrebne dla krwi i wydychanego powietrza).
    """
    return render_template("przelicznik_mgl_promile.html")


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
