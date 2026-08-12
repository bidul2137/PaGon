import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response, redirect, abort, url_for

app = Flask(__name__)


def _flaga(nazwa, domyslnie="0"):
    """Zmienna srodowiskowa traktowana jako przelacznik 0/1."""
    return os.environ.get(nazwa, domyslnie).strip().lower() in ("1", "true", "yes", "on")


# Debugger Werkzeuga daje dostep do interaktywnej konsoli Pythona, wiec wlaczamy
# go wylacznie na jawne zadanie (PAGON_DEBUG=1) i nigdy domyslnie.
TRYB_DEBUG = _flaga("PAGON_DEBUG")

# Zerowy cache plikow statycznych to ustawienie DEWELOPERSKIE. W produkcji
# oznaczaloby ponowne pobieranie kilkudziesieciu megabajtow przy kazdym wejsciu,
# a swiezosc CSS/JS i tak zapewnia static_v() doklejajacy znacznik czasu pliku.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0 if TRYB_DEBUG else 604800


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

# gotowa odpowiedz z baza ADR trzymana w pamieci procesu:
# (znacznik_czasow_plikow, tresc_json). Patrz pomoce_tablica_adr_dane().
_ADR_CACHE = None
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


#: Jedna proba i krotki limit czasu. Wczesniej byly dwie proby po 60 s, wiec
#: jedno zadanie potrafilo zajac watek serwera na dwie minuty — przy jednym
#: workerze wystarczylo kilka takich, zeby aplikacja przestala odpowiadac.
PDF_TIMEOUT_S = 10


def _kontekst_tls():
    """Kontekst TLS z pelna weryfikacja certyfikatu.

    Swiadomie NIE MA tu wariantu bez weryfikacji. Wczesniej po nieudanej probie
    kod ponawial zadanie z ssl._create_unverified_context(), czyli akceptowal
    dowolny certyfikat i zapisywal pobrany plik na dysk — to pozwalalo podstawic
    spreparowany dokument prawny, ktory potem byl serwowany z zaufanego origin.

    Gdy systemowy magazyn CA jest niekompletny (typowe na Windows), korzystamy
    z certifi. To rozwiazuje ten sam problem co wylaczenie weryfikacji, ale bez
    rezygnacji z bezpieczenstwa.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _pobierz_pdf(url):
    """Pobiera PDF z weryfikacja TLS. Zwraca (bajty, None) albo (None, powod).

    Powod jest krotkim komunikatem dla uzytkownika — nie zawiera adresu ani
    szczegolow technicznych, ktore nie sa mu do niczego potrzebne.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "PaGon/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=PDF_TIMEOUT_S,
                                    context=_kontekst_tls()) as odp:
            if odp.status != 200:
                return None, f"Serwer źródła odpowiedział kodem {odp.status}."
            return odp.read(), None
    except ssl.SSLCertVerificationError:
        return None, ("Nie udało się potwierdzić certyfikatu serwera źródła. "
                      "Dokument nie został pobrany.")
    except urllib.error.HTTPError as e:
        return None, f"Serwer źródła odpowiedział kodem {e.code}."
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "Nie udało się połączyć ze źródłem dokumentu."


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


