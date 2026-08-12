# -*- coding: utf-8 -*-
"""Kontrola spójności bazy kodów usterek (załącznik nr 1).

Pilnuje skutków błędu wykrytego 2026-08-12: krzyżyk oceny bywa złożony
1–2 pkt wyżej niż opis usterki, przez co przy kubełkowaniu linii trafiał
do sąsiedniej linii — ocena przyklejała się do poprzedniej usterki albo
ginęła jako duplikat.

Uruchomienie:
    python -m unittest discover -s tests -p "test_*.py" -v
"""
import json
import unittest
from pathlib import Path

KATALOG = Path(__file__).resolve().parent.parent / "data" / "kody_usterek"
REKORDY = json.loads((KATALOG / "periodic_defects.json").read_text(encoding="utf-8"))["records"]
WG_KODU = {r["code"]: r for r in REKORDY}
DOZWOLONE = {"UD", "UP", "UN"}


class TestKompletnoscOcen(unittest.TestCase):

    def test_kazdy_rekord_ma_co_najmniej_jedna_kategorie(self):
        """Rekord bez kategorii oznacza zgubiony krzyżyk, nie brak w źródle."""
        puste = [r["code"] for r in REKORDY if not r["assessment_options"]]
        self.assertEqual(puste, [], f"Rekordy bez kategorii: {puste}")

    def test_kategorie_sa_z_zamknietej_listy(self):
        zle = sorted({o["severity_code"] for r in REKORDY
                      for o in r["assessment_options"]} - DOZWOLONE)
        self.assertEqual(zle, [], f"Nieznane kategorie: {zle}")

    def test_priorytet_zgadza_sie_z_kategoria(self):
        oczekiwany = {"UD": 1, "UP": 2, "UN": 3}
        for r in REKORDY:
            for o in r["assessment_options"]:
                self.assertEqual(o["priority"], oczekiwany[o["severity_code"]],
                                 f"{r['code']}: priorytet nie pasuje do kategorii")

    def test_wszystkie_rekordy_zweryfikowane(self):
        czesciowe = [r["code"] for r in REKORDY
                     if r["verification_status"] != "verified"]
        self.assertEqual(czesciowe, [],
                         f"Rekordy niezweryfikowane: {czesciowe}")

    def test_kody_sa_unikalne(self):
        self.assertEqual(len(WG_KODU), len(REKORDY), "W bazie są zduplikowane kody.")


class TestPrzypadkiKontrolne(unittest.TestCase):
    """Wartości odczytane ręcznie z PDF (Dz.U. 2024 poz. 141, załącznik nr 1)."""

    WZORCE = {
        "6.2.11.a": ["UP"],   # s. 51, krzyżyk y=175, pasmo UP
        "6.2.11.b": ["UP"],   # s. 51, krzyżyk y=192, pasmo UP
        "6.2.11.c": ["UN"],   # s. 51, krzyżyk y=211, pasmo UN
        "1.1.21.b": ["UD", "UP"],   # s. 20, krzyżyki y=287 (UD) i y=306 (UP)
    }

    def test_kategorie_zgodne_ze_zrodlem(self):
        for kod, oczekiwane in self.WZORCE.items():
            self.assertIn(kod, WG_KODU, f"Brak rekordu {kod}")
            mamy = [o["severity_code"] for o in WG_KODU[kod]["assessment_options"]]
            self.assertEqual(mamy, oczekiwane, f"{kod}: kategorie rozjechały się ze źródłem")

    def test_warunki_wielowariantowe_sa_opisane(self):
        """Przy kilku kategoriach użytkownik musi wiedzieć, kiedy którą wybrać."""
        for kod in ("1.1.11.b", "1.1.21.b", "7.3.b"):
            warunki = [o["condition"] for o in WG_KODU[kod]["assessment_options"]]
            self.assertTrue(all(warunki),
                            f"{kod}: wariant bez warunku — nie da się wybrać kategorii")


if __name__ == "__main__":
    unittest.main(verbosity=2)
