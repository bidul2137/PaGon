# -*- coding: utf-8 -*-
"""Testy poprawek bezpieczenstwa z audytu 11.08.2026.

Testy celowo NIE wymagaja zainstalowanego Flaska ani uruchomionego serwera:
badaja kod zrodlowy i pliki danych. Dzieki temu dzialaja w kazdym srodowisku,
takze przed instalacja zaleznosci, i pilnuja wlasnie tych wlasnosci, ktore
latwo przywrocic przez nieuwage.

Uruchomienie:
    python -m unittest discover -s tests -p "test_*.py" -v
"""
import ast
import json
import re
import unittest
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
ZRODLO_APP = (KATALOG / "app.py").read_text(encoding="utf-8")


class TestUruchomienie(unittest.TestCase):
    """KR-02 — debugger i interfejs nasluchu."""

    def test_brak_bezwarunkowego_debug_true(self):
        self.assertNotIn(
            "app.run(debug=True", ZRODLO_APP,
            "app.run nie moze miec na sztywno debug=True — debugger Werkzeuga "
            "udostepnia interaktywna konsole Pythona.")

    def test_brak_bezwarunkowego_hosta_publicznego(self):
        self.assertNotIn(
            'host="0.0.0.0"', ZRODLO_APP,
            "Nasluch na 0.0.0.0 musi wynikac ze zmiennej PAGON_HOST, "
            "a nie byc wpisany w kodzie.")

    def test_debug_zalezy_od_zmiennej_srodowiskowej(self):
        self.assertIn("PAGON_DEBUG", ZRODLO_APP)
        self.assertIn("app.run(debug=TRYB_DEBUG", ZRODLO_APP)

    def test_domyslny_host_to_petla_zwrotna(self):
        self.assertIn('os.environ.get("PAGON_HOST", "127.0.0.1")', ZRODLO_APP)

    def test_debug_z_publicznym_hostem_jest_odrzucany(self):
        """Sama kombinacja PAGON_DEBUG=1 + host publiczny ma przerywac start."""
        self.assertIn("SystemExit", ZRODLO_APP)
        self.assertRegex(ZRODLO_APP, r"TRYB_DEBUG and host != \"127\.0\.0\.1\"")


class TestPobieraniePDF(unittest.TestCase):
    """KR-03 i WY-05 — weryfikacja TLS oraz limit czasu."""

    def test_brak_wylaczonej_weryfikacji_tls(self):
        """Szukamy WYWOLANIA w kodzie, a nie wzmianki w tekscie.

        Kontrola tekstowa oblewalaby na komentarzu opisujacym usunieta podatnosc,
        a jednoczesnie przepuscilaby wywolanie zapisane inaczej. Drzewo skladni
        pomija komentarze i docstringi, wiec bada to, co faktycznie sie wykona.
        """
        drzewo = ast.parse(ZRODLO_APP)
        znalezione = [w.attr for w in ast.walk(drzewo)
                      if isinstance(w, ast.Attribute)
                      and w.attr in ("_create_unverified_context",
                                     "_https_verify_certificates")]
        self.assertEqual(
            znalezione, [],
            "Pobieranie dokumentow prawnych nie moze akceptowac dowolnego "
            "certyfikatu — pozwalaloby to podstawic spreparowany dokument.")

    def test_brak_wylaczonej_weryfikacji_hosta(self):
        """Kontekst TLS nie moze miec rozluznionych ustawien weryfikacji."""
        drzewo = ast.parse(ZRODLO_APP)
        for w in ast.walk(drzewo):
            if isinstance(w, ast.Assign):
                for cel in w.targets:
                    if isinstance(cel, ast.Attribute) and cel.attr == "check_hostname":
                        self.assertNotEqual(getattr(w.value, "value", None), False,
                                            "check_hostname nie moze byc wylaczone.")
                    if isinstance(cel, ast.Attribute) and cel.attr == "verify_mode":
                        self.assertNotIn("CERT_NONE", ast.dump(w.value),
                                         "verify_mode nie moze byc CERT_NONE.")

    def test_timeout_maksymalnie_10_s(self):
        m = re.search(r"PDF_TIMEOUT_S\s*=\s*(\d+)", ZRODLO_APP)
        self.assertIsNotNone(m, "Brak stalej PDF_TIMEOUT_S.")
        self.assertLessEqual(int(m.group(1)), 10,
                             "Limit czasu pobierania PDF ma byc nie wiekszy niz 10 s.")
        self.assertIn("timeout=PDF_TIMEOUT_S", ZRODLO_APP)

    def test_tylko_jedna_proba_pobrania(self):
        """W ciele _pobierz_pdf nie moze byc petli ponawiajacej zadanie."""
        drzewo = ast.parse(ZRODLO_APP)
        fn = next(w for w in ast.walk(drzewo)
                  if isinstance(w, ast.FunctionDef) and w.name == "_pobierz_pdf")
        petle = [w for w in ast.walk(fn) if isinstance(w, (ast.For, ast.While))]
        self.assertEqual(petle, [], "_pobierz_pdf ma wykonywac dokladnie jedna probe.")

    def test_niepowodzenie_nie_zapisuje_cache(self):
        """Przy bledzie zwracamy powod, a nie tresc — wiec nie ma czego zapisac."""
        self.assertIn("dane, powod = _pobierz_pdf(url)", ZRODLO_APP)
        self.assertIn("pdf_blad.html", ZRODLO_APP)

    def test_biala_lista_kluczy_zachowana(self):
        self.assertIn("PDF_ZRODLA.get(klucz)", ZRODLO_APP)


