#!/usr/bin/env python3
"""Holt Berichte und Kennzahlen von SEC EDGAR und schreibt data/<aktie>.json.

Aufruf:  SEC_USER_AGENT="Vorname Nachname kontakt@beispiel.ch" python3 scripts/update_aktien.py
Die SEC verlangt einen User-Agent mit Kontaktangabe (https://www.sec.gov/os/accessing-edgar-data).
Es werden nur öffentliche, kostenlose SEC-Schnittstellen verwendet (maximal wenige Abrufe pro Lauf).
"""
import json, os, sys, time, datetime, re, urllib.request
import xml.etree.ElementTree as ET

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
    'gross_profit': ['GrossProfit'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets'],
    'sbc': ['ShareBasedCompensation'],
}
# Durchschnittliche Aktienzahl (verwässert): nur direkt gemeldete Zeiträume, keine Ableitung
SHARE_TAGS = ['WeightedAverageNumberOfDilutedSharesOutstanding']
# Stichtagswerte (Bilanz)
INSTANT_TAGS = {
    'cash': ['CashAndCashEquivalentsAtCarryingValue'],
    'securities': ['MarketableSecuritiesCurrent', 'AvailableForSaleSecuritiesDebtSecuritiesCurrent', 'ShortTermInvestments'],
    'debt': ['LongTermDebt', 'LongTermDebtNoncurrent', 'ConvertibleNotesPayable', 'DebtInstrumentCarryingAmount'],
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url, ua):
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode('utf-8'))


def months(start, end):
    d = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days
    return round(d / 30.44)


def series(facts, tags, unit='USD', derive=True):
    """Liefert (quartale, jahre) als dict end -> Wert. Q4 und Cashflow werden aus Jahres-/Kumulativwerten abgeleitet."""
    ug = facts.get('facts', {}).get('us-gaap', {})
    for tag in tags:
        units = ug.get(tag, {}).get('units', {}).get(unit)
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
        for (s, en), v in (vals.items() if derive else []):  # abgeleitete Quartale: kumuliert minus Vorperiode mit gleichem Start
            m = months(s, en)
            if m in (6, 9, 12) and en not in quarters:
                prev = [(e2, v2) for (s2, e2), v2 in vals.items() if s2 == s and months(s2, e2) == m - 3]
                if prev:
                    quarters[en] = v - prev[0][1]
        return quarters, years
    return {}, {}


def instant(facts, tags):
    """Stichtagswerte: end -> Wert (zuletzt gemeldeter Wert pro Stichtag, nur 10-Q/10-K)."""
    ug = facts.get('facts', {}).get('us-gaap', {})
    for tag in tags:
        units = ug.get(tag, {}).get('units', {}).get('USD')
        if not units:
            continue
        best = {}
        for e in units:
            if e.get('form') not in ('10-Q', '10-K', '10-K/A', '10-Q/A') or 'start' in e:
                continue
            if e['end'] not in best or e.get('filed', '') >= best[e['end']][0]:
                best[e['end']] = (e.get('filed', ''), e['val'])
        if best:
            return {k: v[1] for k, v in best.items()}
    return {}


def shares_outstanding(facts):
    """Summe aller Aktienklassen laut Titelseite des neusten Berichts (dei:EntityCommonStockSharesOutstanding)."""
    units = facts.get('facts', {}).get('dei', {}).get('EntityCommonStockSharesOutstanding', {}).get('units', {}).get('shares', [])
    units = [e for e in units if e.get('form') in ('10-Q', '10-K')]
    if not units:
        return None
    last = max(e.get('filed', '') for e in units)
    sel = [e for e in units if e.get('filed') == last]
    return {'shares': sum(e['val'] for e in sel), 'as_of': max(e['end'] for e in sel), 'filed': last}


def price(ticker):
    """Letzter Kurs (USD). Quelle: Stooq, ersatzweise Yahoo Finance. Gibt None zurück, wenn beides scheitert."""
    tries = [
        ('Stooq', 'https://stooq.com/q/l/?s=%s.us&f=sd2t2c&h&e=csv' % ticker.lower(), lambda t: (lambda c: (float(c[3]), c[1]))(t.strip().splitlines()[1].split(','))),
        ('Yahoo Finance', 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d' % ticker,
         lambda t: (lambda m: (float(m['regularMarketPrice']), datetime.datetime.fromtimestamp(m['regularMarketTime'], datetime.timezone.utc).strftime('%Y-%m-%d')))(json.loads(t)['chart']['result'][0]['meta'])),
    ]
    for name, url, parse in tries:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                val, day = parse(r.read().decode('utf-8'))
            if val > 0:
                return {'price': val, 'date': day, 'source': name}
        except Exception as ex:
            print('Kurs von %s nicht verfügbar: %s' % (name, ex), file=sys.stderr)
    return None


