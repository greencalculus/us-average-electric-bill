#!/usr/bin/env python3
"""
Build assets/data/elec-rates/recs-bill.json for [gc_elec_bill] (build plan row 166, average electric bill by state).

  python3 scripts/elec-rates/build-recs-bill-data.py --recs recs2020_public_v7.csv [--out assets/data/elec-rates/recs-bill.json]

Input: EIA's 2020 Residential Energy Consumption Survey public microdata, v7
  https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv
  18,496 homes, final weight NWEIGHT and 60 jackknife replicate weights NWEIGHT1..60.
  Standard error, from EIA's microdata guide (June 2023): V = (R-1)/R * sum_r (theta_r - theta)^2, R = 60.

What this file holds, and why it is shaped this way:
  RECS gives the SHAPE of bills (an apartment against the average home, July against the year, air conditioning
  against the rest). It is a 2020 survey and EIA warns that state estimates can be thin, so the LEVEL of every bill
  on the page comes from EIA-861M (revenue / customers, every utility), and RECS only supplies ratios:
    segments   bill of a group of homes / bill of all homes, in the same area (US and each of 10 RECS divisions)
    enduse     share of the electricity bill by end use (US, divisions, and states where precise enough)
    dist       percentiles of the bill relative to the state's own mean (for "where does my bill sit")
    check      RECS 2020 mean bill by state against EIA-861M 2020 bill per customer (shown on the page)
  A ratio is published only with n >= MIN_N homes and a relative standard error <= HIDE_RSE %; between FLAG_RSE and
  HIDE_RSE it is marked "less precise". Build scripts fail loudly: any missing column or empty group exits non-zero.

When the 2024 RECS consumption files arrive (EIA: spring 2027), re-run on them; the page reads the survey year from here.
"""
import argparse, csv, datetime as dt, json, math, os, sys

R = 60
MIN_N = 30
FLAG_RSE = 15.0
HIDE_RSE = 30.0
SRC_URL = 'https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata'
GUIDE_URL = 'https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf'

# End uses, from the DOLEL* columns. These 22 add up to DOLLAREL for every home (checked on build).
ENDUSE = [
    ('cooling', 'Air conditioning', ['COL', 'AHUCOL']),
    ('heating', 'Space heating', ['SPH', 'AHUHEAT']),
    ('water', 'Water heating', ['WTH']),
    ('fridge', 'Fridges and freezers', ['RFG', 'FRZ']),
    ('lighting', 'Lighting', ['LGT']),
    ('tv', 'TVs and devices with them', ['TVREL']),
    ('laundry', 'Washer and dryer', ['CW', 'CDR']),
    ('cooking', 'Cooking and microwave', ['COK', 'MICRO']),
    ('dish', 'Dishwasher', ['DWH']),
    ('fans', 'Fans, dehumidifiers, humidifiers', ['CFAN', 'DHUM', 'HUM']),
    ('pool', 'Pool and hot tub', ['PLPMP', 'HTBPMP', 'HTBHEAT']),
    ('ev', 'Electric car charging', ['EVCHRG']),
    ('other', 'Everything else', ['NEC']),
]


def num(r, c):
    v = r[c]
    return 0.0 if v in ('', '.') else float(v)


def house(r):
    return r['TYPEHUQ'] in ('2', '3')


def apt(r):
    return r['TYPEHUQ'] in ('4', '5')


def sqft_band(lo, hi):
    return lambda r: house(r) and lo <= num(r, 'SQFTEST') < hi


