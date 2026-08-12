# -*- coding: utf-8 -*-
"""Testy statyczne warstwy PWA.

Nie zastępują testu w przeglądarce (`tests/pwa_offline.spec.js`), tylko pilnują
własności, które łatwo zepsuć edycją: strategii cache, wersjonowania magazynów
i tego, czego service worker nie ma prawa zapisywać.

Uruchomienie:
    python -m unittest discover -s tests -p "test_*.py" -v
"""
import json
import re
import unittest
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent
SW = (KATALOG / "static" / "sw.js").read_text(encoding="utf-8")
PWA_JS = (KATALOG / "static" / "js" / "pwa.js").read_text(encoding="utf-8")
BASE = (KATALOG / "templates" / "base.html").read_text(encoding="utf-8")
APP = (KATALOG / "app.py").read_text(encoding="utf-8")


def bez_komentarzy(js):
    """Usuwa komentarze, żeby kontrole nie potykały się o opis w komentarzu.

    Ta pułapka złapała już dwa testy w tym projekcie: sprawdzenie tekstowe
    trafiało we własny komentarz opisujący, czego kod NIE robi.
    """
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"//[^\n]*", "", js)


SW_KOD = bez_komentarzy(SW)


class TestManifest(unittest.TestCase):

    def setUp(self):
        self.m = json.loads((KATALOG / "static" / "manifest.json").read_text(encoding="utf-8"))

    def test_pola_wymagane_do_instalacji(self):
        for pole in ("name", "short_name", "start_url", "display", "icons",
                     "background_color", "theme_color"):
            self.assertIn(pole, self.m, f"manifest bez pola {pole}")
        self.assertEqual(self.m["display"], "standalone")

    def test_ikony_istnieja_i_maja_wymagane_rozmiary(self):
        rozmiary = {i["sizes"] for i in self.m["icons"]}
        self.assertIn("192x192", rozmiary)
        self.assertIn("512x512", rozmiary)
        for ikona in self.m["icons"]:
            plik = KATALOG / ikona["src"].lstrip("/")
            self.assertTrue(plik.exists(), f"brak pliku ikony {ikona['src']}")

    def test_jest_ikona_maskable(self):
        cele = {i.get("purpose", "any") for i in self.m["icons"]}
        self.assertIn("maskable", cele,
                      "Android bez ikony maskable przytnie logo do koła.")

    def test_manifest_wpiety_w_szablon_bazowy(self):
        self.assertIn('rel="manifest"', BASE)
        self.assertIn("apple-touch-icon", BASE)