def form4(sub, cik, ua, old):
    """Insider-Transaktionen aus Form 4. Bereits bekannte Meldungen werden aus der alten Datei übernommen."""
    rec = sub['filings']['recent']
    known = {t['acc']: t for t in old.get('insiders', [])}
    out, fetched = [], 0
    today = datetime.date.today()
    for i, form in enumerate(rec['form']):
        if form != '4':
            continue
        if (today - datetime.date.fromisoformat(rec['filingDate'][i])).days > 400:
            break
        acc = rec['accessionNumber'][i]
        if acc in known or any(t['acc'] == acc for t in out):
            continue
        if fetched >= 60:
            break
        doc = rec['primaryDocument'][i].split('/')[-1]
        url = 'https://www.sec.gov/Archives/edgar/data/%d/%s/%s' % (int(cik), acc.replace('-', ''), doc)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': ua})
            with urllib.request.urlopen(req, timeout=40) as r:
                root = ET.fromstring(r.read())
        except Exception as ex:
            print('Form 4 nicht lesbar', acc, ex, file=sys.stderr)
            continue
        fetched += 1
        time.sleep(0.25)
        name = (root.findtext('.//reportingOwner/reportingOwnerId/rptOwnerName') or '').strip()
        rel = root.find('.//reportingOwner/reportingOwnerRelationship')
        role = ''
        if rel is not None:
            if rel.findtext('isOfficer') in ('1', 'true'):
                role = (rel.findtext('officerTitle') or 'Officer').strip()
            elif rel.findtext('isDirector') in ('1', 'true'):
                role = 'Director'
            elif rel.findtext('isTenPercentOwner') in ('1', 'true'):
                role = '10%-Aktionär'
        plan = bool(re.search(r'10b5-1', ET.tostring(root, encoding='unicode')))
        for tr in root.findall('.//nonDerivativeTable/nonDerivativeTransaction'):
            try:
                code = tr.findtext('.//transactionCoding/transactionCode')
                sh = float(tr.findtext('.//transactionAmounts/transactionShares/value') or 0)
                pr = tr.findtext('.//transactionAmounts/transactionPricePerShare/value')
                ad = tr.findtext('.//transactionAmounts/transactionAcquiredDisposedCode/value')
                out.append({'acc': acc, 'date': tr.findtext('.//transactionDate/value')[:10], 'name': name, 'role': role,
                            'code': code, 'shares': sh, 'price': float(pr) if pr else None, 'ad': ad, 'plan_10b5_1': plan,
                            'url': 'https://www.sec.gov/Archives/edgar/data/%d/%s/' % (int(cik), acc.replace('-', ''))})
            except Exception:
                continue
    merged = out + list(old.get("insiders", []))
    cutoff = (today - datetime.timedelta(days=400)).isoformat()
    merged = [t for t in merged if t['date'] >= cutoff]
    merged.sort(key=lambda t: t['date'], reverse=True)
    return merged


def build(stock, ua, old=None):
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
    sq, sy = series(facts, SHARE_TAGS, unit='shares', derive=False)
    for end, v in sq.items():
        q.setdefault(end, {})['diluted_shares'] = v
    for end, v in sy.items():
        y.setdefault(end, {})['diluted_shares'] = v
    bs = {}
    for key, tags in INSTANT_TAGS.items():
        for end, v in instant(facts, tags).items():
            bs.setdefault(end, {})[key] = v
    for end, v in bs.items():
        if end in q:
            q[end].update(v)
        if end in y:
            y[end].update(v)
    quarters = [dict(end=e, **v) for e, v in sorted(q.items())][-24:]
    annual = [dict(end=e, **v) for e, v in sorted(y.items())][-10:]
    return {
        'company': sub.get('name'), 'cik': cik, 'ticker': stock['ticker'], 'source': 'SEC EDGAR',
        'fiscal_year_end': sub.get('fiscalYearEnd'),
        'updated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'filings': filings, 'quarters': quarters, 'annual': annual,
        'shares_outstanding': shares_outstanding(facts),
        'quote': price(stock['ticker']),
        'insiders': form4(sub, cik, ua, old or {}),
    }


def main():
    ua = os.environ.get('SEC_USER_AGENT', '').strip()
    if '@' not in ua:
        sys.exit('SEC_USER_AGENT fehlt: Bitte "Name kontakt@adresse" setzen (die SEC verlangt eine Kontaktangabe).')
    changed = False
    for st in STOCKS:
        path = os.path.join(ROOT, 'data', st['file'] + '.json')
        old = {}
        try:
            old = json.load(open(path, encoding='utf-8'))
        except Exception:
            pass
        new = build(st, ua, old)
        oq, nq = old.get('quote'), new.get('quote')
        if nq is None and oq:
            new['quote'] = oq
        elif nq and oq and nq.get('date') == oq.get('date'):
            new['quote'] = oq  # pro Handelstag nur einmal speichern, damit nicht ständig neu veröffentlicht wird
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
