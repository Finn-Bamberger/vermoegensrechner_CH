#!/usr/bin/env python3
"""Holt Berichte und Kennzahlen von SEC EDGAR und schreibt data/<aktie>.json.

Aufruf:  SEC_USER_AGENT="Vorname Nachname kontakt@beispiel.ch" python3 scripts/update_aktien.py
Die SEC verlangt einen User-Agent mit Kontaktangabe (https://www.sec.gov/os/accessing-edgar-data).
Es werden nur öffentliche, kostenlose SEC-Schnittstellen verwendet (maximal wenige Abrufe pro Lauf).
"""
import json, os, sys, time, datetime, urllib.request

STOCKS = [
    {'file': 'palantir', 'cik': '0001321655', 'ticker': 'PLTR'},
]
FORMS = ('10-K', '10-K/A', '10-Q', '10-Q/A', '8-K')
# Kennzahl -> mögliche XBRL-Tags (erster Tag mit Daten gewinnt)
TAGS = {
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'],
    'operating_income': ['OperatingIncomeLoss'],
    'net_income': ['NetIncomeLoss', 'ProfitLoss'],
    'op_cash_flow': ['NetCashProvidedByUsedInOperatingActivities'],
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url, ua):
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode('utf-8'))


def months(start, end):
    d = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days
    return round(d / 30.44)


def series(facts, tags):
    """Liefert (quartale, jahre) als dict end -> Wert. Q4 und Cashflow werden aus Jahres-/Kumulativwerten abgeleitet."""
    ug = facts.get('facts', {}).get('us-gaap', {})
    for tag in tags:
        units = ug.get(tag, {}).get('units', {}).get('USD')
        if not units:
            continue
        best = {}  # (start,end) -> (filed, val)
        for e in units:
            if e.get('form') not in ('10-Q', '10-K', '10-K/A', '10-Q/A') or 'start' not in e:
                continue
            k = (e['start'], e['end'])
            if k not in best or e.get('filed', '') >= best[k][0]:
                best[k] = (e.get('filed', ''), e['val'])
        vals = {k: v[1] for k, v in best.items()}
        quarters, years = {}, {}
        for (s, en), v in vals.items():
            m = months(s, en)
            if m == 3:
                quarters[en] = v
            elif m == 12:
                years[en] = v
        for (s, en), v in vals.items():  # abgeleitete Quartale: kumuliert minus Vorperiode mit gleichem Start
            m = months(s, en)
            if m in (6, 9, 12) and en not in quarters:
                prev = [(e2, v2) for (s2, e2), v2 in vals.items() if s2 == s and months(s2, e2) == m - 3]
                if prev:
                    quarters[en] = v - prev[0][1]
        return quarters, years
    return {}, {}


def build(stock, ua):
    cik = stock['cik']
    sub = get('https://data.sec.gov/submissions/CIK%s.json' % cik, ua)
    time.sleep(0.5)
    facts = get('https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json' % cik, ua)
    rec = sub['filings']['recent']
    filings = []
    for i, form in enumerate(rec['form']):
        if form not in FORMS:
            continue
        acc = rec['accessionNumber'][i]
        nod = acc.replace('-', '')
        doc = rec['primaryDocument'][i]
        base = 'https://www.sec.gov/Archives/edgar/data/%d/%s' % (int(cik), nod)
        filings.append({
            'form': form, 'date': rec['filingDate'][i], 'report_date': rec['reportDate'][i] or None,
            'items': rec.get('items', [''] * len(rec['form']))[i] or '',
            'doc_url': base + '/' + doc if doc else None,
            'index_url': '%s/%s-index.htm' % (base, acc),
        })
    filings = filings[:40]
    q, y = {}, {}
    for key, tags in TAGS.items():
        qq, yy = series(facts, tags)
        for end, v in qq.items():
            q.setdefault(end, {})[key] = v
        for end, v in yy.items():
            y.setdefault(end, {})[key] = v
    quarters = [dict(end=e, **v) for e, v in sorted(q.items())][-12:]
    annual = [dict(end=e, **v) for e, v in sorted(y.items())][-6:]
    return {
        'company': sub.get('name'), 'cik': cik, 'ticker': stock['ticker'], 'source': 'SEC EDGAR',
        'fiscal_year_end': sub.get('fiscalYearEnd'),
        'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'filings': filings, 'quarters': quarters, 'annual': annual,
    }


def main():
    ua = os.environ.get('SEC_USER_AGENT', '').strip()
    if '@' not in ua:
        sys.exit('SEC_USER_AGENT fehlt: Bitte "Name kontakt@adresse" setzen (die SEC verlangt eine Kontaktangabe).')
    changed = False
    for st in STOCKS:
        path = os.path.join(ROOT, 'data', st['file'] + '.json')
        new = build(st, ua)
        old = {}
        try:
            old = json.load(open(path, encoding='utf-8'))
        except Exception:
            pass
        # nur schreiben, wenn sich Inhalt (ausser Zeitstempel) geändert hat
        a = dict(old); a.pop('updated_at', None)
        b = dict(new); b.pop('updated_at', None)
        if a != b or not old.get('updated_at'):
            json.dump(new, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            changed = True
            print('aktualisiert:', path)
        else:
            print('unverändert:', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
