# Redemption Queues behind Quarterly Gates: Requests, Rationing, and Balance-Sheet Adjustment in Semi-Liquid Private Credit Funds, 2023–2026

Replication code and results for the manuscript of the same title (single author; submitted to the *Journal of Financial Stability*, October 2026).

**Version DOI:** [to be inserted after the Zenodo release] · **Concept DOI:** [to be inserted]

## What is here

| Folder | Contents |
|---|---|
| `code/` | Every script that produces a result or a table. The offer-level record is built from SEC EDGAR tender-offer filings (`fetch_filings_cache.py`, `fetch_offer_commencements.py`, `build_offer_master.py`); the request analysis and regressions (`m2_analysis_v3.py`, `m2_regressions_v3.py`); the listed twins' discounts and event study (`twin_discounts_v3.py`, `event_study_v3.py`); the XBRL balance-sheet panel (`collect_balance_sheet_xbrl.py`, `balance_sheet_summary_v3.py`); the schedule-of-investments comparison of marks and non-accruals (`soi_asset_side_v3.py`, `soi_asset_side_measures_v3.py`, `soi_nonaccrual_v3.py`); the numerical check of the appendix model (`model_check.py`); the independent re-extraction used for data verification (`reextract_independent.py`); and the generators of every table and prose number (`make_tables_v3.py`, `make_figures_v4.py`). `numeric_audit_v3.py` checks that every number in the manuscript traces to a results file. |
| `results/` | The JSON files from which every table and number is generated. The raw schedule-of-investments extract (`soi_raw_v3.json`, 190 MB) and the filing caches are not included; `python code/soi_asset_side_v3.py` and `python code/fetch_filings_cache.py` rebuild them from EDGAR. |
| `tables/` | The generated standalone tables (`T_*.tex`) and the macro file `numbers_v3.tex` that the manuscript reads. |
| `figures/` | The two figures. |
| `preregistration/` | `PREREG_Q4_2026.md`, the pre-specified tests for the next tender cycle, frozen on 22 October 2026 (SHA-256 of the content recorded in the file) before any of the relevant filings existed. |
| `evidence/` | Every non-accrual sentence parsed from the filings, with accession numbers, and the data-verification report of 16 October 2026. |

## Reproducing

Python 3.11+, with `pandas`, `numpy`, `statsmodels`, `scipy`, `matplotlib`. Run from the repository root; the scripts expect `code/` and `results/` as siblings.

1. `python code/fetch_filings_cache.py` and `python code/fetch_offer_commencements.py` download the tender-offer filings (SEC EDGAR; set a descriptive `User-Agent` as the scripts do).
2. `python code/build_offer_master.py` builds `results/offer_master_v3.json`, the offer-level record with one evidence sentence per value.
3. `python code/m2_analysis_v3.py`, `python code/m2_regressions_v3.py`, `python code/twin_discounts_v3.py`, `python code/event_study_v3.py` produce the request, regression, discount and event-study results.
4. `python code/collect_balance_sheet_xbrl.py` then `python code/balance_sheet_summary_v3.py` build the fund-quarter balance-sheet panel.
5. `python code/soi_asset_side_v3.py` (downloads 175 10-Q/10-K filings), then `python code/soi_asset_side_measures_v3.py` and `python code/soi_nonaccrual_v3.py` produce the asset-side measures.
6. `python code/model_check.py` verifies the appendix model numerically.
7. `python code/make_tables_v3.py` regenerates every table and `numbers_v3.tex`; `python code/make_figures_v4.py` the figures.

Prices for the listed twins come from Yahoo Finance (unadjusted closes); everything else is from EDGAR.

## Data

All inputs are public filings on SEC EDGAR. No proprietary data are used. The results files are derived data and may be reused with attribution.

## Citation

Woo, J. (2026). Redemption Queues behind Quarterly Gates: Requests, Rationing, and Balance-Sheet Adjustment in Semi-Liquid Private Credit Funds, 2023–2026 — replication code and results. Zenodo. DOI to be inserted.
