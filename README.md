# Average Electric Bill by State, Home Type and End Use (US, monthly since 2010)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24067456.svg)](https://doi.org/10.5281/zenodo.24067456)

What US homes pay for electricity each month, for every state and the US, every month since January 2010. Each bill is split three ways: by the kind of home (apartment or house, bedrooms, floor area, people, heating fuel, owned or rented), by what the electricity is used for, and by how much of any change since 2010 came from the price per kWh and how much from the amount used.

- **Bills come from the utilities' own returns.** Every month, each US utility reports to the Energy Information Administration (EIA) what its homes paid and how many homes it served (form EIA-861M). A state's bill is its residential revenue divided by its residential customers. EIA counts gross revenue: energy and demand charges, customer charges, fuel adjustments, environmental surcharges, franchise fees and taxes billed in the normal way.
- **Shapes come from EIA's 2020 Residential Energy Consumption Survey (RECS)**, 18,496 homes, with standard errors from the survey's 60 jackknife replicate weights. Only ratios and shares are taken from the survey; the dollar level always comes from the utilities.
- **Data to August 2026** (EIA-861M, read 3 November 2026). Months of 2026 are EIA's preliminary figures.

Read with charts, a state picker and an "is my bill high?" check: https://greencalculus.com/data/average-electric-bill-by-state/

## Headline: 12 months to August 2026

| | Monthly bill | kWh a month | Price |
|---|---|---|---|
| United States | $158 | 875 | 18.04¢ |
| Highest: Hawaii | $228 | 514 | 44.26¢ |
| Lowest: New Mexico | $100 | 653 | 15.31¢ |

Since 2010 the US bill rose from $111 to $158 a month. The higher price per kWh added $60; homes using less electricity took off $12.

Typical US bill by home (12 months to August 2026, RECS 2020 ratio to the average home):

| Home | Monthly bill | Ratio | Survey error |
|---|---|---|---|
| Apartment, 1 bedroom | $86 | 0.54 | 1.7% |
| Apartment, 2 bedrooms | $113 | 0.71 | 1.5% |
| House, 3 bedrooms | $171 | 1.08 | 0.5% |
| House, 2,000 to 2,499 sq ft | $192 | 1.22 | 1.1% |
| One person living alone | $110 | 0.70 | 0.8% |
| Heated by electricity | $180 | 1.14 | 0.6% |

## Files

| File | Rows | What it holds |
|---|---|---|
| `average-electric-bill-by-state.csv` | 52 | US and every state: 12-month bill, kWh, price, highest and lowest month, change on a year, 2010 bill, change from price and from use, rank |
| `average-electric-bill-by-home.csv` | 1,470 | US and every state: typical bill by type of home, bedrooms, house size, people, heating fuel and tenure, with ratio, survey error, homes surveyed and a quality flag |
| `monthly-electric-bill-by-state.csv` | 10,400 | Every month since January 2010: bill, kWh and price per residential customer, US and every state |
| `electric-bill-end-uses.csv` | 736 | Share of the bill by end use (air conditioning, heating, water heating, fridges, lighting and 8 more), US, census divisions and states |
| `bill-spread-by-state.csv` | 988 | 5th to 95th percentile of household bills within each state, as a ratio to the state mean |
| `survey-vs-utilities-2020.csv` | 52 | RECS 2020 average annual bill against the utilities' own 2020 count, by state |
| `source/elec-rates.json` | | EIA-861M monthly series as read |
| `source/recs-bill.json` | | Every RECS ratio, share, spread and check above, with standard errors and sample sizes |
| `datapackage.json` | | Column descriptions (Frictionless Data) |

## Method

1. **Bill.** Residential revenue ÷ residential customers, each month, from EIA-861M. The 12-month figure is the mean of the latest 12 monthly bills, so a hot summer or a cold winter does not tilt one state against another. Dollars of each year, not adjusted for inflation.
2. **Price and use since 2010.** The change in the bill splits exactly into a price part, (p₁ − p₀) × (k₀ + k₁)/2, and a use part, (k₁ − k₀) × (p₀ + p₁)/2, where p is the price per kWh and k the kWh per home over the 12 months.
3. **Homes and end uses.** From RECS 2020 we take only ratios: a group's mean bill (`DOLLAREL`) ÷ the mean bill in its census division, and each end use's share of `DOLLAREL`. That ratio is applied to the current EIA-861M bill for the state. Standard errors use the 60 replicate weights: SE² = (59/60) × Σ(θᵣ − θ)². A group is shown only when at least 30 homes were surveyed and the relative standard error is at most 30%; between 15% and 30% it is flagged `wide`.
4. **Check.** For 2020 the survey's average US bill was $1,380 a year and the utilities' $1,409, 2.1% apart (`survey-vs-utilities-2020.csv`). State by state they differ more, because the survey holds a few hundred homes per state. That is why the dollar level always comes from the utilities.

To rebuild: `python3 build.py` (tables from `source/`), and `python3 scripts/build-recs-bill-data.py --recs recs2020_public_v7.csv --rates source/elec-rates.json --out source/recs-bill.json` (ratios from the RECS microdata, which EIA publishes at the link below).

## Read before using

- A single home's bill differs from the state average through sales tax, late fees, a utility's own discounts and, above all, how much electricity it uses.
- Homes that buy power from a retail supplier are in the state totals; their supplier's charges are included by EIA.
- RECS 2020 is the newest survey with public microdata. EIA plans to publish RECS 2024 results in 2027; the ratios will move to it then.

## Updates

The live page refreshes every month when EIA publishes a new month. This deposit is a dated snapshot for citation and reproducibility; the concept DOI always points to the newest version.

## Sources

- US Energy Information Administration, Form EIA-861M, Sales and revenue (monthly, states): https://www.eia.gov/electricity/data/eia861m/
- US Energy Information Administration, Form EIA-861 and its instructions (what revenue includes, Schedule 2 Part C): https://www.eia.gov/electricity/data/eia861/
- US Energy Information Administration, 2020 Residential Energy Consumption Survey, public microdata (v7) and "Using the microdata file to compute estimates and relative standard errors": https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata

## Licence and citation

The EIA source data are US Government works in the public domain. This compilation (the bills by home and end use, the price and use split, the checks and the files here) is released under CC BY 4.0: use it freely, with credit.

Say, J. (2026). *Average Electric Bill by State, Home Type and End Use (US, monthly since 2010)* (Version 2026.11.09) [Data set]. GreenCalculus. https://doi.org/10.5281/zenodo.24067456

See `CITATION.cff` for BibTeX and other formats (GitHub's "Cite this repository" button reads it).

Published by [GreenCalculus](https://greencalculus.com/), which publishes sourced energy and emissions data. Free API for the emission factors behind our calculators: https://greencalculus.com/developers/
