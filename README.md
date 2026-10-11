# Vermögensrechner

Statische Seite (Vercel). Quelltext liegt in `src/`, die fertigen Seiten werden daraus gebaut.

- `src/vermoegensrechner.template.html` – gesamte Seite (CSS, HTML, JS), **hier ändern**
- `src/model.js` – Monte-Carlo-Modell (wird in die Vorlage eingefügt)
- `anbieter.json` – Daten des 3a-Anbietervergleichs (von Hand pflegen, Datum `stand` anpassen)
- `build.py` – erzeugt `index.html`, `zinseszins/`, `sparplan/`, `saeule-3a/`, `bitcoin/`, `etf/`, `methodik/`, `datenschutz/`, `impressum/`, `vercel.json`, `robots.txt`

Bauen: `python3 build.py`, danach committen und pushen. Vercel deployt automatisch.
Lokal ansehen: `python3 -m http.server 8000`, dann http://localhost:8000
Die `index.html`-Dateien sind generiert – nie von Hand ändern.
