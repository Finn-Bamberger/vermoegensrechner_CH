import json, os, re, shutil, sys, html as _html
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
 'etf': ('ETF-Tracker: 26 beliebte ETFs mit Kursverlauf | Vermögensrechner',
         'Kurse und Kursverlauf von 26 beliebten ETFs, darunter VTI, VOO, QQQ, GLD sowie Schweizer und europäische Fonds.'),
 'methodik': ('Methodik und Annahmen | Vermögensrechner',
              'Wie die Rechner arbeiten: Annahmen, Steuerlogik der Säule 3a, Datenquellen und Grenzen des Anbieter-Vergleichs.'),
 'datenschutz': ('Datenschutz | Vermögensrechner', 'Welche Daten bei der Nutzung anfallen und wohin sie gehen.'),
 'impressum': ('Impressum | Vermögensrechner', 'Angaben zum Betreiber der Seite.'),
}
# zentrale Angaben für Impressum und Datenschutz (config.json)
CFG = json.load(open(os.path.join(BASE, 'config.json'), encoding='utf-8'))
MISSING = []
CFG_LABELS = {'name': 'Vor- und Nachname bzw. Firma', 'strasse': 'Strasse und Nummer', 'plzort': 'PLZ Ort', 'email': 'E-Mail-Adresse', 'datenschutz_stand': 'Datum (Stand der Datenschutzerklärung)'}
def cfg_sub(m):
    k = m.group(1)
    v = (CFG.get(k) or '').strip()
    if not v or v.startswith('['):
        if k not in MISSING: MISSING.append(k)
        return '<span class="todo">[%s eintragen]</span>' % CFG_LABELS.get(k, k)
    return _html.escape(v)
tpl = re.sub(r'\{\{(\w+)\}\}', cfg_sub, tpl)
full = tpl.replace('// MODEL-PLACEHOLDER', model)
full = full.replace('/*META-JSON*/{}', json.dumps({k: {'title': v[0], 'description': v[1]} for k, v in META.items()}, ensure_ascii=False))
cut = full.index('<header class="site">')
head, body = full[:cut], full[cut:]
head = re.sub(r'<title>.*?</title>\n', '', head, count=1)

FAQ = {
 'btc': [
  ('Wie wird der Kurs berechnet?', 'Der aktuelle Kurs und der Verlauf bis zwei Jahre stammen von der Börse Kraken (Bitcoin in Franken). Für fünf und zehn Jahre sowie «Max» werden Tagesdurchschnittspreise in US-Dollar von Blockchain.info mit den EZB-Devisenkursen der Frankfurter-Schnittstelle in Franken umgerechnet. Die Werte können deshalb von dem Kurs abweichen, den dir ein Anbieter anzeigt.'),
  ('Bitcoin in der Schweiz: Wie wird er besteuert?', 'Bitcoin zählt in der Schweiz in der Regel zum steuerbaren Vermögen und wird mit dem Kurs am Jahresende in der Steuererklärung deklariert. Private Kursgewinne sind für Privatanleger in der Regel steuerfrei; ob jemand als gewerbsmässiger Händler gilt, entscheidet die Steuerbehörde im Einzelfall. Massgebend sind das Recht deines Kantons und dein Einzelfall. Die Eidgenössische Steuerverwaltung veröffentlicht dazu jährlich eine Kursliste mit Jahresendkursen für Kryptowährungen.'),
 ],
}

def faq_html(key):
    if key not in FAQ: return ''
    return ''.join('<h2>%s</h2>\n<p>%s</p>\n' % (q, a) for q, a in FAQ[key])

def jsonld(key):
    import json as _j
    objs = []
    if key == 'start':
        objs.append({'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'Vermögensrechner', 'url': SITE + '/', 'inLanguage': 'de-CH'}
                    | ({'publisher': {'@type': 'Person' if not CFG.get('firma') else 'Organization', 'name': CFG['name'].strip()}} if (CFG.get('name') or '').strip() and not CFG['name'].strip().startswith('[') else {}))
    if key in FAQ:
        objs.append({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in FAQ[key]]})
    return ''.join('<script type="application/ld+json">%s</script>\n' % _j.dumps(o, ensure_ascii=False) for o in objs)

def strip_inactive(html, key):
    # entfernt alle <section id="p-xxx"> ausser der aktiven (mit Tiefenzählung, da Sektionen verschachtelt sein können)
    out, i = [], 0
    pat = re.compile(r'<section id="p-(\w+)"[^>]*>')
    while True:
        m = pat.search(html, i)
        if not m:
            out.append(html[i:]); break
        out.append(html[i:m.start()])
        depth, j = 1, m.end()
        tok = re.compile(r'<section\b|</section>')
        while depth:
            t = tok.search(html, j)
            depth += 1 if t.group() != '</section>' else -1
            j = t.end()
        if m.group(1) == KEY[0]:
            out.append(html[m.start():j].replace(m.group(0), '<section id="p-%s">' % m.group(1), 1))
        i = j
    return ''.join(out)
KEY = [None]

def page(key):
    title, desc = META[key]
    b = body
    def sec(m):
        return '<section id="p-%s"%s>' % (m.group(1), '' if m.group(1) == key else ' hidden')
    KEY[0] = key
    b = b.replace('<!--FAQ-' + key + '-->', faq_html(key))
    b = strip_inactive(b, key)
    pre = ''.join('<link rel="preload" href="/fonts/%s" as="font" type="font/woff2" crossorigin>\n' % f for f in
                  ('instrument-sans-latin-wght-normal-v2.woff2', 'bricolage-grotesque-latin-wght-normal-v2.woff2'))
    url = SITE + PATHS[key]
    head_tags = (
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<title>%(t)s</title>\n<meta name="description" content="%(d)s">\n'
        '<link rel="canonical" href="%(u)s">\n<meta property="og:url" content="%(u)s">\n'
        '<meta property="og:title" content="%(t)s">\n<meta property="og:description" content="%(d)s">\n<meta property="og:type" content="website">\n'
        '<meta property="og:image" content="%(s)s/og.png">\n<meta property="og:locale" content="de_CH">\n'
        '<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="%(t)s">\n'
        '<meta name="twitter:description" content="%(d)s">\n<meta name="twitter:image" content="%(s)s/og.png">\n'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n<meta name="theme-color" content="#0B5D5A">\n'
    ) % {'t': title, 'd': desc, 'u': url, 's': SITE}
    return ('<!doctype html>\n<html lang="de-CH">\n<head>\n' + head_tags + jsonld(key) + pre +
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

if MISSING:
    msg = 'ACHTUNG: In config.json fehlen Angaben für Impressum und Datenschutz: ' + ', '.join(CFG_LABELS.get(k, k) for k in MISSING)
    print('\n' + '!' * 70 + '\n' + msg + '\nDie Seiten zeigen dort noch rote Platzhalter. Vor der Veröffentlichung ausfüllen.\n' + '!' * 70)
    if '--strict' in sys.argv:
        sys.exit(1)
