#!/usr/bin/env python3
"""Builds the tables in this dataset from the two source files in source/.

  source/elec-rates.json  EIA-861M monthly residential revenue, sales and customers by state, as read by
                          GreenCalculus (fields: month, price_cents_per_kwh, kwh_per_customer, bill_usd_per_customer)
  source/recs-bill.json   ratios, end-use shares, bill spread and the survey check, built from EIA's RECS 2020
                          public microdata by scripts/build-recs-bill-data.py (60 jackknife replicate weights)

  python3 build.py        writes the four CSVs below and datapackage.json

average-electric-bill-by-state.csv and average-electric-bill-by-home.csv are written by the live page's refresh
(greencalculus.com) from the same two files and copied here unchanged.
"""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
rates = json.load(open(os.path.join(HERE, 'source', 'elec-rates.json')))
recs = json.load(open(os.path.join(HERE, 'source', 'recs-bill.json')))
names = rates['names']


def write(name, head, rows):
    with open(os.path.join(HERE, name), 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(head)
        w.writerows(rows)
    print(f'{name}: {len(rows)} rows')
    return len(rows)


# 1. Every month since January 2010, every state and the US.
latest = rates['latest']  # EIA-861M: months of the newest year are preliminary until the EIA-861 annual release
rows = []
for st, ser in [('US', rates['us'])] + sorted(rates['states'].items()):
    for m, price, kwh, bill in ser:
        rows.append([st, names.get(st, 'United States') if st != 'US' else 'United States', m, bill, kwh, price,
                     'preliminary' if m[:4] == latest[:4] else 'final'])
n_monthly = write('monthly-electric-bill-by-state.csv',
                  ['state', 'name', 'month', 'bill_usd_per_customer', 'kwh_per_customer', 'price_cents_per_kwh', 'status'], rows)

# 2. What the bill pays for (share of the electricity bill by end use).
lab = recs['enduse']['labels']
rows = []
for kind, block in (('division', recs['enduse']['areas']), ('state', recs['enduse']['states'])):
    for area, uses in sorted(block.items(), key=lambda x: (x[0] != 'US', x[0])):
        for k, v in uses.items():
            if v and v.get('pct') is not None:
                rows.append([kind if area != 'US' else 'us', area, k, lab.get(k, k), v['pct'], v.get('se')])
n_end = write('electric-bill-end-uses.csv', ['area_type', 'area', 'end_use', 'label', 'share_pct', 'standard_error_pct'], rows)

# 3. How spread out bills are within each state (RECS 2020), as ratios to the state's mean bill.
rows = []
ps = recs['dist']['ps']
for st, d in sorted(recs['dist']['states'].items()):
    for p, q in zip(ps, d['p']):
        rows.append([st, p, q, d['n']])
n_dist = write('bill-spread-by-state.csv', ['state', 'percentile', 'ratio_to_state_mean_bill', 'homes_surveyed'], rows)

# 4. The survey against the utilities' own count, 2020.
rows = []
for st, c in sorted(recs['check'].items(), key=lambda x: (x[0] != 'US', x[0])):
    rows.append([st, c['recs'], c['eia'], c['diff'], c['rse'], c['n']])
n_chk = write('survey-vs-utilities-2020.csv',
              ['state', 'recs_2020_annual_bill_usd', 'eia_861m_2020_annual_bill_usd', 'difference_pct', 'recs_relative_standard_error_pct', 'homes_surveyed'], rows)

# datapackage.json (Frictionless Data), so tools can read the columns without the README.
F = lambda n, t, d: {'name': n, 'type': t, 'description': d}
res = [
    {'path': 'average-electric-bill-by-state.csv', 'description': 'Average monthly electric bill per home by state over the latest 12 months, with kWh, price, highest and lowest month, change on a year and the change since 2010 split into price and use.'},
    {'path': 'average-electric-bill-by-home.csv', 'description': 'Typical monthly bill by type of home, bedrooms, house size, people, main heating fuel and tenure, for the US and every state: the state bill times the RECS 2020 ratio for its census division, with the survey error.'},
    {'path': 'monthly-electric-bill-by-state.csv', 'description': 'Every month since January 2010: average bill per residential customer, kWh and price, US and every state (EIA-861M).',
     'schema': {'fields': [F('state', 'string', 'Two-letter code, or US'), F('name', 'string', 'State name'), F('month', 'yearmonth', 'YYYY-MM'),
                           F('bill_usd_per_customer', 'number', 'Residential revenue / residential customers, US dollars of that month'),
                           F('kwh_per_customer', 'number', 'Residential sales / residential customers'), F('price_cents_per_kwh', 'number', 'Residential revenue / residential sales'),
                           F('status', 'string', 'preliminary for months of the newest year (EIA revises them and replaces them with the annual EIA-861 figures); final before that')]}},
    {'path': 'electric-bill-end-uses.csv', 'description': 'Share of the electricity bill by end use (RECS 2020), US, census divisions and states where the survey is precise enough.',
     'schema': {'fields': [F('area_type', 'string', 'us, division (census division; Mountain split North and South as in RECS), or state'), F('area', 'string', 'US, division name or state code'), F('end_use', 'string', 'Key'),
                           F('label', 'string', 'End use'), F('share_pct', 'number', 'Share of the electricity bill, %'), F('standard_error_pct', 'number', 'Jackknife standard error, percentage points')]}},
    {'path': 'bill-spread-by-state.csv', 'description': 'Percentiles of the household bill within each state (RECS 2020) as a ratio to the state mean.',
     'schema': {'fields': [F('state', 'string', 'Two-letter code'), F('percentile', 'integer', '5 to 95'), F('ratio_to_state_mean_bill', 'number', 'Bill at that percentile / state mean bill'), F('homes_surveyed', 'integer', 'RECS 2020 sample size in the state')]}},
    {'path': 'survey-vs-utilities-2020.csv', 'description': 'RECS 2020 average annual bill against the EIA-861M utility returns for 2020, by state.',
     'schema': {'fields': [F('state', 'string', 'Two-letter code, or US'), F('recs_2020_annual_bill_usd', 'number', 'RECS 2020 weighted mean DOLLAREL'), F('eia_861m_2020_annual_bill_usd', 'number', 'Sum of 2020 monthly bills, EIA-861M'),
                           F('difference_pct', 'number', 'RECS minus EIA, % of EIA'), F('recs_relative_standard_error_pct', 'number', 'RSE of the RECS mean'), F('homes_surveyed', 'integer', 'RECS sample size')]}},
    {'path': 'source/recs-bill.json', 'description': 'Every RECS 2020 ratio, share, spread and check used above, with standard errors and sample sizes.'},
]
pkg = {'name': 'us-average-electric-bill', 'title': 'Average Electric Bill by State, Home Type and End Use (US, monthly since 2010)',
       'licenses': [{'name': 'CC-BY-4.0', 'path': 'https://creativecommons.org/licenses/by/4.0/'}],
       'homepage': 'https://greencalculus.com/data/average-electric-bill-by-state/',
       'version': os.environ.get('DATASET_VERSION', ''),
       'sources': [{'title': 'EIA-861M Sales and revenue (monthly, states)', 'path': 'https://www.eia.gov/electricity/data/eia861m/'},
                   {'title': 'EIA Residential Energy Consumption Survey 2020, public microdata', 'path': 'https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata'}],
       'resources': res}
json.dump(pkg, open(os.path.join(HERE, 'datapackage.json'), 'w'), indent=1)
print('datapackage.json written')