# Groups of homes the page compares. Each test reads one home's row.
SEGMENTS = [
    ('type', 'Type of home', [
        ('house', 'Detached house', lambda r: r['TYPEHUQ'] == '2'),
        ('town', 'Townhouse, duplex or row house', lambda r: r['TYPEHUQ'] == '3'),
        ('apt_small', 'Apartment, building of 2 to 4 units', lambda r: r['TYPEHUQ'] == '4'),
        ('apt_big', 'Apartment, building of 5 or more units', lambda r: r['TYPEHUQ'] == '5'),
        ('mobile', 'Mobile home', lambda r: r['TYPEHUQ'] == '1'),
    ]),
    ('apt_beds', 'Apartments by bedrooms', [
        ('studio', 'Studio', lambda r: apt(r) and r['STUDIO'] == '1'),
        ('b1', '1 bedroom', lambda r: apt(r) and r['STUDIO'] != '1' and r['BEDROOMS'] in ('0', '1')),
        ('b2', '2 bedrooms', lambda r: apt(r) and r['BEDROOMS'] == '2'),
        ('b3', '3 or more bedrooms', lambda r: apt(r) and int(r['BEDROOMS']) >= 3),
    ]),
    ('house_beds', 'Houses by bedrooms', [
        ('b12', '1 or 2 bedrooms', lambda r: house(r) and int(r['BEDROOMS']) <= 2),
        ('b3', '3 bedrooms', lambda r: house(r) and r['BEDROOMS'] == '3'),
        ('b4', '4 bedrooms', lambda r: house(r) and r['BEDROOMS'] == '4'),
        ('b5', '5 or more bedrooms', lambda r: house(r) and int(r['BEDROOMS']) >= 5),
    ]),
    ('house_sqft', 'Houses by size', [
        ('s0', 'Under 1,000 sq ft', sqft_band(0, 1000)),
        ('s1', '1,000 to 1,499 sq ft', sqft_band(1000, 1500)),
        ('s2', '1,500 to 1,999 sq ft', sqft_band(1500, 2000)),
        ('s3', '2,000 to 2,499 sq ft', sqft_band(2000, 2500)),
        ('s4', '2,500 to 2,999 sq ft', sqft_band(2500, 3000)),
        ('s5', '3,000 sq ft or more', sqft_band(3000, 1e9)),
    ]),
    ('people', 'People in the home', [
        ('p1', '1 person', lambda r: r['NHSLDMEM'] == '1'),
        ('p2', '2 people', lambda r: r['NHSLDMEM'] == '2'),
        ('p3', '3 people', lambda r: r['NHSLDMEM'] == '3'),
        ('p4', '4 people', lambda r: r['NHSLDMEM'] == '4'),
        ('p5', '5 or more people', lambda r: int(r['NHSLDMEM']) >= 5),
    ]),
    ('heat', 'Main heating', [
        ('elec', 'Heated by electricity', lambda r: r['FUELHEAT'] == '5'),
        ('gas', 'Heated by natural gas', lambda r: r['FUELHEAT'] == '1'),
        ('other', 'Heated by propane, oil, wood or other', lambda r: r['FUELHEAT'] in ('2', '3', '7', '99')),
        ('none', 'No heating', lambda r: r['FUELHEAT'] == '-2'),
    ]),
    ('tenure', 'Own or rent', [
        ('own', 'Owned', lambda r: r['KOWNRENT'] == '1'),
        ('rent', 'Rented', lambda r: r['KOWNRENT'] in ('2', '3')),
    ]),
]


class Home:
    __slots__ = ('r', 'w', 'bill', 'kwh', 'st', 'div')

    def __init__(self, r):
        self.r = r
        self.w = [float(r['NWEIGHT'])] + [float(r['NWEIGHT%d' % i]) for i in range(1, R + 1)]
        self.bill = float(r['DOLLAREL'])
        self.kwh = float(r['KWH'])
        self.st = r['state_postal']
        self.div = r['DIVISION']


def wsum(homes, val):
    s = [0.0] * (R + 1)
    for h in homes:
        v = val(h)
        if v:
            for i in range(R + 1):
                s[i] += h.w[i] * v
    return s


def se_of(th):
    return math.sqrt((R - 1) / R * sum((t - th[0]) ** 2 for t in th[1:]))


def mean_est(homes, val=lambda h: h.bill):
    """Weighted mean, full sample then each replicate. None when a replicate holds none of these homes: the
    error cannot be measured, so the group is too thin to publish."""
    S, W = wsum(homes, val), wsum(homes, lambda h: 1.0)
    if min(W) <= 0:
        return None
    return [S[i] / W[i] for i in range(R + 1)]


