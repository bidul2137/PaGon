# Kwarantanna danych

Pliki w tym katalogu **nie są danymi aplikacji**. Nie czyta ich żaden endpoint
ani szablon i nie trafiają do repozytorium (`.gitignore`).

## additional_inspection.json — załącznik nr 2, dodatkowe badanie techniczne

Zbiór odrzucony przy weryfikacji importu z 11.08.2026.

Powód: dział I załącznika nr 2 ma tę samą budowę kolumn co załącznik nr 1, ale
**nie oznacza usterek literami** — część numeruje cyframi, część nie ma żadnego
oznacznika. Parser napisany pod załącznik nr 1 dzieli je błędnie.

Skutki widoczne w danych:

- 31 rekordów zamiast pełnego wykazu;
- 8 rekordów bez kategorii UD/UP/UN;
- duplikaty kodów `1.1.2.1` i `1.2.1`;
- opisy porozrywane na fragmenty (rekord `1.1.1` = „wyrywkowo śrub lub nakrętek.”).

Plik zachowano w całości jako materiał do poprawienia parsera. Do czasu ponownego
importu i weryfikacji **nie wolno go podłączać do aplikacji** — pokazywałby
funkcjonariuszowi niekompletne i błędnie sklasyfikowane usterki.

Dział II załącznika nr 2 (ustalanie danych technicznych) nie jest tabelą usterek
i wymaga osobnej struktury danych.