class TestCache(unittest.TestCase):
    """WY-04 i SR-01 — naglowki cache."""

    def test_api_taryfikator_ma_cache_control(self):
        blok = re.search(r"def api_taryfikator\(\):.*?(?=\n@app\.route)", ZRODLO_APP, re.S)
        self.assertIsNotNone(blok)
        self.assertIn("Cache-Control", blok.group(0))
        self.assertIn("ETag", blok.group(0),
                      "Dlugi cache bez wersjonowania zamrozilby stare stawki mandatow.")

    def test_wszystkie_endpointy_danych_maja_cache(self):
        braki = []
        for m in re.finditer(r'@app\.route\("([^"]*(?:/dane|/api/)[^"]*)"\)\s*\n'
                             r"def \w+\(.*?(?=\n@app\.route|\Z)", ZRODLO_APP, re.S):
            if "Cache-Control" not in m.group(0):
                braki.append(m.group(1))
        self.assertEqual(braki, [], f"Endpointy danych bez Cache-Control: {braki}")

    def test_zerowy_cache_statykow_tylko_w_debugu(self):
        self.assertIn('SEND_FILE_MAX_AGE_DEFAULT"] = 0 if TRYB_DEBUG', ZRODLO_APP)

    def test_adres_taryfikatora_jest_wersjonowany(self):
        szablon = (KATALOG / "templates" / "taryfikator.html").read_text(encoding="utf-8")
        self.assertIn("wersja_danych", szablon)


class TestZalacznik2PozaAplikacja(unittest.TestCase):
    """WY-01 — dane odrzucone nie moga trafic do uzytkownika.

    Zalacznik nr 2 zostal usuniety z repozytorium 2026-08-12. Zrodlem prawdy
    jest PDF w zrodla/, a importer ma go nie odtwarzac (ZALACZNIKI_DO_IMPORTU).
    """

    KAT = KATALOG / "data" / "kody_usterek"

    def test_dane_zalacznika_2_nie_leza_w_repozytorium(self):
        znalezione = [str(p.relative_to(self.KAT))
                      for p in self.KAT.rglob("additional_inspection*")]
        self.assertEqual(znalezione, [],
                         f"Dane zalacznika nr 2 wrocily do repozytorium: {znalezione}")

    def test_importer_pomija_zalacznik_2(self):
        zrodlo = (self.KAT / "scripts" / "import_vehicle_defects.py").read_text(encoding="utf-8")
        self.assertRegex(zrodlo, r"ZALACZNIKI_DO_IMPORTU\s*=\s*\(1,\)",
                         "Importer znow bralby zalacznik nr 2.")

    def test_wykaz_elementow_ma_tylko_zalacznik_1(self):
        d = json.loads((self.KAT / "inspection_items.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(d), ["annex_1"])

    def test_zaden_endpoint_nie_czyta_zalacznika_2(self):
        self.assertNotIn("additional_inspection", ZRODLO_APP)
        for katalog, wzor in ((KATALOG / "templates", "*.html"),
                              (KATALOG / "static" / "js", "*.js")):
            for plik in katalog.glob(wzor):
                self.assertNotIn("additional_inspection",
                                 plik.read_text(encoding="utf-8"),
                                 f"{plik.name} odwoluje sie do danych w kwarantannie.")

    def test_modul_usterek_laduje_wylacznie_zalacznik_1(self):
        blok = re.search(r"def _kody_usterek_dane\(\):.*?(?=\ndef |\n@app\.route)",
                         ZRODLO_APP, re.S).group(0)
        self.assertIn("periodic_defects.json", blok)
        self.assertNotIn("additional_inspection", blok)

    def test_metadane_nie_wykazuja_zalacznika_2_jako_aktywnego(self):
        m = json.loads((self.KAT / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual([z["number"] for z in m["annexes"]], [1])
        wykluczony = next(z for z in m["excluded_annexes"] if z["number"] == 2)
        self.assertEqual(wykluczony["status"], "not_imported")

    def test_raport_importu_wyjasnia_brak_zalacznika_2(self):
        raport = (self.KAT / "import_report.md").read_text(encoding="utf-8")
        self.assertIn("NIE WPROWADZONY", raport)


if __name__ == "__main__":
    unittest.main(verbosity=2)