def ratio_est(seg, area):
    """Mean bill of seg / mean bill of area, replicate by replicate, so the error covers both."""
    a, b = mean_est(seg), mean_est(area)
    if a is None or b is None or min(b) <= 0:
        return None, None
    return [a[i] / b[i] for i in range(R + 1)], a


def gate(n, rse):
    if n < MIN_N or rse is None or rse > HIDE_RSE:
        return None
    return 'wide' if rse > FLAG_RSE else 'ok'


def rnd(v, dp):
    return None if v is None else round(v, dp)


def wquantiles(pairs, ps):
    """Weighted quantiles of (value, weight) pairs at fractions ps."""
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    out, acc, j = [], 0.0, 0
    for p in ps:
        target = p * tot
        while j < len(pairs) - 1 and acc + pairs[j][1] < target:
            acc += pairs[j][1]
            j += 1
        out.append(pairs[j][0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recs', required=True, help='recs2020_public_v7.csv')
    ap.add_argument('--rates', default='assets/data/elec-rates/elec-rates.json', help='for the EIA-861M 2020 check')
    ap.add_argument('--out', default='assets/data/elec-rates/recs-bill.json')
    a = ap.parse_args()

    with open(a.recs, newline='') as f:
        rd = csv.DictReader(f)
        need = ['NWEIGHT', 'DOLLAREL', 'KWH', 'TYPEHUQ', 'BEDROOMS', 'STUDIO', 'SQFTEST', 'NHSLDMEM', 'FUELHEAT', 'KOWNRENT',
                'state_postal', 'DIVISION'] + ['NWEIGHT%d' % i for i in range(1, R + 1)] + ['DOLEL' + c for _, _, cs in ENDUSE for c in cs]
        miss = [c for c in need if c not in rd.fieldnames]
        if miss:
            sys.exit('missing columns: %s' % miss)
        homes = [Home(r) for r in rd]
    if len(homes) < 15000:
        sys.exit('only %d homes read' % len(homes))

    # The end uses must add up to the total for every home, or the shares would not mean what they say.
    for h in homes:
        s = sum(num(h.r, 'DOLEL' + c) for _, _, cs in ENDUSE for c in cs)
        if abs(s - h.bill) > 1.0:
            sys.exit('end uses do not add up for home %s: %.2f vs %.2f' % (h.r.get('DOAEID') or h.r.get('DOEID'), s, h.bill))

    divs = sorted({h.div for h in homes})
    st_div = {}
    for h in homes:
        if st_div.setdefault(h.st, h.div) != h.div:
            sys.exit('state %s in two divisions' % h.st)
    areas = {'US': homes}
    for d in divs:
        areas[d] = [h for h in homes if h.div == d]
    by_state = {}
    for h in homes:
        by_state.setdefault(h.st, []).append(h)

    # Segments: ratio to the area's mean bill, US and each division.
    segs = []
    for gkey, glabel, items in SEGMENTS:
        rows = []
        for key, label, test in items:
            row = {'key': key, 'label': label, 'areas': {}}
            for ak, ah in areas.items():
                sub = [h for h in ah if test(h.r)]
                if not sub:
                    row['areas'][ak] = None
                    continue
                th, mean = ratio_est(sub, ah)
                if th is None:
                    row['areas'][ak] = None
                    continue
                rse = 100 * se_of(th) / th[0] if th[0] else None
                g = gate(len(sub), rse)
                kwh = mean_est(sub, lambda h: h.kwh)[0]
                row['areas'][ak] = None if g is None else {
                    'ratio': rnd(th[0], 4), 'rse': rnd(rse, 1), 'n': len(sub), 'q': g,
                    'bill2020': rnd(mean[0] / 12, 2), 'kwh2020': round(kwh / 12),
                    'share': rnd(100 * sum(h.w[0] for h in sub) / sum(h.w[0] for h in ah), 1),
                }
            if row['areas']['US'] is None:
                sys.exit('segment %s/%s fails at US level' % (gkey, key))
            rows.append(row)
        segs.append({'key': gkey, 'label': glabel, 'rows': rows})

    # End uses: share of the bill, by area and by state.
    def enduse_for(hs):
        tot = wsum(hs, lambda h: h.bill)
        out = {}
        for key, _, cs in ENDUSE:
            part = wsum(hs, lambda h, cs=cs: sum(num(h.r, 'DOLEL' + c) for c in cs))
            th = [100 * part[i] / tot[i] for i in range(R + 1)]
            se = se_of(th)
            rse = 100 * se / th[0] if th[0] > 0 else None
            out[key] = {'pct': rnd(th[0], 1), 'se': rnd(se, 1)} if th[0] > 0 and rse is not None and rse <= HIDE_RSE else None
        return out

    enduse = {'labels': {k: l for k, l, _ in ENDUSE}, 'areas': {}, 'states': {}}
    for ak, ah in areas.items():
        enduse['areas'][ak] = enduse_for(ah)
    for st, hs in sorted(by_state.items()):
        enduse['states'][st] = enduse_for(hs)

    # Where a bill sits in its state: percentiles of bill / state mean (2020), weighted.
    ps = [i / 20 for i in range(1, 20)]
    dist = {}
    for st, hs in sorted(by_state.items()):
        m = mean_est(hs)[0]
        dist[st] = {'n': len(hs), 'p': [round(v / m, 3) for v in wquantiles([(h.bill, h.w[0]) for h in hs], ps)]}
    m = mean_est(homes)[0]
    dist['US'] = {'n': len(homes), 'p': [round(v / m, 3) for v in wquantiles([(h.bill, h.w[0]) for h in homes], ps)]}

    # Check against EIA-861M 2020 (revenue / customers, every utility).
    with open(a.rates) as f:
        rates = json.load(f)

    def eia2020(ser):
        yr = [r for r in ser if r[0].startswith('2020-')]
        if len(yr) != 12:
            sys.exit('EIA-861M 2020 incomplete')
        return sum(r[3] for r in yr), sum(r[2] for r in yr)

    check = {}
    for st, hs in sorted(by_state.items()):
        th = mean_est(hs)
        eb, ek = eia2020(rates['states'][st])
        check[st] = {'recs': round(th[0]), 'rse': rnd(100 * se_of(th) / th[0], 1), 'n': len(hs), 'eia': round(eb), 'diff': rnd(100 * (th[0] / eb - 1), 1)}
    th = mean_est(homes)
    eb, ek = eia2020(rates['us'])
    kw = mean_est(homes, lambda h: h.kwh)[0]
    check['US'] = {'recs': round(th[0]), 'rse': rnd(100 * se_of(th) / th[0], 1), 'n': len(homes), 'eia': round(eb), 'diff': rnd(100 * (th[0] / eb - 1), 1),
                   'recs_kwh': round(kw), 'eia_kwh': round(ek)}

    out = {
        'schema': 'gc-elec-bill-recs/v1',
        'built': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'survey': 2020,
        'source': {'name': 'EIA Residential Energy Consumption Survey 2020, public microdata v7', 'url': SRC_URL, 'guide': GUIDE_URL,
                   'homes': len(homes), 'replicates': R},
        'rules': {'min_n': MIN_N, 'flag_rse': FLAG_RSE, 'hide_rse': HIDE_RSE},
        'state_division': st_div,
        'segments': segs,
        'enduse': enduse,
        'dist': {'ps': [int(p * 100) for p in ps], 'states': dist},
        'check': check,
    }
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    tmp = a.out + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    os.replace(tmp, a.out)
    print('wrote %s (%d bytes): %d homes, %d segment groups, US check RECS $%d vs EIA $%d (%+.1f%%)' % (
        a.out, os.path.getsize(a.out), len(homes), len(segs), check['US']['recs'], check['US']['eia'], check['US']['diff']))


if __name__ == '__main__':
    main()