class TestServiceWorker(unittest.TestCase):

    def test_magazyny_sa_wersjonowane(self):
        self.assertRegex(SW_KOD, r'const WERSJA = "v\d+"')
        for nazwa in ("powloka", "strony", "dane", "obrazy"):
            self.assertRegex(SW_KOD, rf"pagon-{nazwa}-\$\{{WERSJA\}}")

    def test_stare_magazyny_sa_usuwane_przy_aktywacji(self):
        blok = re.search(r'addEventListener\("activate".*?\n\}\);', SW_KOD, re.S).group(0)
        self.assertIn("caches.delete", blok)
        self.assertIn("clients.claim", blok)

    def test_skipwaiting_tylko_na_zadanie_uzytkownika(self):
        """Automatyczne przejęcie przeładowałoby stronę w trakcie pracy."""
        wywolania = re.findall(r"self\.skipWaiting\(\)", SW_KOD)
        self.assertEqual(len(wywolania), 1, "skipWaiting ma być wywoływane w jednym miejscu.")
        blok_install = re.search(r'addEventListener\("install".*?\n\}\);', SW_KOD, re.S).group(0)
        self.assertNotIn("skipWaiting", blok_install,
                         "skipWaiting w install odbiera użytkownikowi decyzję.")
        self.assertIn('typ === "PRZEJMIJ"', SW_KOD)

    def test_nie_cachuje_zadan_innych_niz_get(self):
        self.assertIn('zadanie.method !== "GET"', SW_KOD)

    def test_nie_cachuje_obcych_origin(self):
        self.assertIn("url.origin !== self.location.origin", SW_KOD)

    def test_nie_cachuje_pdf(self):
        self.assertIn("/pomoce/pdf/", SW_KOD)

    def test_zapisuje_wylacznie_odpowiedzi_200(self):
        """Każde put() musi być poprzedzone kontrolą statusu."""
        puty = re.findall(r"\w+\.put\(", SW_KOD)
        kontrole = re.findall(r"status === 200", SW_KOD)
        self.assertGreaterEqual(len(kontrole), len(puty) - 1,
                                "Któreś put() zapisuje odpowiedź bez sprawdzenia statusu.")

    def test_dane_prawne_maja_klucz_z_wersja(self):
        """Cache-first dla danych jest dopuszczalny TYLKO dzięki ?v= w adresie."""
        self.assertIn("SCIEZKI_DANYCH", SW_KOD)
        self.assertIn("sprzatnijStareDane", SW_KOD)
        for sciezka in ("/pomoce/znaki/dane", "/pomoce/tablica-adr/dane",
                        "/pomoce/kody-czynow/dane", "/pomoce/kody-pocztowe/dane",
                        "/pomoce/kody-usterek/dane", "/api/taryfikator"):
            self.assertIn(sciezka, SW_KOD, f"{sciezka} poza listą danych")

    def test_strony_sa_network_first(self):
        """Widoki renderuje serwer, więc cache nie może przykryć nowej wersji."""
        blok = re.search(r"async function stronaNajpierwZSieci.*?\n\}", SW_KOD, re.S).group(0)
        self.assertLess(blok.index("await fetch"), blok.index("magazyn.match"),
                        "Strony muszą najpierw próbować sieci.")

    def test_magazyn_obrazow_ma_limit(self):
        self.assertIn("LIMIT_OBRAZOW", SW_KOD)
        self.assertIn("przytnijMagazyn", SW_KOD)

    def test_jest_fallback_offline(self):
        self.assertIn("STRONA_OFFLINE", SW_KOD)
        self.assertTrue((KATALOG / "templates" / "offline.html").exists())


class TestRejestracja(unittest.TestCase):

    def test_service_worker_serwowany_z_korzenia(self):
        """Z /static/ jego zasięg nie objąłby żadnej strony aplikacji."""
        self.assertIn('@app.route("/sw.js")', APP)
        self.assertIn("Service-Worker-Allowed", APP)

    def test_plik_sw_bez_cache(self):
        blok = re.search(r"def service_worker\(\):.*?(?=\n@app\.route)", APP, re.S).group(0)
        self.assertIn("no-store", blok,
                      "sw.js zapisany w cache zaciąłby aplikację na starej wersji.")

    def test_rejestracja_pokazuje_pasek_aktualizacji(self):
        self.assertIn('navigator.serviceWorker.register("/sw.js"', PWA_JS)
        self.assertIn("PRZEJMIJ", PWA_JS)
        self.assertIn("controllerchange", PWA_JS)

    def test_przeladowanie_tylko_raz(self):
        self.assertIn("przeladowano", PWA_JS)

    def test_trasa_offline_i_lista_precache(self):
        self.assertIn('@app.route("/offline")', APP)
        self.assertIn('@app.route("/static/precache.json")', APP)


class TestDeklaracjeOffline(unittest.TestCase):
    """Interfejs nie może obiecywać offline przed przejściem testu w przeglądarce."""

    def test_brak_zdania_o_dzialaniu_offline(self):
        winne = []
        for plik in (KATALOG / "templates").glob("*.html"):
            if "działa offline" in plik.read_text(encoding="utf-8"):
                winne.append(plik.name)
        self.assertEqual(winne, [],
                         f"Szablony deklarują działanie offline: {winne}. "
                         "Zdanie wolno przywrócić dopiero po zielonym "
                         "tests/pwa_offline.spec.js.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