def _wersja_taryfikatora():
    """Znacznik wersji danych taryfikatora — czasy modyfikacji plików zrodlowych.

    Sluzy do wersjonowania adresu /api/taryfikator i jako ETag. Po podmianie
    stawek zmienia sie sam, wiec przegladarka pobiera nowa tresc mimo dlugiego
    cache; bez tego uzytkownik zostalby ze starymi kwotami mandatow.
    """
    znaczniki = []
    for p in (TARYFIKATOR_JSON, BASE_DIR / "data" / "nazwy_artykulow.json"):
        try:
            znaczniki.append(int(p.stat().st_mtime))
        except OSError:
            znaczniki.append(0)
    return "-".join(str(z) for z in znaczniki)


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

    def tekst_listy(rekord):
        """Splaszcza list_items rekordu do jednego ciagu.

        Tresc wielu pozycji Pomocy (przypadki uzycia SPB, broni palnej) siedzi
        wylacznie w list_items, a pozycje sub bywaja raz tekstem, raz obiektem
        {"text": ...}. Bez tego wyszukiwarka nie widziala niemal calej strony.
        """
        czesci = []
        for it in rekord.get("list_items") or []:
            if isinstance(it, str):
                czesci.append(it)
                continue
            czesci.append(it.get("text") or "")
            for s in it.get("sub") or []:
                czesci.append(s if isinstance(s, str) else (s.get("text") or ""))
        return " ".join(czesci)

    def szukaj_linkow(items, q, slug=None):
        ql = bez_ogonkow(q.strip())
        out = []
        for r in items:
            if slug and r.get("category") != slug:
                continue
            hay = bez_ogonkow(" ".join([
                r.get("title", ""), r.get("description", ""),
                r.get("tag", ""), r.get("article", ""), r.get("summary", ""),
                r.get("effect", ""), r.get("kod", ""), r.get("country", ""),
                r.get("opis", ""), r.get("note", ""), r.get("list_intro", ""),
                tekst_listy(r),
                " ".join(r.get("keywords", [])),
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
        # Podkafelek nalezacy do huba (numery, SPB) dostaje wlasny powrot DO HUBA.
        # Strzalka w lewym gornym rogu prowadzi do Pomocy — gdyby powrot robil to
        # samo, uzytkownik wypadalby z grupy i musial wchodzic w nia od nowa.
        HUBY = {
            "numery": ("pomoce_numery_telefonow", "Powrót do numerów telefonów"),
            "spb": ("pomoce_spb", "Powrót do środków przymusu"),
        }
        hub = HUBY.get((aktualna_kategoria or {}).get("grupa"))
        return render_template(
            "pomoce.html", widok="linki", kategorie=kategorie,
            kategoria=aktualna_kategoria, query="",
            linki=[r for r in linki if r.get("category") == kategoria_slug],
            hub_url=url_for(hub[0]) if hub else None,
            hub_etykieta=hub[1] if hub else None,
        )

    # Indeks wyszukiwania dla kafelkow: dla kazdej kategorii sklejamy tekst
    # z jej linkow (nazwy, kody, opisy, keywords), zeby wyszukiwarka na stronie
    # kafelkow znajdowala kafelek takze po jego zawartosci (np. "okulary",
    # "ksenon", kod "20.01" -> odpowiedni kafelek).
    kafelki_szukaj = {}
    for r in linki:
        c = r.get("category")
        if not c:
            continue
        czesci = [
            r.get("title", ""), r.get("summary", ""), r.get("tag", ""),
            r.get("kod", ""), r.get("country", ""), r.get("opis", ""),
            r.get("article", ""), r.get("effect", ""), r.get("note", ""),
            " ".join(r.get("keywords", [])),
        ]
        kafelki_szukaj.setdefault(c, []).append(" ".join(p for p in czesci if p))
    kafelki_szukaj = {k: " ".join(v) for k, v in kafelki_szukaj.items()}

    return render_template(
        "pomoce.html", widok="kafelki", kategorie=kategorie,
        kategoria=None, query="", linki=[], kafelki_szukaj=kafelki_szukaj,
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


_ZNAKI_CACHE = None


def load_znaki():
    """Baza znakow drogowych z data/znaki/. Trzymana w pamieci procesu.

    Klucz cache to czasy modyfikacji plikow — po recznej podmianie danych
    wszystko przebuduje sie samo, bez restartu aplikacji.
    """
    global _ZNAKI_CACHE
    katalog = BASE_DIR / "data" / "znaki"
    meta_plik = katalog / "metadata.json"
    if not meta_plik.exists():
        return {"kategorie": [], "znaki": [], "indeks": {}, "indeks_bez_wielkosci": {},
                "metadane": {}, "wersja": "0"}

    with open(meta_plik, encoding="utf-8") as f:
        metadane = json.load(f)
    pliki = [meta_plik] + [katalog / k["file"] for k in metadane.get("categories", [])]
    znacznik = tuple(p.stat().st_mtime_ns for p in pliki if p.exists())

    if _ZNAKI_CACHE is None or _ZNAKI_CACHE["znacznik"] != znacznik:
        znaki = []
        for kat in metadane.get("categories", []):
            plik = katalog / kat["file"]
            if plik.exists():
                with open(plik, encoding="utf-8") as f:
                    znaki.extend(json.load(f))
        _ZNAKI_CACHE = {
            "znacznik": znacznik,
            "kategorie": metadane.get("categories", []),
            "znaki": znaki,
            "indeks": {z["code"]: z for z in znaki},
            # Kody maja mieszana wielkosc liter: seria wielka, koncowka mala
            # (A-11a, D-21a, T-1b). Dodatkowy indeks po wersji wielkimi literami
            # pozwala trafic w rekord niezaleznie od tego, jak uzytkownik wpisze
            # adres — bez psucia oryginalnej pisowni kodu.
            "indeks_bez_wielkosci": {z["code"].upper(): z for z in znaki},
            "metadane": metadane,
            "wersja": "%s-%d" % (metadane.get("dataset_version", "1"), max(znacznik or [0])),
        }
    return _ZNAKI_CACHE


@app.route("/pomoce/znaki")
def pomoce_znaki():
    """Strona glowna modulu 'Znaki drogowe' — wyszukiwarka i kategorie."""
    dane = load_znaki()
    return render_template("znaki.html", kategorie=dane["kategorie"],
                           metadane=dane["metadane"], wersja=dane["wersja"])


@app.route("/pomoce/znaki/kategoria/<seria>")
def pomoce_znaki_kategoria(seria):
    """Widok jednej serii znakow, np. /pomoce/znaki/kategoria/A."""
    dane = load_znaki()
    kat = next((k for k in dane["kategorie"] if k["id"] == seria.upper()), None)
    if not kat:
        abort(404)
    lista = [z for z in dane["znaki"] if z["category_id"] == kat["id"]]
    return render_template("znaki_kategoria.html", kategoria=kat, znaki=lista,
                           wersja=dane["wersja"])


def _wykroczenia_dla_znaku(kod):
    """Rekordy taryfikatora dotyczace danego znaku.

    Wiazemy WYLACZNIE po tytule i streszczeniu rekordu, bo tam kod znaku pada
    celowo ("Niestosowanie sie do znaku B-2 ..."). Pole legal_qualification_text
    cytuje przepis, ktory wylicza kilkanascie znakow naraz — dopasowanie po nim
    dawaloby powiazania wrecz falszywe (B-33 trafialby do wykroczenia o B-37).

    Kod porownujemy jako osobny wyraz, zeby B-2 nie zlapalo B-25 ani B-2a.
    """
    wzor = re.compile(r"(?<![A-Za-z0-9-])" + re.escape(kod) + r"(?![A-Za-z0-9])")
    wynik = []
    for r in load_taryfikator()["rekordy"]:
        if wzor.search(r.get("title") or "") or wzor.search(r.get("summary") or ""):
            wynik.append(r)
    return wynik


@app.route("/pomoce/znaki/znak/<kod>")
def pomoce_znaki_znak(kod):
    """Podstrona pojedynczego znaku."""
    dane = load_znaki()
    # najpierw trafienie dokladne, potem bez wzgledu na wielkosc liter
    znak = dane["indeks"].get(kod) or dane["indeks_bez_wielkosci"].get(kod.upper())
    if not znak:
        abort(404)
    kat = next((k for k in dane["kategorie"] if k["id"] == znak["category_id"]), None)
    powiazane = [dane["indeks"][k] for k in znak.get("related_sign_ids", [])
                 if k in dane["indeks"]]
    return render_template("znaki_znak.html", znak=znak, kategoria=kat,
                           powiazane=powiazane, wersja=dane["wersja"],
                           wykroczenia=_wykroczenia_dla_znaku(znak["code"]))


@app.route("/pomoce/znaki/dane")
def pomoce_znaki_dane():
    """Lekki indeks do wyszukiwarki — bez podstaw prawnych i szczegolow.

    Pelne dane sa renderowane po stronie serwera na podstronie znaku; do
    wyszukiwania wystarcza kod, nazwa, krotki opis, kategoria i grafika.
    """
    dane = load_znaki()
    lekkie = [{
        "code": z["code"], "name": z["name"], "short": z["short_description"],
        "cat": z["category_id"], "catName": z["category_name"],
        "img": z["image_path"], "kw": z.get("keywords", []),
    } for z in dane["znaki"]]
    odp = Response(json.dumps({"znaki": lekkie, "kategorie": dane["kategorie"]},
                              ensure_ascii=False), mimetype="application/json")
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return odp


@app.route("/pomoce/tablica-adr")
def pomoce_tablica_adr():
    """Podstrona 'Tablica ADR' — interaktywna tablica pomaranczowa.

    Dane ADR sa ladowane osobnym zadaniem (/pomoce/tablica-adr/dane), zeby
    nie powiekszac HTML i zeby przegladarka mogla je trzymac w cache — modul
    ma dzialac bez internetu po pierwszym otwarciu.

    Do szablonu przekazujemy znacznik wersji bazy. JS dokleja go do adresu
    danych, wiec po kazdym imporcie przegladarka pobiera plik na nowo, a
    miedzy importami korzysta z cache (tryb offline dziala dalej).
    """
    plik = BASE_DIR / "data" / "adr" / "adr_2025_substances.json"
    try:
        with open(BASE_DIR / "data" / "adr" / "adr_2025_metadata.json", encoding="utf-8") as f:
            wersja = json.load(f).get("dataset_version", "0")
    except OSError:
        wersja = "0"
    try:
        wersja = "%s-%d" % (wersja, int(plik.stat().st_mtime))
    except OSError:
        pass
    return render_template("adr.html", wersja_bazy=wersja)


@app.route("/pomoce/tablica-adr/dane")
def pomoce_tablica_adr_dane():
    """Lokalna baza ADR: substancje + kody zagrozenia + metadane.

    Zadne dane nie sa pobierane z sieci w czasie pracy uzytkownika — trzy pliki
    z data/adr/ sa scalane i zwracane jako jeden JSON.

    Baza ma ok. 2,4 MB, wiec trzymamy gotowa odpowiedz w pamieci procesu.
    Klucz cache to czasy modyfikacji plikow — po recznej podmianie ktoregokolwiek
    z nich odpowiedz przebuduje sie sama, bez restartu aplikacji.
    """
    global _ADR_CACHE
    katalog = BASE_DIR / "data" / "adr"
    pliki = [
        katalog / "adr_2025_substances.json",
        katalog / "adr_2025_danger_codes.json",
        katalog / "adr_2025_metadata.json",
    ]
    try:
        znacznik = tuple(p.stat().st_mtime_ns for p in pliki)
    except OSError:
        abort(404)

    if _ADR_CACHE is None or _ADR_CACHE[0] != znacznik:
        tresc = {}
        for klucz, plik in zip(("substances", "danger_codes", "metadata"), pliki):
            with open(plik, encoding="utf-8") as f:
                tresc[klucz] = json.load(f)
        _ADR_CACHE = (znacznik, json.dumps(tresc, ensure_ascii=False))

    odp = Response(_ADR_CACHE[1], mimetype="application/json")
    # baza zmienia sie tylko przy recznej aktualizacji, a adres zawiera wersje,
    # wiec dlugi cache w przegladarce jest bezpieczny i daje tryb offline
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return odp


_CZYNY_CACHE = None


def _kody_czynow_dane():
    """Kody czynow z zalacznika + kwoty mandatow dolaczone z taryfikatora.

    Mandatow NIE trzymamy w bazie kodow czynow. Wynikaja z innego aktu i leza juz
    w data/taryfikator.json, wiec laczymy jedno z drugim po kodzie czynu dopiero
    tutaj. Dzieki temu kwota istnieje w jednym miejscu — poprawka w taryfikatorze
    jest od razu widoczna w obu modulach i nie da sie doprowadzic do rozbieznosci.

    Jeden kod czynu obejmuje zwykle wiele konkretnych naruszen (C 20 ma ich 26),
    dlatego mandaty sa lista, a nie pojedyncza wartoscia.
    """
    global _CZYNY_CACHE
    katalog = BASE_DIR / "data" / "kody_czynow"
    pliki = [katalog / "codes.json", katalog / "categories.json",
             katalog / "metadata.json", BASE_DIR / "data" / "taryfikator.json"]
    try:
        znacznik = tuple(p.stat().st_mtime_ns for p in pliki)
    except OSError:
        return None
    if _CZYNY_CACHE is not None and _CZYNY_CACHE["znacznik"] == znacznik:
        return _CZYNY_CACHE

    with open(pliki[0], encoding="utf-8") as f:
        kody = json.load(f)
    with open(pliki[1], encoding="utf-8") as f:
        kategorie = json.load(f)
    with open(pliki[2], encoding="utf-8") as f:
        meta = json.load(f)

    mandaty = {}
    for r in load_taryfikator()["rekordy"]:
        if r.get("code"):
            mandaty.setdefault(r["code"], []).append(r)

    indeks = {}
    for k in kody:
        k["mandaty"] = mandaty.get(k["code"], [])
        indeks[k["code_normalized"]] = k
    for kat in kategorie:
        kat["count"] = sum(1 for k in kody if k["category_id"] == kat["id"])

    _CZYNY_CACHE = {"znacznik": znacznik, "kody": kody, "kategorie": kategorie,
                    "meta": meta, "indeks": indeks,
                    "wersja": "%s-%d" % (meta.get("dataset_version", "0"),
                                         int(pliki[0].stat().st_mtime))}
    return _CZYNY_CACHE


def _normalizuj_kod_czynu(wpis):
    """'a-02', ' A 02 ', 'A02' -> 'A02'. Inaczej None."""
    s = re.sub(r"[^A-Za-z0-9]", "", str(wpis or "")).upper()
    m = re.match(r"^([A-J])(\d{1,2})$", s)
    return "%s%02d" % (m.group(1), int(m.group(2))) if m else None


@app.route("/pomoce/kody-czynow")
def pomoce_kody_czynow():
    """Lista kodow czynow z wyszukiwarka."""
    dane = _kody_czynow_dane()
    return render_template("kody_czynow.html",
                           kategorie=(dane or {}).get("kategorie") or [],
                           meta=(dane or {}).get("meta"),
                           wersja=(dane or {}).get("wersja", "0"))


@app.route("/pomoce/kody-czynow/dane")
def pomoce_kody_czynow_dane():
    """Lekki indeks do wyszukiwarki — bez kwalifikacji i zrodel."""
    dane = _kody_czynow_dane()
    if dane is None:
        abort(404)
    lekkie = [{"k": k["code"], "n": k["code_normalized"], "t": k["title"],
               "p": k["points"], "c": k["category_id"],
               "m": bool(k["mandaty"]), "w": k.get("keywords") or []}
              for k in dane["kody"]]
    odp = Response(json.dumps(lekkie, ensure_ascii=False, separators=(",", ":")),
                   mimetype="application/json")
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return odp


@app.route("/pomoce/kody-czynow/kod/<kod>")
def pomoce_kody_czynow_kod(kod):
    """Podstrona pojedynczego kodu czynu."""
    dane = _kody_czynow_dane()
    if dane is None:
        abort(404)
    czyn = dane["indeks"].get(_normalizuj_kod_czynu(kod) or "")
    if not czyn:
        abort(404)
    kat = next((k for k in dane["kategorie"] if k["id"] == czyn["category_id"]), None)
    # powiazane: sasiednie kody tego samego dzialu, a nie dobrane przypadkowo
    tenzial = [k for k in dane["kody"] if k["category_id"] == czyn["category_id"]]
    i = tenzial.index(czyn)
    powiazane = [k for k in tenzial[max(0, i - 2):i + 3] if k is not czyn][:4]
    return render_template("kody_czynow_kod.html", czyn=czyn, kategoria=kat,
                           powiazane=powiazane, meta=dane["meta"])


_KODY_CACHE = None


def _kody_pocztowe_katalog():
    return BASE_DIR / "data" / "kody_pocztowe"


def _kody_pocztowe_dane():
    """Wczytuje lekki indeks wyszukiwania i trzyma go w pamieci procesu.

    Pelne rekordy leza w postal_codes.sqlite (73 tys. pozycji). Do przegladarki
    idzie search_index.json — ta sama tresc, ale nazwy gmin, powiatow i
    wojewodztw zamienione na indeksy do slownikow. To roznica 44 MB kontra
    3,5 MB, dzieki czemu cala baza miesci sie w cache przegladarki i modul
    dziala offline.

    Plik jest juz w docelowej postaci, wiec tylko go czytamy — bez parsowania
    i skladania JSON-a przy kazdym starcie. Kluczem cache sa czasy modyfikacji,
    wiec po recznym imporcie odpowiedz przebuduje sie sama, bez restartu.
    """
    global _KODY_CACHE
    katalog = _kody_pocztowe_katalog()
    pliki = [katalog / "search_index.json", katalog / "metadata.json"]
    try:
        znacznik = tuple(p.stat().st_mtime_ns for p in pliki)
    except OSError:
        return None

    if _KODY_CACHE is not None and _KODY_CACHE["znacznik"] == znacznik:
        return _KODY_CACHE

    tresc = pliki[0].read_text(encoding="utf-8")
    with open(pliki[1], encoding="utf-8") as f:
        meta = json.load(f)

    wersja = "%s-%d" % (meta.get("dataset_version", "0"), int(pliki[0].stat().st_mtime))
    _KODY_CACHE = {"znacznik": znacznik, "tresc": tresc, "wersja": wersja, "meta": meta}
    return _KODY_CACHE


@app.route("/pomoce/kody-pocztowe")
def pomoce_kody_pocztowe():
    """Podstrona 'Kody pocztowe'.

    Baza idzie osobnym zadaniem (/pomoce/kody-pocztowe/dane), zeby przegladarka
    mogla ja trzymac w cache — po pierwszym otwarciu modul dziala bez internetu.
    Adres danych zawiera wersje zbioru, wiec po imporcie pobiera sie nowa baza.
    """
    dane = _kody_pocztowe_dane()
    return render_template(
        "kody_pocztowe.html",
        wersja_bazy=(dane or {}).get("wersja", "0"),
        meta=(dane or {}).get("meta"),
    )


@app.route("/pomoce/kody-pocztowe/dane")
def pomoce_kody_pocztowe_dane():
    """Lokalna baza kodow pocztowych w postaci zwiezlej.

    Nic nie jest pobierane z sieci w czasie pracy uzytkownika — czytamy wylacznie
    pliki z data/kody_pocztowe/.
    """
    dane = _kody_pocztowe_dane()
    if dane is None:
        abort(404)
    odp = Response(dane["tresc"], mimetype="application/json")
    # adres zawiera wersje zbioru, wiec dlugi cache jest bezpieczny i daje offline
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return odp


@app.route("/pomoce/numery-itd")
def pomoce_numery_itd():
    """Wojewodzkie inspektoraty transportu drogowego wraz z oddzialami.

    Ponad 70 pozycji, wiec plaska lista bylaby nie do przejrzenia — widok
    grupuje je po wojewodztwie i rozwija dopiero wybrane.
    """
    with open(BASE_DIR / "data" / "witd.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template("numery_itd.html", dane=dane)


_USTERKI_CACHE = None


def _kody_usterek_dane():
    """Baza usterek okresowego badania technicznego (zalacznik nr 1).

    Zalacznik nr 2 celowo NIE jest tu wczytywany. Jego dzial I ma te sama
    budowe kolumn, ale usterek nie oznacza literami, przez co pierwszy przebieg
    importu rozbil opisy i zgubil kategorie. Do czasu poprawienia parsera modul
    pokazuje wylacznie dane, za ktore mozna reczyc.
    """
    global _USTERKI_CACHE
    katalog = BASE_DIR / "data" / "kody_usterek"
    pliki = [katalog / "periodic_defects.json", katalog / "categories.json",
             katalog / "metadata.json"]
    try:
        znacznik = tuple(p.stat().st_mtime_ns for p in pliki)
    except OSError:
        return None
    if _USTERKI_CACHE is not None and _USTERKI_CACHE["znacznik"] == znacznik:
        return _USTERKI_CACHE

    with open(pliki[0], encoding="utf-8") as f:
        rekordy = json.load(f)["records"]
    with open(pliki[1], encoding="utf-8") as f:
        kategorie = json.load(f)
    with open(pliki[2], encoding="utf-8") as f:
        metadane = json.load(f)
    # Nazwy podgrup ("1.1. Stan techniczny i działanie") nie maja wlasnych
    # usterek, wiec nie ma ich w rekordach — a to one daja naglowkowi karty
    # srodkowy poziom hierarchii, tak jak w tabeli rozporzadzenia.
    try:
        with open(katalog / "inspection_items.json", encoding="utf-8") as f:
            elementy = json.load(f).get("annex_1", {})
    except OSError:
        elementy = {}

    # Dzialy w kolejnosci z rozporzadzenia (0–10), a nie alfabetycznie.
    dzialy, widziane = [], set()
    for r in rekordy:
        kod = r.get("section_code")
        if kod is None or kod in widziane:
            continue
        widziane.add(kod)
        dzialy.append({"kod": kod, "nazwa": r.get("section_name") or "",
                       "ile": sum(1 for x in rekordy if x.get("section_code") == kod)})
    dzialy.sort(key=lambda d: int(d["kod"]) if d["kod"].isdigit() else 999)

    _USTERKI_CACHE = {
        "znacznik": znacznik,
        "wersja": f'{metadane.get("dataset_version", "0")}-{max(znacznik) // 1000000000}',
        "rekordy": rekordy,
        "indeks": {r["code_normalized"]: r for r in rekordy},
        "dzialy": dzialy,
        "kategorie": kategorie.get("categories", []),
        "elementy": elementy,
        "metadane": metadane,
    }
    return _USTERKI_CACHE


@app.route("/sw.js")
def service_worker():
    """Service worker musi byc serwowany z korzenia, inaczej jego zasieg
    ograniczylby sie do /static/ i nie objalby zadnej strony aplikacji.

    Bez cache po stronie przegladarki: to jedyny plik, ktory decyduje
    o wszystkich pozostalych, wiec nie moze sie zaciac na starej wersji.
    """
    sciezka = Path(app.static_folder) / "sw.js"
    try:
        tresc = sciezka.read_text(encoding="utf-8")
    except OSError:
        abort(404)
    odp = Response(tresc, mimetype="application/javascript")
    odp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    odp.headers["Service-Worker-Allowed"] = "/"
    return odp


@app.route("/offline")
def offline():
    """Strona zastepcza, gdy nie ma ani sieci, ani wpisu w cache."""
    return render_template("offline.html")


@app.route("/static/precache.json")
def precache_lista():
    """Lista zasobow do precache, budowana z katalogu — nie z reki.

    Recznie utrzymywana lista rozjezdza sie z projektem przy pierwszym nowym
    pliku CSS. Adresy niosa znacznik czasu modyfikacji (jak static_v), wiec po
    zmianie pliku powstaje nowy klucz cache.
    """
    katalog = Path(app.static_folder)
    lista = []
    for wzor in ("css/*.css", "js/*.js", "icons/*.png"):
        for plik in sorted(katalog.glob(wzor)):
            wzgledna = plik.relative_to(katalog).as_posix()
            lista.append(f"/static/{wzgledna}?v={int(plik.stat().st_mtime)}")
    for nazwa in ("manifest.json", "img/logo-pagon.png", "img/ic-przepisy.png",
                  "img/ic-pomoce.png", "img/ic-taryfikator.png", "img/ic-konto.png"):
        plik = katalog / nazwa
        if plik.exists():
            lista.append(f"/static/{nazwa}?v={int(plik.stat().st_mtime)}")

    odp = Response(json.dumps(lista, ensure_ascii=False, separators=(",", ":")),
                   mimetype="application/json")
    odp.headers["Cache-Control"] = "no-cache"
    return odp


@app.route("/pomoce/kody-usterek")
def pomoce_kody_usterek():
    """Wyszukiwarka usterek okresowego badania technicznego pojazdu."""
    dane = _kody_usterek_dane()
    if dane is None:
        abort(404)
    return render_template("kody_usterek.html", wersja=dane["wersja"],
                           dzialy=dane["dzialy"], kategorie=dane["kategorie"],
                           metadane=dane["metadane"], ile=len(dane["rekordy"]))


@app.route("/pomoce/kody-usterek/dane")
def pomoce_kody_usterek_dane():
    """Lekki indeks do wyszukiwarki — bez podstaw prawnych i metod badania.

    Nazwy pol sa jednoliterowe, bo ten plik siedzi w cache przegladarki i idzie
    do niej w calosci; przy 635 rekordach pelne nazwy kosztowalyby kilkadziesiat
    kilobajtow bez zadnego zysku.
    """
    dane = _kody_usterek_dane()
    if dane is None:
        abort(404)
    lekkie = [{
        "k": r["code"], "n": r["code_normalized"], "o": r["defect"],
        "s": r.get("section_code"), "e": r.get("inspection_item_code"),
        "i": r.get("inspection_item_name") or "",
        "g": dane["elementy"].get(".".join(
            (r.get("inspection_item_code") or "").split(".")[:2]), ""),
        "sn": r.get("section_name") or "",
        "m": r.get("inspection_method") or "",
        "u": r.get("warnings") or [],
        "p": [o["severity_code"] for o in r["assessment_options"]],
        "w": r.get("keywords") or [],
    } for r in dane["rekordy"]]
    odp = Response(json.dumps(lekkie, ensure_ascii=False, separators=(",", ":")),
                   mimetype="application/json")
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return odp


@app.route("/pomoce/kody-usterek/kod/<kod>")
def pomoce_kody_usterek_kod(kod):
    """Szczegoly jednej usterki."""
    dane = _kody_usterek_dane()
    if dane is None:
        abort(404)
    klucz = re.sub(r"[^A-Za-z0-9]", "", kod).upper()
    usterka = dane["indeks"].get(klucz)
    if not usterka:
        abort(404)
    # sasiedzi z tego samego elementu kontroli — najczestszy ruch to porownanie
    # wariantow tej samej pozycji, a nie skok do innego dzialu
    sasiedzi = [r for r in dane["rekordy"]
                if r["inspection_item_code"] == usterka["inspection_item_code"]
                and r["code"] != usterka["code"]][:8]
    podgrupa = dane["elementy"].get(
        ".".join((usterka.get("inspection_item_code") or "").split(".")[:2]))
    return render_template("kody_usterek_kod.html", usterka=usterka,
                           sasiedzi=sasiedzi, podgrupa=podgrupa,
                           metadane=dane["metadane"])


@app.route("/pomoce/numery-straz-graniczna")
def pomoce_numery_sg():
    """Oddzialy Strazy Granicznej wraz z placowkami.

    Ponad 100 placowek, wiec — jak w module ITD — grupujemy je po oddziale
    i rozwijamy dopiero wybrany. Szablon korzysta ze stylow numery_itd.css,
    bo uklad jest ten sam; wystarczy ta sama klasa kontenera .itd-page.
    """
    with open(BASE_DIR / "data" / "straz_graniczna.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template("numery_sg.html", dane=dane)


@app.route("/pomoce/numery-telefonow")
def pomoce_numery_telefonow():
    """Hub 'Numery telefonów i CKT' — podkafelki z numerami poszczegolnych sluzb.

    Kafelki numerow trzymamy w jednym hubie, zeby nie zajmowaly czterech pol
    na glownej siatce Pomocy; kazdy podkafelek prowadzi do wlasnej listy
    (albo — jak CKT — wprost do serwisu zewnetrznego).
    """
    dane = load_pomoce()
    podkafelki = [k for k in dane["kategorie"] if k.get("grupa") == "numery"]
    return render_template(
        "hub.html",
        kategorie=podkafelki,
        tytul="Numery telefonów",
        podtytul=["ALARMOWE", "SŁUŻBOWE", "KSIĄŻKA TELEFONICZNA"],
    )


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


@app.route("/pomoce/kwalifikacja-zdarzenia")
def kwalifikacja_zdarzenia():
    """Podstrona 'Kwalifikacja zdarzenia drogowego' — kreator pytan.

    Drzewo decyzyjne (miejsce, uczestnicy, obrazenia) prowadzi do kwalifikacji
    (art. 86/97/98 KW albo wypadek z art. 177 KK). Kwoty mandatow dolaczane
    z taryfikatora — nie sa wpisane na sztywno.
    """
    with open(BASE_DIR / "data" / "kwalifikacja_zdarzenia.json", encoding="utf-8") as f:
        dane = json.load(f)

    # dolacz warianty mandatu z taryfikatora po ID rekordow (kwalifikacje typu
    # art. 86 KW maja odrebne stawki dla kierujacego poj. mechanicznym i innego
    # uczestnika ruchu — pokazujemy wszystkie warianty, nie jeden arbitralnie)
    taryfikator = {r["id"]: r for r in load_taryfikator()["rekordy"]}
    for w in dane["wyniki"].values():
        warianty = []
        for wpis in w.get("taryfikator_ids") or []:
            rek = taryfikator.get(wpis["id"])
            if rek:
                warianty.append({
                    "etykieta": wpis.get("etykieta"),
                    "mandat": rek.get("mandate_base"),
                    "recydywa": rek.get("mandate_recidive"),
                    "punkty": rek.get("points_max"),
                })
        w["warianty"] = warianty
    return render_template("kwalifikacja_zdarzenia.html", dane=dane)


@app.route("/pomoce/kontrola-trzezwosci")
def kontrola_trzezwosci():
    """Podstrona 'Kontrola trzezwosci — badany na miejscu' — kreator pytan.

    Drzewo decyzyjne (zgoda na badanie, rodzaj urzadzenia, wyniki I i II
    badania) prowadzi do oceny stanu badanego albo do badania krwi.
    Zrodlo: rozporzadzenie MZ i MSWiA z 28.12.2018 r. w sprawie badan na
    zawartosc alkoholu w organizmie oraz art. 46 ust. 2 i 3 ustawy
    o wychowaniu w trzezwosci.
    """
    with open(BASE_DIR / "data" / "kontrola_trzezwosci.json", encoding="utf-8") as f:
        dane = json.load(f)
    return render_template("kontrola_trzezwosci.html", dane=dane)


@app.route("/pomoce/kontrola-trzezwosci-oddalil-sie")
def kontrola_trzezwosci_oddalil():
    """Podstrona 'Kontrola trzezwosci — badany oddalil sie' — kreator pytan.

    Osobna sciezka dla sytuacji, gdy badany oddalil sie z miejsca zdarzenia
    przed badaniem trzezwosci (albo zachodzi podejrzenie spozycia alkoholu
    po zdarzeniu). Rozporzadzenie wymaga wtedy serii pomiarow rozlozonych
    w czasie, a przy urzadzeniu elektrochemicznym — potwierdzenia
    analizatorem spektrometrycznym i dwoch odrebnych protokolow.
    """
    with open(
        BASE_DIR / "data" / "kontrola_trzezwosci_oddalil.json", encoding="utf-8"
    ) as f:
        dane = json.load(f)
    return render_template("kontrola_trzezwosci_oddalil.html", dane=dane)


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

    # 2) pobranie: jedna proba, 10 s, z pelna weryfikacja TLS.
    #    Zachodzi wylacznie w reakcji na klikniecie kafelka przez uzytkownika.
    dane, powod = _pobierz_pdf(url)
    if dane:
        try:
            PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(dane)
        except OSError:
            pass          # brak cache tylko spowolni kolejne wejscie
        return inline(dane)

    # 3) niepowodzenie: NIE osadzamy dokumentu z zewnetrznego adresu i nie
    #    zapisujemy niczego w cache. Pokazujemy powod i odsylacz do zrodla,
    #    zeby uzytkownik mogl otworzyc dokument sam i swiadomie.
    return Response(
        render_template("pdf_blad.html", powod=powod, url=url, klucz=klucz),
        mimetype="text/html", status=502,
    )


@app.route("/taryfikator")
def taryfikator():
    """Zakladka Taryfikator (mandaty i punkty karne).

    Strona-powloka: dane (kategorie + rekordy) sa wczytywane po stronie
    klienta z /api/taryfikator, a wyszukiwanie / filtrowanie / ulubione
    dzieja sie w calosci w JS (localStorage, bez sesji/logowania).
    """
    dane = load_taryfikator()
    return render_template("taryfikator.html", kategorie=dane["kategorie"],
                           wersja_danych=_wersja_taryfikatora())


@app.route("/api/taryfikator")
def api_taryfikator():
    """Zwraca kategorie i rekordy taryfikatora jako JSON dla static/js/taryfikator.js.

    Dodatkowo dolacza wlasne nazwy artykulow (data/nazwy_artykulow.json) —
    KW i PRD nie maja urzedowych tytulow artykulow, wiec sa to opisy wlasne,
    pokazywane w naglowkach przepisow w szczegolach rekordu.
    """
    dane = dict(load_taryfikator())
    try:
        with open(BASE_DIR / "data" / "nazwy_artykulow.json", encoding="utf-8") as f:
            dane["nazwy_artykulow"] = json.load(f).get("nazwy", {})
    except OSError:
        dane["nazwy_artykulow"] = {}

    odp = jsonify(dane)
    # Ten sam schemat co pozostale endpointy danych, ale z ETagiem. Sam
    # "immutable" bez wersjonowania adresu zamrozilby uzytkownika na starym
    # taryfikatorze po zmianie stawek — a to juz bylaby bledna informacja
    # o wysokosci mandatu. Adres jest wersjonowany w szablonie (znacznik czasu
    # pliku), ETag zabezpiecza dodatkowo wpisy z cache sprzed tej zmiany.
    odp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    odp.headers["ETag"] = f'"{_wersja_taryfikatora()}"'
    return odp


@app.route("/konto")
def konto():
    """Zakladka Twoje konto (profil uzytkownika).

    Widok jest w calosci obslugiwany po stronie klienta (static/js/konto.js,
    stan w localStorage). Bez backendu uwierzytelniania -- akcje demo.
    """
    return render_template("konto.html")


if __name__ == "__main__":
    # Domyslnie serwer nasluchuje wylacznie na tej maszynie i bez debuggera.
    # Debugger Werkzeuga udostepnia interaktywna konsole Pythona, wiec
    # wystawiony na 0.0.0.0 oznacza zdalne wykonanie kodu przez kazdego w sieci.
    # Oba ustawienia wymagaja teraz jawnej decyzji przez zmienne srodowiskowe.
    host = os.environ.get("PAGON_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("PAGON_PORT", "5000"))
    except ValueError:
        port = 5000

    if TRYB_DEBUG and host != "127.0.0.1":
        # Sama kombinacja jest na tyle grozna, ze nie pozwalamy jej wlaczyc
        # przez nieuwage — trzeba wybrac jedno albo drugie.
        raise SystemExit(
            "Odmowa startu: PAGON_DEBUG=1 razem z PAGON_HOST=%s wystawia konsole "
            "debuggera na siec. Wylacz debugger albo nasluchuj na 127.0.0.1." % host
        )

    app.run(debug=TRYB_DEBUG, host=host, port=port)
