import json, os, re, shutil
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = BASE  # Ausgabe direkt im Repo-Root
old = open(os.path.join(BASE, 'src', 'model.js'), encoding='utf-8').read()
model = old.strip('\n')
tpl = open(os.path.join(BASE, 'src', 'vermoegensrechner.template.html'), encoding='utf-8').read()
assert '// MODEL-PLACEHOLDER' in tpl and '/*META-JSON*/{}' in tpl

SITE = 'https://vermoegensrechner-five.vercel.app'  # bei eigener Domain hier anpassen
PATHS = {'start': '/', 'zins': '/zinseszins/', 'sparplan': '/sparplan/', 'drei': '/saeule-3a/', 'btc': '/bitcoin/',
         'etf': '/etf/', 'methodik': '/methodik/', 'datenschutz': '/datenschutz/', 'impressum': '/impressum/'}
META = {
 'start': ('Vermögensrechner: Zinseszins, Sparplan, Säule 3a, Bitcoin und ETFs',
           'Gratis-Rechner für die Schweiz: Zinseszins, Sparplan-Simulation, Säule 3a mit Steuern und Anbieter-Vergleich, Bitcoin-Kurs und ETF-Tracker.'),
 'zins': ('Zinseszins-Rechner mit Teuerung und Kaufkraft | Vermögensrechner',
          'Zinseszins rechnen: Endkapital, Zinsanteil und Kaufkraft nach Teuerung, mit Jahrestabelle. Gratis für die Schweiz.'),
 'sparplan': ('Sparplan-Simulation mit Monte-Carlo | Vermögensrechner',
              'Wie wahrscheinlich erreichst du dein Sparziel? 10\'000 simulierte Börsenverläufe, nach Gebühren und Teuerung, in heutigen Franken.'),
 'drei': ('Säule 3a: Steuern, Break-even und Anbieter-Vergleich | Vermögensrechner',
          'Lohnt sich die Säule 3a? Vergleich mit dem freien Depot nach Steuern, Szenarien, Break-even sowie Gebühren und Konditionen der 3a-Anbieter in der Schweiz.'),
 'btc': ('Bitcoin-Kurs in CHF mit Kurshistorie bis 10 Jahre | Vermögensrechner',
         'Aktueller Bitcoin-Kurs in Schweizer Franken und Kursverlauf von einem Tag bis zehn Jahre.'),
 'etf': ('ETF-Tracker: 24 beliebte ETFs mit Kursverlauf | Vermögensrechner',
         'Kurse und Kursverlauf von 24 beliebten ETFs, darunter VTI, VOO, QQQ, GLD sowie Schweizer und europäische Fonds.'),
 'methodik': ('Methodik und Annahmen | Vermögensrechner',
              'Wie die Rechner arbeiten: Annahmen, Steuerlogik der Säule 3a, Datenquellen und Grenzen des Anbieter-Vergleichs.'),
 'datenschutz': ('Datenschutz | Vermögensrechner', 'Welche Daten bei der Nutzung anfallen und wohin sie gehen.'),
 'impressum': ('Impressum | Vermögensrechner', 'Angaben zum Betreiber der Seite.'),
}
full = tpl.replace('// MODEL-PLACEHOLDER', model)
full = full.replace('/*META-JSON*/{}', json.dumps({k: {'title': v[0], 'description': v[1]} for k, v in META.items()}, ensure_ascii=False))
cut = full.index('<header class="site">')
head, body = full[:cut], full[cut:]
head = re.sub(r'<title>.*?</title>\n', '', head, count=1)

def page(key):
    title, desc = META[key]
    b = body
    def sec(m):
        return '<section id="p-%s"%s>' % (m.group(1), '' if m.group(1) == key else ' hidden')
    b = re.sub(r'<section id="p-(\w+)"(?: hidden)?>', sec, b)
    pre = ''.join('<link rel="preload" href="/fonts/%s" as="font" type="font/woff2" crossorigin>\n' % f for f in
                  ('instrument-sans-latin-wght-normal.woff2', 'bricolage-grotesque-latin-wght-normal.woff2'))
    return ('<!doctype html>\n<html lang="de-CH">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<title>%s</title>\n<meta name="description" content="%s">\n'
            '<link rel="canonical" href="%s">\n<meta property="og:url" content="%s">\n<meta property="og:title" content="%s">\n<meta property="og:description" content="%s">\n<meta property="og:type" content="website">\n'
            '<meta name="theme-color" content="#0B5D5A">\n' % (title, desc, SITE + PATHS[key], SITE + PATHS[key], title, desc) + pre +
            '<style>html{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
            + head + '</head>\n<body data-page="%s">\n' % key + b.rstrip() +
            '\n<noscript><p style="padding:16px">Für die Rechner wird JavaScript benötigt.</p></noscript>\n</body>\n</html>\n')

for key, path in PATHS.items():
    d = os.path.join(OUT, path.strip('/'))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(page(key))

open(os.path.join(OUT, 'vercel.json'), 'w').write(json.dumps({
    'trailingSlash': True,
    'headers': [{'source': '/(.*)', 'headers': [
        {'key': 'X-Content-Type-Options', 'value': 'nosniff'},
        {'key': 'Referrer-Policy', 'value': 'strict-origin-when-cross-origin'}]},
        {'source': '/fonts/(.*)', 'headers': [{'key': 'Cache-Control', 'value': 'public, max-age=31536000, immutable'}]}]}, indent=2))
open(os.path.join(OUT, 'robots.txt'), 'w').write('User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n' % SITE)
open(os.path.join(OUT, 'sitemap.xml'), 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    ''.join('  <url><loc>%s%s</loc></url>\n' % (SITE, v) for v in PATHS.values()) + '</urlset>\n')
print('gebaut', {k: len(page(k)) for k in PATHS})
