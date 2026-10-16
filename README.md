# Vermögensrechner

Statische Seite (Vercel). Quelltext liegt in `src/`, die fertigen Seiten werden daraus gebaut.

- `src/vermoegensrechner.template.html` – gesamte Seite (CSS, HTML, JS), **hier ändern**
- `src/model.js` – Monte-Carlo-Modell (wird in die Vorlage eingefügt)
- `data/aktien/` – Firmenliste (`universe.json`) und automatisch erzeugte Firmendaten; `scripts/update_aktien.py` und `.github/workflows/aktien.yml` aktualisieren sie von SEC EDGAR
- `build.py` – erzeugt `index.html`, `zinseszins/`, `bitcoin/`, `etf/`, `methodik/`, `datenschutz/`, `impressum/`, `vercel.json`, `robots.txt`

Bauen: `python3 build.py`, danach committen und pushen. Vercel deployt automatisch.
Lokal ansehen: `python3 -m http.server 8000`, dann http://localhost:8000
Die `index.html`-Dateien sind generiert – nie von Hand ändern.
